# OrganAIzer Services – Architecture

## System Overview

OrganAIzer Services is a **Python FastAPI** backend that powers an AI-driven productivity platform. The system exposes a unified REST API consumed by:

- A **React/Vite single-page application** (frontend)
- A **Chrome Extension** (OrganAIzer Extension)
- Any REST-capable client

The central intelligence is the **Executive AI Agent** — a single, stateful, session-aware conversational agent that orchestrates all high-value actions: email management, calendar management, voice interaction, and general AI tasks.

---

## Backend Structure

```
backend/
├── main.py                  # FastAPI app entry point; registers all routers
├── core/
│   ├── config.py            # Environment-based configuration (singleton)
│   ├── error_handling.py    # Centralized exception handlers
│   ├── logging_config.py    # Structured JSON logging setup
│   └── middleware.py        # Request/response logging middleware
├── api/                     # Thin HTTP layer — request parsing, response formatting
│   ├── executive_agent.py   # Executive AI chat, session management
│   ├── integrations.py      # Google + Microsoft OAuth, Calendar, Gmail, Outlook
│   ├── voice_mode.py        # Realtime voice WebSocket endpoint
│   ├── stt.py               # Speech-to-Text endpoint
│   ├── tts.py               # Text-to-Speech endpoint
│   ├── chat.py              # Direct LLM chat (OpenRouter)
│   ├── image_gen.py         # Image generation endpoints
│   ├── youtube.py           # YouTube transcription
│   ├── video.py             # Unified video transcription
│   ├── document.py          # Document upload, summarization, Q&A
│   ├── translation.py       # Multi-language translation
│   └── knowledge_base.py    # RAG / semantic search
├── services/                # Business logic; service layer
│   ├── executive_agent_service.py  # Core Executive AI brain
│   ├── stt_service.py       # Google STT wrapper
│   ├── tts_service.py       # Google TTS wrapper
│   ├── image_gen_service.py # Gemini/Vertex image generation
│   ├── youtube_service.py   # Video download + transcription
│   ├── nano_banana_service.py # LLM-powered summarize/translate (Chrome ext)
│   └── providers/           # Provider abstraction layer
│       ├── base.py          # Abstract provider interface
│       └── microsoft_provider.py  # Microsoft Graph API wrapper
├── utils/
│   ├── intent_router.py     # Deterministic intent classification (pre-LLM)
│   ├── slot_extraction.py   # Semantic slot extraction for email/calendar tasks
│   ├── token_storage.py     # Secure OAuth token persistence
│   └── user_settings.py     # Per-user configuration store
├── models/                  # Pydantic request/response schemas
├── config/
│   └── google_scopes.py     # Authoritative Google OAuth scope definition
└── middleware/
    └── correlation_id.py    # Request correlation ID injection
```

---

## Executive AI Agent

The **Executive Agent** (`backend/services/executive_agent_service.py`) is the **only** conversational AI in the system. There is no secondary "Chat AI" — all intelligent interaction routes through it.

### Session Management
- Each user session is identified by a `session_id` string.
- Sessions are stored in-memory in `ExecutiveAgent.sessions` (class-level dict).
- Each session holds: conversation history, active task, pending action, last action history.
- Sessions persist for the lifetime of the backend process.

### Capabilities
| Capability | Description |
|---|---|
| Email Management | Read, summarize, draft, and send emails (Gmail & Outlook) |
| Calendar Management | List and create calendar events (Google & Outlook) |
| Knowledge Companion | Answer factual/general questions with session memory |
| Image Generation | Generate images from natural language via Gemini |
| Text-to-Speech | Convert text to audio |
| Daily Digest | Aggregate emails + calendar into a morning summary |

### Safety Protocols
- Email sends **always require explicit user confirmation** before execution.
- Delete operations require a second confirmation.
- Emails are summarized before the agent suggests a reply.
- Pending actions are stored in session state; confirmation/cancellation is tracked.

---

## Intent Router

**Location:** `backend/utils/intent_router.py`

The Intent Router runs **before** the LLM on every user message. Its purpose is to prevent LLM misinterpretation of control signals (confirmations, cancellations, slot values).

### Priority Order

| Priority | Intent Type | Description |
|---|---|---|
| 1 | `CANCEL_ACTION` | "cancel", "stop", "abort", "never mind" |
| 2 | State-specific | `EMAIL_SELECT_SENDER` or `CAL_PROVIDER_SELECT` states force provider-selection routing |
| 3 | `DECLINE_OPTIONAL` / `CONFIRM_ACTION` | Context-aware: "no" means different things depending on what was last asked |
| 4 | `PROVIDE_SLOT_VALUE` | While a task is locked (collecting), all input is treated as slot data |
| 5 | `SWITCH_TOPIC` | Detected if user switches tasks while another is in progress |
| 6 | `CALENDAR_CREATE` / `CALENDAR_LIST` | Keyword-pattern-based calendar intent detection |
| Default | `GENERAL_MESSAGE` | Falls through to LLM for open-ended responses |

### Task Locking
When a task is in status `collecting`, `awaiting_confirmation`, or `drafted`, it is **locked**. The Intent Router will not allow fallback responses or topic resets while a task is locked.

---

## Email Architecture

### Email State Machine
Email drafting follows a deterministic state machine:

```
IDLE → EMAIL_COLLECTING (gathering: to, subject, body) 
     → EMAIL_SELECT_SENDER (choose gmail or outlook)
     → EMAIL_DRAFT_READY (awaiting_confirmation)
     → [CONFIRM → send] | [CANCEL → discard]
```

### Slot Extraction
`backend/utils/slot_extraction.py` extracts structured data from natural language:
- **Email slots:** recipient (`to`), `subject`, `body`, `cc`
- **Calendar slots:** `title`, `date`, `time`, `duration`, `location`, `attendees`

Extraction uses regex patterns and semantic matching, running before LLM inference.

### Multi-Account Handling
Users can connect both **Gmail** and **Outlook**. When drafting an email with both connected, the agent asks which account to send from. The chosen provider is stored in the active task state.

---

## Calendar Architecture

### Calendar State Machine
```
IDLE → CALENDAR_COLLECTING (gathering: title, date, time)
     → CAL_PROVIDER_SELECT (choose google or outlook — only if both connected)
     → CALENDAR_CONFIRM (awaiting_confirmation)
     → [CONFIRM → create event] | [CANCEL → discard]
```

### Supported Providers
| Provider | API | Scopes Required |
|---|---|---|
| Google Calendar | Google Calendar API v3 | `calendar`, `calendar.events` |
| Outlook Calendar | Microsoft Graph `/me/calendarView` | `Calendars.ReadWrite` |

---

## Voice Integration

Voice is **integrated into the Executive AI** — there is no standalone voice assistant.

### Architecture
```
User (browser microphone)
  → POST /api/stt/transcribe  (audio file → text via Google STT)
  → POST /api/agent/chat       (text → Executive AI response)
  → POST /api/tts/generate     (response text → audio URL)
  → Browser plays audio (in-browser player or auto-play)
```

### WebSocket Voice Mode
`/api/voice/ws` provides a WebSocket endpoint for **real-time bidirectional voice** interaction. The `VoiceExecutiveAgent` React component manages the full session lifecycle on the frontend.

### STT Service
- **Engine:** Google Speech-to-Text API
- **Formats:** MP3, WAV, M4A, OGG, FLAC
- **Route:** `POST /api/stt/transcribe`

### TTS Service
- **Engine:** Google Text-to-Speech (gTTS)
- **Output:** MP3 audio file served via `/api/tts/audio/{id}`
- **Features:** Automatic language detection, Markdown normalization

---

## OAuth & Security Model

### Google OAuth 2.0
- **Flow:** Authorization Code Flow with offline access (refresh token)
- **Credentials source:** `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` env vars → auto-builds `credentials.json`
- **Scopes:** Defined in `backend/config/google_scopes.py` — Gmail read/send + Calendar read/write
- **Callback:** `GET /api/integrations/google/auth/callback` → redirects to frontend with `?auth=success`
- **CSRF protection:** Random `state` token validated on callback

### Microsoft OAuth 2.0
- **Flow:** Authorization Code Flow via MSAL
- **Authority:** `https://login.microsoftonline.com/consumers` (personal + work accounts)
- **Scopes:** `Mail.Read`, `Mail.Send`, `Calendars.ReadWrite`, `User.Read`, `offline_access`
- **Token refresh:** Automatic token refresh on expiry (5-minute buffer) via MSAL
- **Callback:** `GET /api/integrations/outlook/auth/callback`

### Token Storage
`backend/utils/token_storage.py` provides a `TokenStorage` abstraction:
- Tokens are persisted to local filesystem by default (JSON files under `backend/data/`)
- In production, replace with an encrypted database or secrets manager (e.g., AWS Secrets Manager, Vault)
- Access tokens and refresh tokens are stored per `(user_id, provider)` key

### CORS
Currently configured with `allow_origins=["*"]` for development.  
**For production:** restrict to your frontend domain in `backend/main.py`.

---

## Chrome Extension Communication

The Chrome Extension (`OrganAIzer_Extension`) communicates with the backend via standard HTTP REST:

| Feature | Endpoint |
|---|---|
| AI Chat (LLM) | `POST /api/chat` or `POST /api/llm` (legacy alias) |
| Summarize | `POST /api/nano-banana/summarize` |
| Translate | `POST /api/translate` |
| TTS | `POST /api/tts/generate` |
| Image Generation | `POST /api/image-gen/generate` |

The extension passes an `X-API-Key` header when configured. CORS is permissive to allow cross-origin browser requests.

---

## Frontend Architecture

| Item | Detail |
|---|---|
| Framework | React 18 + Vite |
| Styling | Tailwind CSS |
| API client | `frontend/src/lib/api.ts` (typed fetch wrapper) |
| Key components | `ExecutiveAgent.tsx`, `VoiceExecutiveAgent.tsx`, `IntegrationsPage.tsx` |
| Environment | `frontend/.env` → `VITE_API_BASE_URL` points to backend |

The frontend exposes a full-featured chat interface for the Executive AI, an integrations page for connecting Google/Microsoft accounts, and a voice mode UI.
