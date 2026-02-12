# Google Calendar 403 Error - FIXED

## Problem
Calling `/api/google/calendar/events` returns:
```
403 Forbidden
{
  "detail": "Not authenticated"
}
```

## Root Cause
The `/api/google` routes require an API key because they're mounted under the authenticated `/api` router. However, the route you need is the OAuth-based one that doesn't require an API key.

## Solution

### Use the Correct Endpoint

**❌ WRONG (requires API key):**
```
GET /api/google/calendar/events
```

**✅ CORRECT (requires Google OAuth token):**
```
GET /api/integrations/google/calendar/events?user_id=default_user
```

## Complete Endpoint Mapping

### Calendar Endpoints (OAuth-based, no API key needed)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/integrations/google/calendar/events` | List calendar events |
| POST | `/api/integrations/google/calendar/events` | Create calendar event |

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/integrations/google/auth/start` | Start Google OAuth flow |
| GET | `/api/integrations/google/auth/callback` | OAuth callback (automatic) |
| GET | `/api/integrations/status` | Check connection status |
| DELETE | `/api/integrations/google/disconnect` | Disconnect Google account |

## Authentication Flow

### Step 1: Check if Google is Connected
```bash
curl http://localhost:8000/api/integrations/status?user_id=default_user
```

Response:
```json
{
  "google": {
    "provider": "google",
    "connected": true,  // ✅ or false ❌
    "scopes": ["https://www.googleapis.com/auth/calendar", ...]
  },
  "microsoft": {
    "provider": "microsoft",
    "connected": false
  }
}
```

### Step 2: If Not Connected, Authenticate
Open in browser:
```
http://localhost:8000/api/integrations/google/auth/start?user_id=default_user
```

This will:
1. Redirect to Google OAuth consent screen
2. After approval, redirect to callback URL
3. Store OAuth tokens securely

### Step 3: List Calendar Events
```bash
curl "http://localhost:8000/api/integrations/google/calendar/events?user_id=default_user&limit=10"
```

Response:
```json
{
  "events": [
    {
      "id": "abc123",
      "summary": "Team Meeting",
      "start": "2026-02-12T14:00:00+01:00",
      "end": "2026-02-12T15:00:00+01:00",
      "status": "confirmed"
    }
  ],
  "count": 1
}
```

### Step 4: Create Calendar Event
```bash
curl -X POST "http://localhost:8000/api/integrations/google/calendar/events?user_id=default_user" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Team Standup",
    "date": "2026-02-12",
    "start_time": "09:00",
    "end_time": "09:30",
    "timezone": "Europe/Berlin",
    "description": "Daily standup meeting",
    "confirm": true
  }'
```

## Common Errors

### 1. "Not authenticated" (403)
**Cause:** Using wrong endpoint that requires API key
**Fix:** Use `/api/integrations/google/calendar/events` instead of `/api/google/calendar/events`

### 2. "No Google tokens found" (401)
**Cause:** Google account not connected
**Fix:** Complete OAuth flow via `/api/integrations/google/auth/start`

### 3. "scope_changed" (409)
**Cause:** App permissions updated, need to reconnect
**Fix:** Disconnect and reconnect Google account:
```bash
# Disconnect
curl -X DELETE "http://localhost:8000/api/integrations/google/disconnect?user_id=default_user"

# Reconnect via browser
# Open: http://localhost:8000/api/integrations/google/auth/start?user_id=default_user
```

## Testing Your Setup

Run this test script:
```bash
# Test 1: Check status
echo "=== Checking Google connection status ==="
curl -s "http://localhost:8000/api/integrations/status?user_id=default_user" | python -m json.tool

# If not connected, open this URL in browser:
echo ""
echo "=== If not connected, open this URL ==="
echo "http://localhost:8000/api/integrations/google/auth/start?user_id=default_user"
echo ""

# Test 2: List events
echo "=== Listing calendar events ==="
curl -s "http://localhost:8000/api/integrations/google/calendar/events?user_id=default_user&limit=5" | python -m json.tool
```

## Quick Reference

### Environment Variables Required
```env
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
```

### Credentials File
Must exist: `backend/credentials.json`

### Callback URL Configuration
Must be set in Google Cloud Console:
```
http://localhost:8000/api/integrations/google/auth/callback
```

## Next Steps

1. ✅ Verify Google OAuth is configured (check .env)
2. ✅ Ensure credentials.json exists in backend/
3. ✅ Check connection status
4. ✅ If not connected, authenticate via browser
5. ✅ Use correct endpoints for calendar operations

The issue is now resolved - use `/api/integrations/google/calendar/events` instead of `/api/google/calendar/events`!
