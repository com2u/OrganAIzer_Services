import { useState, useEffect, useRef, useCallback } from 'react';

// AudioWorklet processor source — downsamples mic (browser rate → 8 kHz int16)
// and upsamples received SIP audio (8 kHz int16 → browser rate float32).
const PHONE_WORKLET_SRC = `
class PhoneProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._ratio = 6;
    this._capBuf = [];
    this._capTarget = Math.round(6 * 160);
    this._playBuf = [];
    this.port.onmessage = (e) => {
      if (e.data.type === 'config') {
        this._ratio = e.data.sampleRate / 8000;
        this._capTarget = Math.round(this._ratio * 160);
      } else if (e.data.type === 'audio') {
        const view = new DataView(e.data.buffer);
        const n = e.data.buffer.byteLength / 2;
        const ratio = Math.round(this._ratio);
        for (let i = 0; i < n; i++) {
          const s = view.getInt16(i * 2, true) / 32768.0;
          for (let j = 0; j < ratio; j++) this._playBuf.push(s);
        }
      }
    };
  }
  process(inputs, outputs) {
    const inp = inputs[0]?.[0];
    const out = outputs[0]?.[0];
    if (inp) {
      for (let i = 0; i < inp.length; i++) this._capBuf.push(inp[i]);
      if (this._capBuf.length >= this._capTarget) {
        const pcm = new Int16Array(160);
        for (let i = 0; i < 160; i++) {
          const si = Math.min(Math.round(i * this._ratio), this._capBuf.length - 1);
          pcm[i] = Math.max(-32768, Math.min(32767, Math.round(this._capBuf[si] * 32768)));
        }
        this.port.postMessage({ type: 'capture', buf: pcm.buffer }, [pcm.buffer]);
        this._capBuf.splice(0, this._capTarget);
      }
    }
    if (out) {
      for (let i = 0; i < out.length; i++)
        out[i] = i < this._playBuf.length ? this._playBuf[i] : 0;
      this._playBuf.splice(0, Math.min(out.length, this._playBuf.length));
    }
    return true;
  }
}
registerProcessor('phone-processor', PhoneProcessor);
`;

interface ActiveCall {
  caller: string;
  caller_name?: string;
  started_at: string;
  mode: 'ai' | 'human';
}

interface RingingCall {
  caller: string;
  caller_name?: string;
  ringing_since: string;
  direction: 'inbound' | 'outbound';
}

interface PhoneStatus {
  registered: boolean;
  extension: string;
  server: string;
  active_call: ActiveCall | null;
  ringing_call: RingingCall | null;
}

interface Contact {
  name: string;
  number: string;
  status: string;
}

interface CallLogEntry {
  ts: string;
  direction: 'inbound' | 'outbound';
  caller: string;
  caller_name: string;
  started_at: string;
  duration_seconds: number;
  turn_count: number;
  summary: string;
}

const API_KEY      = (import.meta.env.VITE_API_KEY      as string) ?? '';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) ?? '';

function useCallDuration(startedAt: string | null): string {
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (!startedAt) return;
    const start = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    intervalRef.current = setInterval(tick, 1000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [startedAt]);

  const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
  const s = (elapsed % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function PhonePage() {
  const [status, setStatus]       = useState<PhoneStatus | null>(null);
  const [contacts, setContacts]   = useState<Contact[]>([]);
  const [search, setSearch]       = useState('');
  const [dialNumber, setDialNumber] = useState('');
  const [dialError, setDialError] = useState<string | null>(null);
  const [dialing, setDialing]     = useState(false);
  const [whisper, setWhisper]       = useState('');
  const [whisperSent, setWhisperSent] = useState(false);
  const [ringDeciding, setRingDeciding] = useState(false);
  const [talking, setTalking]       = useState(false);
  const [talkError, setTalkError]   = useState<string | null>(null);
  const [hangingUp, setHangingUp]   = useState(false);
  const [callLog, setCallLog]       = useState<CallLogEntry[]>([]);
  const pollRef    = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletRef  = useRef<AudioWorkletNode | null>(null);
  const wsAudioRef  = useRef<WebSocket | null>(null);

  const duration = useCallDuration(
    status?.active_call?.started_at ?? null
  );

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/phone/status`, {
        headers: { 'X-API-Key': API_KEY },
      });
      if (res.ok) setStatus(await res.json());
    } catch {
      // silently ignore — offline state is shown via status===null
    }
  };

  const fetchContacts = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/phone/contacts`, {
        headers: { 'X-API-Key': API_KEY },
      });
      if (res.ok) setContacts(await res.json());
    } catch {
      setContacts([]);
    }
  };

  const fetchCallLog = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/phone/log`, {
        headers: { 'X-API-Key': API_KEY },
      });
      if (res.ok) setCallLog(await res.json());
    } catch {
      // silently ignore
    }
  };

  const handleHangup = async () => {
    setHangingUp(true);
    try {
      await fetch(`${API_BASE_URL}/api/phone/hangup`, {
        method: 'POST',
        headers: { 'X-API-Key': API_KEY },
      });
      await fetchStatus();
    } catch {
      // ignore
    } finally {
      setHangingUp(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchContacts();
    fetchCallLog();
    pollRef.current = setInterval(fetchStatus, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleDial = async (number: string) => {
    if (!number.trim()) return;
    setDialing(true);
    setDialError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/phone/dial`, {
        method: 'POST',
        headers: { 'X-API-Key': API_KEY, 'Content-Type': 'application/json' },
        body: JSON.stringify({ number: number.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setDialError(data?.detail?.message ?? `Error ${res.status}`);
      }
    } catch {
      setDialError('Could not reach the backend.');
    } finally {
      setDialing(false);
    }
  };

  const stopTalking = useCallback(() => {
    wsAudioRef.current?.close();
    wsAudioRef.current = null;
    workletRef.current?.disconnect();
    workletRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    setTalking(false);
  }, []);

  // Stop audio bridge + refresh call log when call ends
  const prevActiveRef = useRef<boolean>(false);
  useEffect(() => {
    const isActive = !!status?.active_call;
    if (!isActive && talking) stopTalking();
    if (!isActive && prevActiveRef.current) fetchCallLog();
    prevActiveRef.current = isActive;
  }, [status?.active_call, talking, stopTalking]);

  const startTalking = async () => {
    setTalkError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;

      // Register worklet from inline source via Blob URL
      const blob = new Blob([PHONE_WORKLET_SRC], { type: 'application/javascript' });
      const blobUrl = URL.createObjectURL(blob);
      await ctx.audioWorklet.addModule(blobUrl);
      URL.revokeObjectURL(blobUrl);

      const worklet = new AudioWorkletNode(ctx, 'phone-processor', {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [1],
      });
      workletRef.current = worklet;
      worklet.port.postMessage({ type: 'config', sampleRate: ctx.sampleRate });

      // mic → worklet → speakers
      ctx.createMediaStreamSource(stream).connect(worklet);
      worklet.connect(ctx.destination);

      // WebSocket audio bridge
      const wsBase = API_BASE_URL.replace(/^http/, 'ws');
      const ws = new WebSocket(`${wsBase}/api/phone/call-audio`);
      wsAudioRef.current = ws;
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => setTalking(true);
      ws.onclose = () => stopTalking();
      ws.onerror = () => { setTalkError('Audio connection failed.'); stopTalking(); };

      // SIP → browser: feed received PCM to worklet playback buffer
      ws.onmessage = (e: MessageEvent) => {
        worklet.port.postMessage({ type: 'audio', buffer: e.data }, [e.data as ArrayBuffer]);
      };

      // browser → SIP: send captured PCM over WebSocket
      worklet.port.onmessage = (e: MessageEvent) => {
        if (e.data.type === 'capture' && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data.buf as ArrayBuffer);
        }
      };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setTalkError(`Microphone error: ${msg}`);
      stopTalking();
    }
  };

  const handleRingDecision = async (decision: 'ai' | 'human') => {
    setRingDeciding(true);
    try {
      await fetch(`${API_BASE_URL}/api/phone/ring/${decision}`, {
        method: 'POST',
        headers: { 'X-API-Key': API_KEY },
      });
      await fetchStatus();
    } catch {
      // ignore
    } finally {
      setRingDeciding(false);
    }
  };

  const handleWhisper = async () => {
    if (!whisper.trim()) return;
    try {
      await fetch(`${API_BASE_URL}/api/phone/whisper`, {
        method: 'POST',
        headers: { 'X-API-Key': API_KEY, 'Content-Type': 'application/json' },
        body: JSON.stringify({ instruction: whisper.trim() }),
      });
      setWhisper('');
      setWhisperSent(true);
      setTimeout(() => setWhisperSent(false), 2000);
    } catch {
      // silently ignore
    }
  };

  const filteredContacts = contacts.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.number.includes(search)
  );

  const registered = status?.registered ?? false;

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto space-y-6">

        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-1">📞 AI Phone</h1>
              <p className="text-gray-600 text-sm">
                AI-powered voice calling via COMtrexx PBX
              </p>
            </div>
            {/* Registration pill */}
            <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${
              registered
                ? 'bg-green-100 text-green-800'
                : 'bg-gray-100 text-gray-600'
            }`}>
              <span className={`w-2 h-2 rounded-full ${registered ? 'bg-green-500' : 'bg-gray-400'}`} />
              {registered
                ? `Registered — ext. ${status?.extension}`
                : 'Offline — SIP not connected'}
            </span>
          </div>
          {registered && status?.server && (
            <p className="mt-2 text-xs text-gray-400">Server: {status.server}</p>
          )}
          {!registered && (
            <p className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              Set <code className="font-mono">COMTREXX_SIP_USER</code>,{' '}
              <code className="font-mono">COMTREXX_SIP_PASS</code>, and{' '}
              <code className="font-mono">COMTREXX_EXTENSION</code> in{' '}
              <code className="font-mono">backend/.env</code> to activate.
            </p>
          )}
        </div>

        {/* Ringing / decision card */}
        {status?.ringing_call && !status?.active_call && (
          <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-5 animate-pulse-subtle">
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-yellow-700 mb-1">
                  {status.ringing_call.direction === 'inbound' ? '📲 Incoming call' : '📞 Call answered'}
                </p>
                <p className="text-xl font-bold text-yellow-900">
                  {status.ringing_call.caller_name || status.ringing_call.caller}
                </p>
                {status.ringing_call.caller_name && (
                  <p className="text-sm text-yellow-700 font-mono">{status.ringing_call.caller}</p>
                )}
                <p className="text-xs text-yellow-600 mt-1">
                  {status.ringing_call.direction === 'inbound'
                    ? 'Who should answer?'
                    : 'The other person picked up — who handles it?'}
                </p>
              </div>
              <span className="text-3xl">{status.ringing_call.direction === 'inbound' ? '🔔' : '📡'}</span>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => handleRingDecision('ai')}
                disabled={ringDeciding}
                className="flex-1 py-2.5 bg-green-600 text-white rounded-lg font-medium text-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 transition-colors"
              >
                AI answers
              </button>
              <button
                onClick={() => handleRingDecision('human')}
                disabled={ringDeciding}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-medium text-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 transition-colors"
              >
                I'll take it
              </button>
            </div>
          </div>
        )}

        {/* Active call card */}
        {status?.active_call && (
          <div className="bg-green-50 border border-green-300 rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-green-700 mb-1">
                  Active call · {status.active_call.mode === 'ai' ? 'AI handling' : 'You are live'}
                </p>
                <p className="text-xl font-bold text-green-900">
                  {status.active_call.caller_name || status.active_call.caller}
                </p>
                {status.active_call.caller_name && (
                  <p className="text-sm text-green-700">{status.active_call.caller}</p>
                )}
              </div>
              <div className="text-right space-y-2">
                <p className="text-3xl font-mono font-bold text-green-800">{duration}</p>
                <button
                  onClick={handleHangup}
                  disabled={hangingUp}
                  className="block w-full px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-medium hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50 transition-colors"
                >
                  {hangingUp ? 'Hanging up…' : '📵 Hang up'}
                </button>
              </div>
            </div>

            {/* Talk button — only when operator is bridged in */}
            {status.active_call.mode === 'human' && (
              <div className="border-t border-green-200 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-green-700 mb-2">
                  Your microphone
                </p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={talking ? stopTalking : startTalking}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm focus:outline-none focus:ring-2 transition-colors ${
                      talking
                        ? 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500 animate-pulse'
                        : 'bg-green-700 text-white hover:bg-green-800 focus:ring-green-500'
                    }`}
                  >
                    <span>{talking ? '🔴' : '🎙'}</span>
                    {talking ? 'Stop talking' : 'Talk'}
                  </button>
                  {talking && (
                    <span className="text-xs text-green-700">Live — caller can hear you</span>
                  )}
                  {talkError && (
                    <span className="text-xs text-red-600">{talkError}</span>
                  )}
                </div>
              </div>
            )}

            {/* Operator whisper — only when AI is on the call */}
            {status.active_call.mode === 'ai' && <div className="border-t border-green-200 pt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-green-700 mb-2">
                Whisper to AI
              </p>
              <p className="text-xs text-green-600 mb-2">
                Type an instruction — the AI will follow it on the next reply. The caller won't hear this.
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. Focus on the calendar feature now"
                  value={whisper}
                  onChange={e => setWhisper(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleWhisper()}
                  className="flex-1 border border-green-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 bg-white focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
                />
                <button
                  onClick={handleWhisper}
                  disabled={!whisper.trim()}
                  className="px-4 py-2 bg-green-700 text-white rounded-lg text-sm font-medium hover:bg-green-800 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {whisperSent ? 'Sent ✓' : 'Send'}
                </button>
              </div>
            </div>}
          </div>
        )}

        {/* Dial pad */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Dial</h2>
          <div className="flex gap-3">
            <input
              type="tel"
              placeholder="+49 xxx xxxxxxx"
              value={dialNumber}
              onChange={e => { setDialNumber(e.target.value); setDialError(null); }}
              onKeyDown={e => e.key === 'Enter' && handleDial(dialNumber)}
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
            <button
              onClick={() => handleDial(dialNumber)}
              disabled={dialing || !dialNumber.trim()}
              className="px-6 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {dialing ? 'Calling…' : 'Call'}
            </button>
          </div>
          {dialError && (
            <p className="mt-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              {dialError}
            </p>
          )}
        </div>

        {/* Contacts */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-800">
              Contacts
              {contacts.length > 0 && (
                <span className="ml-2 text-sm font-normal text-gray-500">
                  ({contacts.length})
                </span>
              )}
            </h2>
            <button
              onClick={fetchContacts}
              className="text-xs text-gray-500 hover:text-gray-700 underline"
            >
              Reload
            </button>
          </div>

          {contacts.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-6">
              No contacts loaded.{' '}
              <span className="text-gray-400">
                Place <code className="font-mono">AI_Phone_Contacts.xlsx</code> in the{' '}
                <code className="font-mono">backend/</code> folder and click Reload.
              </span>
            </p>
          ) : (
            <>
              <input
                type="text"
                placeholder="Search by name or number…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full mb-4 border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
              />
              <div className="divide-y divide-gray-100">
                {filteredContacts.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-4">No matches.</p>
                ) : (
                  filteredContacts.map((c, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between py-3 group"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {c.name || <span className="text-gray-400 italic">No name</span>}
                        </p>
                        <p className="text-xs text-gray-500 font-mono">{c.number}</p>
                        {c.status && (
                          <p className="text-xs text-gray-400 mt-0.5">{c.status}</p>
                        )}
                      </div>
                      <button
                        onClick={() => { setDialNumber(c.number); setDialError(null); }}
                        className="ml-4 flex-shrink-0 text-xs text-green-600 border border-green-200 rounded px-2.5 py-1 opacity-0 group-hover:opacity-100 hover:bg-green-50 transition-all"
                      >
                        Dial
                      </button>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        {/* Call log */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-800">Recent calls</h2>
            <button
              onClick={fetchCallLog}
              className="text-xs text-gray-500 hover:text-gray-700 underline"
            >
              Reload
            </button>
          </div>
          {callLog.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">No calls recorded yet.</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {callLog.map((entry, i) => {
                const mins = Math.floor(entry.duration_seconds / 60);
                const secs = (entry.duration_seconds % 60).toString().padStart(2, '0');
                const dur  = mins > 0 ? `${mins}m ${secs}s` : `${entry.duration_seconds}s`;
                const when = new Date(entry.ts).toLocaleString();
                return (
                  <div key={i} className="py-3 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-gray-400">
                          {entry.direction === 'inbound' ? '↙' : '↗'}
                        </span>
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {entry.caller_name || entry.caller}
                        </p>
                        {entry.caller_name && (
                          <p className="text-xs text-gray-400 font-mono hidden sm:block">{entry.caller}</p>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">{when}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-sm font-mono text-gray-600">{dur}</p>
                      <p className="text-xs text-gray-400">{entry.turn_count} turns</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
