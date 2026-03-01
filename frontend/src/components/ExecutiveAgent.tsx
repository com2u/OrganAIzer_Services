import { useState, useEffect, useRef, useCallback } from 'react';

// Type definitions
interface Message {
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
  type?: string;
  data?: any;
  draft_ready?: boolean;
  draft_updated?: boolean;
  pending_confirmation?: boolean;
  collecting_details?: boolean;
  email_sent?: boolean;
  requires_oauth?: boolean;
  // State Machine Information
  agent_state?: string;
  active_task?: any;
  pending_action?: any;
  last_action?: any;
}

interface Capabilities {
  agent_name: string;
  version: string;
  capabilities: {
    [key: string]: {
      description: string;
      providers?: string[];
      features: string[];
    };
  };
}

interface DebugInfo {
  system_prompt: string;
  messages: any[];
  model: string;
  current_time: any;
}

function ExecutiveAgent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loadingCapabilities, setLoadingCapabilities] = useState(true);
  const [debugMode, setDebugMode] = useState(false);
  const [debugInfo,  setDebugInfo] = useState<DebugInfo | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // CRITICAL: Track current agent state machine
  const [agentState, setAgentState] = useState<string>('IDLE');
  const [activeTask, setActiveTask] = useState<any>(null);
  const [pendingAction, setPendingAction] = useState<any>(null);
  const [lastAction, setLastAction] = useState<any>(null);

  // ── Push-to-talk state (for simple voice messages) ─────────────────────────
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // ── Realtime Voice Mode state ───────────────────────────────────────────────
  type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';
  const [voiceMode, setVoiceMode] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [partialTranscript, setPartialTranscript] = useState('');
  const voiceModeRef = useRef(false);   // avoids stale-closure in WS callbacks
  const wsRef = useRef<WebSocket | null>(null);
  const voiceAudioRef = useRef<HTMLAudioElement | null>(null);
  // ──────────────────────────────────────────────────────────────────────────

  const API_KEY = import.meta.env.VITE_API_KEY || 'test-key-123';
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch capabilities on component mount
  useEffect(() => {
    fetchCapabilities();
  }, []);

  const fetchCapabilities = async () => {
    setLoadingCapabilities(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/capabilities`, {
        headers: {
          'X-API-Key': API_KEY,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch capabilities: ${response.statusText}`);
      }

      const data = await response.json();
      setCapabilities(data);
    } catch (err) {
      console.error('Error fetching capabilities:', err);
      setError(`Failed to load capabilities: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoadingCapabilities(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY,
        },
        body: JSON.stringify({
          message: input,
          session_id: 'default',
          user_id: 'default_user',
          provider: 'gmail',
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();

      const agentMessage: Message = {
        role: 'agent',
        content: data.message || 'No response',
        timestamp: new Date(),
        type: data.type,
        data: data.data,
        draft_ready: data.draft_ready,
        draft_updated: data.draft_updated,
        pending_confirmation: data.pending_confirmation,
        collecting_details: data.collecting_details,
        email_sent: data.email_sent,
        requires_oauth: data.requires_oauth,
        // State Machine Information
        agent_state: data.agent_state,
        active_task: data.active_task,
        pending_action: data.pending_action,
        last_action: data.last_action,
      };

      setMessages((prev) => [...prev, agentMessage]);
      
      // CRITICAL: Update state machine tracking
      if (data.agent_state) setAgentState(data.agent_state);
      if (data.active_task !== undefined) setActiveTask(data.active_task);
      if (data.pending_action !== undefined) setPendingAction(data.pending_action);
      if (data.last_action !== undefined) setLastAction(data.last_action);
      
      // Update debug info if debug mode is on
      if (debugMode) {
        updateDebugInfo(input, data);
      }
    } catch (err) {
      console.error('Error sending message:', err);
      setError(`Error: ${err instanceof Error ? err.message : 'Failed to send message'}`);
      
      // Add error message to chat
      const errorMessage: Message = {
        role: 'agent',
        content: `❌ Error: ${err instanceof Error ? err.message : 'Failed to send message'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const updateDebugInfo = async (userInput: string, responseData: any) => {
    // Fetch current system time from backend
    try {
      const timeResponse = await fetch(`${API_BASE_URL}/api/agent/debug/time`, {
        headers: {
          'X-API-Key': API_KEY,
        },
      }).catch(() => null);
      
      const timeData = timeResponse?.ok ? await timeResponse.json() : null;
      
      setDebugInfo({
        system_prompt: "OrganAIzer system prompt with date/time context injected",
        messages: [
          { role: "system", content: "System message with current date/time" },
          { role: "user", content: userInput },
          { role: "assistant", content: responseData.message }
        ],
        model: "LLM Model (configured in backend)",
        current_time: timeData || { 
          date: new Date().toISOString().split('T')[0],
          time: new Date().toTimeString().split(' ')[0].substring(0, 5),
          timezone: "Europe/Berlin"
        }
      });
    } catch (err) {
      console.error('Debug info update error:', err);
    }
  };

  // ── Voice recording logic ──────────────────────────────────────────────────
  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      // Stop recording
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      return;
    }

    // Start recording
    setVoiceError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;
      audioChunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        setIsRecording(false);
        stopStream();

        if (audioChunksRef.current.length === 0) return;

        setIsTranscribing(true);
        try {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append('file', audioBlob, 'recording.webm');

          const res = await fetch(`${API_BASE_URL}/api/stt/transcribe`, {
            method: 'POST',
            headers: { 'X-API-Key': API_KEY },
            body: formData,
          });

          if (!res.ok) throw new Error(`STT failed: ${res.statusText}`);
          const result = await res.json();
          // Backend STTTranscribeResponse uses field name 'transcript'
          const text: string = result.transcript || result.text || '';

          if (text.trim()) {
            // Put transcript in the input box so user can review / send
            setInput(text.trim());
          } else {
            setVoiceError('No speech detected. Please try again.');
          }
        } catch (err: any) {
          setVoiceError(`Transcription error: ${err.message}`);
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err: any) {
      setVoiceError('Microphone access denied. Please allow microphone permission.');
    }
  }, [isRecording, API_BASE_URL, API_KEY, stopStream]);
  // ──────────────────────────────────────────────────────────────────────────

  // ── Realtime Voice Mode WS logic ──────────────────────────────────────────
  const connectVoiceWS = useCallback(() => {
    const wsBase = API_BASE_URL.replace(/^http/, 'ws');
    const url = `${wsBase}/api/voice/stream?session_id=default&user_id=default_user&provider=gmail`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => console.log('[VoiceMode] WS connected');

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string);
        switch (data.type) {
          case 'state':
            setVoiceState(data.state as VoiceState);
            break;
          case 'stt.partial':
            setPartialTranscript(data.text || '');
            break;
          case 'stt.final':
            setPartialTranscript('');
            if (data.text) {
              setMessages((prev) => [
                ...prev,
                { role: 'user', content: data.text, timestamp: new Date() },
              ]);
            }
            break;
          case 'ai.response.text':
            if (data.text) {
              setMessages((prev) => [
                ...prev,
                { role: 'agent', content: data.text, timestamp: new Date() },
              ]);
            }
            break;
          case 'tts.audio': {
            // Stop any current playback first (barge-in)
            if (voiceAudioRef.current) {
              voiceAudioRef.current.pause();
            }
            const audio = new Audio(`${API_BASE_URL}${data.audio_url}`);
            voiceAudioRef.current = audio;
            audio.play().catch((e) => console.warn('[VoiceMode] audio play failed:', e));
            break;
          }
          case 'error':
            setVoiceError(data.message || 'Voice mode error');
            break;
        }
      } catch (e) {
        console.error('[VoiceMode] WS parse error:', e);
      }
    };

    ws.onclose = () => {
      console.log('[VoiceMode] WS closed');
      // Auto-reconnect if voice mode is still on
      if (voiceModeRef.current) {
        setTimeout(connectVoiceWS, 2000);
      }
    };

    ws.onerror = (e) => console.error('[VoiceMode] WS error:', e);
  }, [API_BASE_URL]);

  // Connect/disconnect WS when voiceMode toggles
  useEffect(() => {
    voiceModeRef.current = voiceMode;
    if (voiceMode) {
      connectVoiceWS();
    } else {
      // Clean up
      wsRef.current?.close();
      wsRef.current = null;
      voiceAudioRef.current?.pause();
      voiceAudioRef.current = null;
      setVoiceState('idle');
      setPartialTranscript('');
      stopStream();
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
    }
  }, [voiceMode, connectVoiceWS, stopStream]);

  /** Start streaming audio to the backend WS (push-to-talk press) */
  const startVoiceSpeaking = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    // Stop AI speech (barge-in)
    if (voiceAudioRef.current) {
      voiceAudioRef.current.pause();
      voiceAudioRef.current = null;
    }
    setVoiceError(null);
    wsRef.current.send(JSON.stringify({ type: 'audio_start' }));

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(e.data);
        }
      };

      mr.start(500); // emit chunks every 500 ms
      setIsRecording(true);
    } catch {
      setVoiceError('Microphone access denied.');
    }
  }, []);

  /** Stop streaming audio (push-to-talk release) */
  const stopVoiceSpeaking = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    stopStream();
    setIsRecording(false);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'audio_end' }));
    }
  }, [stopStream]);
  // ──────────────────────────────────────────────────────────────────────────

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Voice state helpers
  const voiceStateLabel: Record<string, string> = {
    idle: 'Ready — hold mic to speak',
    listening: 'Listening…',
    thinking: 'Thinking…',
    speaking: 'Speaking…',
  };
  const voiceStateColor: Record<string, string> = {
    idle: 'text-gray-300',
    listening: 'text-red-400',
    thinking: 'text-yellow-400',
    speaking: 'text-green-400',
  };
  const voiceStateEmoji: Record<string, string> = {
    idle: '🎤',
    listening: '🎙️',
    thinking: '🤔',
    speaking: '🔊',
  };

  return (
    <div className="max-w-6xl mx-auto p-6">

      {/* ── Voice Mode fullscreen overlay ─────────────────────────────────── */}
      {voiceMode && (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-90 flex flex-col items-center justify-center select-none">
          {/* Status icon */}
          <div className={`text-7xl mb-4 ${voiceState === 'listening' || voiceState === 'speaking' ? 'animate-pulse' : ''}`}>
            {voiceStateEmoji[voiceState]}
          </div>

          {/* State label */}
          <p className={`text-2xl font-semibold mb-6 ${voiceStateColor[voiceState]}`}>
            {voiceStateLabel[voiceState]}
          </p>

          {/* Partial transcript */}
          {partialTranscript && (
            <p className="text-gray-300 text-lg mb-6 max-w-xl text-center italic">
              "{partialTranscript}"
            </p>
          )}

          {/* Hold-to-speak mic button */}
          <button
            onMouseDown={startVoiceSpeaking}
            onMouseUp={stopVoiceSpeaking}
            onTouchStart={(e) => { e.preventDefault(); startVoiceSpeaking(); }}
            onTouchEnd={(e) => { e.preventDefault(); stopVoiceSpeaking(); }}
            disabled={voiceState === 'thinking' || voiceState === 'speaking'}
            className={`w-28 h-28 rounded-full flex items-center justify-center text-5xl shadow-2xl transition-all
              ${isRecording ? 'bg-red-600 scale-110 ring-4 ring-red-400' : 'bg-blue-600 hover:bg-blue-500'}
              disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            🎤
          </button>

          <p className="text-gray-500 text-sm mt-3">
            {isRecording ? 'Release to send' : 'Hold to speak'}
          </p>

          {/* Voice error */}
          {voiceError && (
            <div className="mt-4 px-4 py-2 bg-red-900 text-red-200 rounded-lg text-sm max-w-sm text-center">
              ⚠️ {voiceError}
              <button onClick={() => setVoiceError(null)} className="ml-2 text-red-300 hover:text-white">✕</button>
            </div>
          )}

          {/* Chat transcript (last 4 messages) */}
          <div className="mt-8 w-full max-w-lg space-y-2 px-4 max-h-40 overflow-y-auto">
            {messages.slice(-4).map((m, i) => (
              <div key={i} className={`text-sm rounded px-3 py-1 ${m.role === 'user' ? 'bg-blue-900 text-blue-100 text-right' : 'bg-gray-800 text-gray-200 text-left'}`}>
                {m.content.substring(0, 120)}{m.content.length > 120 ? '…' : ''}
              </div>
            ))}
          </div>

          {/* Exit button */}
          <button
            onClick={() => setVoiceMode(false)}
            className="mt-8 px-8 py-3 bg-gray-700 text-white rounded-full hover:bg-gray-600 text-sm font-medium"
          >
            ✕ Exit Voice Mode
          </button>
        </div>
      )}
      {/* ─────────────────────────────────────────────────────────────────── */}

      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800">🤖 OrganAIzer Executive Agent</h1>
        <div className="flex gap-2">
          {/* Voice Mode toggle */}
          <button
            onClick={() => setVoiceMode((v) => !v)}
            title="Toggle realtime voice conversation mode"
            className={`px-4 py-2 rounded-lg transition-colors font-medium ${
              voiceMode
                ? 'bg-purple-600 text-white hover:bg-purple-700'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {voiceMode ? '🔴 Voice ON' : '🗣️ Voice Mode'}
          </button>
          <button
            onClick={() => setDebugMode(!debugMode)}
            className={`px-4 py-2 rounded-lg transition-colors ${
              debugMode
                ? 'bg-orange-600 text-white hover:bg-orange-700'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            🐛 Debug {debugMode ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>

      {/* Capabilities Section */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-700">Agent Capabilities</h2>
        {loadingCapabilities ? (
          <div className="flex items-center justify-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="ml-3 text-gray-600">Loading capabilities...</span>
          </div>
        ) : capabilities ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b pb-2">
              <span className="font-medium text-gray-700">Agent Name:</span>
              <span className="text-gray-900 font-bold">{capabilities.agent_name}</span>
            </div>
            <div className="flex items-center justify-between border-b pb-2">
              <span className="font-medium text-gray-700">Version:</span>
              <span className="text-gray-900">{capabilities.version}</span>
            </div>
            <div>
              <h3 className="font-medium text-gray-700 mb-2">Supported Capabilities:</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(capabilities.capabilities).map(([key, value]) => (
                  <div key={key} className="bg-gray-50 p-3 rounded">
                    <h4 className="font-semibold text-sm text-blue-600 capitalize mb-1">
                      {key.replace(/_/g, ' ')}
                    </h4>
                    <p className="text-xs text-gray-600 mb-2">{value.description}</p>
                    {value.providers && (
                      <p className="text-xs text-gray-500">
                        Providers: {value.providers.join(', ')}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-red-600">Failed to load capabilities</div>
        )}
      </div>

      {/* Debug Panel - State Machine Visualization */}
      {debugMode && (
        <div className="bg-gray-900 text-green-400 rounded-lg shadow-md p-6 mb-6 font-mono text-sm">
          <h2 className="text-xl font-semibold mb-4 text-green-300">🐛 Agent State Machine (DEBUG)</h2>
          <div className="space-y-3">
            <div>
              <div className="text-green-300 font-bold mb-1">Current State:</div>
              <div className={`p-3 rounded font-bold text-lg ${
                agentState === 'IDLE' ? 'bg-blue-800' :
                agentState.startsWith('EMAIL') ? 'bg-purple-800' :
                agentState.startsWith('CALENDAR') ? 'bg-orange-800' :
                'bg-gray-800'
              }`}>
                {agentState}
              </div>
            </div>
            
            <div>
              <div className="text-green-300 font-bold mb-1">Active Task:</div>
              <div className="bg-gray-800 p-2 rounded">
                {activeTask ? (
                  <div>
                    <div>Type: <span className="text-yellow-400">{activeTask.type}</span></div>
                    <div>Status: <span className="text-yellow-400">{activeTask.status}</span></div>
                    <div>Locked: <span className="text-yellow-400">{activeTask.locked_at || 'N/A'}</span></div>
                    {activeTask.data && Object.keys(activeTask.data).length > 0 && (
                      <details className="mt-2">
                        <summary className="cursor-pointer text-cyan-400">View Data</summary>
                        <pre className="text-xs mt-1 overflow-auto max-h-32">
                          {JSON.stringify(activeTask.data, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                ) : (
                  <span className="text-gray-500">None</span>
                )}
              </div>
            </div>
            
            <div>
              <div className="text-green-300 font-bold mb-1">Pending Action:</div>
              <div className="bg-gray-800 p-2 rounded">
                {pendingAction ? (
                  <div>
                    <div>Type: <span className="text-yellow-400">{pendingAction.type}</span></div>
                    <div>Status: <span className="text-yellow-400">{pendingAction.status}</span></div>
                    {pendingAction.data && (
                      <details className="mt-2">
                        <summary className="cursor-pointer text-cyan-400">View Slots</summary>
                        <pre className="text-xs mt-1 overflow-auto max-h-32">
                          {JSON.stringify(pendingAction.data, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                ) : (
                  <span className="text-gray-500">None</span>
                )}
              </div>
            </div>
            
            <div>
              <div className="text-green-300 font-bold mb-1">Last Action:</div>
              <div className="bg-gray-800 p-2 rounded">
                {lastAction ? (
                  <div>
                    <div>Type: <span className="text-yellow-400">{lastAction.action_type}</span></div>
                    <div>Outcome: <span className={
                      lastAction.outcome.includes('SENT') || lastAction.outcome.includes('CREATED') ? 
                      'text-green-400' : 'text-red-400'
                    }>{lastAction.outcome}</span></div>
                    <div className="text-xs text-gray-400">{lastAction.timestamp}</div>
                  </div>
                ) : (
                  <span className="text-gray-500">None</span>
                )}
              </div>
            </div>
            
            {debugInfo && (
              <>
                <div className="border-t border-gray-700 pt-3 mt-3">
                  <div className="text-green-300 font-bold mb-1">Current Time (Backend):</div>
                  <div className="bg-gray-800 p-2 rounded text-xs">
                    {debugInfo.current_time.date} {debugInfo.current_time.time} ({debugInfo.current_time.timezone})
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Chat Section */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-700">Chat with Agent</h2>

        {/* Error Display */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Messages Display */}
        <div className="border rounded-lg bg-gray-50 mb-4 p-4 h-96 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 mt-20">
              <p className="text-lg mb-2">👋 Hello! I'm OrganAIzer, your Executive Agent.</p>
              <p className="text-sm">Ask me to help with emails, calendar, knowledge queries, or image generation!</p>
              <div className="mt-4 text-xs text-left max-w-md mx-auto space-y-1">
                <p>💡 Try asking:</p>
                <ul className="list-disc list-inside pl-2 space-y-1">
                  <li>"What day is today?"</li>
                  <li>"Draft me an email"</li>
                  <li>"Show me my recent emails"</li>
                  <li>"What's on my calendar today?"</li>
                </ul>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`mb-4 ${
                  msg.role === 'user' ? 'text-right' : 'text-left'
                }`}
              >
                <div
                  className={`inline-block max-w-[80%] rounded-lg px-4 py-2 ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : msg.draft_ready || msg.draft_updated
                      ? 'bg-green-50 border-2 border-green-500 text-gray-800'
                      : msg.email_sent
                      ? 'bg-blue-50 border-2 border-blue-500 text-gray-800'
                      : 'bg-gray-200 text-gray-800'
                  }`}
                >
                  <div className="font-semibold text-xs mb-1 flex items-center gap-2">
                    <span>{msg.role === 'user' ? '👤 You' : '🤖 OrganAIzer'}</span>
                    {msg.draft_updated && <span className="text-green-600">✏️ Draft Updated</span>}
                    {msg.draft_ready && !msg.draft_updated && <span className="text-green-600">📝 Draft Ready</span>}
                    {msg.email_sent && <span className="text-blue-600">✅ Sent</span>}
                  </div>
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                  {msg.data && (
                    <div className="mt-2 text-xs opacity-75">
                      <details>
                        <summary className="cursor-pointer">View data</summary>
                        <pre className="mt-1 text-xs bg-black bg-opacity-10 p-2 rounded overflow-x-auto">
                          {JSON.stringify(msg.data, null, 2)}
                        </pre>
                      </details>
                    </div>
                  )}
                  <div className="text-xs opacity-75 mt-1">
                    {msg.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Voice Error */}
        {voiceError && (
          <div className="bg-yellow-100 border border-yellow-400 text-yellow-800 px-4 py-2 rounded mb-3 flex items-center justify-between text-sm">
            <span>🎤 {voiceError}</span>
            <button onClick={() => setVoiceError(null)} className="ml-2 text-yellow-900 hover:text-yellow-950">✕</button>
          </div>
        )}

        {/* Voice status bar */}
        {(isRecording || isTranscribing) && (
          <div className="mb-3 flex items-center gap-3">
            {isRecording && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-red-100 rounded-lg text-sm text-red-700 font-medium">
                <span className="inline-block w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                Recording… click 🎤 to stop
              </div>
            )}
            {isTranscribing && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-100 rounded-lg text-sm text-blue-700 font-medium">
                <span className="animate-spin inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
                Transcribing…
              </div>
            )}
          </div>
        )}

        {/* Input Section */}
        <div className="flex gap-2">
          {/* Microphone button */}
          <button
            onClick={toggleRecording}
            disabled={isTranscribing || loading}
            title={isRecording ? 'Stop recording' : 'Record voice message (transcript will appear in input)'}
            className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              isRecording
                ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse'
                : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
            }`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={isRecording ? '🔴 Recording… click mic to stop' : isTranscribing ? 'Transcribing…' : 'Type or record your message…'}
            disabled={loading || isRecording || isTranscribing}
            className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim() || isRecording || isTranscribing}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? (
              <span className="flex items-center">
                <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Sending...
              </span>
            ) : (
              'Send'
            )}
          </button>
        </div>

        {/* Status Indicator */}
        <div className="mt-4 text-sm text-gray-600">
          {loading ? (
            <span className="flex items-center">
              <span className="inline-block w-2 h-2 bg-yellow-500 rounded-full mr-2 animate-pulse"></span>
              Agent is thinking...
            </span>
          ) : (
            <span className="flex items-center">
              <span className="inline-block w-2 h-2 bg-green-500 rounded-full mr-2"></span>
              Ready
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default ExecutiveAgent;
