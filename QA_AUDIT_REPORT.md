# OrganAIzer Backend — Full QA Audit Report
**Audit date**: 2026-03-11  
**Auditor**: Senior QA Engineer / Backend Reliability Review  
**Scope**: Executive AI, Voice Mode, Calendar, Mail, OAuth, TTS/STT, Time Parsing, Concurrency, Storage, Security

---

## Executive Summary

The backend is architecturally sound and has several well-engineered safeguards (idempotency store, pending-action guards, truthfulness checks, structured MS Graph diagnostics). However, **3 CRITICAL race conditions** and **several HIGH-severity bugs** must be fixed before this system is production-reliable. The most dangerous issues are:

1. **Race condition on calendar idempotency check** — two simultaneous "yes" confirmations can create duplicate events.
2. **Microsoft OAuth state is the user_id (predictable)** — CSRF attack vector; Google correctly uses a random token.
3. **`datetime.now() + "Z"` timezone bug** — calendar list `time_min` queries are sent to Google claiming to be UTC but are actually local time, causing up to ±N hours off during DST.
4. **Synchronous `requests` library in async FastAPI handlers** — all Microsoft Graph calls block the asyncio event loop.
5. **Named month-day dates not parsed** — "meeting March 31" silently defaults to today's date.

---

## A) QA Report by Severity

---

### 🔴 CRITICAL

---

#### C-01: Race Condition in Calendar Idempotency Store (Duplicate Event Creation)

**File**: `backend/services/executive_agent_service.py`  
**Lines**: `_execute_calendar_event_creation`, around `_CALENDAR_IDEMPOTENCY_STORE` usage

**Root cause**:  
The idempotency check is a non-atomic read-check-write sequence:
```python
if request_id in _CALENDAR_IDEMPOTENCY_STORE:          # (1) READ
    return cached_result
# ... call API ...                                       # (2) CALL
_CALENDAR_IDEMPOTENCY_STORE[request_id] = event_id      # (3) WRITE
```
Two simultaneous POST /api/agent/chat requests with the same session confirming the same event will *both* pass step (1) simultaneously, *both* call the calendar API, and create two identical events. Python's GIL makes dict reads/writes individually atomic, but the three-step check-call-store sequence is NOT atomic across `await` boundaries.

**User impact**: Duplicate calendar events created silently. User sees two identical events.

**Reproduction path**:
```python
# Two concurrent agent.process_message("yes", ...) calls with identical pending_action
import asyncio
result1, result2 = await asyncio.gather(
    agent1.process_message("yes", user_id="u1"),
    agent2.process_message("yes", user_id="u1"),   # same user, same action
)
# Both schedule calendar event → two provider API calls → two events
```

**Minimal safe fix**: Wrap with `asyncio.Lock`:
```python
_CALENDAR_IDEMPOTENCY_LOCK = asyncio.Lock()

async with _CALENDAR_IDEMPOTENCY_LOCK:
    if request_id in _CALENDAR_IDEMPOTENCY_STORE:
        return cached_result
    # ...call API...
    _CALENDAR_IDEMPOTENCY_STORE[request_id] = event_id
```

---

#### C-02: Microsoft OAuth State = user_id (CSRF Attack Vector)

**File**: `backend/api/integrations.py`  
**Lines**: `microsoft_auth_start` and `_ms_handle_callback`

**Root cause**:  
```python
# microsoft_auth_start:
auth_url = app.get_authorization_request_url(
    scopes=MICROSOFT_SCOPES,
    state=user_id,          # ← PREDICTABLE! user_id is often "default_user"
)
```
The Google OAuth correctly uses `secrets.token_urlsafe(32)` as the state. Microsoft uses the literal `user_id` string. An attacker who knows the `user_id` (typically "default_user") can craft a malicious redirect URI to complete the OAuth flow on behalf of the victim.

**User impact**: OAuth CSRF attack — attacker can link their own Microsoft account tokens to a victim's user_id.

**Reproduction path**: Craft `GET /api/integrations/microsoft/auth/callback?code=<stolen>&state=default_user`.

**Minimal safe fix**: Use the same random state pattern as Google:
```python
state = secrets.token_urlsafe(32)
_oauth_states[state] = {"user_id": user_id, "timestamp": datetime.now()}
# Return state in the auth_url
```

---

#### C-03: `datetime.now() + "Z"` — Calendar List Time Is NOT UTC

**File**: `backend/services/executive_agent_service.py`  
**Lines**: `_handle_calendar_list_events`, `_handle_calendar_read`

**Root cause**:  
```python
now = datetime.now()  # ← NAIVE LOCAL TIME (Europe/Berlin = UTC+1 or UTC+2)
time_min = target.replace(hour=0, ...).isoformat() + "Z"
#                                                    ^^^^ CLAIMS UTC but is LOCAL
```
Appending `"Z"` tells the Google Calendar API "this is UTC". But `datetime.now()` returns local time. For `Europe/Berlin` at UTC+1, midnight local time sent as `00:00Z` means 01:00 local — events from midnight to 01:00 are excluded.

**User impact**: Calendar queries for "today" or "tomorrow" miss events at the start of the day (midnight to UTC-offset). For Berlin (UTC+1), January "today" events from 00:00–01:00 are excluded. During DST (UTC+2) events from 00:00–02:00 are excluded.

**Reproduction path**: Ask "what events do I have today?" at 00:30 Europe/Berlin. The `time_min` sent to Google = `00:30Z` = `01:30 Berlin` → the 00:30 event is not returned.

**Minimal safe fix**: Use `datetime.utcnow()` for UTC-appended strings:
```python
now = datetime.utcnow()  # or datetime.now(timezone.utc)
time_min = target.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
```

---

#### C-04: All Microsoft Graph Calls Block the Event Loop (Synchronous `requests`)

**File**: `backend/api/integrations.py`  
**Function**: `_ms_request()`, called from all `/microsoft/*` endpoints

**Root cause**:  
```python
resp = http_requests.request(method=m, url=url, headers=headers, **kwargs)
```
This is the synchronous `requests` library called inside async FastAPI route handlers. FastAPI is `asyncio`-based; a synchronous HTTP call blocks the entire event loop for the duration of the Graph API call (typically 200–2000ms).

**User impact**: Under any concurrent load (2+ simultaneous requests), all other requests are blocked while one Graph API call is in progress. Voice WebSocket keep-alive pings can be dropped. TTS/STT requests stall.

**Reproduction path**: Open voice mode and trigger a Microsoft calendar operation simultaneously — voice state machine will hang.

**Minimal safe fix**: Use `httpx.AsyncClient` (already used in executive_agent_service.py) or run in `thread_executor`:
```python
import asyncio, functools
async def _ms_request_async(method, endpoint, access_token, user_id=None, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, functools.partial(_ms_request, method, endpoint, access_token, user_id, **kwargs)
    )
```

---

### 🟠 HIGH

---

#### H-01: `pytz.localize()` Called on Already-Aware Datetime → Silent Wrong Timezone or AmbiguousTimeError

**File**: `backend/services/executive_agent_service.py`  
**Lines**: `_execute_calendar_event_creation`

**Root cause**:
```python
start_dt_naive = datetime.fromisoformat(f"{date}T{time_str}:00")
start_dt_aware = tz_obj.localize(start_dt_naive)
```
If `time_str` ever contains a timezone offset (e.g., if a future slot-extractor or NLU change passes "20:00+01:00"), `datetime.fromisoformat()` returns a **timezone-aware** datetime. Calling `pytz.localize()` on an already-aware datetime raises `ValueError: Not naive datetime (tzinfo is already set)` uncaught, causing a 500 error.

Additionally, during DST transition (e.g., 02:30 Europe/Berlin on 26 Oct 2025 is ambiguous), `pytz.localize()` without `is_dst=False` will raise `AmbiguousTimeError` — also uncaught.

**User impact**: 500 error during calendar creation at DST transition times; potential failure if timezone-aware strings ever reach this code path.

**Minimal safe fix**:
```python
if start_dt_naive.tzinfo is not None:
    start_dt_aware = start_dt_naive  # already aware
else:
    try:
        start_dt_aware = tz_obj.localize(start_dt_naive, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        start_dt_aware = tz_obj.localize(start_dt_naive, is_dst=False)  # non-DST
```

---

#### H-02: Google OAuth Tokens Not Re-Saved After Auto-Refresh

**File**: `backend/api/integrations.py`  
**Functions**: All Google API endpoints (`google_calendar_list_events`, `google_calendar_create_event`, `google_gmail_list_messages`, `google_gmail_send`)

**Root cause**:  
```python
credentials = Credentials(
    token=token_data.get("access_token"),
    refresh_token=token_data.get("refresh_token"),
    ...
)
service = build('calendar', 'v3', credentials=credentials)
# Google library auto-refreshes credentials.token if expired
# but: NO token_storage.save_tokens() call after the request
```
After a Google access token expires, the `google-auth` library transparently refreshes it using the refresh_token. BUT the refreshed `credentials.token` is never written back to `token_storage`. Next request loads the same expired token, wastes a network call to refresh again.

**User impact**: Extra network call on every Google API request after token expiry. If `refresh_token` is absent (first possible failure mode), subsequent calls silently fail without a clear "please reconnect" message.

**Minimal safe fix**: After each Google API call:
```python
if credentials.token != token_data.get("access_token"):
    token_data["access_token"] = credentials.token
    if credentials.expiry:
        token_data["expiry"] = credentials.expiry.isoformat()
    token_storage.save_tokens(user_id, "google", token_data)
```

---

#### H-03: Named Month-Day Dates Not Parsed ("March 31", "April 5")

**File**: `backend/utils/slot_extraction.py`  
**Function**: `_extract_date`  
**File**: `backend/services/nlu_service.py`  
**Function**: `_extract_date`

**Root cause**:  
The date extractor only handles:
- "today", "tomorrow", "yesterday", "next week"  
- "next/last/this {weekday}"  
- ISO format `YYYY-MM-DD`
- US format `MM/DD/YYYY`

It does NOT handle:
- "March 31", "April 5", "31 March", "31st of March"
- "the 31st", "March 31st"

**User impact**: "meeting March 31 at 23:30" → date is not extracted → defaults to today. Event is created for today instead of March 31.

**Reproduction path**: Say "create a meeting on March 31 at 23:30". Date = today (wrong).

**Minimal safe fix**: Add `dateutil.parser.parse` with a fallback:
```python
from dateutil import parser as dateutil_parser
try:
    parsed = dateutil_parser.parse(message, fuzzy=True, default=datetime.now())
    return parsed.strftime("%Y-%m-%d")
except (ValueError, OverflowError):
    pass
```
Or add regex for common month patterns:
```python
months = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
           'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\b|\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?\b', message_lower)
```

---

#### H-04: Bare Weekday Not Parsed ("meeting on Friday")

**File**: `backend/utils/slot_extraction.py`  
**Function**: `_extract_date`

**Root cause**:  
The weekday loop only handles "next {day}", "last {day}", "this {day}". It does NOT handle bare "friday" or "on friday".

**User impact**: "meeting on Friday at 14:30" → date not extracted → defaults to today.

**Minimal safe fix**: Add a bare-weekday fallback that resolves to the *next upcoming* occurrence:
```python
for day_name, day_num in weekdays.items():
    if re.search(r'\b' + day_name + r'\b', message_lower):  # bare weekday
        days_ahead = (day_num - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # "Friday" when today is Friday = next Friday
        return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
```

---

#### H-05: OAuth State Expiry NOT Checked at Callback Time (Only at Restart)

**File**: `backend/api/integrations.py`  
**Function**: `google_auth_callback`

**Root cause**:  
`_cleanup_expired_oauth_states()` is only called from `google_auth_start`. If a state was created more than 10 minutes ago and `google_auth_start` was never called again, the old state can still be used at `google_auth_callback`:
```python
if state not in _oauth_states:    # ← TTL NOT checked
    raise HTTPException(...)
user_data = _oauth_states.pop(state)
```

**Minimal safe fix**: Check TTL at callback time:
```python
user_data = _oauth_states.get(state)
if not user_data:
    raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
age = (datetime.now() - user_data["timestamp"]).total_seconds()
if age > _OAUTH_STATE_TTL_SECONDS:
    _oauth_states.pop(state, None)
    raise HTTPException(status_code=400, detail="OAuth state expired. Please restart the auth flow.")
_oauth_states.pop(state)
```

---

#### H-06: `ExecutiveAgent.sessions` Dict Has No TTL Eviction (Memory Leak)

**File**: `backend/services/executive_agent_service.py`  
**Lines**: `ExecutiveAgent.sessions` (class variable)

**Root cause**:  
Every unique `session_id` creates a `ConversationMemory` object in `ExecutiveAgent.sessions` that is never removed unless the `DELETE /api/agent/session/{session_id}` endpoint is called explicitly. Each session stores up to 10 messages + task history. In a long-running server with many users, this leaks indefinitely.

**User impact**: Memory grows unbounded over time; server becomes unresponsive under long-running deployment.

**Minimal safe fix**: Add background TTL cleanup:
```python
SESSION_TTL_HOURS = 24

@classmethod
def cleanup_stale_sessions(cls, max_age_hours: int = SESSION_TTL_HOURS):
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    stale = [sid for sid, mem in cls.sessions.items() if mem.last_activity < cutoff]
    for sid in stale:
        del cls.sessions[sid]
    if stale:
        logger.info("[SESSION] Cleaned up %d stale sessions", len(stale))
```
Call from a background task or periodically from a request handler.

---

#### H-07: Outlook Mail Send Never Returns `message_id`

**File**: `backend/api/integrations.py`  
**Function**: `microsoft_mail_send`

**Root cause**:  
`/me/sendMail` returns HTTP 202 with empty body. `_ms_request` returns `{}` for empty responses. `MailSendResponse(success=True, message_id=None)` is returned. In `executive_agent_service._execute_email_send`, `message_id = result_data.get("message_id")` is always `None` for Outlook.

Unlike Google Calendar (where missing `event_id` triggers a failure), there is NO equivalent truthfulness check for Outlook email sends. The backend claims `success=True` with no machine-readable proof.

**User impact**: Users/integrations cannot verify an Outlook email was actually sent. No audit trail with message ID.

**Minimal safe fix**: For Outlook, use `/me/messages` + `$sendMail` (draft-then-send) or the `/me/messages/{id}/send` flow which returns the message ID. Or at minimum log a warning that Outlook `sendMail` provides no message_id.

---

### 🟡 MEDIUM

---

#### M-01: `_CALENDAR_IDEMPOTENCY_STORE` Grows Without Bound

**File**: `backend/services/executive_agent_service.py`

**Root cause**: The dict `_CALENDAR_IDEMPOTENCY_STORE: Dict[str, str] = {}` is never evicted.

**Minimal safe fix**: Use a simple TTL decorator or cap to last 10,000 entries.

---

#### M-02: `credentials.json` Contains `client_secret` Written to Disk

**File**: `backend/api/integrations.py`  
**Function**: `get_credentials_json_path`

**Root cause**:  
```python
credentials_data = {"web": {"client_id": ..., "client_secret": ..., ...}}
creds_path.write_text(json.dumps(credentials_data, indent=2))
```
The `client_secret` is written to `backend/credentials.json`. If this file ends up in a git repo or shared volume, the secret leaks.

**Minimal safe fix**: Check `.gitignore` includes `credentials.json`. Add a startup check: if `credentials.json` exists and is readable by world, log a warning. Better: construct the `Flow` object directly from credentials dict without writing to disk.

---

#### M-03: `TokenStorage` Generates New Fernet Key on Every Cold Start

**File**: `backend/utils/token_storage.py`

**Root cause**:  
```python
if not key:
    key = Fernet.generate_key().decode()
    logger.warning(f"Generated key (save this in .env): TOKEN_ENCRYPTION_KEY={key}")
```
On every cold start without `TOKEN_ENCRYPTION_KEY` set (e.g., Docker container restart), a new key is generated. All previously encrypted tokens become permanently unreadable.

**User impact**: All users are logged out on every container/process restart in misconfigured deployments.

**Minimal safe fix**: Do NOT generate a key silently. Raise a startup error or use a deterministic fallback:
```python
if not key:
    raise RuntimeError(
        "TOKEN_ENCRYPTION_KEY environment variable is required. "
        "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )
```

---

#### M-04: Voice Mode `_session_registry` Not Locked for Concurrent Connections

**File**: `backend/api/voice_mode.py`

**Root cause**: Same `session_id` can have two concurrent WebSocket connections (reconnect scenario). The new connection unconditionally overwrites `_session_registry[session_id]`, silently resetting the `interrupted` flag of any ongoing session.

**Minimal safe fix**: Use `asyncio.Lock` per session, or reject new connections if one already exists for the same session_id.

---

#### M-05: `CORS allow_origins=["*"]` with Production Credentials

**File**: `backend/main.py`

**Root cause**: `allow_origins=["*"]` is appropriate for development but in production allows any website to make cross-origin requests to the backend. Comment says "In production, specify allowed origins" but no mechanism enforces this.

**Minimal safe fix**: Read from `ALLOWED_ORIGINS` env var with a fail-safe:
```python
origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
```

---

#### M-06: `tz_name` Variable Overwritten Mid-Function (Bug in Idempotency)

**File**: `backend/services/executive_agent_service.py`  
**Lines**: `_execute_calendar_event_creation`

**Root cause**:  
```python
tz_name = os.getenv("TIMEZONE", "Europe/Berlin")    # ← line ~275
# ... many lines later ...
tz_name = os.getenv("TIMEZONE", "UTC")              # ← line ~305 (used for idempotency hash)
```
`tz_name` is set twice: once with default `"Europe/Berlin"` for localization, then once with default `"UTC"` for the idempotency hash. These two values CAN DIFFER if `TIMEZONE` env var is not set:
- `start_dt_aware` uses `Europe/Berlin` timezone
- But `request_id` hash uses `UTC` as timezone_name

This means the idempotency hash uses `"UTC"` even though the event was created with `"Europe/Berlin"`. If the code is ever refactored, two identical-feeling requests could get different hashes.

**Minimal safe fix**: Use one variable throughout:
```python
tz_name = os.getenv("TIMEZONE", "Europe/Berlin")
# use tz_name everywhere including the idempotency hash
```

---

#### M-07: `_handle_calendar_list_events` Time Filtering Done Client-Side (Incomplete)

**File**: `backend/services/executive_agent_service.py`

**Root cause**:
```python
# Requests max_results=15 from Google, then client-side filters by time_max
if time_max:
    filtered = [...]
```
If there are >15 events before `time_max` (e.g., a heavy calendar day), some will be silently excluded.

**Minimal safe fix**: Pass `time_max` as a query parameter to the Google Calendar API endpoint, which supports `time_max` natively.

---

#### M-08: `SlotExtractor._extract_location` Only Matches Title-Case Locations

**File**: `backend/utils/slot_extraction.py`

**Root cause**: 
```python
r'\b(?:at|in|@)\s+([A-Z][A-Za-z0-9\s]+...)'  # requires UPPERCASE start
```
"at home", "in meeting room b", "@ zoom" → all fail.

---

### 🔵 LOW

---

#### L-01: `_CALENDAR_IDEMPOTENCY_STORE` Uses `tz_name = os.getenv("TIMEZONE", "UTC")` (Inconsistency with Creation)

See M-06. The default differs from the timezone used for building the datetime.

---

#### L-02: No Structured Logging of `session_id` / `request_id` Across Voice Pipeline Steps

**File**: `backend/api/voice_mode.py`

The `ws_session_id` is a randomly-generated 8-char ID per WebSocket connection, but the `session_id` (shared with text chat) is not included in AI/TTS latency log entries. Makes end-to-end tracing difficult.

---

#### L-03: `ScopeChangedError` Has No Auto-Recovery Path

**File**: `backend/utils/token_storage.py`

When scope hash changes, `load_tokens()` raises `ScopeChangedError`. Only `google_calendar_list_events` and similar endpoints would propagate this to users, but most callers catch `Exception` broadly and this error is logged as a generic failure.

---

#### L-04: Session `ConversationMemory.created_at` and `last_activity` Use Naive `datetime.now()`

**File**: `backend/services/executive_agent_service.py`

Naive datetime comparisons (no timezone) can behave incorrectly across DST transitions if the server runs continuously.

---

#### L-05: `_extract_duration` Regex Can Match Unrelated Text

**File**: `backend/utils/slot_extraction.py`

"Schedule 2 hours of training" → duration=120. If "2 hours" is part of the event description/title, duration is incorrectly set.

---

#### L-06: `ConversationMemory.history` has `MAX_HISTORY = 10` but `action_history` keeps last 20

These limits are reasonable but undocumented. No tests validate these limits.

---

#### L-07: Debug endpoints expose JWT internals in `/microsoft/token-debug` and `/microsoft/debug/me`

These are intentional diagnostic tools, but they should be gated behind an admin API key or disabled in production.

---

#### L-08: `_ms_auth_from_helper` imported but also `_ms_authority` defined locally in integrations.py

**File**: `backend/api/integrations.py`

```python
from utils.ms_token import get_valid_ms_token, _refresh_ms_token, _ms_authority as _ms_auth_from_helper
# ...
def _ms_authority() -> str:  # ← locally defined
```
Two different `_ms_authority` functions. A refactor that changes one won't automatically change the other. They currently use the same logic, but this is a maintenance bomb.

---

## B) Confirmed Fixes Summary

| ID | Fix | Status |
|----|-----|--------|
| C-01 | `asyncio.Lock` for idempotency store | ✅ Implemented |
| C-02 | Random state token for Microsoft OAuth | ✅ Implemented |
| C-03 | `datetime.utcnow()` for calendar list time_min | ✅ Implemented |
| H-01 | Guard `pytz.localize()` against aware datetimes + AmbiguousTimeError | ✅ Implemented |
| H-03 | Named month-day date parsing ("March 31") | ✅ Implemented |
| H-04 | Bare weekday date parsing ("meeting on Friday") | ✅ Implemented |
| H-05 | TTL check at OAuth callback time | ✅ Implemented |
| M-03 | Raise on missing `TOKEN_ENCRYPTION_KEY` | ✅ Implemented (Warning mode for backward compat) |
| M-06 | Fix `tz_name` double-definition inconsistency | ✅ Implemented |

---

## C) Remaining Architectural Risks

1. **Single-process in-memory session state** (`ExecutiveAgent.sessions`, `_CALENDAR_IDEMPOTENCY_STORE`, `_session_registry`): These work for single-instance deployments. Scale-out (multiple workers) will break them. Replace with Redis before horizontal scaling.

2. **Synchronous `requests` library in async handlers**: All Microsoft Graph calls block the event loop. Replace with `httpx.AsyncClient` or `run_in_executor`.

3. **No distributed lock for OAuth flows**: The `asyncio.Lock` added for idempotency is per-process. Multi-worker deployments can still duplicate calendar events.

4. **Google credentials auto-refresh not persisted**: Google `Credentials` may auto-refresh silently without updating `token_storage`. Long-running sessions will repeatedly refresh on each request.

5. **Outlook email has no `message_id` proof**: `sendMail` returns 202 (empty). Truthfulness check is weaker than calendar events.

6. **`BACKEND_URL=http://localhost:8000` self-loop**: In Kubernetes/Docker deployments with multiple replicas, agent calls itself via the wrong URL. Should resolve to the service name.

---

## D) Recommended Next Backend Priorities

1. **[P0]** Replace `_CALENDAR_IDEMPOTENCY_STORE`, `ExecutiveAgent.sessions`, and `_session_registry` with Redis for multi-worker safety.
2. **[P0]** Replace `requests` with `httpx.AsyncClient` in all Microsoft Graph calls.
3. **[P1]** Add `dateutil` for robust named-date parsing (covers "March 31", "Next Friday", etc.).
4. **[P1]** Add Google token refresh persistence after auto-refresh.
5. **[P1]** Restrict `CORS allow_origins` via environment variable.
6. **[P2]** Add session TTL eviction for `ExecutiveAgent.sessions`.
7. **[P2]** Gate debug endpoints (`/token-debug`, `/debug/me`) behind admin API key.
8. **[P2]** Add Outlook `message_id` truthfulness check (draft-send flow).
9. **[P3]** Consolidate the two `_ms_authority()` functions (integrations.py vs ms_token.py).
10. **[P3]** Add `python-dateutil` based fallback in `_extract_date` for all natural date formats.
