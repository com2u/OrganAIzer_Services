import { useState } from 'react';

const GoogleIntegration = () => {
  const [emails, setEmails] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [sendForm, setSendForm] = useState({ to: '', subject: '', body: '' });

  const apiKey = import.meta.env.VITE_API_KEY;

  const handleReadEmails = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const response = await fetch('/api/google/emails', {
        headers: {
          'X-API-Key': apiKey
        }
      });
      if (!response.ok) {
        throw new Error('Failed to read emails');
      }
      const data = await response.json();
      setEmails(data.emails);
      setSuccess('Emails loaded successfully');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSendEmail = async () => {
    if (!sendForm.to || !sendForm.subject || !sendForm.body) {
      setError('Please fill all fields');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const response = await fetch('/api/google/emails/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },
        body: JSON.stringify(sendForm),
      });
      if (!response.ok) {
        throw new Error('Failed to send email');
      }
      await response.json();
      setSuccess('Email sent successfully');
      setSendForm({ to: '', subject: '', body: '' });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReadCalendar = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const response = await fetch('/api/google/calendar/events', {
        headers: {
          'X-API-Key': apiKey
        }
      });
      if (!response.ok) {
        throw new Error('Failed to read calendar events');
      }
      const data = await response.json();
      setEvents(data.events);
      setSuccess('Calendar events loaded successfully');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto bg-white p-8 rounded-xl shadow-lg border border-gray-200">
      <div className="flex items-center mb-6">
        <div className="bg-blue-500 p-3 rounded-full mr-4">
          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
        </div>
        <h2 className="text-3xl font-bold text-gray-800">Google Integration</h2>
      </div>

      <p className="text-gray-600 mb-6">Integrate with Google Gmail and Calendar APIs.</p>

      <div className="space-y-6">
        {/* Read Emails */}
        <div>
          <button
            onClick={handleReadEmails}
            disabled={loading}
            className="bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Read Emails'}
          </button>
          {emails.length > 0 && (
            <div className="mt-4">
              <h3 className="text-lg font-semibold">Emails:</h3>
              <ul className="list-disc pl-5">
                {emails.map((email, index) => (
                  <li key={index} className="mb-2">
                    <strong>{email.subject}</strong> from {email.from} - {email.snippet}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Send Email */}
        <div>
          <h3 className="text-lg font-semibold mb-2">Send Email</h3>
          <div className="space-y-2">
            <input
              type="email"
              placeholder="To"
              value={sendForm.to}
              onChange={(e) => setSendForm({ ...sendForm, to: e.target.value })}
              className="w-full p-2 border border-gray-300 rounded"
            />
            <input
              type="text"
              placeholder="Subject"
              value={sendForm.subject}
              onChange={(e) => setSendForm({ ...sendForm, subject: e.target.value })}
              className="w-full p-2 border border-gray-300 rounded"
            />
            <textarea
              placeholder="Body"
              value={sendForm.body}
              onChange={(e) => setSendForm({ ...sendForm, body: e.target.value })}
              className="w-full p-2 border border-gray-300 rounded"
              rows={4}
            />
            <button
              onClick={handleSendEmail}
              disabled={loading}
              className="bg-green-600 text-white py-2 px-4 rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? 'Sending...' : 'Send Email'}
            </button>
          </div>
        </div>

        {/* Read Calendar */}
        <div>
          <button
            onClick={handleReadCalendar}
            disabled={loading}
            className="bg-purple-600 text-white py-2 px-4 rounded-lg hover:bg-purple-700 disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Read Calendar Events'}
          </button>
          {events.length > 0 && (
            <div className="mt-4">
              <h3 className="text-lg font-semibold">Calendar Events:</h3>
              <ul className="list-disc pl-5">
                {events.map((event, index) => (
                  <li key={index} className="mb-2">
                    <strong>{event.summary}</strong> - {event.start} to {event.end}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {success && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <span className="text-green-800">{success}</span>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <span className="text-red-800">{error}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default GoogleIntegration;