# OrganAIzer Services

AI-powered personal assistant with calendar management, email management, and realtime voice interaction.

---

## Table of Contents

1. [What the app can do](#what-the-app-can-do)
2. [Architecture](#architecture)
3. [Executive Agent — brain capabilities](#executive-agent--brain-capabilities)
4. [Provider integrations](#provider-integrations)
5. [Voice mode](#voice-mode)
6. [Environment setup](#environment-setup)
7. [Running locally](#running-locally)
8. [How frontend and backend talk](#how-frontend-and-backend-talk)
9. [Known limitations](#known-limitations)

---

## What the app can do

These features are **fully implemented and wired end-to-end**:

| Feature | How to use it |
|---------|---------------|
| **Create calendar events** | "Create a meeting tomorrow at 2pm" / "Add an appointment with Alice on Friday at 10am" |
| **Read calendar events** | "What meetings do I have today?" / "Show my calendar for next week" |
| **Send emails** | "Send an email to john@example.com about the project update" |
| **Read emails** | "Show my last 5 emails" / "Any emails from Sarah today?" |
| **Voice mode** | Click the mic button — speak naturally, hear the response via TTS |
| **Google integration** | Connect Google account for Gmail + Google Calendar access |
| **Microsoft / Outlook integration** | Connect Microsoft account for Outlook mail + Outlook Calendar access |
| **LLM chat** | General questions answered by AI (Gemini / Claude / GPT via OpenRouter) |
| **TTS / STT standalone** | `/tts` and `/stt` pages for text-to-speech and speech-to-text |
| **Image generation** | `/image-gen` page using Gemini image generation |
| **YouTube transcription** | `/youtube` page |
| **Document analysis** | `/documents` page for PDF/DOCX Q&A |
| **Translation** | `/translation` page |

---

## Architecture

```
┌────────────────────────────────────────────────┐
│  Frontend (React + Vite)  :5173 dev / nginx prod│
│                                                │
│  ┌─────────────────┐   ┌──────────────────┐   │
│  │  ExecutiveAgent │   │  IntegrationsPage│   │
│  │  (chat UI)      │   │  (OAuth flow)    │   │
│  └────────┬────────┘   └────────┬─────────┘   │
│           │ POST /api/agent/chat │ GET/POST     │
│           │ WS /api/voice/stream │ /api/integr… │
└───────────┼─────────────────────┼─────────────┘
            │                     │
┌───────────▼─────────────────────▼─────────────┐
│  Backend (FastAPI)  :8000                      │
│                                                │
│  ┌──────────────────────────────────────────┐  │
│  │  Executive Agent Service                │  │
│  │  ┌─────────────┐  ┌────────────────┐   │  │
│  │  │ IntentRouter│  │ SlotExtractor  │   │  │
│  │  │ (classify)  │  │ (parse slots)  │   │  │
│  │  └──────┬──────┘  └────────────────┘   │  │
│  │         │                              │  │
│  │  ┌──────▼──────────────────────────┐  │  │
│  │  │ Action Handlers                 │  │  │
│  │  │  _handle_calendar_event_creation│  │  │
│  │  │  _handle_calendar_list_events   │  │  │
│  │  │  _handle_calendar_read          │  │  │
│  │  │  _handle_send_email             │  │  │
│  │  │  _handle_email_read             │  │  │
│  │  └──────┬──────────────────────────┘  │  │
│  └─────────┼────────────────────────────┘  │
│            │                               │
│  ┌─────────▼────────────────────────────┐  │
│  │  Integrations API                    │  │
│  │  /api/integrations/google/*          │  │
│  │  /api/integrations/microsoft/*       │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  Voice Mode WebSocket: /api/voice/stream    │
│  (STT via Whisper + TTS via Google TTS)     │
└─────────────────────────────────────────────┘
            │                     │
     ┌──────▼──────┐    ┌────────▼────────┐
     │  Google APIs │    │ Microsoft Graph │
     │  Gmail       │    │ Outlook Mail    │
     │  Calendar    │    │ Outlook Calendar│
     └─────────────┘    └────────────────┘
```

---

## Executive Agent — brain capabilities

The Executive Agent (`POST /api/agent/chat`) handles all natural-language orchestration. It uses:

- **IntentRouter** — deterministic keyword-based intent classification (runs before LLM)
- **SlotExtractor** — extracts dates, times, emails, event titles from free text
- **NLUExtractor** — LLM-powered slot correction during draft modification
- **ConversationMemory** — per-session state tracking (active task, pending confirmations)

### Intent types

| Intent | Example phrases | Action |
|--------|----------------|--------|
| `CALENDAR_CREATE` | "create a meeting tomorrow at 9", "add an appointment with Alice" | Collects slots → confirmation → POST calendar |
| `CALENDAR_LIST` | "show my calendar", "events today" | GET calendar events |
| `CALENDAR_READ` | "what do I have next week?", "when is my next meeting?" | GET calendar events (date range) |
| `EMAIL_READ` | "show my last 5 emails", "any emails from John?" | GET emails |
| `email send` | "send an email to boss@company.com" | Collects slots → confirmation → POST email |
| `CONFIRM_ACTION` | "yes", "send it", "create it" | Executes pending action |
| `CANCEL_ACTION` | "cancel", "stop", "never mind" | Clears pending state |
| `GENERAL_MESSAGE` | Any other question | LLM response |

### State machine

```
User message
     │
     ▼
IntentRouter.route_message()
     │
     ├─ CALENDAR_CREATE → _handle_calendar_event_creation
     │     │
     │     ├─ Missing slots? → ask user (calendar_slot_request)
     │     ├─ All slots, no provider? → ask user (calendar_provider_request)
     │     │     → Frontend shows 📅 Google Calendar / 📅 Outlook buttons
     │     ├─ Provider not connected? → tell user (provider_not_connected)
     │     │     → Frontend shows 🔗 Go to Integrations link
     │     └─ All ready → confirmation message (action_needed: "confirmation")
     │           → Frontend shows ✓ Yes / ✕ No buttons
     │           → User says yes → _execute_calendar_event_creation → POST API
     │
     ├─ EMAIL_READ → _handle_email_read → GET API → formatted list
     │
     ├─ CALENDAR_READ → _handle_calendar_read → GET API → formatted list
     │
     └─ General → LLM chat response
```

### Provider routing

The agent uses two separate provider fields:
- `calendar_provider` — for calendar operations (`google` | `outlook`)
- `mail_provider` — for email operations (`gmail` | `outlook`)

The frontend automatically selects providers based on which accounts are connected:
- Both connected (or Google only) → Google for calendar, Gmail for email
- Microsoft only → both use Outlook

---

## Provider integrations

### Google (Gmail + Google Calendar)

1. Create credentials at [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Enable Gmail API and Google Calendar API
3. Add redirect URI: `http://localhost:8000/api/integrations/google/auth/callback`
4. Set in `backend/.env`:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```

### Microsoft (Outlook Mail + Outlook Calendar)

1. Register app at [Azure Portal](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps)
2. Add redirect URI: `http://localhost:8000/api/integrations/microsoft/auth/callback`
3. Set in `backend/.env`:
   ```
   MICROSOFT_CLIENT_ID=...
   MICROSOFT_CLIENT_SECRET=...
   MICROSOFT_TENANT_ID=common
   MICROSOFT_REDIRECT_URI=http://localhost:8000/api/integrations/microsoft/auth/callback
   ```

### OAuth flow

```
Frontend Integrations page
    → Click "Connect Google" / "Connect Microsoft"
    → GET /api/integrations/{google|microsoft}/auth/start?user_id=default_user
    → Browser redirects to Google/Microsoft consent page
    → User approves
    → Callback: GET /api/integrations/{google|microsoft}/auth/callback
    → Tokens encrypted + stored in backend/data/tokens/
    → Frontend Integrations page polls /api/integrations/{google|microsoft}/status
```

---

## Voice mode

Voice mode uses a WebSocket at `wss://your-backend/api/voice/stream`.

```
Frontend holds mic button
    → WS: {"type": "audio_start"}
    → WS: <binary webm/opus audio chunks>
    → WS: {"type": "audio_end"}
    ← WS: {"type": "stt.final", "text": "create a meeting tomorrow"}
    ← WS: {"type": "state", "state": "thinking"}
    ← WS: {"type": "ai.response.text", "text": "📅 Ready to create..."}
    ← WS: {"type": "tts.audio", "audio_url": "/api/tts/audio/abc123.mp3"}
    ← WS: {"type": "state", "state": "idle"}
```

**Requirements:**
- `ffmpeg` must be on PATH (converts webm/opus → 16kHz WAV for Whisper)
- Whisper model pre-loaded on startup (model size set by `VOICE_STT_MODEL`)

**Voice model performance guide:**

| Model | RAM | CPU latency | Recommended for |
|-------|-----|-------------|-----------------|
| `tiny` | 1 GB | ~1–2 s | Testing only |
| `base` | 1 GB | ~2–4 s | **Default — dev/prod CPU** |
| `small` | 2 GB | ~4–8 s | Better accuracy on CPU |
| `medium` | 5 GB | ~15–30 s | GPU only |
| `large` | 10 GB | ~60+ s | GPU only |

---

## Environment setup

### Backend (`backend/.env`)

```bash
# Copy and fill in all values
cp backend/.env.example backend/.env
```

Required variables:

```bash
# Authentication
API_KEYS=your-api-key-here

# LLM (OpenRouter)
OPENROUTER_API_KEY=sk-or-...

# Google
GOOGLE_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...

# Microsoft
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_TENANT_ID=common
MICROSOFT_REDIRECT_URI=http://localhost:8000/api/integrations/microsoft/auth/callback

# Token encryption (generate once, never change)
TOKEN_ENCRYPTION_KEY=...  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# URLs
OAUTH_REDIRECT_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000

# Voice
VOICE_STT_MODEL=base     # tiny|base|small|medium|large
UPLOAD_STT_MODEL=medium
VOICE_DEBUG=false

# Dev
BACKEND_RELOAD=false      # IMPORTANT: keep false when testing voice/agent
TIMEZONE=Europe/Berlin
```

### Frontend (`frontend/.env`)

```bash
cp frontend/.env.example frontend/.env
```

```bash
# Must match backend API_KEYS
VITE_API_KEY=your-api-key-here

# Leave unset for auto-configuration (dev=localhost:8000, prod=relative URL)
# VITE_API_BASE_URL=http://localhost:8000
```

---

## Running locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

pip install -r requirements.txt
uvicorn main:app --port 8000 --no-reload
# Use --no-reload to prevent session state wipes during voice/agent testing
```

Backend runs at `http://localhost:8000`  
API docs at `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

### Prerequisites

- Python 3.10+
- Node 18+
- `ffmpeg` on PATH (required for voice mode)
- `torch` + `whisper` (installed via requirements.txt, downloads model on first use)

---

## How frontend and backend talk

### Text chat (Executive Agent)

```http
POST /api/agent/chat
X-API-Key: {VITE_API_KEY}
Content-Type: application/json

{
  "message": "Create a meeting tomorrow at 10am",
  "session_id": "agent-1234567890",
  "user_id": "default_user",
  "calendar_provider": "google",
  "mail_provider": "gmail"
}
```

Response:
```json
{
  "message": "📅 Ready to create your calendar event: ...",
  "success": true,
  "type": "calendar_confirmation",
  "action_needed": "confirmation",
  "data": { "title": "Meeting", "date": "2026-03-10", "time": "10:00" }
}
```

Key response types and what the frontend does with them:

| `type` | `action_needed` | Frontend reaction |
|--------|----------------|-------------------|
| `calendar_confirmation` | `"confirmation"` | Shows ✓ Yes / ✕ No buttons |
| `calendar_provider_request` | — | Shows 📅 Google Calendar / 📅 Outlook buttons |
| `provider_not_connected` | — | Shows 🔗 Go to Integrations link |
| `calendar_created` | — | Renders success message |
| `calendar_list` | — | Renders formatted event list |
| `email_confirmation` | `"confirmation"` | Shows ✓ Yes / ✕ No buttons |
| `email_sent` | — | Renders success message |
| `email_list` | — | Renders formatted email list |
| `calendar_slot_request` | — | User provides missing info (date, time, etc.) |
| `email_slot_request` | — | User provides missing info (recipient, subject, body) |
| `error` | — | Shows error text |
| `chat` | — | Plain chat message |

### Voice mode (WebSocket)

```
WS /api/voice/stream?session_id=...&user_id=...&provider=gmail
```

Voice mode shares the same `session_id` as text chat — voice and text messages appear in the same conversation thread.

### Integration status check

```http
GET /api/integrations/google/status?user_id=default_user
GET /api/integrations/microsoft/status?user_id=default_user
```

### Connect / disconnect

```http
GET  /api/integrations/google/auth/start?user_id=default_user
GET  /api/integrations/microsoft/auth/start?user_id=default_user
POST /api/integrations/google/disconnect?user_id=default_user
POST /api/integrations/microsoft/disconnect?user_id=default_user
```

---

## Known limitations

| Area | Limitation |
|------|-----------|
| **User accounts** | Single user (`default_user`). No auth, no multi-user support. |
| **Session state** | Stored in-memory in the backend process. Lost on restart. Do not run with `BACKEND_RELOAD=true` when testing the agent. |
| **Calendar update/delete** | Not yet implemented in the agent (read + create only). |
| **Intent router language** | Intent patterns are English-only. Non-English messages fall through to the LLM which responds but does not call calendar/email APIs. |
| **Whisper model quality** | `base` model (default) works well for clear speech. Background noise or heavy accents may require `small` or `medium` (but `medium`+ needs GPU). |
| **ffmpeg dependency** | Voice mode requires `ffmpeg` on PATH. If missing, Whisper receives raw webm which may fail. |
| **Token storage** | OAuth tokens stored as encrypted files in `backend/data/tokens/`. Not suitable for multi-instance deployments without shared storage. |
| **Idempotency store** | Calendar creation idempotency is in-memory only. Restarting the backend clears it. |
| **Multi-provider** | If both Google and Microsoft are connected, Google is used by default. Microsoft is only auto-selected when Google is disconnected. |
