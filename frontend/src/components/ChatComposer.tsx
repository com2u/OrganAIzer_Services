import { useRef, useState, useCallback } from 'react';
import { sttTranscribe } from '../lib/apiClient';

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  onVoiceMode?: () => void;
}

export default function ChatComposer({ onSend, disabled = false, onVoiceMode }: Props) {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const canSend = input.trim().length > 0 && !disabled && !isRecording && !isTranscribing;

  const handleSend = () => {
    if (!canSend) return;
    onSend(input.trim());
    setInput('');
  };

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const toggleMic = useCallback(async () => {
    setMicError(null);

    if (isRecording) {
      // Stop → triggers onstop handler
      mediaRecorderRef.current?.stop();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;
      chunksRef.current = [];

      // Detect the best supported MIME type at call-time.
      // Hardcoding 'audio/webm' throws a DOMException on Safari (unsupported).
      const mimeCandidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
      const chosenMime = mimeCandidates.find(
        t => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)
      ) ?? '';
      const mr = new MediaRecorder(stream, chosenMime ? { mimeType: chosenMime } : {});
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = async () => {
        setIsRecording(false);
        stopStream();
        if (chunksRef.current.length === 0) return;

        setIsTranscribing(true);
        try {
          const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
          const text = await sttTranscribe(blob);
          if (text.trim()) setInput(text.trim());
        } catch {
          setMicError('Transkription fehlgeschlagen');
        } finally {
          setIsTranscribing(false);
        }
      };

      mr.start();
      setIsRecording(true);
    } catch {
      setMicError('Mikrofon-Zugriff verweigert');
    }
  }, [isRecording, stopStream]);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 pointer-events-none">
      {/* Fade-out gradient so the message list text fades under the bar */}
      <div className="h-10 bg-gradient-to-t from-gray-100 to-transparent" />

      <div className="bg-gray-100 px-4 pb-5 pt-1 pointer-events-auto">
        <div className="max-w-3xl mx-auto space-y-2">
          {/* Status strip */}
          {(isRecording || isTranscribing || micError) && (
            <div className="flex justify-center">
              <div
                className={`flex items-center gap-2 text-xs px-3 py-1 rounded-full shadow-sm border ${
                  micError
                    ? 'bg-red-50 border-red-200 text-red-700'
                    : isRecording
                    ? 'bg-red-50 border-red-200 text-red-700'
                    : 'bg-blue-50 border-blue-200 text-blue-700'
                }`}
              >
                {micError ? (
                  <>⚠️ {micError}<button onClick={() => setMicError(null)} className="ml-1 opacity-60 hover:opacity-100">✕</button></>
                ) : isRecording ? (
                  <>
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse inline-block" />
                    Aufnahme läuft… nochmal tippen zum Stoppen
                  </>
                ) : (
                  <>
                    <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse inline-block" />
                    Transkribiere…
                  </>
                )}
              </div>
            </div>
          )}

          {/* Pill composer bar */}
          <div className="flex items-center gap-2 bg-white rounded-2xl shadow-md border border-gray-200 px-3 py-2.5">
            {/* + attachment button */}
            <button
              type="button"
              title="Anhang hinzufügen (demnächst)"
              className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                         text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
            </button>

            {/* Text input */}
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={
                isRecording
                  ? '🔴 Aufnahme läuft…'
                  : isTranscribing
                  ? 'Transkribiere…'
                  : 'Stelle irgendeine Frage'
              }
              disabled={disabled || isRecording || isTranscribing}
              className="flex-1 min-w-0 bg-transparent text-gray-800 placeholder-gray-400
                         text-sm leading-tight outline-none disabled:opacity-50"
              autoComplete="off"
            />

            {/* Send button — only shown when there is input */}
            <button
              type="button"
              onClick={handleSend}
              disabled={!canSend}
              title="Senden (Enter)"
              className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                canSend
                  ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm'
                  : 'hidden'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-7-7 7 7-7 7" />
              </svg>
            </button>

            {/* Mic button */}
            <button
              type="button"
              onClick={toggleMic}
              disabled={disabled || isTranscribing}
              title={isRecording ? 'Aufnahme stoppen' : 'Spracheingabe starten'}
              className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                          transition-colors disabled:opacity-40 ${
                isRecording
                  ? 'bg-red-500 text-white'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
              }`}
            >
              {isRecording ? (
                /* Stop square icon while recording */
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <rect x="5" y="5" width="10" height="10" rx="1" />
                </svg>
              ) : (
                /* Mic icon */
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round"
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4
                       m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              )}
            </button>

            {/* Voice-mode button */}
            <button
              type="button"
              onClick={onVoiceMode}
              title="Echtzeit-Sprachmodus"
              className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                         text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round"
                  d="M15.536 8.464a5 5 0 010 7.072
                     m2.828-9.9a9 9 0 010 12.728
                     M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586
                     l4.707-4.707C10.923 3.663 12 4.109 12 5v14
                     c0 .891-1.077 1.337-1.707.707L5.586 15z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
