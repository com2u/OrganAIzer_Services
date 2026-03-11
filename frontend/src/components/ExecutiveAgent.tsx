import { useState, useRef, useEffect, useCallback } from 'react';
import ChatComposer from './ChatComposer';
import { agentChat, ttsGenerate, API_BASE_URL } from '../lib/apiClient';

// ── Types ────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  audioUrl?: string;
  /** Backend response type (calendar_created, email_sent, provider_not_connected, …) */
  responseType?: string;
  /** Backend action_needed field — 'confirmation' shows yes/no quick-reply buttons */
  actionNeeded?: string;
}

interface Props {
  /** Called when the user clicks "Go to Integrations" from a provider_not_connected message */
  onPageChange?: (page: string) => void;
}

type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface DebugEntry {
  ts: string;
  event: string;
  data?: unknown;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

/** Build a WebSocket base URL from the API base URL (handles http→ws and https→wss). */
function toWsBase(apiBase: string): string {
  if (apiBase) return apiBase.replace(/^http/, 'ws');
  // Same-origin: derive from location
  const proto   = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host    = window.location.host;
  return `${proto}://${host}`;
}

const SESSION_ID = `agent-${Date.now()}`;

// These chips must use English phrases that the backend intent router matches deterministically.
// German phrases fall through to the LLM general-message handler and never call the calendar/email API.
const SUGGESTIONS = [
  'What meetings do I have today?',
  'Show my last 5 emails',
  'Create a meeting tomorrow at 10am',
  'Send an email to my boss',
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ExecutiveAgent({ onPageChange }: Props = {}) {
  const [messages,        setMessages]        = useState<Message[]>([]);
  const [loading,         setLoading]         = useState(false);
  const [error,           setError]           = useState<string | null>(null);
  const [autoSpeak,       setAutoSpeak]       = useState(false);

  // Integration connection state — determines which calendar/mail provider to use
  const [googleConnected,    setGoogleConnected]    = useState(false);
  const [microsoftConnected, setMicrosoftConnected] = useState(false);

  // Realtime voice-mode state
  const [voiceMode,       setVoiceMode]       = useState(false);
  const [voiceState,      setVoiceState]      = useState<VoiceState>('idle');
  const [partialTranscript, setPartialTranscript] = useState('');
  const [voiceError,      setVoiceError]      = useState<string | null>(null);
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);

  // Debug panel
  const [debugOpen,       setDebugOpen]       = useState(false);
  const [debugLog,        setDebugLog]        = useState<DebugEntry[]>([]);
  const [wsStatus,        setWsStatus]        = useState<'disconnected'|'connecting'|'open'|'error'>('disconnected');
  const [lastLatency,     setLastLatency]     = useState<Record<string,number>>({});

  const bottomRef          = useRef<HTMLDivElement>(null);
  const audioRef           = useRef<HTMLAudioElement | null>(null);
  const wsRef              = useRef<WebSocket | null>(null);
  const voiceModeRef       = useRef(false);
  const vmMediaRecorderRef = useRef<MediaRecorder | null>(null);
  const vmStreamRef        = useRef<MediaStream | null>(null);
  const voiceStateRef      = useRef<VoiceState>('idle');

  // Keep voiceStateRef in sync
  useEffect(() => { voiceStateRef.current = voiceState; }, [voiceState]);

  // Query integration status on mount — determines which provider to send per-message
  useEffect(() => {
    const apiKey = (import.meta.env.VITE_API_KEY as string) ?? '';
    const fetchStatus = async () => {
      try {
        const gRes = await fetch(`${API_BASE_URL}/api/integrations/google/status?user_id=default_user`, {
          headers: { 'X-API-Key': apiKey },
        });
        if (gRes.ok) {
          const gData = await gRes.json();
          setGoogleConnected(Boolean(gData.connected));
        }
      } catch { /* network error → stays false */ }
      try {
        const mRes = await fetch(`${API_BASE_URL}/api/integrations/microsoft/status?user_id=default_user`, {
          headers: { 'X-API-Key': apiKey },
        });
        if (mRes.ok) {
          const mData = await mRes.json();
          setMicrosoftConnected(Boolean(mData.connected));
        }
      } catch { /* network error → stays false */ }
    };
    fetchStatus();
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // ── Debug log helper ────────────────────────────────────────────────────────

  const addDebug = useCallback((event: string, data?: unknown) => {
    setDebugLog(prev => [
      { ts: new Date().toISOString().slice(11, 23), event, data },
      ...prev.slice(0, 79),   // keep last 80 entries
    ]);
  }, []);

  // ── Audio helper ────────────────────────────────────────────────────────────

  const playAudio = useCallback((url: string) => {
    audioRef.current?.pause();
    const audio = new Audio(url);
    audioRef.current  = audio;
    audio.onended     = () => setVoiceState(vs => vs === 'speaking' ? 'idle' : vs);
    audio.play().catch(() => {});
  }, []);

  // ── Text-chat send ──────────────────────────────────────────────────────────

  const handleSend = useCallback(async (text: string) => {
    // Derive provider from real connection state:
    //   Microsoft only  → use outlook for both calendar and mail
    //   Google only, or both, or neither → use google/gmail (will give 401 if neither connected)
    const calendarProvider = (!googleConnected && microsoftConnected) ? 'outlook' : 'google';
    const mailProvider     = (!googleConnected && microsoftConnected) ? 'outlook' : 'gmail';

    const userMsg: Message = {
      id: makeId(), role: 'user', content: text, timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setError(null);

    try {
      const data = await agentChat(text, SESSION_ID, 'default_user', calendarProvider, mailProvider);
      const assistantText = data.message || '(no response)';

      let audioUrl: string | undefined;
      if (autoSpeak) {
        audioUrl = (await ttsGenerate(assistantText)) ?? undefined;
      }

      const assistantMsg: Message = {
        id: makeId(), role: 'assistant', content: assistantText,
        timestamp: new Date(), audioUrl,
        // Use canonical task_state from standardized envelope; fall back to
        // action_needed for backward compat with any cached responses.
        responseType: data.type ?? undefined,
        actionNeeded: data.task_state === 'CONFIRMING' ? 'confirmation'
          : (data.action_needed ?? undefined),
      };
      setMessages(prev => [...prev, assistantMsg]);
      if (audioUrl) playAudio(audioUrl);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      setError(msg);
      setMessages(prev => [
        ...prev,
        { id: makeId(), role: 'assistant', content: `❌ ${msg}`, timestamp: new Date() },
      ]);
    } finally {
      setLoading(false);
    }
  }, [autoSpeak, playAudio, googleConnected, microsoftConnected]);

  // ── Realtime voice-mode WS ──────────────────────────────────────────────────

  const stopVmStream = useCallback(() => {
    vmStreamRef.current?.getTracks().forEach(t => t.stop());
    vmStreamRef.current = null;
  }, []);

  const connectVoiceWS = useCallback(() => {
    setWsStatus('connecting');
    const wsBase = toWsBase(API_BASE_URL);
    // Use the same provider logic as text chat: prefer Gmail/Google, fall back to Outlook/Microsoft
    const wsProvider = (!googleConnected && microsoftConnected) ? 'outlook' : 'gmail';
    const url = `${wsBase}/api/voice/stream?session_id=${SESSION_ID}&user_id=default_user&provider=${wsProvider}`;
    addDebug('ws:connecting', { url });
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus('open');
      addDebug('ws:open');
    };

    ws.onmessage = ev => {
      try {
        const data = JSON.parse(ev.data as string);
      switch (data.type) {
          case 'ready':
            // Backend acknowledged the connection — we are truly ready
            setWsStatus('open');
            addDebug('ws:ready');
            break;
          case 'state':
            setVoiceState(data.state as VoiceState);
            addDebug('state', data.state);
            break;
          case 'stt.partial':
            setPartialTranscript(data.text ?? '');
            break;
          case 'stt.final':
            setPartialTranscript('');
            if (data.text) {
              setMessages(prev => [
                ...prev,
                { id: makeId(), role: 'user', content: data.text, timestamp: new Date() },
              ]);
              addDebug('stt.final', data.text.slice(0, 80));
            }
            break;
          case 'ai.response.text':
            if (data.text) {
              setMessages(prev => [
                ...prev,
                { id: makeId(), role: 'assistant', content: data.text, timestamp: new Date() },
              ]);
              addDebug('ai.response', data.text.slice(0, 80));
            }
            break;
          case 'tts.audio':
            if (data.audio_url) {
              // Stop any current playback before starting new one
              audioRef.current?.pause();
              const fullUrl = data.audio_url.startsWith('http')
                ? data.audio_url
                : `${API_BASE_URL}${data.audio_url}`;
              const audio = new Audio(fullUrl);
              audioRef.current = audio;
              audio.onended = () => {
                setVoiceState('idle');
                addDebug('tts:ended');
              };
              audio.play().catch(e => addDebug('tts:play_err', String(e)));
              addDebug('tts.audio', { url: fullUrl });
            }
            break;
          case 'stt':
            // {"type": "stt", "status": "no_speech"|"no_audio", "reason": "..."}
            // Emitted when the server detected silence or a too-short recording.
            if (data.status === 'no_speech') {
              addDebug('stt:no_speech');
              setPartialTranscript('');
            } else if (data.status === 'no_audio') {
              addDebug('stt:no_audio', data.reason);
              setVoiceError('No audio recorded — please hold the button while speaking.');
            }
            break;
          case 'error':
            setVoiceError(data.message ?? 'Voice-Fehler');
            addDebug('error', data.message);
            break;
          case 'debug':
            // Server-side debug payloads (VOICE_DEBUG=true)
            if (data.data?.total_round_trip_ms !== undefined) {
              setLastLatency(prev => ({ ...prev, round_trip: data.data.total_round_trip_ms }));
            }
            if (data.data?.tts_latency_ms !== undefined) {
              setLastLatency(prev => ({ ...prev, tts: data.data.tts_latency_ms }));
            }
            if (data.data?.ai_latency_ms !== undefined) {
              setLastLatency(prev => ({ ...prev, ai: data.data.ai_latency_ms }));
            }
            addDebug('debug', data.data);
            break;
          case 'pong':
            addDebug('pong');
            break;
        }
      } catch { /* ignore parse errors */ }
    };

    ws.onclose = ev => {
      setWsStatus('disconnected');
      addDebug('ws:close', { code: ev.code });
      if (voiceModeRef.current) setTimeout(connectVoiceWS, 2000);
    };
    ws.onerror = () => {
      setWsStatus('error');
      addDebug('ws:error');
    };
  }, [addDebug, googleConnected, microsoftConnected]);

  useEffect(() => {
    voiceModeRef.current = voiceMode;
    if (voiceMode) {
      connectVoiceWS();
    } else {
      wsRef.current?.close();
      wsRef.current = null;
      audioRef.current?.pause();
      audioRef.current = null;
      setVoiceState('idle');
      setPartialTranscript('');
      stopVmStream();
      if (vmMediaRecorderRef.current?.state === 'recording') vmMediaRecorderRef.current.stop();
      setIsVoiceRecording(false);
    }
  }, [voiceMode, connectVoiceWS, stopVmStream]);

  /** Send an explicit interrupt to the server and stop local playback. */
  const sendInterrupt = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    }
    addDebug('interrupt:sent');
  }, [addDebug]);

  const startVmSpeaking = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    // Interrupt any ongoing TTS
    sendInterrupt();
    setVoiceError(null);
    wsRef.current.send(JSON.stringify({ type: 'audio_start' }));
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      vmStreamRef.current = stream;
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      vmMediaRecorderRef.current = mr;
      mr.ondataavailable = e => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(e.data);
        }
      };
      mr.start(500);
      setIsVoiceRecording(true);
      addDebug('mic:start');
    } catch {
      setVoiceError('Mikrofon-Zugriff verweigert');
    }
  }, [sendInterrupt, addDebug]);

  const stopVmSpeaking = useCallback(() => {
    if (vmMediaRecorderRef.current?.state === 'recording') vmMediaRecorderRef.current.stop();
    stopVmStream();
    setIsVoiceRecording(false);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'audio_end' }));
    }
    addDebug('mic:stop');
  }, [stopVmStream, addDebug]);

  // ── Voice overlay helpers ───────────────────────────────────────────────────

  const voiceLabel: Record<VoiceState, string> = {
    idle:      'Bereit — Taste halten zum Sprechen',
    listening: 'Zuhören…',
    thinking:  'Nachdenken…',
    speaking:  'Sprechen…',
  };
  const voiceColor: Record<VoiceState, string> = {
    idle: 'text-gray-300', listening: 'text-red-400', thinking: 'text-yellow-400', speaking: 'text-green-400',
  };
  const voiceEmoji: Record<VoiceState, string> = {
    idle: '🎤', listening: '🎙️', thinking: '🤔', speaking: '🔊',
  };

  // ── WS status badge ────────────────────────────────────────────────────────

  const wsStatusColor: Record<string, string> = {
    disconnected: 'bg-gray-400',
    connecting:   'bg-yellow-400',
    open:         'bg-green-400',
    error:        'bg-red-500',
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 105px)' }}>

      {/* ── Realtime voice-mode fullscreen overlay ───────────────────────── */}
      {voiceMode && (
        <div className="fixed inset-0 z-50 bg-black/90 flex flex-col items-center justify-center select-none">
          {/* State emoji */}
          <div className={`text-7xl mb-4 ${voiceState === 'listening' || voiceState === 'speaking' ? 'animate-pulse' : ''}`}>
            {voiceEmoji[voiceState]}
          </div>

          {/* State label */}
          <p className={`text-2xl font-semibold mb-6 ${voiceColor[voiceState]}`}>
            {voiceLabel[voiceState]}
          </p>

          {/* WS status indicator */}
          <div className="flex items-center gap-2 mb-4">
            <div className={`w-2 h-2 rounded-full ${wsStatusColor[wsStatus]}`}></div>
            <span className="text-gray-500 text-xs">{wsStatus}</span>
          </div>

          {/* Partial transcript */}
          {partialTranscript && (
            <p className="text-gray-300 text-lg mb-6 max-w-xl text-center italic">
              "{partialTranscript}"
            </p>
          )}

          {/* Hold-to-speak button */}
          <button
            onMouseDown={startVmSpeaking}
            onMouseUp={stopVmSpeaking}
            onTouchStart={e => { e.preventDefault(); startVmSpeaking(); }}
            onTouchEnd={e => { e.preventDefault(); stopVmSpeaking(); }}
            disabled={voiceState === 'thinking'}
            className={`w-28 h-28 rounded-full flex items-center justify-center text-5xl shadow-2xl transition-all
              ${isVoiceRecording ? 'bg-red-600 scale-110 ring-4 ring-red-400' : 'bg-blue-600 hover:bg-blue-500'}
              disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            🎤
          </button>
          <p className="text-gray-500 text-sm mt-3">
            {isVoiceRecording ? 'Loslassen zum Senden' : 'Halten zum Sprechen'}
          </p>

          {/* Interrupt button (only while speaking) */}
          {voiceState === 'speaking' && (
            <button
              onClick={sendInterrupt}
              className="mt-4 px-5 py-2 bg-yellow-600 text-white rounded-full text-sm hover:bg-yellow-500 transition-colors"
            >
              ⚡ Unterbrechen
            </button>
          )}

          {/* Voice error */}
          {voiceError && (
            <div className="mt-4 px-4 py-2 bg-red-900 text-red-200 rounded-lg text-sm max-w-sm text-center">
              ⚠️ {voiceError}
              <button onClick={() => setVoiceError(null)} className="ml-2 text-red-300 hover:text-white">✕</button>
            </div>
          )}

          {/* Last 4 messages preview */}
          <div className="mt-8 w-full max-w-lg space-y-2 px-4 max-h-40 overflow-y-auto">
            {messages.slice(-4).map(m => (
              <div key={m.id}
                className={`text-sm rounded px-3 py-1 ${
                  m.role === 'user' ? 'bg-blue-900 text-blue-100 text-right' : 'bg-gray-800 text-gray-200 text-left'
                }`}>
                {m.content.substring(0, 120)}{m.content.length > 120 ? '…' : ''}
              </div>
            ))}
          </div>

          {/* Debug panel (voice overlay) */}
          {debugOpen && (
            <div className="mt-4 w-full max-w-lg px-4">
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs text-green-400 font-mono max-h-36 overflow-y-auto">
                <div className="text-gray-500 mb-1">
                  🔧 debug · session={SESSION_ID.slice(-8)} · ws={wsStatus}
                  {Object.keys(lastLatency).length > 0 && (
                    <span className="ml-2">
                      | ai={lastLatency.ai}ms tts={lastLatency.tts}ms rt={lastLatency.round_trip}ms
                    </span>
                  )}
                </div>
                {debugLog.slice(0, 15).map((e, i) => (
                  <div key={i} className="truncate">
                    <span className="text-gray-600">{e.ts}</span>{' '}
                    <span className="text-yellow-400">{e.event}</span>{' '}
                    {e.data !== undefined && (
                      <span className="text-green-300">{JSON.stringify(e.data).slice(0, 80)}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Bottom buttons */}
          <div className="mt-6 flex items-center gap-4">
            <button
              onClick={() => setDebugOpen(v => !v)}
              className={`px-4 py-2 rounded-full text-xs font-medium transition-colors ${
                debugOpen ? 'bg-green-800 text-green-100' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              🔧 Debug
            </button>
            <button
              onClick={() => setVoiceMode(false)}
              className="px-8 py-3 bg-gray-700 text-white rounded-full hover:bg-gray-600 text-sm font-medium"
            >
              ✕ Sprachmodus beenden
            </button>
          </div>
        </div>
      )}

      {/* ── Message list ──────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-36">

        {/* Empty state */}
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-5xl mb-3 select-none">🤖</div>
            <p className="text-lg font-semibold text-gray-700">OrganAIzer Executive Agent</p>
            <p className="text-sm text-gray-400 mt-1">Tippe, spreche oder wähle einen Vorschlag</p>
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-md w-full">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  className="bg-white border border-gray-200 rounded-xl px-3 py-2.5 text-sm
                             text-gray-600 hover:bg-gray-50 hover:border-gray-300
                             shadow-sm transition-colors text-left"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map(msg => (
          <div key={msg.id} className={`flex mb-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center
                              mr-2 flex-shrink-0 mt-0.5 text-sm select-none">
                🤖
              </div>
            )}
            <div className="max-w-[75%] min-w-0">
              <div className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-md'
                  : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-md'
              }`}>
                {msg.content}
              </div>
              <div className="flex items-center gap-2 mt-1 px-1">
                <span className="text-xs text-gray-400">
                  {msg.timestamp.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
                </span>
                {msg.audioUrl && (
                  <button
                    onClick={() => playAudio(msg.audioUrl!)}
                    className="text-xs text-indigo-500 hover:text-indigo-700 flex items-center gap-0.5"
                    title="Abspielen"
                  >
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" />
                    </svg>
                    Abspielen
                  </button>
                )}
              </div>

              {/* ── Confirmation quick-reply buttons ───────────────────── */}
              {msg.role === 'assistant' && msg.actionNeeded === 'confirmation' && (
                <div className="flex gap-2 mt-2 px-1">
                  <button
                    onClick={() => handleSend('yes')}
                    disabled={loading}
                    className="px-4 py-1.5 bg-green-600 text-white text-xs font-medium
                               rounded-full hover:bg-green-700 disabled:opacity-50 transition-colors"
                  >
                    ✓ Ja
                  </button>
                  <button
                    onClick={() => handleSend('no')}
                    disabled={loading}
                    className="px-4 py-1.5 bg-gray-500 text-white text-xs font-medium
                               rounded-full hover:bg-gray-600 disabled:opacity-50 transition-colors"
                  >
                    ✕ Nein
                  </button>
                </div>
              )}

              {/* ── Calendar provider selection quick-reply ────────────── */}
              {msg.role === 'assistant' && msg.responseType === 'calendar_provider_request' && (
                <div className="flex gap-2 mt-2 px-1 flex-wrap">
                  <button
                    onClick={() => handleSend('Google Calendar')}
                    disabled={loading}
                    className="px-4 py-1.5 bg-blue-600 text-white text-xs font-medium
                               rounded-full hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    📅 Google Calendar
                  </button>
                  <button
                    onClick={() => handleSend('Outlook Calendar')}
                    disabled={loading}
                    className="px-4 py-1.5 bg-cyan-700 text-white text-xs font-medium
                               rounded-full hover:bg-cyan-800 disabled:opacity-50 transition-colors"
                  >
                    📅 Outlook
                  </button>
                </div>
              )}

              {/* ── Provider not connected — deep-link to Integrations ── */}
              {msg.role === 'assistant' && msg.responseType === 'provider_not_connected' && onPageChange && (
                <div className="mt-2 px-1">
                  <button
                    onClick={() => onPageChange('integrations')}
                    className="text-xs text-blue-600 hover:text-blue-800 underline
                               flex items-center gap-1 transition-colors"
                  >
                    🔗 Integrations-Seite öffnen
                  </button>
                </div>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center
                              ml-2 flex-shrink-0 mt-0.5 text-sm select-none">
                👤
              </div>
            )}
          </div>
        ))}

        {/* Typing indicator */}
        {loading && (
          <div className="flex justify-start mb-4">
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center
                            mr-2 flex-shrink-0 text-sm select-none">🤖</div>
            <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1.5 items-center">
                {[0, 150, 300].map(d => (
                  <span key={d} className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: `${d}ms` }} />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Error toast ───────────────────────────────────────────────────── */}
      {error && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50
                        bg-red-50 border border-red-300 text-red-700 text-sm
                        px-4 py-2 rounded-lg shadow-md flex items-center gap-2 max-w-sm">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      {/* ── Debug panel (text chat view) ─────────────────────────────────── */}
      {debugOpen && !voiceMode && (
        <div className="fixed bottom-28 right-4 z-40 w-80 max-h-60 overflow-y-auto
                        bg-gray-950 border border-gray-700 rounded-xl shadow-2xl p-3
                        text-xs text-green-400 font-mono">
          <div className="flex items-center justify-between mb-1">
            <span className="text-gray-500">
              🔧 debug · session={SESSION_ID.slice(-8)}
            </span>
            <button onClick={() => setDebugOpen(false)} className="text-gray-600 hover:text-gray-300">✕</button>
          </div>
          {Object.keys(lastLatency).length > 0 && (
            <div className="text-yellow-400 mb-1">
              ai={lastLatency.ai ?? '?'}ms · tts={lastLatency.tts ?? '?'}ms · rt={lastLatency.round_trip ?? '?'}ms
            </div>
          )}
          {debugLog.length === 0 && (
            <div className="text-gray-600 italic">No events yet. Open voice mode to see data.</div>
          )}
          {debugLog.map((e, i) => (
            <div key={i} className="truncate leading-5">
              <span className="text-gray-600">{e.ts}</span>{' '}
              <span className="text-yellow-400">{e.event}</span>{' '}
              {e.data !== undefined && (
                <span className="text-green-300">{JSON.stringify(e.data).slice(0, 60)}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── TTS auto-speak toggle + debug toggle ─────────────────────────── */}
      <div className="fixed bottom-[5.5rem] right-4 z-50 flex flex-col items-end gap-1.5">
        <button
          onClick={() => setDebugOpen(v => !v)}
          className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full shadow transition-colors ${
            debugOpen
              ? 'bg-green-700 text-white'
              : 'bg-white text-gray-400 border border-gray-200 hover:border-gray-300'
          }`}
          title="Debug panel"
        >
          🔧 Debug
        </button>
        <button
          onClick={() => setAutoSpeak(v => !v)}
          className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full shadow transition-colors ${
            autoSpeak ? 'bg-indigo-600 text-white' : 'bg-white text-gray-500 border border-gray-200 hover:border-gray-300'
          }`}
          title={autoSpeak ? 'TTS deaktivieren' : 'Antworten automatisch vorlesen'}
        >
          🔊 {autoSpeak ? 'TTS an' : 'TTS aus'}
        </button>
      </div>

      {/* ── Floating pill composer ────────────────────────────────────────── */}
      <ChatComposer
        onSend={handleSend}
        disabled={loading}
        onVoiceMode={() => setVoiceMode(true)}
      />
    </div>
  );
}
