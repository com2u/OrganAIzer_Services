# Google OAuth Scope Fix - Complete Implementation

**Project:** OrganAIzer  
**Date:** 2026-02-10  
**Status:** ✅ COMPLETE

## Problem Statement

Users were experiencing `scope_changed` errors when trying to use Google Calendar features after we added the broader `https://www.googleapis.com/auth/calendar` scope. The backend was detecting scope mismatches but the reconnect flow was not robust, leading to:

- Confusing error messages
- No clear path to resolve the issue
- Calendar event creation failing silently
- Inconsistent scope definitions across codebase

## Solution Overview

Implemented a comprehensive scope management and reconnect flow system with:

1. **Single Source of Truth** for OAuth scopes
2. **Scope Hash Versioning** to detect permission changes
3. **Automatic Scope Mismatch Detection** on every API call
4. **Robust Token Reset/Revocation** functionality
5. **Forced Re-consent Flow** with proper OAuth parameters
6. **Frontend Reconnect UX** with blocking modal
7. **Comprehensive Error Handling** across all layers

---

## Architecture

### 1. Canonical Scope Configuration

**File:** `backend/config/google_scopes.py`

This is the **SINGLE SOURCE OF TRUTH** for all Google OAuth scopes. No other file should define scopes.

```python
GOOGLE_SCOPES: List[str] = [
    'https://www.googleapis.com/auth/calendar',           # Full calendar access
    'https://www.googleapis.com/auth/calendar.events',    # Calendar events
    'https://www.googleapis.com/auth/gmail.modify',       # Gmail modify
    'https://www.googleapis.com/auth/gmail.readonly',     # Gmail read
    'https://www.googleapis.com/auth/gmail.send',         # Gmail send
    'https://www.googleapis.com/auth/userinfo.email',     # User email
    'openid',                                              # OpenID
]
```

**Key Features:**
- Scopes are automatically sorted for deterministic ordering
- Hash generated from scope list: `CURRENT_SCOPE_HASH`
- Scope validation functions: `validate_token_scopes()`, `scopes_match()`
- Version tracking prevents subtle permission bugs

### 2. Scope Hash Versioning

**Concept:** Every scope configuration has a unique SHA256 hash (first 16 chars).

```python
CURRENT_SCOPE_HASH = compute_scope_hash(GOOGLE_SCOPES)
# Example: "5a3f2c1d8e9b0a7c"
```

When scopes change:
- Hash automatically changes
- System detects mismatch on token load
- Forces user to reconnect

### 3. Token Storage with Validation

**File:** `backend/utils/token_storage.py`

**New Features:**
- `ScopeChangedError` exception for scope mismatches
- `validate_scope_hash` parameter in `load_tokens()`
- Automatic hash comparison on load
- Detailed error information (old vs new scopes)

**Usage:**
```python
try:
    tokens = storage.load_tokens(
        user_id, 
        "google", 
        validate_scope_hash=True
    )
except ScopeChangedError as e:
    # e.old_scopes, e.new_scopes, e.old_hash, e.new_hash
    # Trigger reconnect flow
```

### 4. OAuth Flow Updates

**File:** `backend/api/integrations.py`

**OAuth Start Endpoint (`/google/auth/start`):**
```python
authorization_url, _ = flow.authorization_url(
    access_type='offline',              # Required for refresh token
    include_granted_scopes='false',     # Don't merge with old scopes
    prompt='consent'                     # Force consent for upgrades
)
```

**OAuth Callback Endpoint (`/google/auth/callback`):**
- Validates received scopes match required scopes
- Stores tokens with `scope_hash`
- Returns structured errors for scope mismatches
- Handles insufficient scope errors

**Token Reset Endpoint (`/google/reset`):**
- Revokes tokens with Google (best effort)
- Deletes stored tokens
- Returns reconnect URL

### 5. Provider-Level Scope Validation

**File:** `backend/services/providers/google_provider.py`

Every API call validates scope hash:
```python
def _get_credentials(self) -> Credentials:
    try:
        tokens = self.token_storage.load_tokens(
            self.user_id, 
            "google",
            validate_scope_hash=True  # Validates on every call
        )
    except ScopeChangedError as e:
        # Re-raised to API layer
        raise
```

### 6. API-Level Error Handling

**Files:** `backend/api/calendar.py`, `backend/api/email.py`

All endpoints catch `ScopeChangedError` and return structured HTTP 409 response:

```python
except ScopeChangedError as e:
    raise HTTPException(
        status_code=409,
        detail={
            "error": "scope_changed",
            "message": "OrganAIzer needs updated access...",
            "old_scopes": e.old_scopes,
            "new_scopes": e.new_scopes,
            "action": "RECONNECT_GOOGLE"
        }
    )
```

### 7. Frontend Reconnect UX

**File:** `frontend/src/components/GoogleIntegration.tsx`

**Features:**
- Global error handler for scope_changed errors
- Blocking modal with clear messaging
- One-click reconnect button
- Automatic redirect to OAuth flow
- Session refresh after reconnect

**Modal Display:**
```
┌───────────────────────────────────┐
│  ⚠️  Google Permissions Update    │
│                                    │
│  OrganAIzer needs updated access  │
│  to your Google Calendar...       │
│                                    │
│  [Reconnect Google Account]       │
│  [Cancel]                         │
└───────────────────────────────────┘
```

---

## Implementation Details

### Files Modified

**Backend:**
1. `backend/config/google_scopes.py` - NEW (canonical scopes)
2. `backend/utils/token_storage.py` - Updated (scope validation)
3. `backend/api/integrations.py` - Updated (OAuth flow)
4. `backend/services/providers/google_provider.py` - Updated (scope checks)
5. `backend/services/google_service.py` - Updated (import canonical scopes)
6. `backend/api/calendar.py` - Updated (error handling)

**Frontend:**
7. `frontend/src/components/GoogleIntegration.tsx` - Updated (reconnect UX)

**Tests & Docs:**
8. `test_google_scope_fix.py` - NEW (comprehensive tests)
9. `GOOGLE_OAUTH_SCOPE_FIX_IMPLEMENTATION.md` - NEW (this file)

### Key Changes Summary

**Backend Changes:**
- ✅ Single canonical scope list with hash versioning
- ✅ Scope mismatch detection on token load
- ✅ OAuth flow forces re-consent with correct parameters
- ✅ Token revocation on disconnect/reset
- ✅ Structured error responses (HTTP 409)
- ✅ Calendar event creation permission error handling

**Frontend Changes:**
- ✅ Global scope_changed error detection
- ✅ Blocking reconnect modal with clear messaging
- ✅ Automatic OAuth redirect on reconnect
- ✅ App name displayed as "OrganAIzer" (not organAIzer)

---

## Testing

### Run Test Suite

```bash
cd OrganAIzer_Services
python test_google_scope_fix.py
```

**Tests:**
1. **Scope Hash Generation** - Validates hash consistency and mismatch detection
2. **Scope Changed Error Detection** - Simulates old token with new scopes
3. **Scope Import Consistency** - Ensures all modules use canonical scopes

### Manual Testing Steps

1. **Simulate Scope Change:**
   ```bash
   # Delete existing Google tokens
   rm data/tokens/default_user_google.enc
   
   # Connect with old scopes (manually edit config temporarily)
   # Then restore new scopes
   # Next API call should trigger reconnect
   ```

2. **Test Calendar Creation:**
   ```bash
   # After reconnect, create a calendar event
   curl -X POST http://localhost:8000/api/calendar/create \
     -H "X-API-Key: YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "summary": "Test Event",
       "start": "2026-02-11T10:00:00Z",
       "end": "2026-02-11T11:00:00Z",
       "confirm": true,
       "dry_run": false
     }'
   ```

3. **Verify Frontend Modal:**
   - Open `/google` in browser
   - If scope mismatch exists, modal should appear
   - Click "Reconnect Google Account"
   - Should redirect to Google OAuth
   - After consent, should return to app

---

## Error Flow Diagram

```
User Action (e.g., Create Calendar Event)
         ↓
API Endpoint (/api/calendar/create)
         ↓
Calendar Provider (_get_credentials)
         ↓
Token Storage (load_tokens with validation)
         ↓
    [Scope Hash Check]
         ↓
    scope_hash == CURRENT_SCOPE_HASH?
         ↓
    NO ─→ ScopeChangedError
         ↓
    API Layer catches error
         ↓
    HTTP 409 with structured detail
         ↓
    Frontend detects error.action === "RECONNECT_GOOGLE"
         ↓
    Show Reconnect Modal
         ↓
    User clicks "Reconnect"
         ↓
    Redirect to /api/integrations/google/auth/start
         ↓
    Google OAuth (with prompt=consent)
         ↓
    Callback stores new tokens + scope_hash
         ↓
    ✅ User can now create events
```

---

## Deployment Checklist

- [x] Canonical scope configuration created
- [x] Token storage updated with validation
- [x] OAuth endpoints updated (start + callback)
- [x] Provider-level scope validation added
- [x] API-level error handling implemented
- [x] Frontend reconnect modal implemented
- [x] Test suite created and passing
- [x] Documentation completed

### Environment Variables Required

Ensure these are set in `backend/.env`:

```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/google/auth/callback
TOKEN_ENCRYPTION_KEY=your_encryption_key_here
```

### Google Cloud Console Setup

1. **Add Required Scopes** in OAuth Consent Screen:
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/calendar.events`
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `openid`

2. **Verify Redirect URI** matches backend configuration

3. **Test OAuth Flow** in development before production

---

## Monitoring & Maintenance

### Logs to Watch

**Scope Mismatch Detection:**
```
WARNING: Scope hash mismatch detected for user default_user.
INFO: Stored hash: abc123..., Current hash: def456...
INFO: Deleting old tokens and forcing re-consent
```

**Successful Reconnect:**
```
INFO: Google OAuth successful for user default_user. Scopes: [...]
INFO: Received scopes from Google: [...]
```

**Calendar Creation After Reconnect:**
```
INFO: 📅 Creating Google Calendar event: summary='Test', start=2026-02-11T10:00:00Z
INFO: ✅ Google Calendar event created successfully: event_id=abc123
```

### Future Scope Changes

When adding/removing scopes:

1. Update `backend/config/google_scopes.py` ONLY
2. Hash automatically updates
3. All users get reconnect prompt on next API call
4. No code changes needed elsewhere
5. Test with `test_google_scope_fix.py`

---

## Troubleshooting

### Issue: Modal doesn't appear

**Check:**
- Frontend error handler in API call
- HTTP 409 response with `action: "RECONNECT_GOOGLE"`
- Browser console for JavaScript errors

### Issue: OAuth fails after reconnect

**Check:**
- Google Cloud Console has all scopes listed
- `prompt=consent` in authorization URL
- `include_granted_scopes=false` parameter set
- Redirect URI matches exactly

### Issue: Scope hash always mismatches

**Check:**
- All modules import from `config.google_scopes`
- No local scope definitions remain
- Run `test_google_scope_fix.py` to verify

---

## Success Criteria

✅ **All Implemented:**

1. ✅ Single canonical scope list used across codebase
2. ✅ Scope hash versioning prevents stale permissions
3. ✅ Automatic detection on every authenticated API call
4. ✅ Token reset with optional revocation
5. ✅ OAuth flow forces re-consent with exact scopes
6. ✅ Frontend modal blocks and guides user to reconnect
7. ✅ Calendar events created successfully post-reconnect
8. ✅ Comprehensive tests validate the fix
9. ✅ Documentation explains architecture and usage

---

## Contact & Support

For issues or questions:
- Review this documentation
- Check test suite: `python test_google_scope_fix.py`
- Review logs for scope-related warnings
- Verify Google Cloud Console configuration

**Project:** OrganAIzer  
**Implementation Date:** 2026-02-10
