import { useState, useRef, useEffect, useCallback } from 'react';
import ChatComposer from '../components/ChatComposer';
import { agentChat, ttsGenerate } from '../lib/apiClient';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  audioUrl?: string;
}

// Stable session ID for the page lifetime
const SESSION_ID = `chat-${Date.now()}`;

const SUGGESTIONS = [
  'Was ist heute auf meinem Kalender?',
  'Zeige meine letzten E-Mails',
  'Erstelle einen Termin für morgen 10 Uhr',
  'Schreibe eine E-Mail an meinen Chef',
];

function makeId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoSpeak, setAutoSpeak] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Auto-scroll on new messages / loading changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const playAudio = (url: string) => {
    audioRef.current?.pause();
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.play().catch(() => {});
  };

  const handleSend = useCallback(
    async (text: string) => {
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
          {
            id: makeId(),
            role: 'assistant',
            content: `❌ ${msg}`,
            timestamp: new Date(),
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [autoSpeak],
  );

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 105px)' }}>
      {/* ── Message list ─────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-36">
        {/* Empty-state with suggestions */}
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-5xl mb-3 select-none">🤖</div>
            <p className="text-lg font-semibold text-gray-700">OrganAIzer Executive Agent</p>
            <p className="text-sm text-gray-400 mt-1">Stell eine Frage oder wähle einen Vorschlag</p>
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-sm w-full">
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
          <div
            key={msg.id}
            className={`flex mb-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {/* Avatar – assistant */}
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center
                              mr-2 flex-shrink-0 mt-0.5 text-sm select-none">
                🤖
              </div>
            )}

            <div className="max-w-[75%] min-w-0">
              {/* Bubble */}
              <div
                className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-md'
                    : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-md'
                }`}
              >
                {msg.content}
              </div>

              {/* Timestamp + play button */}
              <div className="flex items-center gap-2 mt-1 px-1">
                <span className="text-xs text-gray-400">
                  {msg.timestamp.toLocaleTimeString('de-DE', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
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

            {/* Avatar – user */}
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
                            mr-2 flex-shrink-0 text-sm select-none">
              🤖
            </div>
            <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1.5 items-center">
                {[0, 150, 300].map((delay) => (
                  <span
                    key={delay}
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: `${delay}ms` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Error toast ──────────────────────────────────────────────────── */}
      {error && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-50
                        bg-red-50 border border-red-300 text-red-700 text-sm
                        px-4 py-2 rounded-lg shadow-md flex items-center gap-2 max-w-sm">
          <span>⚠️ {error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-auto text-red-400 hover:text-red-600"
          >
            ✕
          </button>
        </div>
      )}

      {/* ── TTS auto-speak toggle ─────────────────────────────────────────── */}
      <div className="fixed bottom-[5.5rem] right-4 z-50">
        <button
          onClick={() => setAutoSpeak((v) => !v)}
          className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full shadow transition-colors ${
            autoSpeak
              ? 'bg-indigo-600 text-white'
              : 'bg-white text-gray-500 border border-gray-200 hover:border-gray-300'
          }`}
          title={autoSpeak ? 'TTS deaktivieren' : 'Antworten automatisch vorlesen'}
        >
          🔊 {autoSpeak ? 'TTS an' : 'TTS aus'}
        </button>
      </div>

      {/* ── Floating composer ────────────────────────────────────────────── */}
      <ChatComposer onSend={handleSend} disabled={loading} />
    </div>
  );
}
