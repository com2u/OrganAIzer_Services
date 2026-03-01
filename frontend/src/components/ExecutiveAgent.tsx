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
}

type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

const SESSION_ID = `agent-${Date.now()}`;

const SUGGESTIONS = [
  'Was ist heute auf meinem Kalender?',
  'Zeige meine letzten E-Mails',
  'Erstelle einen Termin für morgen 10 Uhr',
  'Schreibe eine E-Mail an meinen Chef',
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ExecutiveAgent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoSpeak, setAutoSpeak] = useState(false);

  // Realtime voice-mode state
  const [voiceMode, setVoiceMode] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [partialTranscript, setPartialTranscript] = useState('');
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const voiceModeRef = useRef(false);
  const vmMediaRecorderRef = useRef<MediaRecorder | null>(null);
  const vmStreamRef = useRef<MediaStream | null>(null);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // ── Audio helper ────────────────────────────────────────────────────────────

  const playAudio = useCallback((url: string) => {
    audioRef.current?.pause();
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.play().catch(() => {});
  }, []);

  // ── Text-chat send ──────────────────────────────────────────────────────────

  const handleSend = useCallback(async (text: string) => {
    const userMsg: Message = {
      id: makeId(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);

    try {
      const data = await agentChat(text, SESSION_ID);
      const assistantText = data.message || '(keine Antwort)';

      let audioUrl: string | undefined;
      if (autoSpeak) {
        audioUrl = (await ttsGenerate(assistantText)) ?? undefined;
      }

      const assistantMsg: Message = {
        id: makeId(),
        role: 'assistant',
        content: assistantText,
        timestamp: new Date(),
        audioUrl,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      if (audioUrl) playAudio(audioUrl);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unbekannter Fehler';
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { id: makeId(), role: 'assistant', content: `❌ ${msg}`, timestamp: new Date() },
      ]);
    } finally {
      setLoading(false);
    }
  }, [autoSpeak, playAudio]);

  // ── Realtime voice-mode WS ──────────────────────────────────────────────────

  const stopVmStream = useCallback(() => {
    vmStreamRef.current?.getTracks().forEach((t) => t.stop());
    vmStreamRef.current = null;
  }, []);

  const connectVoiceWS = useCallback(() => {
    // Build ws URL: replace http→ws in base, fall back to current host
    const base = API_BASE_URL || window.location.origin;
    const wsBase = base.replace(/^http/, 'ws');
    const url = `${wsBase}/api/voice/stream?session_id=${SESSION_ID}&user_id=default_user&provider=gmail`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => console.log('[Voice] WS connected');

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string);
        switch (data.type) {
          case 'state':
            setVoiceState(data.state as VoiceState);
            break;
          case 'stt.partial':
            setPartialTranscript(data.text ?? '');
            break;
          case 'stt.final':
            setPartialTranscript('');
            if (data.text) {
              setMessages((prev) => [...prev, { id: makeId(), role: 'user', content: data.text, timestamp: new Date() }]);
            }
            break;
          case 'ai.response.text':
            if (data.text) {
              setMessages((prev) => [...prev, { id: makeId(), role: 'assistant', content: data.text, timestamp: new Date() }]);
            }
            break;
          case 'tts.audio':
            if (data.audio_url) {
              audioRef.current?.pause();
              const audio = new Audio(`${API_BASE_URL}${data.audio_url}`);
              audioRef.current = audio;
              audio.play().catch(() => {});
            }
            break;
          case 'error':
            setVoiceError(data.message ?? 'Voice-Fehler');
            break;
        }
      } catch { /* ignore parse errors */ }
    };

    ws.onclose = () => {
      if (voiceModeRef.current) setTimeout(connectVoiceWS, 2000);
    };
    ws.onerror = (e) => console.error('[Voice] WS error', e);
  }, []);

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

  const startVmSpeaking = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    audioRef.current?.pause();
    audioRef.current = null;
    setVoiceError(null);
    wsRef.current.send(JSON.stringify({ type: 'audio_start' }));
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      vmStreamRef.current = stream;
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      vmMediaRecorderRef.current = mr;
      mr.ondataavailable = (e) => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(e.data);
      };
      mr.start(500);
      setIsVoiceRecording(true);
    } catch {
      setVoiceError('Mikrofon-Zugriff verweigert');
    }
  }, []);

  const stopVmSpeaking = useCallback(() => {
    if (vmMediaRecorderRef.current?.state === 'recording') vmMediaRecorderRef.current.stop();
    stopVmStream();
    setIsVoiceRecording(false);
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'audio_end' }));
  }, [stopVmStream]);

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

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 105px)' }}>

      {/* ── Realtime voice-mode fullscreen overlay ──────────────────────── */}
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
            onTouchStart={(e) => { e.preventDefault(); startVmSpeaking(); }}
            onTouchEnd={(e) => { e.preventDefault(); stopVmSpeaking(); }}
            disabled={voiceState === 'thinking' || voiceState === 'speaking'}
            className={`w-28 h-28 rounded-full flex items-center justify-center text-5xl shadow-2xl transition-all
              ${isVoiceRecording ? 'bg-red-600 scale-110 ring-4 ring-red-400' : 'bg-blue-600 hover:bg-blue-500'}
              disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            🎤
          </button>
          <p className="text-gray-500 text-sm mt-3">
            {isVoiceRecording ? 'Loslassen zum Senden' : 'Halten zum Sprechen'}
          </p>

          {/* Voice error */}
          {voiceError && (
            <div className="mt-4 px-4 py-2 bg-red-900 text-red-200 rounded-lg text-sm max-w-sm text-center">
              ⚠️ {voiceError}
              <button onClick={() => setVoiceError(null)} className="ml-2 text-red-300 hover:text-white">✕</button>
            </div>
          )}

          {/* Last messages preview */}
          <div className="mt-8 w-full max-w-lg space-y-2 px-4 max-h-40 overflow-y-auto">
            {messages.slice(-4).map((m) => (
              <div key={m.id}
                className={`text-sm rounded px-3 py-1 ${
                  m.role === 'user' ? 'bg-blue-900 text-blue-100 text-right' : 'bg-gray-800 text-gray-200 text-left'
                }`}>
                {m.content.substring(0, 120)}{m.content.length > 120 ? '…' : ''}
              </div>
            ))}
          </div>

          {/* Exit button */}
          <button
            onClick={() => setVoiceMode(false)}
            className="mt-8 px-8 py-3 bg-gray-700 text-white rounded-full hover:bg-gray-600 text-sm font-medium"
          >
            ✕ Sprachmodus beenden
          </button>
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
              {SUGGESTIONS.map((s) => (
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
        {messages.map((msg) => (
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
                {[0, 150, 300].map((d) => (
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

      {/* ── TTS auto-speak toggle ─────────────────────────────────────────── */}
      <div className="fixed bottom-[5.5rem] right-4 z-50">
        <button
          onClick={() => setAutoSpeak((v) => !v)}
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
