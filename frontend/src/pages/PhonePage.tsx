import { useState, useEffect, useRef } from 'react';

interface ActiveCall {
  caller: string;
  caller_name?: string;
  started_at: string;
}

interface PhoneStatus {
  registered: boolean;
  extension: string;
  server: string;
  active_call: ActiveCall | null;
}

interface Contact {
  name: string;
  number: string;
  status: string;
}

const API_KEY      = (import.meta.env.VITE_API_KEY      as string) ?? '';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) ?? '';

function useCallDuration(startedAt: string | null): string {
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!startedAt) {
      setElapsed(0);
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
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
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  useEffect(() => {
    fetchStatus();
    fetchContacts();
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

        {/* Active call card */}
        {status?.active_call && (
          <div className="bg-green-50 border border-green-300 rounded-lg p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-green-700 mb-1">
                  Active call
                </p>
                <p className="text-xl font-bold text-green-900">
                  {status.active_call.caller_name || status.active_call.caller}
                </p>
                {status.active_call.caller_name && (
                  <p className="text-sm text-green-700">{status.active_call.caller}</p>
                )}
              </div>
              <div className="text-right">
                <p className="text-3xl font-mono font-bold text-green-800">{duration}</p>
                <p className="text-xs text-green-600 mt-0.5">duration</p>
              </div>
            </div>
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

      </div>
    </div>
  );
}
