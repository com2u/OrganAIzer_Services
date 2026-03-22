import { useState, useEffect, useRef, useCallback } from 'react';
import { getOrCreateSessionId } from '../lib/session';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Message {
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
}

interface ConversationState {
  isRecording: boolean;
  isTranscribing: boolean;
  isThinking: boolean;
  isSpeaking: boolean;
  liveTranscript: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

/**
 * VoiceExecutiveAgent
 *
 * Uses a single persistent WebSocket to /api/voice/stream for the full pipeline:
 *   mic → binary chunks → (audio_end) → backend STT → Executive AI → TTS
 *
 * WS protocol (client → server):
 *   {"type":"audio_start"}   – user pressed mic
 *   <binary Blob>            – 250 ms audio chunk (webm/opus)
 *   {"type":"audio_end"}     – user released mic
 *   {"type":"interrupt"}     – stop TTS, resume listening
 *   {"type":"ping"}          – keepalive
 *
 * WS protocol (server → client) handled here:
 *   {"type":"ready"}
 *   {"type":"state",            "state":"idle|listening|thinking|speaking"}
 *   {"type":"stt.partial",      "text":"..."}
 *   {"type":"stt.final",        "text":"..."}
 *   {"type":"ai.response.text", "text":"..."}
 *   {"type":"tts.audio",        "audio_url":"..."}
 *   {"type":"stt",              "status":"no_speech|no_audio"}
 *   {"type":"error",            "message":"..."}
 *   {"type":"pong"}
 */
function VoiceExecutiveAgent() {
  const [messages, setMessages]     = useState<Message[]>([]);
  const [state, setState]           = useState<ConversationState>({
    isRecording:    false,
    isTranscribing: false,
    isThinking:     false,
    isSpeaking:     false,
    liveTranscript: '',
  });
  const [error, setError]           = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  // Use sessionStorage-persisted ID so re-renders / navigation don't start a new context.
  const [sessionId]                 = useState(() => getOrCreateSessionId());

  // Refs – survive re-renders without triggering them
  const wsRef                 = useRef<WebSocket | null>(null);
  const mediaRecorderRef      = useRef<MediaRecorder | null>(null);
  const streamRef             = useRef<MediaStream | null>(null);
  const audioPlayerRef        = useRef<HTMLAudioElement | null>(null);
  const mimeTypeRef           = useRef<string>('audio/webm');
  const recordingStartTimeRef = useRef<number>(0);
  const reconnectTimerRef     = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef            = useRef(true);

  // Environment – vite.config.ts defines VITE_API_BASE_URL
  // Dev:  "http://localhost:8000"  → ws://localhost:8000
  // Prod: ""                       → wss://<origin>
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

  // ── Auto-scroll ─────────────────────────────────────────────────────────────
  const messagesEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Build WebSocket URL ─────────────────────────────────────────────────────
  const getWsUrl = useCallback((): string => {
    // Do NOT hard-lock calendar_provider / mail_provider here.
    // Omitting them lets the Executive Agent apply its own provider resolution
    // hierarchy (explicit user mention → session preference → clarification).
    // The backend will ask the user "Google or Microsoft?" when ambiguous.
    const params = `session_id=${sessionId}&user_id=voice_user`;
    if (API_BASE_URL) {
      // Convert http(s):// → ws(s)://
      const wsBase = API_BASE_URL
        .replace(/^https:/, 'wss:')
        .replace(/^http:/, 'ws:');
      return `${wsBase}/api/voice/stream?${params}`;
    }
    // Same-origin (production, served by nginx)
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/api/voice/stream?${params}`;
  }, [API_BASE_URL, sessionId]);

  // ── Play TTS audio ──────────────────────────────────────────────────────────
  const playTTS = useCallback(async (audioUrl: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const audio = new Audio(audioUrl);
      audioPlayerRef.current = audio;

      audio.onended = () => {
        setState(prev => ({ ...prev, isSpeaking: false }));
        resolve();
      };
      audio.onerror = (err) => {
        setState(prev => ({ ...prev, isSpeaking: false }));
        console.error('[VoiceAgent] Audio playback error:', err);
        reject(err);
      };
      audio.play().catch(err => {
        setState(prev => ({ ...prev, isSpeaking: false }));
        console.error('[VoiceAgent] Audio play failed:', err);
        reject(err);
      });
    });
  }, []);

  // ── WebSocket: create & wire up ─────────────────────────────────────────────
  const connectWS = useCallback(() => {
    if (!mountedRef.current) return;

    // Already open – skip
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const url = getWsUrl();
    console.log('[VoiceAgent] WS connecting →', url);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[VoiceAgent] WS connected');
      if (mountedRef.current) setWsConnected(true);
    };

    ws.onmessage = (event) => {
      // Binary frames are not expected server→client in this protocol
      if (typeof event.data !== 'string') return;

      let data: Record<string, any>;
      try { data = JSON.parse(event.data as string); } catch { return; }

      const type: string = data['type'] ?? '';
      // Lightweight console trace for DevTools WS frame inspection
      console.log(
        '[VoiceAgent] WS ←',
        type,
        data['state'] ?? data['text']?.slice?.(0, 60) ?? data['status'] ?? '',
      );

      switch (type) {
        // ── Server acknowledged the connection ─────────────────────────────
        case 'ready':
          break;

        // ── Conversation-state machine ──────────────────────────────────────
        case 'state':
          switch (data['state']) {
            case 'idle':
              setState(prev => ({
                ...prev,
                isTranscribing: false,
                isThinking:     false,
                isSpeaking:     false,
                // Keep liveTranscript if mic is still physically held
                liveTranscript: prev.isRecording ? prev.liveTranscript : '',
              }));
              break;
            case 'listening':
              // Backend confirmed audio_start was received
              setState(prev => ({ ...prev, liveTranscript: 'Listening…' }));
              break;
            case 'thinking':
              // Covers both STT processing and AI inference
              setState(prev => ({
                ...prev,
                isTranscribing: false,
                isThinking:     true,
                liveTranscript: 'Processing…',
              }));
              break;
            case 'speaking':
              setState(prev => ({ ...prev, isThinking: false, isSpeaking: true }));
              break;
          }
          break;

        // ── Interim STT result (live feedback while mic is held) ────────────
        case 'stt.partial':
          if (data['text']) {
            setState(prev => ({ ...prev, liveTranscript: data['text'] as string }));
          }
          break;

        // ── Final STT result → add user bubble ─────────────────────────────
        case 'stt.final':
          if (data['text']) {
            setMessages(prev => [
              ...prev,
              { role: 'user', content: data['text'] as string, timestamp: new Date() },
            ]);
            setState(prev => ({ ...prev, liveTranscript: '', isTranscribing: false }));
          }
          break;

        // ── Executive AI reply → add agent bubble ──────────────────────────
        case 'ai.response.text':
          if (data['text']) {
            setMessages(prev => [
              ...prev,
              { role: 'agent', content: data['text'] as string, timestamp: new Date() },
            ]);
            setState(prev => ({ ...prev, isThinking: false }));
          }
          break;

        // ── TTS audio ready → play it ────────────────────────────────────
        case 'tts.audio': {
          const audioPath = data['audio_url'] as string | undefined;
          if (audioPath) {
            // audio_url is a server-relative path like /api/tts/audio/<id>
            const fullUrl = `${API_BASE_URL}${audioPath}`;
            setState(prev => ({ ...prev, isSpeaking: true }));
            playTTS(fullUrl).catch(e => {
              console.error('[VoiceAgent] TTS play error:', e);
              setState(prev => ({ ...prev, isSpeaking: false }));
            });
          }
          break;
        }

        // ── STT silent / too-short – go quietly idle ──────────────────────
        case 'stt':
          // status: "no_speech" | "no_audio"
          setState(prev => ({ ...prev, isThinking: false, liveTranscript: '' }));
          break;

        // ── Server-side error ────────────────────────────────────────────
        case 'error':
          setError((data['message'] as string) || 'Voice server error');
          setState(prev => ({
            ...prev,
            isThinking: false,
            isSpeaking: false,
            liveTranscript: '',
          }));
          break;

        case 'pong':
          break;

        default:
          // Unknown message type – ignore silently
          break;
      }
    };

    ws.onclose = (evt) => {
      console.log('[VoiceAgent] WS closed', evt.code, evt.reason);
      if (mountedRef.current) {
        setWsConnected(false);
        // Auto-reconnect unless normal close (code 1000)
        if (evt.code !== 1000) {
          reconnectTimerRef.current = setTimeout(() => connectWS(), 3000);
        }
      }
    };

    ws.onerror = (err) => {
      console.error('[VoiceAgent] WS error:', err);
    };
  }, [getWsUrl, playTTS, API_BASE_URL]);

  // ── Mount: open WS; unmount: close WS + cleanup ─────────────────────────
  useEffect(() => {
    mountedRef.current = true;
    connectWS();
    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close(1000, 'component unmounted');
      streamRef.current?.getTracks().forEach(t => t.stop());
      audioPlayerRef.current?.pause();
    };
  }, [connectWS]);

  // ── Best supported MediaRecorder MIME type ───────────────────────────────
  const getSupportedMimeType = (): string => {
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/ogg',
    ];
    for (const t of candidates) {
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)) return t;
    }
    return '';
  };

  // ── Toggle microphone recording ──────────────────────────────────────────
  const toggleRecording = async () => {
    if (state.isRecording) {
      // ── STOP ──────────────────────────────────────────────────────────────
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop();
        // audio_end is sent inside onstop after final chunks flush
      }
    } else {
      // ── START ─────────────────────────────────────────────────────────────
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setError('Not connected to voice server. Please wait a moment…');
        connectWS();
        return;
      }

      setError(null);

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        streamRef.current = stream;

        // Prefer opus codec for a valid EBML/webm container
        const chosenMime = getSupportedMimeType();
        mimeTypeRef.current = chosenMime || 'audio/webm';
        console.log('[VoiceAgent] MediaRecorder mimeType:', mimeTypeRef.current);

        const options: MediaRecorderOptions = {};
        if (chosenMime) options.mimeType = chosenMime;
        const recorder = new MediaRecorder(stream, options);
        mediaRecorderRef.current = recorder;

        // ── Stream each 250 ms chunk directly over the open WebSocket ──────
        recorder.ondataavailable = (event) => {
          if (event.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
            // ws.send(Blob) is enqueued synchronously → arrives before audio_end
            wsRef.current.send(event.data);
          }
        };

        // ── After all chunks are flushed, notify backend ─────────────────
        recorder.onstop = () => {
          setState(prev => ({ ...prev, isRecording: false }));
          streamRef.current?.getTracks().forEach(t => t.stop());
          streamRef.current = null;

          const elapsed = Date.now() - recordingStartTimeRef.current;
          console.log(`[VoiceAgent] Recording stopped: ${elapsed} ms`);

          if (elapsed < 400) {
            setError('Recording too short – please hold the button while speaking.');
            // Still send audio_end so backend returns to idle
          }

          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'audio_end' }));
            console.log('[VoiceAgent] Sent audio_end');
          }
        };

        // Tell backend to prepare for audio, then start capturing chunks
        wsRef.current.send(JSON.stringify({ type: 'audio_start' }));
        recordingStartTimeRef.current = Date.now();
        recorder.start(250); // 250 ms timeslice guarantees EBML header in first chunk
        setState(prev => ({ ...prev, isRecording: true, liveTranscript: 'Listening…' }));

      } catch (err: unknown) {
        console.error('[VoiceAgent] Microphone access error:', err);
        // Distinguish permission denial from other mic failures so the user
        // gets actionable guidance rather than a generic message.
        const domErr = err as DOMException | undefined;
        if (domErr?.name === 'NotAllowedError' || domErr?.name === 'PermissionDeniedError') {
          setError(
            'Microphone access was denied. Please allow microphone access in your browser settings (🔒 icon in the address bar) and try again.'
          );
        } else if (domErr?.name === 'NotFoundError' || domErr?.name === 'DevicesNotFoundError') {
          setError('No microphone found. Please connect a microphone and try again.');
        } else {
          setError(`Could not access microphone: ${domErr?.message ?? String(err)}`);
        }
        // Always reset recording state so the button re-enables after an error.
        setState(prev => ({ ...prev, isRecording: false, isTranscribing: false, liveTranscript: '' }));
      }
    }
  };

  // ── Stop TTS playback + tell backend ────────────────────────────────────
  const stopTTS = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
      setState(prev => ({ ...prev, isSpeaking: false }));
    }
    wsRef.current?.send(JSON.stringify({ type: 'interrupt' }));
  };

  // ── Clear conversation ──────────────────────────────────────────────────
  const clearConversation = () => {
    setMessages([]);
    setError(null);
    stopTTS();
  };

  // ── Render ──────────────────────────────────────────────────────────────
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

      {/* Status bar */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4 flex-wrap gap-y-2">

            {/* WebSocket connection dot */}
            <div className={`flex items-center space-x-1 text-xs font-medium ${
              wsConnected ? 'text-green-600' : 'text-amber-600'
            }`}>
              <div className={`w-2 h-2 rounded-full ${
                wsConnected ? 'bg-green-500' : 'bg-amber-500 animate-pulse'
              }`} />
              <span>{wsConnected ? 'Connected' : 'Connecting…'}</span>
            </div>

            {/* Recording indicator */}
            <div className={`flex items-center space-x-2 px-4 py-2 rounded-lg ${
              state.isRecording ? 'bg-red-100' : 'bg-gray-100'
            }`}>
              <div className={`w-3 h-3 rounded-full ${
                state.isRecording ? 'bg-red-500 animate-pulse' : 'bg-gray-400'
              }`} />
              <span className="font-medium">
                {state.isRecording ? 'Recording…' : 'Ready'}
              </span>
            </div>

            {state.isTranscribing && (
              <div className="flex items-center space-x-2 px-4 py-2 bg-blue-100 rounded-lg">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent" />
                <span className="text-blue-700 font-medium">Transcribing…</span>
              </div>
            )}

            {state.isThinking && (
              <div className="flex items-center space-x-2 px-4 py-2 bg-purple-100 rounded-lg">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-purple-600 border-t-transparent" />
                <span className="text-purple-700 font-medium">AI Thinking…</span>
              </div>
            )}

            {state.isSpeaking && (
              <div className="flex items-center space-x-2 px-4 py-2 bg-green-100 rounded-lg">
                <div className="flex space-x-1">
                  <div className="w-1 h-4 bg-green-600 animate-pulse" />
                  <div className="w-1 h-4 bg-green-600 animate-pulse" style={{ animationDelay: '0.2s' }} />
                  <div className="w-1 h-4 bg-green-600 animate-pulse" style={{ animationDelay: '0.4s' }} />
                </div>
                <span className="text-green-700 font-medium">Speaking…</span>
              </div>
            )}
          </div>

          {state.isSpeaking && (
            <button
              onClick={stopTTS}
              className="px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition-colors"
            >
              Stop
            </button>
          )}
        </div>

        {/* Live transcript / status hint */}
        {state.liveTranscript && (
          <div className="mt-3 p-3 bg-gray-50 rounded text-gray-600 italic">
            {state.liveTranscript}
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          <div className="flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-900 hover:text-red-950">✕</button>
          </div>
        </div>
      )}

      {/* Conversation bubble list */}
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
              <div key={idx} className={`mb-4 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                <div className={`inline-block max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800'
                }`}>
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

      {/* Microphone button */}
      <div className="flex justify-center">
        <button
          onClick={toggleRecording}
          disabled={!wsConnected || state.isThinking || state.isSpeaking}
          className={`
            relative w-24 h-24 rounded-full flex items-center justify-center
            transition-all duration-300 shadow-lg
            ${state.isRecording ? 'bg-red-500 hover:bg-red-600 scale-110' : 'bg-blue-600 hover:bg-blue-700'}
            ${(!wsConnected || state.isThinking || state.isSpeaking) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          {state.isRecording ? (
            // Stop icon
            <svg className="w-12 h-12 text-white" fill="currentColor" viewBox="0 0 20 20">
              <rect x="6" y="6" width="8" height="8" rx="1" />
            </svg>
          ) : (
            // Mic icon
            <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          )}

          {/* Pulse rings while recording */}
          {state.isRecording && (
            <>
              <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 animate-ping" />
              <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 animate-ping"
                style={{ animationDelay: '0.5s' }} />
            </>
          )}
        </button>
      </div>

      <div className="text-center mt-4 text-sm text-gray-600">
        {state.isRecording ? (
          <p className="font-semibold text-red-600">Click to stop recording</p>
        ) : !wsConnected ? (
          <p className="text-amber-600">Connecting to voice server…</p>
        ) : (
          <p>Click to start speaking</p>
        )}
      </div>

      {/* How-it-works panel */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-semibold text-blue-900 mb-2">💡 How it works:</h3>
        <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
          <li>Click the microphone button and speak your request</li>
          <li>Click again to stop recording (audio streams live to backend)</li>
          <li>AI transcribes, thinks, and responds automatically</li>
          <li>Response is spoken aloud and shown in the conversation</li>
          <li>Continue the conversation naturally</li>
        </ol>
        <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
          <strong>⚠️ Safety:</strong> For sensitive actions (sending emails, deleting events),
          the AI will ask for confirmation before executing.
        </div>
      </div>
    </div>
  );
}

export default VoiceExecutiveAgent;
