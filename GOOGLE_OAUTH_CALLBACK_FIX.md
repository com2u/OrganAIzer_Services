# Google OAuth Callback URL Fix

## Problem Summary

The Google OAuth flow was failing with a "missing code parameter" error due to redirect_uri mismatches between:
- Frontend start URL
- Backend start handler
- Backend callback handler  
- Google Cloud OAuth Authorized redirect URIs

## Root Cause

While the routes were mostly correct (`/auth/start` and `/auth/callback`), there was potential for inconsistency because:
1. The `redirect_uri` was being read from environment variables in multiple places
2. No validation that the same exact URL was used in both start and callback endpoints
3. Missing diagnostic logging when callback failed
4. No startup logging to confirm the configured redirect_uri

## Solution Implemented

### 1. Hard-Coded Canonical Callback URL

**File**: `backend/api/integrations.py`

```python
# CANONICAL GOOGLE OAUTH CALLBACK URL (MUST MATCH GOOGLE CLOUD CONSOLE EXACTLY)
GOOGLE_OAUTH_CALLBACK_URL = "http://localhost:8000/api/integrations/google/auth/callback"
```

Both the start and callback endpoints now use this constant instead of reading from environment variables separately. This ensures perfect consistency.

### 2. Enhanced Callback Validation

The callback handler now:
- Returns detailed JSON error (not HTTP 400) when `code` parameter is missing
- Logs the full callback URL and query string for debugging
- Provides troubleshooting steps in the error response
- Uses emoji logging for easy log scanning (🔐, 📍, ✅, ❌, etc.)

**Missing Code Response**:
```json
{
  "error": "missing_code",
  "detail": "Google did not supply an auth code. Likely redirect_uri mismatch.",
  "expected_redirect_uri": "http://localhost:8000/api/integrations/google/auth/callback",
  "actual_callback_url": "http://localhost:8000/api/integrations/google/auth/callback?error=...",
  "query_string": "error=...",
  "troubleshooting": [
    "1. Verify Google Cloud Console has EXACTLY: http://localhost:8000/api/integrations/google/auth/callback",
    "2. No trailing slash",
    "3. Scheme (http), host (localhost), port (8000), and path must match exactly",
    "4. Clear browser cookies and try again"
  ]
}
```

### 3. Enhanced State Validation Logging

The state parameter validation now includes:
- Clear success/failure emoji markers
- State token preview (first 10 characters)
- Explanation of potential causes for state mismatch

### 4. Startup Logging

**File**: `backend/main.py`

Added OAuth configuration display on server startup:

```
======================================================================
🚀 OrganAIzer Backend Server Starting
======================================================================
✅ Server URL: http://localhost:8000
✅ API Docs: http://localhost:8000/docs
✅ Health Check: http://localhost:8000/health
✅ Executive Agent: http://localhost:8000/api/agent/capabilities
----------------------------------------------------------------------
🔐 OAuth Configuration:
   Google OAuth redirect_uri: http://localhost:8000/api/integrations/google/auth/callback
======================================================================
```

### 5. Detailed Request Logging

The callback endpoint now logs:
- Client IP address
- Full callback URL
- Query string
- Parameter presence status (not values for security)

## Routes Verification

### ✅ Current Routes (All Correct)

| Route | Purpose | Status |
|-------|---------|--------|
| `/api/integrations/google/auth/start` | Initiate OAuth flow | ✅ Active |
| `/api/integrations/google/auth/callback` | Handle OAuth redirect | ✅ Active |

### ❌ No Old Routes Found

Search confirmed there are no stale `/oauth/` routes in the codebase.

## Frontend Verification

**File**: `frontend/src/components/GoogleIntegration.tsx`

Frontend correctly uses:
```typescript
window.location.href = `/api/integrations/google/auth/start?user_id=${userId}`;
```

No changes needed to frontend.

## Google Cloud Console Configuration

### Required Authorized Redirect URI

Add this EXACT URL in Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs:

```
http://localhost:8000/api/integrations/google/auth/callback
```

**Critical Requirements**:
- ❌ NO trailing slash
- ✅ Scheme: `http` (for localhost development)
- ✅ Host: `localhost`
- ✅ Port: `8000`
- ✅ Path: `/api/integrations/google/auth/callback`

### How to Verify

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project
3. Navigate to "APIs & Services" → "Credentials"
4. Click on your OAuth 2.0 Client ID
5. Under "Authorized redirect URIs", verify the exact URL above is listed
6. Save if you made changes

## Testing the Fix

### Manual Testing

1. Start the backend server:
   ```bash
   cd backend
   python main.py
   ```

2. Check the startup logs confirm the redirect_uri:
   ```
   🔐 OAuth Configuration:
      Google OAuth redirect_uri: http://localhost:8000/api/integrations/google/auth/callback
   ```

3. Navigate to the frontend and click "Connect Google"

4. Monitor backend logs for the OAuth flow:
   ```
   🔐 Starting Google OAuth for user_id=default_user
   📍 Using canonical redirect_uri: http://localhost:8000/api/integrations/google/auth/callback
   📥 OAuth callback received from: ...
   🔑 Parameters: code=[PRESENT], state=[PRESENT], error=[NONE]
   ✅ State validated successfully for user default_user
   ✅ Google OAuth successful for user default_user
   ```

### Automated Testing

Run the test script:
```bash
python test_google_oauth_callback.py
```

## State Handling

### State Generation (Start Endpoint)
- Cryptographically secure random token
- 32 bytes, URL-safe encoding
- Stored persistently in token storage (survives backend restarts)

### State Validation (Callback Endpoint)
- Retrieved from token storage
- Compared with incoming state parameter
- Deleted after successful validation
- Clear error messages for mismatches

## Error Scenarios

### 1. Missing Code Parameter
**Cause**: redirect_uri mismatch between backend and Google Cloud Console

**Response**: JSON with troubleshooting steps (see section 2 above)

### 2. Missing State Parameter
**Cause**: Possible CSRF attack or malformed request

**Response**: HTTP 400 - "Missing 'state' parameter"

### 3. State Mismatch
**Cause**: Reused token, backend restart, or CSRF attack

**Response**: HTTP 400 - "Invalid state parameter. Please restart OAuth flow"

### 4. User Denied Access
**Cause**: User clicked "Cancel" on Google consent screen

**Response**: HTTP 400 - "Google OAuth denied: {error}"

## Files Modified

1. ✅ `backend/api/integrations.py` - Hard-coded canonical callback URL, enhanced logging
2. ✅ `backend/main.py` - Added startup OAuth configuration logging
3. ✅ `backend/.env` - Already had correct `GOOGLE_REDIRECT_URI` (no changes needed)

## Files Verified (No Changes Needed)

1. ✅ `frontend/src/components/GoogleIntegration.tsx` - Uses correct `/auth/start` route
2. ✅ No old `/oauth/` routes found in codebase

## Acceptance Criteria

- [x] Clicking "Connect Google" redirects to Google consent screen
- [x] After consent, Google redirects to exact callback URL
- [x] Backend logs show the canonical redirect_uri on startup
- [x] Backend logs detailed diagnostics if callback fails
- [x] Callback validates state parameter with clear error messages
- [x] No 404 routes involved
- [x] No "missing code" errors (when Google Cloud Console is configured correctly)
- [x] Token exchange succeeds and tokens are stored

## Troubleshooting Guide

### If you still see "missing code" error:

1. **Check Google Cloud Console**:
   - Verify EXACT URL: `http://localhost:8000/api/integrations/google/auth/callback`
   - No trailing slash
   - Port 8000, not 8001 or other

2. **Check backend startup logs**:
   - Confirm it shows the correct redirect_uri
   - Should match Google Cloud Console exactly

3. **Clear browser state**:
   - Clear cookies for localhost
   - Try in incognito mode

4. **Check browser console/network tab**:
   - Look at the redirect URL Google sends you to
   - Compare with expected callback URL

5. **Check backend logs**:
   - Look for the callback request
   - Check the "actual_callback_url" in the error response
   - Compare with "expected_redirect_uri"

## Production Deployment

For production deployment, update:

1. **Environment Variable** (`backend/.env`):
   ```
   GOOGLE_REDIRECT_URI=https://yourdomain.com/api/integrations/google/auth/callback
   ```

2. **Code Constant** (`backend/api/integrations.py`):
   ```python
   GOOGLE_OAUTH_CALLBACK_URL = os.getenv(
       "GOOGLE_REDIRECT_URI",
       "http://localhost:8000/api/integrations/google/auth/callback"
   )
   ```

3. **Google Cloud Console**:
   - Add production URI to Authorized redirect URIs
   - Use HTTPS, not HTTP
   - Match your domain exactly

## Summary

This fix ensures the Google OAuth callback URL is consistent throughout the application by:
1. Using a single source of truth (GOOGLE_OAUTH_CALLBACK_URL constant)
2. Enhanced logging for diagnostics
3. Clear error messages with troubleshooting steps
4. Startup logging to confirm configuration
5. State validation with detailed error messages

The OAuth flow is now robust, debuggable, and provides clear guidance when issues occur.
