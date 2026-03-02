import { useState, useEffect } from 'react';
import ErrorBanner from '../components/ErrorBanner';

/**
 * IntegrationsPage - Manage Google and Microsoft OAuth Integrations
 * Allows users to connect their Google and Microsoft accounts
 */

interface TokenStatus {
  connected: boolean;
  scopes?: string[];
  email?: string;
}

export default function IntegrationsPage() {
  const [googleStatus, setGoogleStatus] = useState<TokenStatus | null>(null);
  const [microsoftStatus, setMicrosoftStatus] = useState<TokenStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const API_KEY = import.meta.env.VITE_API_KEY || 'test-key-123';
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

  useEffect(() => {
    // Check for OAuth callback success/error in URL
    const params = new URLSearchParams(window.location.search);
    const authStatus = params.get('auth');
    const provider = params.get('provider');
    const message = params.get('message');

    if (authStatus === 'success' && provider) {
      setSuccess(`Successfully connected ${provider.charAt(0).toUpperCase() + provider.slice(1)}!`);
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
      checkTokenStatus();
    } else if (authStatus === 'error') {
      setError(`Authentication failed: ${message || 'Unknown error'}`);
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Check token status on load
    checkTokenStatus();
  }, []);

  const checkTokenStatus = async () => {
    // Check Google connection status via backend
    try {
      const res = await fetch(`${API_BASE_URL}/api/integrations/google/status?user_id=default_user`, {
        headers: { 'X-API-Key': API_KEY },
      });
      if (res.ok) {
        const data = await res.json();
        setGoogleStatus({ connected: data.connected, scopes: data.scopes });
      } else {
        setGoogleStatus({ connected: false });
      }
    } catch {
      setGoogleStatus({ connected: false });
    }
    // Check Microsoft connection status via backend
    try {
      const msRes = await fetch(`${API_BASE_URL}/api/integrations/microsoft/status?user_id=default_user`, {
        headers: { 'X-API-Key': API_KEY },
      });
      if (msRes.ok) {
        const msData = await msRes.json();
        setMicrosoftStatus({ connected: msData.connected, scopes: msData.scopes });
      } else {
        setMicrosoftStatus({ connected: false });
      }
    } catch {
      setMicrosoftStatus({ connected: false });
    }
  };

  const connectGoogle = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/integrations/google/auth/start?user_id=default_user`, {
        headers: {
          'X-API-Key': API_KEY,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to initiate Google OAuth: ${response.statusText}`);
      }

      const data = await response.json();
      
      // Redirect to Google OAuth
      window.location.href = data.auth_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to Google');
      setLoading(false);
    }
  };

  const connectMicrosoft = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/integrations/microsoft/auth/start?user_id=default_user`, {
        headers: {
          'X-API-Key': API_KEY,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.message || 'Microsoft integration is not yet implemented');
      }

      const data = await response.json();
      window.location.href = data.auth_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to Microsoft');
      setLoading(false);
    }
  };

  const disconnectGoogle = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/integrations/google/disconnect?user_id=default_user`, {
        method: 'DELETE',
        headers: { 'X-API-Key': API_KEY },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail?.message || 'Failed to disconnect Google');
      }
      setSuccess('Google account disconnected.');
      await checkTokenStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect Google');
    } finally {
      setLoading(false);
    }
  };

  const disconnectMicrosoft = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/integrations/microsoft/disconnect?user_id=default_user`, {
        method: 'DELETE',
        headers: { 'X-API-Key': API_KEY },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail?.message || 'Failed to disconnect Microsoft');
      }
      setSuccess('Microsoft account disconnected.');
      await checkTokenStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect Microsoft');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">🔗 Integrations</h1>
          <p className="text-gray-600">
            Connect your Google and Microsoft accounts to enable calendar, email, and other productivity features.
          </p>
        </div>

        {/* Success Message */}
        {success && (
          <div className="mb-6 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded">
            <div className="flex items-center justify-between">
              <span>{success}</span>
              <button onClick={() => setSuccess(null)} className="text-green-900 hover:text-green-950">✕</button>
            </div>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="mb-6">
            <ErrorBanner message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        {/* Google Integration */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-600" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Google</h2>
                <p className="text-sm text-gray-600">Gmail, Google Calendar, Drive</p>
                {googleStatus?.connected ? (
                  <div className="mt-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      ✓ Connected
                    </span>
                    {googleStatus.email && (
                      <span className="ml-2 text-xs text-gray-600">{googleStatus.email}</span>
                    )}
                  </div>
                ) : (
                  <div className="mt-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      ○ Not Connected
                    </span>
                  </div>
                )}
              </div>
            </div>
            <div>
              {googleStatus?.connected ? (
                <button
                  onClick={disconnectGoogle}
                  disabled={loading}
                  className="px-4 py-2 border border-red-600 text-red-600 rounded-lg hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Disconnect
                </button>
              ) : (
                <button
                  onClick={connectGoogle}
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Connecting...' : 'Connect Google'}
                </button>
              )}
            </div>
          </div>

          {/* Google Features */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Available Features:</h3>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-gray-600">
              <li className="flex items-center">
                <span className="mr-2">📧</span> Send and receive emails via Gmail
              </li>
              <li className="flex items-center">
                <span className="mr-2">📅</span> Create and manage calendar events
              </li>
              <li className="flex items-center">
                <span className="mr-2">🔍</span> Search email and calendar
              </li>
              <li className="flex items-center">
                <span className="mr-2">📎</span> Access Drive files (coming soon)
              </li>
            </ul>
          </div>
        </div>

        {/* Microsoft Integration */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-orange-600" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.4 24H0V12.6h11.4V24zM24 24H12.6V12.6H24V24zM11.4 11.4H0V0h11.4v11.4zm12.6 0H12.6V0H24v11.4z"/>
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">Microsoft</h2>
                <p className="text-sm text-gray-600">Outlook, Teams, OneDrive</p>
                {microsoftStatus?.connected ? (
                  <div className="mt-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      ✓ Connected
                    </span>
                    {microsoftStatus.email && (
                      <span className="ml-2 text-xs text-gray-600">{microsoftStatus.email}</span>
                    )}
                  </div>
                ) : (
                  <div className="mt-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      ○ Not Connected
                    </span>
                  </div>
                )}
              </div>
            </div>
            <div>
              {microsoftStatus?.connected ? (
                <button
                  onClick={disconnectMicrosoft}
                  disabled={loading}
                  className="px-4 py-2 border border-red-600 text-red-600 rounded-lg hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Disconnect
                </button>
              ) : (
                <button
                  onClick={connectMicrosoft}
                  disabled={loading}
                  className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Connecting...' : 'Connect Microsoft'}
                </button>
              )}
            </div>
          </div>

          {/* Microsoft Features */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Available Features:</h3>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-gray-600">
              <li className="flex items-center">
                <span className="mr-2">📧</span> Send and receive emails via Outlook
              </li>
              <li className="flex items-center">
                <span className="mr-2">📅</span> Create and manage calendar events
              </li>
              <li className="flex items-center">
                <span className="mr-2">💬</span> Teams integration (planned)
              </li>
              <li className="flex items-center">
                <span className="mr-2">📁</span> OneDrive access (planned)
              </li>
            </ul>
          </div>
        </div>

        {/* Info Box */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">🔒 Privacy & Security</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• Your credentials are stored securely and encrypted</li>
            <li>• We only request the minimum permissions needed</li>
            <li>• You can revoke access at any time</li>
            <li>• Tokens are stored locally and never shared with third parties</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
