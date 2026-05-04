import { useState, useEffect, useRef, useCallback } from 'react';

const API_KEY      = (import.meta.env.VITE_API_KEY      as string) ?? '';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) ?? '';

// ── types ─────────────────────────────────────────────────────────────────────

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

interface EscalationAlert {
  caller: string;
  caller_name?: string;
  reason: string;
  summary: string;
  email_sent: boolean;
  at: string;
}

interface PhoneStatus {
  registered: boolean;
  extension: string;
  server: string;
  active_call: ActiveCall | null;
  ringing_call: RingingCall | null;
  last_escalation: EscalationAlert | null;
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

interface CallMessageOption {
  display_name?: string;
  masked_number?: string;
}

interface CallMessageResponse {
  action?: 'confirm_prompt' | 'calling' | 'cancelled' | 'error' | 'clarification_needed' | 'none' | string;
  message?: string;
  options?: CallMessageOption[];
}

// ── audio worklet source (inline blob) ───────────────────────────────────────
// Downsamples mic audio (browser rate → 8 kHz int16) for the SIP side,
// and upsamples received 8 kHz int16 back to browser rate for playback.
const WORKLET_SRC = `
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

// ── helpers ───────────────────────────────────────────────────────────────────

// The backend may return `caller` as a plain string OR as a parsed SIP address
// object {raw, tag, address, number, caller, host}. Extract a display string.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function callerStr(v: any): string {
  if (!v) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'object')
    return v.number || v.caller || v.address || v.raw || JSON.stringify(v);
  return String(v);
}

// ── call duration hook ────────────────────────────────────────────────────────

function useCallDuration(startedAt: string | null): string {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (!startedAt) { setElapsed(0); return; }
    const origin = new Date(startedAt).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - origin) / 1000));
    tick();
    timerRef.current = setInterval(tick, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [startedAt]);

  const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
  const s = (elapsed % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

// ── component ─────────────────────────────────────────────────────────────────

export default function PhonePage() {
  const [status,   setStatus]   = useState<PhoneStatus | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [callLog,  setCallLog]  = useState<CallLogEntry[]>([]);
  const [search,   setSearch]   = useState('');
  const [dialNum,  setDialNum]  = useState('');
  const [dialErr,  setDialErr]  = useState<string | null>(null);
  const [dialing,  setDialing]  = useState(false);
  const [callRequest, setCallRequest] = useState('');
  const [callFlowMsg, setCallFlowMsg] = useState<string | null>(null);
  const [callFlowAction, setCallFlowAction] = useState<string | null>(null);
  const [callFlowOptions, setCallFlowOptions] = useState<CallMessageOption[]>([]);
  const [callFlowLoading, setCallFlowLoading] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [hangingUp, setHangingUp] = useState(false);
  const [whisper,  setWhisper]  = useState('');
  const [whisperOk, setWhisperOk] = useState(false);
  const [talking,  setTalking]  = useState(false);
  const [talkErr,  setTalkErr]  = useState<string | null>(null);

  const pollRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const ctxRef      = useRef<AudioContext | null>(null);
  const workletRef  = useRef<AudioWorkletNode | null>(null);
  const wsRef       = useRef<WebSocket | null>(null);
  const prevActive  = useRef(false);

  const duration = useCallDuration(
    status?.active_call?.started_at
      ? String(status.active_call.started_at)
      : null
  );

  // ── API helpers ──────────────────────────────────────────────────────────────

  const headers = () => ({ 'X-API-Key': API_KEY });
  const jsonHeaders = () => ({ 'X-API-Key': API_KEY, 'Content-Type': 'application/json' });

  const loadStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE_URL}/api/phone/status`, { headers: headers() });
      if (r.ok) setStatus(await r.json());
    } catch { /* offline */ }
  }, []);

  const loadContacts = async () => {
    try {
      const r = await fetch(`${API_BASE_URL}/api/phone/contacts`, { headers: headers() });
      if (r.ok) setContacts(await r.json());
    } catch { setContacts([]); }
  };

  const loadCallLog = async () => {
    try {
      const r = await fetch(`${API_BASE_URL}/api/phone/log`, { headers: headers() });
      if (r.ok) setCallLog(await r.json());
    } catch { /* ignore */ }
  };

  // ── lifecycle ────────────────────────────────────────────────────────────────

  useEffect(() => {
    loadStatus();
    loadContacts();
    loadCallLog();
    pollRef.current = setInterval(loadStatus, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [loadStatus]);

  // Refresh call log and stop audio bridge when active call ends
  useEffect(() => {
    const isActive = !!status?.active_call;
    if (!isActive && talking) stopTalking();
    if (!isActive && prevActive.current) loadCallLog();
    prevActive.current = isActive;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.active_call]);

  // ── dial ─────────────────────────────────────────────────────────────────────

  const handleDial = async (number: string) => {
    const n = number.trim();
    if (!n) return;
    setDialing(true);
    setDialErr(null);
    try {
      const r = await fetch(`${API_BASE_URL}/api/phone/dial`, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({ number: n }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        setDialErr(d?.detail?.message ?? `Error ${r.status}`);
      }
    } catch {
      setDialErr('Could not reach the backend.');
    } finally {
      setDialing(false);
    }
  };

  // ── ring decision ────────────────────────────────────────────────────────────

  const handleCallMessage = async (message: string) => {
    const text = message.trim();
    if (!text) return;

    setCallFlowLoading(true);
    setCallFlowMsg(null);
    setCallFlowOptions([]);

    try {
      const r = await fetch(`${API_BASE_URL}/api/phone/message`, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({ message: text, session_id: 'phone_page' }),
      });
      const data = await r.json().catch(() => ({}));

      if (!r.ok) {
        setCallFlowAction('error');
        setCallFlowMsg(
          r.status === 409
            ? data?.detail?.message ?? 'A call is already active.'
            : data?.detail?.message ?? `Error ${r.status}`
        );
        return;
      }

      const result = data as CallMessageResponse;
      const action = result.action ?? 'none';
      setCallFlowAction(action);
      setCallFlowOptions(result.options ?? []);

      if (action === 'none') {
        setCallFlowMsg('No call request detected');
      } else {
        setCallFlowMsg(result.message ?? '');
      }

      if (action === 'calling') {
        setCallRequest('');
        setCallFlowOptions([]);
        await loadStatus();
      }
    } catch {
      setCallFlowAction('error');
      setCallFlowMsg('Could not reach the backend.');
    } finally {
      setCallFlowLoading(false);
    }
  };

  const handleRingDecision = async (decision: 'ai' | 'human') => {
    setDeciding(true);
    try {
      await fetch(`${API_BASE_URL}/api/phone/ring/${decision}`, {
        method: 'POST',
        headers: headers(),
      });
      await loadStatus();
    } catch { /* ignore */ } finally {
      setDeciding(false);
    }
  };

  // ── hang up ──────────────────────────────────────────────────────────────────

  const handleHangup = async () => {
    setHangingUp(true);
    try {
      await fetch(`${API_BASE_URL}/api/phone/hangup`, {
        method: 'POST',
        headers: headers(),
      });
      await loadStatus();
    } catch { /* ignore */ } finally {
      setHangingUp(false);
    }
  };

  // ── whisper ──────────────────────────────────────────────────────────────────

  const handleWhisper = async () => {
    if (!whisper.trim()) return;
    try {
      await fetch(`${API_BASE_URL}/api/phone/whisper`, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({ instruction: whisper.trim() }),
      });
      setWhisper('');
      setWhisperOk(true);
      setTimeout(() => setWhisperOk(false), 2000);
    } catch { /* ignore */ }
  };

  // ── escalation dismiss ───────────────────────────────────────────────────────

  const dismissEscalation = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/phone/escalation/dismiss`, {
        method: 'POST',
        headers: headers(),
      });
      await loadStatus();
    } catch { /* ignore */ }
  };

  // ── audio bridge ─────────────────────────────────────────────────────────────

  const stopTalking = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    workletRef.current?.disconnect();
    workletRef.current = null;
    ctxRef.current?.close();
    ctxRef.current = null;
    setTalking(false);
  }, []);

  const startTalking = async () => {
    setTalkErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const ctx = new AudioContext();
      ctxRef.current = ctx;

      const blob = new Blob([WORKLET_SRC], { type: 'application/javascript' });
      const url  = URL.createObjectURL(blob);
      await ctx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);

      const worklet = new AudioWorkletNode(ctx, 'phone-processor', {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        outputChannelCount: [1],
      });
      workletRef.current = worklet;
      worklet.port.postMessage({ type: 'config', sampleRate: ctx.sampleRate });

      ctx.createMediaStreamSource(stream).connect(worklet);
      worklet.connect(ctx.destination);

      const wsBase = API_BASE_URL.replace(/^http/, 'ws');
      const ws = new WebSocket(`${wsBase}/api/phone/call-audio`);
      wsRef.current = ws;
      ws.binaryType = 'arraybuffer';

      ws.onopen  = () => setTalking(true);
      ws.onclose = () => stopTalking();
      ws.onerror = () => { setTalkErr('Audio connection failed.'); stopTalking(); };

      ws.onmessage = (e: MessageEvent) => {
        worklet.port.postMessage({ type: 'audio', buffer: e.data }, [e.data as ArrayBuffer]);
      };

      worklet.port.onmessage = (e: MessageEvent) => {
        if (e.data.type === 'capture' && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data.buf as ArrayBuffer);
        }
      };
    } catch (err: unknown) {
      setTalkErr(`Microphone error: ${err instanceof Error ? err.message : String(err)}`);
      stopTalking();
    }
  };

  // ── derived ───────────────────────────────────────────────────────────────────

  const registered = status?.registered ?? false;
  const filtered   = contacts.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) || c.number.includes(search)
  );

  // ── render ────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto space-y-6">

        {/* ── Header / registration status ── */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Phone</h1>
              <p className="text-sm text-gray-500 mt-0.5">AI-powered voice calling via COMtrexx PBX</p>
            </div>
            <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
              registered ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'
            }`}>
              <span className={`w-2 h-2 rounded-full ${registered ? 'bg-green-500' : 'bg-gray-400'}`} />
              {registered ? `Registered — ext. ${status?.extension}` : 'Offline — SIP not connected'}
            </span>
          </div>
          {registered && status?.server && (
            <p className="mt-2 text-xs text-gray-400">Server: {status.server}</p>
          )}
          {!registered && (
            <p className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              Set <code className="font-mono">COMTREXX_SIP_USER</code>,{' '}
              <code className="font-mono">COMTREXX_SIP_PASS</code> and{' '}
              <code className="font-mono">COMTREXX_EXTENSION</code> in{' '}
              <code className="font-mono">backend/.env</code> to activate.
            </p>
          )}
        </div>

        {/* ── Escalation alert ── */}
        {status?.last_escalation && (
          <div className="bg-red-50 border-2 border-red-400 rounded-lg p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-red-700 mb-1">
                  Caller requested a human
                </p>
                <p className="text-lg font-bold text-red-900">
                  {callerStr(status.last_escalation.caller_name) || callerStr(status.last_escalation.caller)}
                  {status.last_escalation.caller_name && (
                    <span className="ml-2 text-sm font-mono font-normal text-red-700">
                      {callerStr(status.last_escalation.caller)}
                    </span>
                  )}
                </p>
                {status.last_escalation.reason && (
                  <p className="text-sm text-red-800 mt-1">
                    <span className="font-medium">Reason:</span> {status.last_escalation.reason}
                  </p>
                )}
                {status.last_escalation.summary && (
                  <p className="text-sm text-red-700 mt-2 italic">
                    {status.last_escalation.summary}
                  </p>
                )}
                <div className="flex items-center gap-4 mt-3 text-xs text-red-600">
                  <span>{new Date(status.last_escalation.at).toLocaleTimeString()}</span>
                  <span>
                    {status.last_escalation.email_sent
                      ? '✓ Escalation email sent'
                      : '⚠ Email not sent — check SMTP / Gmail config'}
                  </span>
                </div>
              </div>
              <button
                onClick={dismissEscalation}
                className="flex-shrink-0 px-3 py-1.5 bg-red-700 text-white rounded-lg text-xs font-medium hover:bg-red-800 transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* ── Ringing card ── */}
        {status?.ringing_call && !status?.active_call && (
          <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-5">
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-yellow-700 mb-1">
                  {status.ringing_call.direction === 'inbound' ? 'Incoming call' : 'Outbound — answered'}
                </p>
                <p className="text-xl font-bold text-yellow-900">
                  {callerStr(status.ringing_call.caller_name) || callerStr(status.ringing_call.caller)}
                </p>
                {status.ringing_call.caller_name && (
                  <p className="text-sm font-mono text-yellow-700">{callerStr(status.ringing_call.caller)}</p>
                )}
              </div>
              <span className="text-3xl">{status.ringing_call.direction === 'inbound' ? '🔔' : '📡'}</span>
            </div>
            <p className="text-xs text-yellow-700 mb-3">
              {status.ringing_call.direction === 'inbound'
                ? 'Who should answer?'
                : 'The other side picked up — who handles this?'}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => handleRingDecision('ai')}
                disabled={deciding}
                className="flex-1 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                AI answers
              </button>
              <button
                onClick={() => handleRingDecision('human')}
                disabled={deciding}
                className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                I'll take it
              </button>
            </div>
          </div>
        )}

        {/* ── Active call card ── */}
        {status?.active_call && (
          <div className="bg-green-50 border border-green-300 rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-green-700 mb-1">
                  Active call · {status.active_call.mode === 'ai' ? 'AI handling' : 'You are live'}
                </p>
                <p className="text-xl font-bold text-green-900">
                  {callerStr(status.active_call.caller_name) || callerStr(status.active_call.caller)}
                </p>
                {status.active_call.caller_name && (
                  <p className="text-sm text-green-700 font-mono">{callerStr(status.active_call.caller)}</p>
                )}
              </div>
              <div className="text-right space-y-2">
                <p className="text-3xl font-mono font-bold text-green-800">{duration}</p>
                <button
                  onClick={handleHangup}
                  disabled={hangingUp}
                  className="block w-full px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
                >
                  {hangingUp ? 'Hanging up…' : 'Hang up'}
                </button>
              </div>
            </div>

            {/* Microphone — human mode */}
            {status.active_call.mode === 'human' && (
              <div className="border-t border-green-200 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-green-700 mb-2">
                  Your microphone
                </p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={talking ? stopTalking : startTalking}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      talking
                        ? 'bg-red-600 text-white hover:bg-red-700 animate-pulse'
                        : 'bg-green-700 text-white hover:bg-green-800'
                    }`}
                  >
                    {talking ? '🔴 Stop talking' : '🎙 Talk'}
                  </button>
                  {talking && <span className="text-xs text-green-700">Live — caller can hear you</span>}
                  {talkErr  && <span className="text-xs text-red-600">{talkErr}</span>}
                </div>
              </div>
            )}

            {/* Whisper — AI mode */}
            {status.active_call.mode === 'ai' && (
              <div className="border-t border-green-200 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-green-700 mb-1">
                  Whisper to AI
                </p>
                <p className="text-xs text-green-600 mb-2">
                  Give the AI a silent instruction — the caller won't hear it.
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="e.g. Ask about their budget"
                    value={whisper}
                    onChange={e => setWhisper(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleWhisper()}
                    className="flex-1 border border-green-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                  <button
                    onClick={handleWhisper}
                    disabled={!whisper.trim()}
                    className="px-4 py-2 bg-green-700 text-white rounded-lg text-sm font-medium hover:bg-green-800 disabled:opacity-50 transition-colors"
                  >
                    {whisperOk ? 'Sent ✓' : 'Send'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Dial pad ── */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">AI call request</h2>
          <div className="space-y-3">
            <textarea
              rows={3}
              placeholder="Rufe Max an und sag ihm, dass der Termin verschoben wurde"
              value={callRequest}
              onChange={e => {
                setCallRequest(e.target.value);
                setCallFlowMsg(null);
                setCallFlowOptions([]);
              }}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
            />
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => handleCallMessage(callRequest)}
                disabled={callFlowLoading || !callRequest.trim()}
                className="px-5 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {callFlowLoading ? 'Sending...' : 'Send request'}
              </button>
              {callFlowAction === 'confirm_prompt' && (
                <>
                  <button
                    onClick={() => handleCallMessage('ja')}
                    disabled={callFlowLoading}
                    className="px-4 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    Ja
                  </button>
                  <button
                    onClick={() => handleCallMessage('nein')}
                    disabled={callFlowLoading}
                    className="px-4 py-2.5 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 disabled:opacity-50 transition-colors"
                  >
                    Nein
                  </button>
                </>
              )}
            </div>
            {callFlowMsg && (
              <div className={`text-sm rounded px-3 py-2 border ${
                callFlowAction === 'error'
                  ? 'bg-amber-50 border-amber-200 text-amber-700'
                  : 'bg-green-50 border-green-200 text-green-800'
              }`}>
                <p>{callFlowMsg}</p>
                {callFlowAction === 'clarification_needed' && callFlowOptions.length > 0 && (
                  <ul className="mt-2 list-disc pl-5 space-y-1">
                    {callFlowOptions.map((option, idx) => (
                      <li key={idx}>
                        {[option.display_name, option.masked_number].filter(Boolean).join(' - ')}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Dial</h2>
          <div className="flex gap-3">
            <input
              type="tel"
              placeholder="+49 xxx xxxxxxx"
              value={dialNum}
              onChange={e => { setDialNum(e.target.value); setDialErr(null); }}
              onKeyDown={e => e.key === 'Enter' && handleDial(dialNum)}
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <button
              onClick={() => handleDial(dialNum)}
              disabled={dialing || !dialNum.trim()}
              className="px-6 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {dialing ? 'Calling…' : 'Call'}
            </button>
          </div>
          {dialErr && (
            <p className="mt-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              {dialErr}
            </p>
          )}
        </div>

        {/* ── Contacts ── */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-800">
              Contacts
              {contacts.length > 0 && (
                <span className="ml-2 text-sm font-normal text-gray-400">({contacts.length})</span>
              )}
            </h2>
            <button onClick={loadContacts} className="text-xs text-gray-400 hover:text-gray-600 underline">
              Reload
            </button>
          </div>

          {contacts.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">
              No contacts loaded.{' '}
              <span>
                Place <code className="font-mono">AI_Phone_Contacts.xlsx</code> in{' '}
                <code className="font-mono">backend/</code> and click Reload.
              </span>
            </p>
          ) : (
            <>
              <input
                type="text"
                placeholder="Search by name or number…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full mb-4 border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500"
              />
              <div className="divide-y divide-gray-100">
                {filtered.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-4">No matches.</p>
                ) : (
                  filtered.map((c, i) => (
                    <div key={i} className="flex items-center justify-between py-3 group">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{c.name || '—'}</p>
                        <p className="text-xs text-gray-500 font-mono">{c.number}</p>
                        {c.status && <p className="text-xs text-gray-400 mt-0.5">{c.status}</p>}
                      </div>
                      <button
                        onClick={() => { setDialNum(c.number); setDialErr(null); }}
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

        {/* ── Call log ── */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-800">Recent calls</h2>
            <button onClick={loadCallLog} className="text-xs text-gray-400 hover:text-gray-600 underline">
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
                return (
                  <div key={i} className="py-3 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-gray-400">
                          {entry.direction === 'inbound' ? '↙' : '↗'}
                        </span>
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {callerStr(entry.caller_name) || callerStr(entry.caller)}
                        </p>
                        {entry.caller_name && (
                          <p className="text-xs text-gray-400 font-mono hidden sm:block">{callerStr(entry.caller)}</p>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {new Date(entry.ts).toLocaleString()}
                      </p>
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
