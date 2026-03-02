# Microsoft Integration — How to Verify

This checklist confirms the full Microsoft Calendar + Mail integration is working end-to-end.

---

## 1. Start the backend

```bash
cd backend
python main.py
# or
uvicorn main:app --reload --port 8000
```

---

## 2. Check token file for `default_user`

After a successful OAuth flow, tokens are stored at:
```
data/tokens/default_user_microsoft.enc
```

If the file exists, tokens were saved. If missing, OAuth never completed.

---

## 3. Check Microsoft connection status

```bash
curl http://localhost:8000/api/integrations/microsoft/status?user_id=default_user
```

**Expected (connected):**
```json
{
  "connected": true,
  "scopes": ["https://graph.microsoft.com/Mail.Send", "https://graph.microsoft.com/Mail.Read", "..."],
  "has_refresh_token": true
}
```

**If `connected: false`:** Go to step 4 (OAuth).

---

## 4. Authenticate Microsoft (if not connected)

```bash
curl http://localhost:8000/api/integrations/microsoft/auth/start?user_id=default_user
```

Open the `auth_url` in your browser, sign in, and grant consent.
You will be redirected back to the frontend. The token file is now created.

---

## 5. Verify token audience (aud) in logs

After any Microsoft API call, look for these **structured log lines**:

```
[MS_TOKEN] user=default_user  has_access_token=True  has_refresh_token=True  token_prefix=eyJ0eXAiOiJK...
[MS_TOKEN] user=default_user  expires_at=2026-03-03T12:00:00  expired_or_expiring_soon=False
[MS_TOKEN] user=default_user  jwt.aud=https://graph.microsoft.com  jwt.scp=Calendars.ReadWrite Mail.Read Mail.Send User.Read  jwt.exp=2026-03-03T12:00:00
```

### ✅ `jwt.aud` must be `https://graph.microsoft.com` (or GUID `00000003-0000-0000-c000-000000000000`)

### ❌ If `jwt.aud` is your Azure Client ID (e.g., `a2da9786-...`)
This means an **id_token** was stored instead of an **access_token**.
- **Fix:** Delete `data/tokens/default_user_microsoft.enc` and re-authenticate.
- The current code stores `result["access_token"]` (correct), NOT `result["id_token"]`.

---

## 6. Test Calendar — List Events

```bash
curl "http://localhost:8000/api/integrations/microsoft/calendar/events?user_id=default_user&max_results=5"
```

**Expected:** `{"events": [...], "total": N}`  
**401 response:** `{"detail": {"code": "MICROSOFT_UNAUTHORIZED", ...}}`  — do NOT re-authenticate, check logs first  
**403 response:** `{"detail": {"code": "MICROSOFT_FORBIDDEN", ...}}` — check Azure API permissions

---

## 7. Test Calendar — Create Event

```bash
curl -X POST "http://localhost:8000/api/integrations/microsoft/calendar/events?user_id=default_user" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "Test Meeting",
    "start": "2026-03-04T09:00:00",
    "end": "2026-03-04T10:00:00",
    "location": "Fulda"
  }'
```

**Expected:**
```json
{
  "id": "AAMkAD...",
  "summary": "Test Meeting",
  "start": "2026-03-04T09:00:00",
  "end": "2026-03-04T10:00:00",
  "location": "Fulda"
}
```

**Logs to expect:**
```
[MS_GRAPH] → POST https://graph.microsoft.com/v1.0/me/calendar/events
[MS_GRAPH] ← POST https://graph.microsoft.com/v1.0/me/calendar/events  status=201
✅ Created Outlook calendar event 'Test Meeting' for user default_user
```

---

## 8. Test Calendar — Update Event

```bash
# Use EVENT_ID from step 7
curl -X PATCH "http://localhost:8000/api/integrations/microsoft/calendar/events/AAMkAD...?user_id=default_user" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "Test Meeting (Updated)",
    "start": "2026-03-04T11:00:00",
    "end": "2026-03-04T12:00:00"
  }'
```

---

## 9. Test Calendar — Delete Event

```bash
curl -X DELETE "http://localhost:8000/api/integrations/microsoft/calendar/events/AAMkAD...?user_id=default_user"
```

**Expected:** `{"status": "deleted", "event_id": "AAMkAD..."}`

---

## 10. Test Mail — List Last 5 Emails

```bash
curl "http://localhost:8000/api/integrations/microsoft/mail/messages?user_id=default_user&max_results=5"
```

**Expected:**
```json
{
  "emails": [
    {
      "id": "AAMkAD...",
      "from": "Someone <someone@example.com>",
      "subject": "Re: Project Update",
      "received": "2026-03-02T...",
      "preview": "Hello, I wanted to follow up...",
      "unread": false
    }
  ],
  "total": 5
}
```

---

## 11. Test Mail — Read Specific Email

```bash
# Use EMAIL_ID from step 10
curl "http://localhost:8000/api/integrations/microsoft/mail/messages/AAMkAD...?user_id=default_user"
```

**Expected:** Full message body including `body` (HTML/text content).

---

## 12. Test Mail — Send Email

```bash
curl -X POST "http://localhost:8000/api/integrations/microsoft/mail/send?user_id=default_user" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "recipient@example.com",
    "subject": "Test from OrganAIzer",
    "body": "This is a test email from the Microsoft integration."
  }'
```

**Expected:** `{"success": true, "message": "Email sent successfully via Outlook to recipient@example.com"}`

---

## 13. Test Executive AI — Calendar via natural language

```bash
curl -X POST "http://localhost:8000/api/executive-agent/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "show me my calendar today",
    "user_id": "default_user",
    "calendar_provider": "microsoft",
    "mail_provider": "outlook"
  }'
```

**Expected:** Agent lists Outlook Calendar events for today (or says no events).

---

## 14. Test Executive AI — Email via natural language

```bash
curl -X POST "http://localhost:8000/api/executive-agent/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "what are my last 3 emails?",
    "user_id": "default_user",
    "calendar_provider": "microsoft",
    "mail_provider": "outlook"
  }'
```

**Expected:** Agent returns 3 most recent Outlook emails with summaries.

---

## 15. Test Executive AI — Calendar create via natural language

```bash
# Step 1: Initiate
curl -X POST "http://localhost:8000/api/executive-agent/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "create a meeting tomorrow at 10am for 1 hour in Fulda",
    "user_id": "default_user",
    "calendar_provider": "microsoft",
    "mail_provider": "outlook",
    "session_id": "test-session-ms-1"
  }'
# Response: confirmation request (type=calendar_confirmation)

# Step 2: Confirm
curl -X POST "http://localhost:8000/api/executive-agent/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "yes",
    "user_id": "default_user",
    "calendar_provider": "microsoft",
    "mail_provider": "outlook",
    "session_id": "test-session-ms-1"
  }'
# Response: type=calendar_created with event_id
```

---

## 16. Run unit tests

```bash
cd backend
pytest tests/test_microsoft_integration.py -v
```

**Expected all pass:**
```
tests/test_microsoft_integration.py::TestGetValidMsToken::test_returns_token_when_valid PASSED
tests/test_microsoft_integration.py::TestGetValidMsToken::test_refreshes_when_expired PASSED
tests/test_microsoft_integration.py::TestGetValidMsToken::test_raises_401_when_no_tokens PASSED
tests/test_microsoft_integration.py::TestGetValidMsToken::test_raises_401_when_refresh_fails PASSED
tests/test_microsoft_integration.py::TestGetValidMsToken::test_access_token_stored_not_id_token PASSED
tests/test_microsoft_integration.py::TestGetValidMsToken::test_correct_graph_token_no_audience_warning PASSED
tests/test_microsoft_integration.py::TestMsRequest::test_401_raises_microsoft_unauthorized PASSED
tests/test_microsoft_integration.py::TestMsRequest::test_403_raises_microsoft_forbidden PASSED
tests/test_microsoft_integration.py::TestMsRequest::test_200_returns_json PASSED
tests/test_microsoft_integration.py::TestMsRequest::test_204_returns_empty_dict PASSED
tests/test_microsoft_integration.py::TestMsRequest::test_401_with_user_id_attempts_refresh_and_retry PASSED
tests/test_microsoft_integration.py::TestIntentRouting::test_last_3_emails_routes_email_read PASSED
...
```

---

## 17. Diagnosing persistent 401

If you still get `MICROSOFT_UNAUTHORIZED` from Graph after reconnecting:

### Check 1: Token audience
Look for `jwt.aud=` in logs. It must be `https://graph.microsoft.com`.

### Check 2: Token expiry
Look for `expired_or_expiring_soon=True`. If so, auto-refresh should have run.
If refresh failed, look for `[MS_TOKEN] Token refresh FAILED`.

### Check 3: Scopes
Look for `jwt.scp=` — it must include `Calendars.ReadWrite` (not just `User.Read`).

### Check 4: Token file freshness
Delete the token file and re-authenticate:
```bash
del data\tokens\default_user_microsoft.enc
# Then GET /api/integrations/microsoft/auth/start?user_id=default_user
```

### Check 5: Azure app registration
In Azure Portal → App Registration → API Permissions:
- `Microsoft Graph → Delegated → Calendars.ReadWrite` ✅
- `Microsoft Graph → Delegated → Mail.Read` ✅
- `Microsoft Graph → Delegated → Mail.Send` ✅
- `Microsoft Graph → Delegated → User.Read` ✅

Make sure you clicked **"Grant admin consent"** (or the user granted consent during OAuth).

### Check 6: Tenant ID
Verify `MICROSOFT_TENANT_ID` in `.env` matches your Azure app registration tenant.
For personal accounts (`@outlook.com`, `@hotmail.com`), use `consumers`.
For work/school accounts, use your tenant GUID or `common`.

---

## 18. Log reference — what to look for

| Log line | Meaning |
|---|---|
| `[MS_TOKEN] has_access_token=True` | Token was found in storage ✅ |
| `[MS_TOKEN] jwt.aud=https://graph.microsoft.com` | Correct Graph token ✅ |
| `[MS_TOKEN] ⚠️ WRONG TOKEN AUDIENCE` | id_token stored instead of access_token ❌ |
| `[MS_TOKEN] expired_or_expiring_soon=True` | Auto-refresh triggered |
| `[MS_TOKEN] Token refreshed successfully` | Refresh succeeded ✅ |
| `[MS_TOKEN] Token refresh FAILED` | Refresh_token expired → re-auth needed |
| `[MS_GRAPH] → POST .../me/calendar/events` | Graph call initiated |
| `[MS_GRAPH] ← POST .../me/calendar/events status=201` | Success ✅ |
| `[MS_GRAPH] 401 Unauthorized. endpoint=...` | Graph rejected token ❌ |
| `[MS_GRAPH] 403 Forbidden. endpoint=...` | Missing permission ❌ |
| `[MS_GRAPH] Retrying with fresh token for user=...` | 401-retry triggered |
| `✅ Created Outlook calendar event` | Event created ✅ |
| `✅ Outlook email sent` | Email sent ✅ |
