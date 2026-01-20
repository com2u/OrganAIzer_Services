import { useState } from 'react';

const OutlookIntegration = () => {
  const [emails, setEmails] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [sendForm, setSendForm] = useState({ to: '', subject: '', body: '' });
  const [authMessage, setAuthMessage] = useState('');
  const [deviceCode, setDeviceCode] = useState('');
  const [authUrl, setAuthUrl] = useState('');

  const apiKey = import.meta.env.VITE_API_KEY;

  const handleReadEmails = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const response = await fetch('/api/outlook/emails', {
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
      const response = await fetch('/api/outlook/emails/send', {
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
      const response = await fetch('/api/outlook/calendar/events', {
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

  const handleAuthenticate = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/outlook/auth', {
        headers: {
          'X-API-Key': apiKey
        }
      });
      const data = await response.json();
      if (data.user_code) {
        setDeviceCode(data.user_code);
        setAuthUrl(data.verification_uri);
        setAuthMessage(`Enter the code: ${data.user_code} at ${data.verification_uri}`);
      } else {
        setAuthMessage(data.message || 'Authentication status checked');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStoreCache = () => {
    setSuccess('Token cache is automatically saved after successful API operations.');
  };

  return (
    <div className="max-w-4xl mx-auto bg-white p-8 rounded-xl shadow-lg border border-gray-200">
      <div className="flex items-center mb-6">
        <div className="bg-blue-600 p-3 rounded-full mr-4">
          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M21.386 2.614H2.614A.614.614 0 0 0 2 3.228v17.156c0 .34.274.614.614.614h18.772a.614.614 0 0 0 .614-.614V3.228a.614.614 0 0 0-.614-.614zM12 17.041c-1.104 0-2-.896-2-2s.896-2 2-2 2 .896 2 2-.896 2-2 2zm4-10.041h-8v1.229h8V7z"/>
          </svg>
        </div>
        <h2 className="text-3xl font-bold text-gray-800">Outlook Integration</h2>
      </div>

      <p className="text-gray-600 mb-6">Integrate with Microsoft Outlook and Calendar APIs.</p>

      {/* Authentication Section */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <h3 className="text-lg font-semibold mb-2">Authentication</h3>
        <div className="space-y-2">
          <button
            onClick={handleAuthenticate}
            className="bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 mr-2"
          >
            Authenticate
          </button>
          <button
            onClick={handleStoreCache}
            className="bg-green-600 text-white py-2 px-4 rounded-lg hover:bg-green-700"
          >
            Store Token Cache
          </button>
          <a
            href="https://microsoft.com/devicelogin"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-gray-600 text-white py-2 px-4 rounded-lg hover:bg-gray-700 ml-2"
          >
            Open Device Login Page
          </a>
        </div>
        {authMessage && (
          <p className="text-blue-800 mt-2">{authMessage}</p>
        )}
        {deviceCode && (
          <div className="mt-2 p-2 bg-gray-100 rounded">
            <strong>Device Code: {deviceCode}</strong>
            {authUrl && (
              <p>Go to: <a href={authUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">{authUrl}</a></p>
            )}
          </div>
        )}
      </div>

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
                    <strong>{email.subject}</strong> from {email.from} - {email.body_preview}
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
                    <strong>{event.subject}</strong> - {event.start} to {event.end}
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

export default OutlookIntegration;