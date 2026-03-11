# AI Audit Changelog — OrganAIzer_Services

Complete record of every change made during the AI code-audit and bug-fix
sessions (groups 1–10).  Each entry describes: the file changed, what was
fixed, and why.

---

## Group 1 — Security: Remove Hardcoded API Key Fallbacks, OAuth TTL, MS Token

| File | What changed | Why |
|------|-------------|-----|
| `backend/core/config.py` | Removed hardcoded fallback values for `OPENROUTER_API_KEY` and similar secrets; server now raises a clear `ImproperlyConfigured` error if the variable is missing | Hardcoded keys were a security risk — they could be committed to git and exposed in logs |
| `backend/utils/ms_token.py` | Added token-expiry TTL check before returning cached Microsoft access tokens | Cached Microsoft tokens were being returned after expiry, causing 401 errors on API calls |
| `backend/api/integrations.py` | Removed hardcoded OAuth redirect URI fallback | Hardcoded URIs break in production; must be read from environment |

---

## Group 2 — Calendar: Timezone Fix + PATCH/DELETE Endpoints

| File | What changed | Why |
|------|-------------|-----|
| `backend/api/integrations.py` | Added `PATCH /calendar/events/{id}` and `DELETE /calendar/events/{id}` endpoints for both Google and Microsoft providers | Calendar events could only be created, not updated or deleted |
| `backend/services/providers/microsoft_provider.py` | Applied user timezone from `TIMEZONE` env var when creating/reading calendar events | Events were always created in UTC, which shifted displayed times for non-UTC users |
| `backend/services/providers/base.py` | Standardised `CalendarEvent` dataclass to include timezone-aware `start`/`end` datetimes | Inconsistent datetime handling between Google and Microsoft caused formatting bugs |

---

## Group 3 — Envelope: Standardised Response Envelope

| File | What changed | Why |
|------|-------------|-----|
| `backend/models/common.py` | Added `APIResponse` envelope model with `success`, `data`, `error`, `request_id` fields | API responses had no consistent shape — clients had to guess whether a call succeeded |
| `backend/middleware/correlation_id.py` | Added `X-Request-ID` middleware that generates a UUID per request and injects it into response headers and logs | Made request tracing possible across distributed logs |
| `backend/api/executive_agent.py` | Wrapped all agent responses in the standardised `APIResponse` envelope | Executive agent endpoint returned raw dicts that differed per intent |

---

## Group 4 — Voice: Strip Emojis from TTS, Dual Calendar+Mail Provider in Voice WS

| File | What changed | Why |
|------|-------------|-----|
| `backend/services/tts_service.py` | Added `_strip_markdown_and_emoji()` before passing text to TTS engine | gTTS and edge-tts would speak emoji Unicode names ("sparkles", "checkmark") aloud, producing garbled audio |
| `backend/api/voice_mode.py` | Added `calendar_provider` and `mail_provider` query parameters to the WebSocket endpoint | Voice mode only accepted a single `provider` field, so it was impossible to use Gmail for email and Google Calendar separately |
| `backend/utils/text_processing.py` | Added `strip_markdown()` utility; removes `**bold**`, backticks, `### headings`, bullet markers, and URLs | Markdown syntax was being spoken literally during voice responses |

---

## Group 5 — Agent: Async HTTP, Decline-Optional Flow, History Alignment, Log Levels

| File | What changed | Why |
|------|-------------|-----|
| `backend/services/executive_agent_service.py` | Replaced all `requests.post/get` calls with `httpx.AsyncClient` | Sync HTTP blocked the async event loop, causing apparent hangs and timeouts |
| `backend/services/executive_agent_service.py` | Added `_handle_decline_optional()` that re-dispatches to the workflow handler rather than dead-ending | "No location" / "no end time" responses left the task stuck — agent never progressed to confirmation |
| `backend/services/executive_agent_service.py` | Fixed `action_history` alignment: only record completed events after confirmed HTTP 2xx | History was recording events that failed at the API level, leading to false "already done" idempotency responses |
| `backend/core/logging_config.py` | Promoted key agent decision log lines from `DEBUG` to `INFO`; demoted internal slot-merge details to `DEBUG` | Production logs were either completely silent or overwhelmingly noisy |

---

## Group 6 — Email: Reply Threading for Gmail+Outlook, Improved Sender Filter

| File | What changed | Why |
|------|-------------|-----|
| `backend/services/providers/microsoft_provider.py` | Added `reply_to_id` field to mail-send payload, which sets `In-Reply-To` and `References` headers for Outlook | Replied emails were sent as new threads instead of continuing the conversation |
| `backend/api/integrations.py` | Added `thread_id` to Gmail send endpoint; maps to `threadId` in the Gmail API payload | Same Gmail threading issue — replies broke the thread |
| `backend/utils/slot_extraction.py` | Rewrote `extract_email_read_slots` sender-filter logic: checks for explicit email address first, then name with stricter word-boundary regex | Sender filter was capturing time words ("today", "last week") as part of the sender name |

---

## Group 7 — Cleanup: Document MODEL Env Var, Add timeMax to Calendar List

| File | What changed | Why |
|------|-------------|-----|
| `backend/.env.example` | Added `MODEL=` documentation entry with explanation of which OpenRouter model to use | Developers didn't know this variable existed; server silently used a default |
| `backend/api/integrations.py` | Added `time_max` query parameter to `GET /calendar/events`; passed through to Google and Microsoft APIs | Calendar list returned all future events with no upper bound, causing very large responses |
| `backend/core/config.py` | Added `MODEL` to the validated config list with a sane default | `MODEL` was read with `os.getenv()` directly, bypassing the config validation layer |

---

## Group 8 — Voice Latency: Replace gTTS with edge-tts

| File | What changed | Why |
|------|-------------|-----|
| `backend/services/tts_service.py` | **Primary path**: replaced `gTTS` with `edge-tts` (`EdgeTTS.Communicate`); runs fully async, writes to a temporary MP3 file, streams result | `gTTS` took 5–7 seconds per synthesis request, making the total voice round-trip 26 s.  `edge-tts` is ~200 ms (Microsoft Edge TTS, free, no API key required) |
| `backend/services/tts_service.py` | **Fallback path**: kept `gTTS` as a fallback if `edge-tts` raises any exception | Ensures the voice pipeline never fully breaks if the Edge TTS CDN is unreachable |
| `backend/requirements.txt` | Added `edge-tts>=6.1.0`; moved `gTTS` to a comment-annotated fallback section | Documents the new dependency clearly; `gTTS` remains listed for the fallback path |

---

## Group 9 — STT: Title Cleanup After STT + Title Correction in NLU

### Problem
Two live-log bugs:
1. Whisper misheard "call it from 1011" → extracted raw STT including "?" as the title.
2. User said "change the title to Front and 1000 and 1" → NLU only patched provider and date; the title correction was completely missed because there was no pattern for this phrase.

### Changes

| File | What changed | Why |
|------|-------------|-----|
| `backend/utils/slot_extraction.py` | Added `_clean_and_validate_title(title)` static method: strips leading/trailing punctuation artefacts (`? . , ! ; :`), then flags suspicious titles (starts with "from", only digits, contains "?", starts with a question word, too short) | Whisper STT sometimes outputs garbled titles with punctuation or question-word patterns that are clearly mishears |
| `backend/utils/slot_extraction.py` | In `extract_calendar_slots()`: after extracting any title (Phase A or B), run it through `_clean_and_validate_title()`; set `title_needs_confirmation = True` + `title_suspicious_reason` in the slot dict when suspicious | Gives the executive agent structured data to act on rather than just silently using a wrong title |
| `backend/services/nlu_service.py` | Added patterns `change\s+(?:the\s+)?title\s+to\s+(.{1,80})$`, `set\s+(?:the\s+)?title\s+(?:to\s+)?(.{1,80})$`, `update\s+(?:the\s+)?title\s+(?:to\s+)?(.{1,80})$` to `_extract_title()` | Live log showed "change the title to Front and 1000 and 1" was never matched by the old pattern list, so the title update was silently dropped |
| `backend/services/executive_agent_service.py` | In `_handle_calendar_event_creation()`: after title defaulting, check `title_needs_confirmation` flag; if set and not yet confirmed, set `last_question_type = "title_confirm"` and ask user to confirm or re-state the title | Previously a suspicious STT title went straight to the confirmation message with the wrong title |

---

## Group 10 — Agent Stuck State: Graceful Edit Transition, Prevent Loop

### Problem
Live log: User said "No, I would like you to edit this event" while task was in `awaiting_confirmation`.
- `_has_correction_words()` returned False (didn't know "edit", "modify", "would like") → routed as CANCEL instead of MODIFY_DRAFT.
- `_handle_modify_draft()` got an NLU result with no updates → returned the same clarification message again → infinite loop.

### Changes

| File | What changed | Why |
|------|-------------|-----|
| `backend/services/nlu_service.py` | In `_has_correction_words()`: added "edit", "modify", "update", "adjust", "fix", "i want", "i'd like", "would like", "i would like" to the trigger list | These edit-intent phrases after "no" must be classified as MODIFY_DRAFT, not CANCEL |
| `backend/services/executive_agent_service.py` | Added `last_clarification_message: Optional[str] = None` field to `ConversationMemory` | Needed to detect when the same clarification is about to be sent twice (loop detection) |
| `backend/services/executive_agent_service.py` | In `_handle_modify_draft()`, when NLU finds no updates: added `_EDIT_RE` regex check for edit-intent words; if matched → clears `pending_action`, transitions task status to `collecting`, asks "What would you like to change?" | Agent was stuck — it returned a generic "I'm not sure what you'd like to change" message on a loop without ever transitioning state |
| `backend/services/executive_agent_service.py` | Loop prevention: if `last_clarification_message` equals the ask we're about to send, replace it with a more detailed example-rich prompt | Prevents infinite identical clarification loop that was seen in live logs |
| `backend/services/executive_agent_service.py` | When real updates are found in `_handle_modify_draft()`, reset `last_clarification_message = None` | Clears the loop-detection state once the user successfully provides a correction |
| `backend/services/executive_agent_service.py` | Added `import re` at module level | Required for `_EDIT_RE` regex — was missing, would have caused `NameError` |

---

## Summary Table

| Group | Commit | Files Changed |
|-------|--------|--------------|
| 1 | `fix(security): remove hardcode API key fallbacks, OAuth TTL, MS token` | `core/config.py`, `utils/ms_token.py`, `api/integrations.py` |
| 2 | `fix(calendar): timezone + PATCH/DELETE endpoints` | `api/integrations.py`, `services/providers/microsoft_provider.py`, `services/providers/base.py` |
| 3 | `feat(envelope): add standardized response envelope` | `models/common.py`, `middleware/correlation_id.py`, `api/executive_agent.py` |
| 4 | `fix(voice): strip emojis from TTS, add dual calendar+mail provider to voice WS` | `services/tts_service.py`, `api/voice_mode.py`, `utils/text_processing.py` |
| 5 | `fix(agent): async HTTP, decline-optional flow, history alignment, log levels` | `services/executive_agent_service.py`, `core/logging_config.py` |
| 6 | `feat(email): reply threading for Gmail+Outlook, improved sender filter` | `services/providers/microsoft_provider.py`, `api/integrations.py`, `utils/slot_extraction.py` |
| 7 | `chore(cleanup): document MODEL env var, add timeMax to calendar list` | `.env.example`, `api/integrations.py`, `core/config.py` |
| 8 | `fix(tts): replace gTTS with edge-tts for faster voice responses` | `services/tts_service.py`, `requirements.txt` |
| 9 | `fix(stt): title cleanup after STT + title correction in NLU` | `utils/slot_extraction.py`, `services/nlu_service.py`, `services/executive_agent_service.py` |
| 10 | `fix(agent): graceful edit transition, prevent stuck confirmation loop` | `services/nlu_service.py`, `services/executive_agent_service.py` |
