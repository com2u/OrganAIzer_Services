# OrganAIzer Services – API Overview

> **Interactive Documentation:** http://localhost:8000/docs (Swagger UI) | http://localhost:8000/redoc  
> **Base URL:** `http://localhost:8000`  
> **OpenAPI Spec:** `openapi.yaml` / `openapi.json`

---

## Response Format

### Success Response
All successful endpoints return their data directly (per their Pydantic response model).

### Error Response
All errors return a consistent JSON structure:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description of the error",
    "details": {}
  }
}
```

### Common HTTP Status Codes
| Code | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request / invalid input |
| `401` | Not authenticated (OAuth token missing or expired) |
| `404` | Resource not found |
| `422` | Validation error (Pydantic schema mismatch) |
| `500` | Internal server error |

---

## Executive AI Agent

**Base path:** `/api/agent`

The central conversational AI. All session-based interaction goes here.

### POST `/api/agent/chat`
Chat with the Executive AI.

**Request:**
```json
{
  "message": "Show me my emails",
  "session_id": "user-session-123",
  "user_id": "default_user",
  "mail_provider": "gmail",
  "calendar_provider": "google"
}
```

**Response:**
```json
{
  "message": "Here are your 5 most recent emails...",
  "success": true,
  "type": "email_list",
  "data": { "emails": [...] },
  "agent_state": "IDLE",
  "active_task": null,
  "pending_action": null,
  "last_action": { "type": "list_emails", "timestamp": "..." }
}
```

**`agent_state` values:**
- `IDLE` — no active task
- `EMAIL_COLLECTING` — gathering email slots (to, subject, body)
- `EMAIL_DRAFT_READY` — email drafted, awaiting confirmation
- `CALENDAR_COLLECTING` — gathering calendar slots (title, date, time)
- `CALENDAR_CONFIRM` — event ready, awaiting confirmation

### GET `/api/agent/session/{session_id}`
Get session details (message count, context, last activity).

### DELETE `/api/agent/session/{session_id}`
Clear a session (reset conversation state).

### GET `/api/agent/sessions`
List all active sessions.

### GET `/api/agent/capabilities`
Returns the full list of agent capabilities and supported providers.

---

## Google Integration (OAuth, Calendar, Gmail)

**Base path:** `/api/integrations/google`

### GET `/api/integrations/google/auth/start`
Start Google OAuth flow.

**Query params:** `user_id` (default: `default_user`)  
**Response:** `{ "auth_url": "https://accounts.google.com/...", "state": "..." }`  
**Usage:** Redirect the user to `auth_url` in a browser.

### GET `/api/integrations/google/auth/callback`  
OAuth callback — handled automatically by Google redirect. Stores tokens and redirects frontend to `FRONTEND_URL?auth=success&provider=google`.

### GET `/api/integrations/google/status`
Check if Google is connected for a user.

**Response:** `{ "connected": true, "scopes": [...], "has_refresh_token": true }`

### GET `/api/integrations/google/calendar/events`
List Google Calendar events.

**Query params:** `user_id`, `max_results` (default: 10), `time_min` (ISO 8601)  
**Response:**
```json
{
  "events": [
    {
      "id": "abc123",
      "summary": "Team Standup",
      "start": "2026-03-01T09:00:00Z",
      "end": "2026-03-01T09:30:00Z",
      "location": null,
      "attendees": ["colleague@example.com"]
    }
  ],
  "total": 1
}
```

### POST `/api/integrations/google/calendar/events`
Create a Google Calendar event.

**Request:**
```json
{
  "summary": "Team Meeting",
  "start": "2026-03-01T14:00:00Z",
  "end": "2026-03-01T15:00:00Z",
  "description": "Weekly sync",
  "location": "Conference Room A",
  "attendees": ["person@example.com"]
}
```

### POST `/api/integrations/google/gmail/send`
Send an email via Gmail.

**Request:**
```json
{
  "to": "recipient@example.com",
  "subject": "Hello",
  "body": "Email body text",
  "cc": null,
  "bcc": null
}
```

---

## Microsoft / Outlook Integration

**Base path:** `/api/integrations/outlook`

### GET `/api/integrations/outlook/auth/start`
Start Microsoft OAuth flow. Redirects directly to Microsoft consent screen.

**Query params:** `user_id`

### GET `/api/integrations/outlook/auth/callback`
OAuth callback from Microsoft. Stores tokens, redirects frontend.

### GET `/api/integrations/outlook/status`
Check if Outlook is connected.

### GET `/api/integrations/outlook/calendar/events`
List Outlook Calendar events (same response format as Google Calendar).

**Query params:** `user_id`, `max_results`, `time_min`

### POST `/api/integrations/outlook/calendar/events`
Create an Outlook Calendar event (same request format as Google Calendar).

### POST `/api/integrations/outlook/mail/send`
Send an email via Outlook / Microsoft Graph.

---

## Speech-to-Text (STT)

**Base path:** `/api/stt`

### POST `/api/stt/transcribe`
Transcribe an audio file to text.

**Request:** `multipart/form-data`
- `file`: Audio file (MP3, WAV, M4A, OGG, FLAC)
- `language` (optional): Language hint (e.g., `"en"`, `"de"`)

**Response:**
```json
{
  "transcript": "Hello, this is a test transcription.",
  "language": "en",
  "confidence": 0.95
}
```

---

## Text-to-Speech (TTS)

**Base path:** `/api/tts`

### POST `/api/tts/generate`
Convert text to speech audio.

**Request:**
```json
{
  "text_md": "# Hello\n\nThis is **markdown** text."
}
```

**Response:**
```json
{
  "text_normalized": "Hello. This is markdown text.",
  "language": "en",
  "audio_url": "/api/tts/audio/abc123"
}
```

### GET `/api/tts/audio/{id}`
Download/stream the generated MP3 audio file.

**Response:** Binary `audio/mpeg` stream.

---

## AI Chat (Direct LLM)

**Base path:** `/api`

### POST `/api/chat`
Direct LLM chat without Executive AI session management.

**Request:**
```json
{
  "message": "What is the capital of France?",
  "model": "google/gemini-2.5-flash",
  "history": []
}
```

**Response:**
```json
{
  "message": "The capital of France is Paris.",
  "model": "google/gemini-2.5-flash"
}
```

### POST `/api/llm`
Legacy alias for `/api/chat`. Used by the Chrome Extension.

---

## Image Generation

**Base path:** `/api`

### POST `/api/image-gen/generate`
Generate images from a text prompt.

**Request:**
```json
{
  "prompt": "A futuristic city at sunset",
  "aspect_ratio": "16:9",
  "count": 1
}
```

**Response:**
```json
{
  "images": [
    { "url": "/static/images/abc123.png", "prompt": "..." }
  ]
}
```

### POST `/api/nano-banana/summarize`
Summarize or translate text using LLM (used by Chrome Extension).

**Request:**
```json
{
  "text": "Long article content...",
  "mode": "summarize",
  "language": "en"
}
```

---

## Video Transcription

**Base path:** `/api`

### POST `/api/video/transcribe`
Transcribe a video from URL or file upload.

**Query params:** `url` (YouTube or video URL)  
**Or form-data:** `file` (video file upload)

### GET `/api/youtube/transcribe`
Transcribe a YouTube video by URL.

**Query params:** `url`, `quality` (`fast` | `accurate`)

---

## Document Analysis

**Base path:** `/api`

### POST `/api/documents/upload`
Upload a document (PDF, DOCX, TXT, MD) for analysis.

### POST `/api/documents/{id}/summarize`
Generate an AI summary of an uploaded document.

### POST `/api/documents/{id}/chat`
Q&A chat over an uploaded document.

---

## Translation

**Base path:** `/api`

### POST `/api/translate`
Translate text between languages.

**Request:**
```json
{
  "text": "Bonjour le monde",
  "source_language": "fr",
  "target_language": "en"
}
```

---

## Knowledge Base (RAG)

**Base path:** `/api`

### POST `/api/knowledge-base/add`
Add content to the knowledge base.

### POST `/api/knowledge-base/search`
Semantic search over knowledge base content.

### POST `/api/knowledge-base/query`
Natural language Q&A over the knowledge base.

---

## System

### GET `/health`
Health check.

**Response:** `{ "status": "ok" }`

### GET `/`
API root — returns version info and links to docs.

### GET `/docs`
Swagger UI (interactive API documentation).

### GET `/redoc`
ReDoc API documentation.

### GET `/static/images/{filename}`
Serve generated image files.

---

## Chrome Extension Endpoints

The OrganAIzer Chrome Extension uses these endpoints:

| Feature | Method | Endpoint |
|---|---|---|
| AI Chat | POST | `/api/chat` |
| LLM (legacy) | POST | `/api/llm` |
| Summarize | POST | `/api/nano-banana/summarize` |
| Translate | POST | `/api/translate` |
| TTS | POST | `/api/tts/generate` |
| Image Gen | POST | `/api/image-gen/generate` |

The extension sends an `X-API-Key` header and expects CORS to be open (wildcard origin).
