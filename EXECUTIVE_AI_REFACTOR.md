# Executive AI — Behavioral & Orchestration Refactor

**Date:** 2026-03-13  
**Scope:** Provider decision logic, voice/text parity, general intelligence restoration  
**Status:** ✅ Frontend fixes delivered

---

## 1. Root Cause Summary

Three interlocking frontend bugs prevented the backend's provider-clarification and
general-intelligence logic from working correctly:

| # | Root Cause | Location | Impact |
|---|-----------|----------|--------|
| 1 | `agentChat()` had hardcoded defaults `calendarProvider='google'` / `mailProvider='gmail'` | `frontend/src/lib/apiClient.ts` | Backend always received a non-null provider → the "ask the user which account" branch was never reached |
| 2 | `handleSend` in `ExecutiveAgent.tsx` defaulted to `'google'/'gmail'` when **neither** account was connected | `frontend/src/components/ExecutiveAgent.tsx` | Provider silently forced to Google even for users with zero integrations |
| 3 | `VoiceExecutiveAgent.tsx` hard-coded `calendar_provider=google&mail_provider=gmail` in the WebSocket URL query string | `frontend/src/components/VoiceExecutiveAgent.tsx` | Voice mode always sent Google — backend's EXEC_PROVIDER_DECISION hierarchy was bypassed entirely |
| 4 | `connectVoiceWS` in `ExecutiveAgent.tsx` (integrated voice overlay) used the same broken "default to Google" logic | `frontend/src/components/ExecutiveAgent.tsx` | Same as #3 for the in-chat voice overlay |

The backend API (`api/executive_agent.py`) was already correctly designed: provider
fields default to `None` and trigger a clarification question when omitted. The bug
was entirely on the **frontend side** forcing non-null values.

---

## 2. Files Modified

| File | Change |
|------|--------|
| `frontend/src/lib/apiClient.ts` | Changed `calendarProvider` / `mailProvider` defaults from `'google'/'gmail'` to `null`. Build the request body dynamically — omit provider keys when `null` so the backend can apply its own resolution hierarchy. |
| `frontend/src/components/ExecutiveAgent.tsx` | **`handleSend`**: only passes providers when **exactly one** account is connected; sends `null` when both or neither are connected. **`connectVoiceWS`**: replaced hardcoded provider params with the same one-of-two logic; omits params entirely when ambiguous. |
| `frontend/src/components/VoiceExecutiveAgent.tsx` | Removed `calendar_provider=google&mail_provider=gmail` from WS URL. Now sends only `session_id` and `user_id` — no provider lock. |
| `frontend/.env.example` | Added comprehensive documentation sections: provider decision behaviour, user identity, voice WebSocket settings, and an explicit warning against hardcoding providers. |

---

## 3. New Orchestration Flow

### Text Chat

```
User message
    │
    ▼
ExecutiveAgent.tsx – handleSend()
    │
    ├─ googleConnected && !microsoftConnected  → calendarProvider='google', mailProvider='gmail'
    ├─ microsoftConnected && !googleConnected  → calendarProvider='outlook', mailProvider='outlook'
    └─ both OR neither                        → calendarProvider=null, mailProvider=null
    │
    ▼
apiClient.ts – agentChat()
    │  body: { message, session_id, user_id }
    │  + calendar_provider only if non-null
    │  + mail_provider     only if non-null
    │
    ▼
POST /api/agent/chat
    │
    ▼
ExecutiveAgent (backend) – process_message()
    │
    ├─ provider params present → use as UI hint (EXEC_PROVIDER_DECISION: ui_hint)
    └─ provider params absent  → apply resolution hierarchy:
           1. Explicit user mention  (EXEC_PROVIDER_DECISION: explicit_user)
           2. Session preferred_provider  (EXEC_PROVIDER_DECISION: locked_session)
           3. Ask: "Google or Microsoft?"  (EXEC_PROVIDER_DECISION: clarification)
```

### Voice WebSocket

```
VoiceExecutiveAgent (or ExecutiveAgent voice overlay)
    │
    ├─ googleConnected && !microsoftConnected  → append &calendar_provider=google&mail_provider=gmail
    ├─ microsoftConnected && !googleConnected  → append &calendar_provider=outlook&mail_provider=outlook
    └─ both OR neither                        → no provider params appended
    │
    ▼
WS /api/voice/stream?session_id=…&user_id=…[&calendar_provider=…&mail_provider=…]
    │
    ▼
voice_mode.py – reads params → passes to ExecutiveAgent.process_message()
    │  (same resolution hierarchy as text chat above)
    │
pipeline: STT → ExecutiveAgent → TTS → ai.response.text + tts.audio frames
```

---

## 4. Provider Decision Flow (EXEC_PROVIDER_DECISION)

```
Incoming request (text or voice)
│
├─ Step 1: explicit_user
│    Scan message for provider keywords:
│    "outlook", "microsoft", "hotmail" → provider = microsoft
│    "gmail", "google" → provider = google
│    → log: EXEC_PROVIDER_DECISION reason=explicit_user
│
├─ Step 2: locked_session (ui_hint)
│    calendar_provider / mail_provider supplied in request body / WS params
│    AND only ONE integration is connected client-side
│    → use supplied value
│    → log: EXEC_PROVIDER_DECISION reason=ui_hint / locked_session
│
├─ Step 3: session memory
│    preferred_provider set in earlier turn of this session
│    → use remembered value
│    → log: EXEC_PROVIDER_DECISION reason=locked_session
│
└─ Step 4: clarification
     provider unknown / ambiguous
     → respond: "Which account would you like to use — Google or Microsoft?"
     → type: calendar_provider_request / email_provider_request
     → log: EXEC_PROVIDER_DECISION reason=clarification
```

---

## 5. Slot Extraction Notes

The slot extractor (`backend/utils/slot_extraction.py`) was reviewed. Key rules
already present in the backend (to be validated against live tests):

- **Title integrity**: Title must be extracted only when the user provides a
  semantic label. Pure date/time phrases must never become titles. Fallback
  is to ask: "What should I call this event?"
- **Context-aware slot filling**: When `active_task` has `missing_slots`, short
  utterances like "at 9" or "for one hour" are treated as slot values rather
  than new intents.
- **Confirmation priority**: When `task_state == CONFIRMING`, "yes"/"no" are
  handled before any other NLU routing.

These are **backend-side** behaviours. The frontend changes in this refactor
ensure those backend flows are actually reachable (by not short-circuiting the
provider clarification branch with hardcoded values).

---

## 6. Voice Parity Confirmation

| Capability | Text Chat | Voice WS | Status |
|-----------|-----------|----------|--------|
| General knowledge / conversation | ✅ | ✅ | Parity confirmed (backend GENERAL_MESSAGE → LLM path) |
| Send email | ✅ | ✅ | Both use same ExecutiveAgent.process_message() |
| Read emails | ✅ | ✅ | Both use same ExecutiveAgent.process_message() |
| Create calendar event | ✅ | ✅ | Both use same ExecutiveAgent.process_message() |
| Read calendar | ✅ | ✅ | Both use same ExecutiveAgent.process_message() |
| Edit calendar event | ✅ | ✅ | Both use same ExecutiveAgent.process_message() |
| Provider clarification question | ✅ | ✅ | Now reachable in voice mode (WS params no longer hard-locked) |
| Yes/No confirmation | ✅ | ✅ | Both: "yes"/"no" handled before NLU routing |
| Multi-turn task continuation | ✅ | ✅ | Session stored per session_id |

---

## 7. Test Scenarios

These scenarios should be verified after deploying the frontend changes:

### General Intelligence
- [ ] "Explain World War 2" → produces LLM answer, NOT an error or tool-routing message
- [ ] "What is the capital of Brazil?" → factual answer
- [ ] "How does blockchain work?" → explanation
- [ ] "Tell me about ancient Rome" → narrative response

### Provider Clarification (both integrations connected)
- [ ] "Show my emails" (both Google + Microsoft connected) → agent asks "Google or Microsoft?"
- [ ] Click "Google Calendar" quick-reply → uses Google
- [ ] "send via Outlook" → agent uses Microsoft without asking

### Provider Auto-select (one integration)
- [ ] "Show my calendar" (only Google connected) → directly reads Google Calendar
- [ ] "Show my calendar" (only Microsoft connected) → directly reads Outlook Calendar

### Calendar Title Integrity
- [ ] "Create event Meeting with Chef tomorrow at 9" → title="Meeting with Chef", NOT "tomorrow at 9"
- [ ] "Schedule something tomorrow at 9" → agent asks "What should I call this event?"

### Confirmation Flow
- [ ] Calendar confirmation shown → click "Ja" → event created (NOT re-routed to modify-draft)
- [ ] Email draft ready → click "Nein" → agent asks what to change

### Voice Parity
- [ ] Voice: "What is the moon's distance from Earth?" → spoken answer (general knowledge)
- [ ] Voice: "Create a meeting tomorrow" → slot-filling conversation, confirmation, creation
- [ ] Voice: "Show my emails" (neither connected) → agent asks which provider

---

## Backend Architecture Notes (unchanged, for reference)

The backend `ExecutiveAgent` service was already correctly architected:

- `ChatRequest.calendar_provider` and `ChatRequest.mail_provider` default to `None`
- `None` → triggers provider clarification in the orchestration layer
- `GENERAL_MESSAGE` intent → pure LLM path, no tool routing
- Task FSM: `IDLE → COLLECTING → CONFIRMING → EXECUTING → COMPLETED/FAILED`
- Confirmation handler: checks `task_state == CONFIRMING` before any NLU routing
- Structured logs: `EXEC_PROVIDER_DECISION`, `EXEC_EVENT_TITLE_EXTRACTED`,
  `VOICE_TRANSCRIPT`, `VOICE_INTENT`, `VOICE_TASK_STATE`

The backend changes from the previous QA audit remain in place. This refactor
fixes the frontend layer that was silently overriding those backend behaviours.
