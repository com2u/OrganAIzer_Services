import { useState, useEffect, useRef } from 'react';

// Type definitions
interface Message {
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
  audioUrl?: string;
  isPlaying?: boolean;
}

interface ConversationState {
  isRecording: boolean;
  isTranscribing: boolean;
  isThinking: boolean;
  isSpeaking: boolean;
  liveTranscript: string;
}

function VoiceExecutiveAgent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [state, setState] = useState<ConversationState>({
    isRecording: false,
    isTranscribing: false,
    isThinking: false,
    isSpeaking: false,
    liveTranscript: ''
  });
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(`voice-session-${Date.now()}`);
  
  // Audio refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const API_KEY = import.meta.env.VITE_API_KEY || 'test-key-123';
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
    };
  }, []);

  // Auto-scroll to bottom
  const messagesEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /**
   * Toggle microphone recording
   */
  const toggleRecording = async () => {
    if (state.isRecording) {
      // Stop recording
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    } else {
      // Start recording
      try {
        setError(null);
        
        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ 
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          } 
        });
        
        streamRef.current = stream;
        audioChunksRef.current = [];

        // Create MediaRecorder
        const mediaRecorder = new MediaRecorder(stream, {
          mimeType: 'audio/webm'
        });
        
        mediaRecorderRef.current = mediaRecorder;

        // Collect audio chunks
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };

        // Handle recording stop
        mediaRecorder.onstop = async () => {
          setState(prev => ({ ...prev, isRecording: false, liveTranscript: '' }));
          
          // Stop all tracks
          if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
          }

          // Process the recorded audio
          if (audioChunksRef.current.length > 0) {
            await processRecording();
          }
        };

        // Start recording
        mediaRecorder.start();
        setState(prev => ({ 
          ...prev, 
          isRecording: true,
          liveTranscript: 'Listening...'
        }));

      } catch (err) {
        console.error('Microphone access error:', err);
        setError('Failed to access microphone. Please grant permission.');
      }
    }
  };

  /**
   * Process recorded audio: STT → Executive AI → TTS
   */
  const processRecording = async () => {
    try {
      // Step 1: Create audio blob
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      
      // Step 2: Transcribe audio (STT)
      setState(prev => ({ ...prev, isTranscribing: true, liveTranscript: 'Transcribing...' }));
      
      const transcribedText = await transcribeAudio(audioBlob);
      
      if (!transcribedText || transcribedText.trim().length === 0) {
        setState(prev => ({ ...prev, isTranscribing: false, liveTranscript: '' }));
        setError('No speech detected. Please try again.');
        return;
      }

      // Add user message
      const userMessage: Message = {
        role: 'user',
        content: transcribedText,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, userMessage]);
      
      setState(prev => ({ 
        ...prev, 
        isTranscribing: false, 
        isThinking: true,
        liveTranscript: '' 
      }));

      // Step 3: Send to Executive AI
      const aiResponse = await sendToExecutiveAI(transcribedText);
      
      setState(prev => ({ ...prev, isThinking: false }));

      // Step 4: Generate TTS for response
      const ttsUrl = await generateTTS(aiResponse);

      // Add agent message
      const agentMessage: Message = {
        role: 'agent',
        content: aiResponse,
        timestamp: new Date(),
        audioUrl: ttsUrl || undefined
      };
      setMessages(prev => [...prev, agentMessage]);

      // Step 5: Auto-play TTS
      if (ttsUrl) {
        await playTTS(ttsUrl);
      }

    } catch (err: any) {
      console.error('Recording processing error:', err);
      setError(`Error: ${err.message}`);
      setState(prev => ({ 
        ...prev, 
        isTranscribing: false, 
        isThinking: false, 
        isSpeaking: false 
      }));
    }
  };

  /**
   * Transcribe audio using STT service
   */
  const transcribeAudio = async (audioBlob: Blob): Promise<string> => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');

    const response = await fetch(`${API_BASE_URL}/api/stt/transcribe`, {
      method: 'POST',
      headers: {
        'X-API-Key': API_KEY
      },
      body: formData
    });

    if (!response.ok) {
      throw new Error(`STT failed: ${response.statusText}`);
    }

    const data = await response.json();
    return data.text;
  };

  /**
   * Send transcribed text to Executive AI
   */
  const sendToExecutiveAI = async (message: string): Promise<string> => {
    const response = await fetch(`${API_BASE_URL}/api/agent/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY
      },
      body: JSON.stringify({
        message: message,
        session_id: sessionId,
        user_id: 'voice_user',
        provider: 'gmail'
      })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `AI response failed: ${response.status}`);
    }

    const data = await response.json();
    
    // Handle different response types
    let responseMessage = data.message || 'No response';
    
    // Add context for confirmations
    if (data.pending_confirmation) {
      return responseMessage; // Already has confirmation prompt
    }
    
    if (data.email_sent) {
      return responseMessage + ' Is there anything else I can help you with?';
    }
    
    if (data.requires_oauth) {
      return 'You need to connect your account first. Please check the web interface for authorization.';
    }

    return responseMessage;
  };

  /**
   * Generate TTS for AI response
   */
  const generateTTS = async (text: string): Promise<string | null> => {
    try {
      // Clean text for TTS (remove markdown formatting)
      const cleanText = text
        .replace(/\*\*/g, '')
        .replace(/\*/g, '')
        .replace(/\n+/g, '. ')
        .replace(/[\-•]/g, '')
        .trim();

      const response = await fetch(`${API_BASE_URL}/api/tts/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY
        },
        body: JSON.stringify({
          text_md: cleanText
        })
      });

      if (!response.ok) {
        console.error('TTS generation failed:', response.statusText);
        return null;
      }

      const data = await response.json();
      return data.audio_url;

    } catch (err) {
      console.error('TTS error:', err);
      return null;
    }
  };

  /**
   * Play TTS audio
   */
  const playTTS = async (audioUrl: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      setState(prev => ({ ...prev, isSpeaking: true }));

      const audio = new Audio(audioUrl);
      audioPlayerRef.current = audio;

      audio.onended = () => {
        setState(prev => ({ ...prev, isSpeaking: false }));
        resolve();
      };

      audio.onerror = (err) => {
        setState(prev => ({ ...prev, isSpeaking: false }));
        console.error('Audio playback error:', err);
        reject(err);
      };

      audio.play().catch(err => {
        setState(prev => ({ ...prev, isSpeaking: false }));
        console.error('Audio play error:', err);
        reject(err);
      });
    });
  };

  /**
   * Stop current TTS playback
   */
  const stopTTS = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
      setState(prev => ({ ...prev, isSpeaking: false }));
    }
  };

  /**
   * Clear conversation
   */
  const clearConversation = () => {
    setMessages([]);
    setError(null);
    stopTTS();
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800">🎤 Voice Executive AI</h1>
        <button
          onClick={clearConversation}
          className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
        >
          Clear Chat
        </button>
      </div>

      {/* Status Indicator */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {/* Recording Indicator */}
            <div className={`flex items-center space-x-2 px-4 py-2 rounded-lg ${
              state.isRecording ? 'bg-red-100' : 'bg-gray-100'
            }`}>
              <div className={`w-3 h-3 rounded-full ${
                state.isRecording ? 'bg-red-500 animate-pulse' : 'bg-gray-400'
              }`}></div>
              <span className="font-medium">
                {state.isRecording ? 'Recording...' : 'Ready'}
              </span>
            </div>

            {/* Processing Indicators */}
            {state.isTranscribing && (
              <div className="flex items-center space-x-2 px-4 py-2 bg-blue-100 rounded-lg">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent"></div>
                <span className="text-blue-700 font-medium">Transcribing...</span>
              </div>
            )}

            {state.isThinking && (
              <div className="flex items-center space-x-2 px-4 py-2 bg-purple-100 rounded-lg">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-purple-600 border-t-transparent"></div>
                <span className="text-purple-700 font-medium">AI Thinking...</span>
              </div>
            )}

            {state.isSpeaking && (
              <div className="flex items-center space-x-2 px-4 py-2 bg-green-100 rounded-lg">
                <div className="flex space-x-1">
                  <div className="w-1 h-4 bg-green-600 animate-pulse"></div>
                  <div className="w-1 h-4 bg-green-600 animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-1 h-4 bg-green-600 animate-pulse" style={{ animationDelay: '0.4s' }}></div>
                </div>
                <span className="text-green-700 font-medium">Speaking...</span>
              </div>
            )}
          </div>

          {/* Stop Speaking Button */}
          {state.isSpeaking && (
            <button
              onClick={stopTTS}
              className="px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition-colors"
            >
              Stop
            </button>
          )}
        </div>

        {/* Live Transcript */}
        {state.liveTranscript && (
          <div className="mt-3 p-3 bg-gray-50 rounded text-gray-600 italic">
            {state.liveTranscript}
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          <div className="flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-900 hover:text-red-950">✕</button>
          </div>
        </div>
      )}

      {/* Conversation Display */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-700">Conversation</h2>
        
        <div className="border rounded-lg bg-gray-50 p-4 h-96 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 mt-20">
              <div className="text-6xl mb-4">🎤</div>
              <p className="text-lg mb-2">Voice Assistant Ready</p>
              <p className="text-sm">Click the microphone button below to start talking</p>
              <div className="mt-4 text-xs text-left max-w-md mx-auto space-y-1">
                <p>💡 Try saying:</p>
                <ul className="list-disc list-inside pl-2 space-y-1">
                  <li>"Draft an email to john@example.com"</li>
                  <li>"What's on my calendar today?"</li>
                  <li>"Schedule a meeting tomorrow at 2pm"</li>
                  <li>"What day is today?"</li>
                </ul>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`mb-4 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}
              >
                <div
                  className={`inline-block max-w-[80%] rounded-lg px-4 py-2 ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-800'
                  }`}
                >
                  <div className="font-semibold text-xs mb-1">
                    {msg.role === 'user' ? '🎤 You' : '🤖 OrganAIzer'}
                  </div>
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                  <div className="text-xs opacity-75 mt-1">
                    {msg.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Microphone Control */}
      <div className="flex justify-center">
        <button
          onClick={toggleRecording}
          disabled={state.isTranscribing || state.isThinking || state.isSpeaking}
          className={`
            relative w-24 h-24 rounded-full flex items-center justify-center
            transition-all duration-300 shadow-lg
            ${state.isRecording 
              ? 'bg-red-500 hover:bg-red-600 scale-110' 
              : 'bg-blue-600 hover:bg-blue-700'
            }
            ${(state.isTranscribing || state.isThinking || state.isSpeaking) 
              ? 'opacity-50 cursor-not-allowed' 
              : 'cursor-pointer'
            }
          `}
        >
          {state.isRecording ? (
            <svg className="w-12 h-12 text-white" fill="currentColor" viewBox="0 0 20 20">
              <rect x="6" y="6" width="8" height="8" rx="1" />
            </svg>
          ) : (
            <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          )}
          
          {/* Pulse animation when recording */}
          {state.isRecording && (
            <>
              <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 animate-ping"></span>
              <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 animate-ping" style={{ animationDelay: '0.5s' }}></span>
            </>
          )}
        </button>
      </div>

      <div className="text-center mt-4 text-sm text-gray-600">
        {state.isRecording ? (
          <p className="font-semibold text-red-600">Click to stop recording</p>
        ) : (
          <p>Click to start speaking</p>
        )}
      </div>

      {/* Instructions */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-semibold text-blue-900 mb-2">💡 How it works:</h3>
        <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
          <li>Click the microphone button and speak your request</li>
          <li>Click again to stop recording (auto-transcribes)</li>
          <li>AI processes your request and responds</li>
          <li>Response is automatically spoken aloud</li>
          <li>Continue the conversation naturally</li>
        </ol>
        <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
          <strong>⚠️ Safety:</strong> For sensitive actions (sending emails, deleting events), 
          the AI will ask for voice confirmation before executing.
        </div>
      </div>
    </div>
  );
}

export default VoiceExecutiveAgent;
