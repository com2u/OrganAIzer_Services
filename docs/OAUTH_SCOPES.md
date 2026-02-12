# OAuth Scopes Configuration

**Product Name:** OrganAIzer (exact spelling required)

This document provides the definitive reference for OAuth scopes used in OrganAIzer for Google and Microsoft integrations.

## Table of Contents
- [Google OAuth Scopes](#google-oauth-scopes)
- [Microsoft OAuth Scopes](#microsoft-oauth-scopes)
- [Scope Change Handling](#scope-change-handling)
- [Re-consent Instructions](#re-consent-instructions)

---

## Google OAuth Scopes

### Current Stable Scopes
**Location:** `backend/api/integrations.py` → `GOOGLE_SCOPES`

```python
GOOGLE_SCOPES = sorted([
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send'
])
```

### Scope Breakdown

| Scope | Purpose | Required For |
|-------|---------|--------------|
| `openid` | OpenID Connect authentication | User identification |
| `https://www.googleapis.com/auth/userinfo.email` | Get user's email address | User profile |
| `https://www.googleapis.com/auth/calendar.events` | **Calendar events only** (create, read, update, delete events) | Calendar management |
| `https://www.googleapis.com/auth/gmail.readonly` | Read Gmail messages | Email reading, summarization |
| `https://www.googleapis.com/auth/gmail.modify` | Modify Gmail (labels, drafts) | Email management, drafts |
| `https://www.googleapis.com/auth/gmail.send` | Send emails via Gmail | Email sending |

### Important Notes

#### Calendar Scope Choice
We use `calendar.events` (events-only) instead of `calendar` (full calendar access) because:
- **Principle of Least Privilege**: Only request what's needed
- **User Trust**: Events-only is less invasive than full calendar access
- **Sufficient Functionality**: Covers all OrganAIzer calendar features

If you need full calendar access (e.g., managing multiple calendars, calendar settings), change to:
```python
'https://www.googleapis.com/auth/calendar'  # Full calendar access
```

#### Gmail Scope Choices
- `gmail.readonly`: Read-only access to messages
- `gmail.modify`: Modify labels and create drafts (does NOT include sending)
- `gmail.send`: Send emails

**Alternative (Full Gmail Access):**
If you need complete Gmail control, you can use:
```python
'https://www.googleapis.com/auth/gmail.modify'  # Includes read, modify, send
```

### Scope Stability Rules

1. **Sorting**: Scopes are alphabetically sorted for deterministic ordering
2. **No mid-flight changes**: Never modify scopes while users are authenticated
3. **Versioned changes**: Track scope changes in git commits
4. **Force re-consent**: Use `prompt=consent` when scopes change

---

## Microsoft OAuth Scopes

### Current Stable Scopes
**Location:** `backend/api/integrations.py` → `MICROSOFT_SCOPES`

```python
MICROSOFT_SCOPES = [
    'User.Read',
    'Mail.Read',
    'Mail.Send',
    'Calendars.ReadWrite'
]
```

### Scope Breakdown

| Scope | Purpose | Required For |
|-------|---------|--------------|
| `User.Read` | Read user profile information | User identification, email address |
| `Mail.Read` | Read emails | Email reading, summarization |
| `Mail.Send` | Send emails | Email sending |
| `Calendars.ReadWrite` | Full calendar access (read and write) | Calendar event management |

### Microsoft-Specific Notes

#### Authority Types
- **Common**: `/common` - Supports both work/school and personal accounts
- **Consumers**: `/consumers` - Personal Microsoft accounts only (outlook.com, live.com)  
- **Organizations**: `/organizations` - Work/school accounts only

**OrganAIzer uses `/consumers` for personal account support.**

#### Delegated vs Application Permissions
OrganAIzer uses **Delegated Permissions** (user context):
- Actions performed on behalf of the signed-in user
- User must consent to permissions
- Refresh tokens available with `offline_access` (automatically included)

#### Alternative Scopes
For more restrictive access:
```python
['Mail.ReadBasic', 'Mail.Send', 'Calendars.Read']  # More restrictive
```

For broader access:
```python
['Mail.ReadWrite', 'Mail.Send', 'Calendars.ReadWrite']  # Full mail management
```

---

## Scope Change Handling

### Detection Mechanism

**File:** `backend/api/integrations.py` → `google_auth_callback()`

```python
def _scopes_match(scopes1: list, scopes2: list) -> bool:
    """Check if two scope lists are equivalent (order-independent)."""
    normalized1 = set(_normalize_scopes(scopes1))
    normalized2 = set(_normalize_scopes(scopes2))
    return normalized1 == normalized2
```

### Automatic Handling

When scope mismatch is detected:

1. **Warning logged**: `"Scope mismatch detected for user {user_id}"`
2. **Old tokens deleted**: Previous tokens are removed
3. **409 Conflict returned**: Client receives clear error message with:
   - `error`: `"scope_changed"`
   - `message`: "Permissions changed, please reconnect Google."
   - `old_scopes`: Previously granted scopes
   - `new_scopes`: Currently requested scopes
   - `action`: Re-authentication instructions

4. **Client action**: User must disconnect and reconnect to grant new scopes

### Force Re-consent

Both Google and Microsoft OAuth flows use `prompt=consent`:

```python
# Google
authorization_url, _ = flow.authorization_url(
    access_type='offline',
    include_granted_scopes='true',
    prompt='consent'  # Force consent screen
)

# Microsoft
auth_url = app.get_authorization_request_url(
    scopes=MICROSOFT_SCOPES,
    redirect_uri=redirect_uri,
    state=user_id,
    prompt='consent'  # Force consent to ensure refresh token
)
```

---

## Re-consent Instructions

### When to Re-consent

Re-authentication is required when:
- ✅ Scopes have been added or removed
- ✅ "Scope has changed" error appears
- ✅ New features require additional permissions
- ✅ Token refresh fails with auth errors

### Google Re-consent Process

#### Option 1: Via API (Automated)
1. Visit: `/api/integrations/google/disconnect?user_id=default_user`
2. Visit: `/api/integrations/google/auth/start?user_id=default_user`
3. Grant permissions on Google consent screen
4. Verify connection: `/api/integrations/status?user_id=default_user`

#### Option 2: Manual Cleanup
1. Delete token file: `data/tokens/default_user_google.enc`
2. Visit: `/api/integrations/google/auth/start?user_id=default_user`
3. Complete OAuth flow

#### Option 3: Revoke via Google Account
1. Go to: https://myaccount.google.com/permissions
2. Find "OrganAIzer" app
3. Click "Remove Access"
4. Re-authenticate through OrganAIzer

### Microsoft Re-consent Process

#### Option 1: Via API (Automated)
1. Visit: `/api/integrations/microsoft/disconnect?user_id=default_user`
2. Visit: `/api/integrations/microsoft/auth/start?user_id=default_user`
3. Grant permissions on Microsoft consent screen
4. Verify connection: `/api/integrations/microsoft/status?user_id=default_user`

#### Option 2: Manual Cleanup
1. Delete token file: `data/tokens/default_user_microsoft.enc`
2. Visit: `/api/integrations/microsoft/auth/start?user_id=default_user`
3. Complete OAuth flow

#### Option 3: Revoke via Microsoft Account
1. Go to: https://account.microsoft.com/privacy/app-access
2. Find "OrganAIzer" app
3. Click "Revoke permissions"
4. Re-authenticate through OrganAIzer

---

## Testing Scope Configuration

### Verify Current Scopes

**Google:**
```bash
curl "http://localhost:8000/api/integrations/status?user_id=default_user" \
  -H "X-API-Key: YOUR_API_KEY"
```

**Microsoft:**
```bash
curl "http://localhost:8000/api/integrations/microsoft/status?user_id=default_user" \
  -H "X-API-Key: YOUR_API_KEY"
```

### Check Outlook-Specific Capabilities
```bash
curl "http://localhost:8000/api/outlook-health/status?user_id=default_user" \
  -H "X-API-Key: YOUR_API_KEY"
```

---

## Environment Variables

### Required for Google OAuth
```bash
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/google/auth/callback
```

### Required for Microsoft OAuth
```bash
MICROSOFT_CLIENT_ID=your_application_id_here
MICROSOFT_CLIENT_SECRET=your_client_secret_here
OAUTH_REDIRECT_BASE_URL=http://localhost:8000
```

---

## Troubleshooting

### "Scope has changed" Error

**Cause:** Stored tokens have different scopes than currently requested scopes.

**Solution:**
1. Check current scope configuration in `backend/api/integrations.py`
2. Delete stored tokens for affected user
3. Re-authenticate with new scopes
4. Verify via status endpoint

### Missing Permissions Errors

**Symptoms:**
- "Insufficient permissions" API errors
- Calendar/email operations fail with 403
- Scope check shows missing required scopes

**Solution:**
1. Verify scope configuration matches requirements
2. Force re-consent with `prompt=consent`
3. Check OAuth app configuration in Google/Microsoft console
4. Ensure scopes are enabled in OAuth app settings

### Token Refresh Failures

**Symptoms:**
- 401 Unauthorized on API calls
- "Invalid grant" or "Token expired" errors
- Refresh token missing from stored tokens

**Solution:**
1. Check that `offline_access` (Microsoft) or `access_type='offline'` (Google) is set
2. Verify refresh token exists in stored token data
3. Re-authenticate if refresh token is missing
4. Check token expiry time in status response

---

## Scope Audit Log

Track all scope changes here for compliance and debugging:

| Date | Change | Reason | Author |
|------|--------|--------|--------|
| 2024-01-15 | Initial scopes defined | Project setup | System |
| 2024-12-29 | Switched from `calendar` to `calendar.events` | Least privilege principle | System |

---

## References

- [Google OAuth 2.0 Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)
- [Microsoft Graph Permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Google Calendar API Scopes](https://developers.google.com/calendar/api/guides/auth)
- [Microsoft Graph Mail API](https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview)
