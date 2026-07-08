# Voice Mode – Developer Guide

This document describes how to run Voice Mode locally, the WebSocket protocol,
the event-creation idempotency model, and how to troubleshoot with the debug panel.

---

## 0. Fix applied (2026-03-01) – WS "connecting" / never reaching 101

### Root causes (two bugs)

1. **`websockets` library not installed in venv** — Even though
   `uvicorn[standard]` is in `requirements.txt`, pip does not always install
   optional extras transitively; the venv lacked `websockets` entirely.
   Uvicorn logs `WARNING: No supported WebSocket library detected` and
   silently treats every WS upgrade as a plain HTTP GET → FastAPI returns 404
   for `/api/voice/stream` (registered only as `@router.websocket`, not GET).
   Result: repeated `GET /api/voice/stream → 404` and the frontend reconnect
   loop every 2 s.

2. **`VITE_API_BASE_URL` not defined** — `apiClient.ts` exports
   `API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''`.  With an empty
   string `toWsBase('')` fell back to same-origin `ws://localhost:5173/…`.
   Even after adding `ws: true` to the Vite proxy, the Vite WS proxy is
   unreliable under some OS/node versions.  Defining `VITE_API_BASE_URL` to
   `http://localhost:8000` in dev makes `toWsBase` produce
   `ws://localhost:8000` — a **direct** connection that bypasses the Vite
   proxy entirely.

### Files changed

| File | Change |
|------|--------|
| `backend/requirements.txt` | Added `websockets>=11.0` as an explicit dependency |
| `frontend/vite.config.ts` | Added `VITE_API_BASE_URL` define (`http://localhost:8000` in dev, `""` in prod); kept `ws:true` in proxy as belt-and-suspenders |
| `backend/api/voice_mode.py` | Added `{"type":"ready"}` immediately after `websocket.accept()` |
| `frontend/src/components/ExecutiveAgent.tsx` | Added `case 'ready':` handler that confirms `wsStatus = 'open'` and logs `ws:ready` |

### WS URL strategy (chosen: direct to backend in dev)

| Environment | WS URL built by frontend | How it reaches backend |
|-------------|--------------------------|------------------------|
| **Dev** (`npm run dev`) | `ws://localhost:8000/api/voice/stream` | Direct — no Vite proxy involvement |
| **Prod** (nginx/Docker) | `wss://<origin>/api/voice/stream` | nginx `proxy_pass` with `Upgrade` headers (same-origin, `VITE_API_BASE_URL=""`) |

### How to install the WS library (one-time, per venv)

```bash
# From the project root, with the venv active:
venv\Scripts\pip install "websockets>=11.0"
# OR simply reinstall all requirements:
venv\Scripts\pip install -r backend\requirements.txt
```

### How to run locally

```bash
# Terminal 1 – backend
cd backend
..\venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000
# OR use the helper bat:
# start_backend_venv.bat

# Terminal 2 – frontend
cd frontend
npm install   # first time only
npm run dev   # → http://localhost:5173
```

Open `http://localhost:5173` → Executive Agent → click 🎤 in the composer.

Expected DevTools → Network → WS:
```
Request URL:  ws://localhost:8000/api/voice/stream?…
Status:       101 Switching Protocols
```

Expected backend log on connect:
```
INFO  [VOICE] ▶ WS connected  ws=<id>  session=…  user=…
```

Debug panel event sequence on success:
```
ws:connecting  {"url":"ws://localhost:8000/api/voice/stream?…"}
ws:open
ws:ready        ← backend acknowledged
state           "idle"
```

---

## 1. Running Voice Mode locally

### Backend

```bash
# In the backend directory
cd backend

# Required env vars (add to backend/.env):
# VOICE_DEBUG=true         → enable server-side debug payloads over WS
# BACKEND_URL=http://localhost:8000
# TIMEZONE=Europe/Berlin

# Start the server
uvicorn main:app --reload --port 8000
```

The voice WebSocket endpoint is available at:
```
ws://localhost:8000/api/voice/stream
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # Vite dev server → http://localhost:5173
```

Open **Executive Agent** → click the 🎤 button in the chat composer to enter voice mode.

### Enable server-side debug payloads

Set `VOICE_DEBUG=true` in `backend/.env` (or as an env var).  When enabled the
server emits additional `{"type": "debug", "data": {...}}` frames over the
WebSocket that the frontend debug panel will render.

---

## 2. WebSocket Protocol

### Connection

```
ws(s)://<host>/api/voice/stream
  ?session_id=<string>   ← MUST match the text-chat session_id so voice + text share the same thread
  &user_id=<string>
  &provider=<gmail|outlook>
```

### Client → Server messages

| Type | Payload | Description |
|------|---------|-------------|
| `audio_start` | `{}` | User pressed mic button. Server enters `listening` state. Any ongoing TTS is interrupted automatically. |
| `audio_end`   | `{}` | User released mic button. Server finalises STT → Executive AI → TTS pipeline. |
| `interrupt`   | `{}` | Explicit interrupt: stop TTS playback immediately, return to `idle`. |
| `ping`        | `{}` | Keepalive. Server responds with `pong`. |
| *(binary)*    | raw audio bytes (webm/opus via MediaRecorder) | Streaming audio chunks while recording. |

### Server → Client messages

| Type | Payload | Description |
|------|---------|-------------|
| `state`             | `{state: "idle"\|"listening"\|"thinking"\|"speaking"}` | State machine transition |
| `stt.partial`       | `{text: "..."}` | Live partial transcript (emitted every ~1.5 s of audio) |
| `stt.final`         | `{text: "..."}` | Finalised transcript after `audio_end` |
| `ai.response.text`  | `{text: "..."}` | Full Executive AI reply text |
| `tts.audio`         | `{audio_url: "/api/tts/audio/<id>", audio_id: "<id>"}` | URL to play the TTS MP3 |
| `error`             | `{message: "..."}` | Error description |
| `pong`              | `{}` | Response to `ping` |
| `debug` *(dev only)*| `{data: {...}}` | Latency timings + state when `VOICE_DEBUG=true` |

### State machine

```
idle  ──audio_start──▶  listening  ──audio_end──▶  thinking  ──▶  speaking  ──▶  idle
 ▲                          │                                          │
 └──────────interrupt────────┴──────────────────────────────────────────┘
```

---

## 3. Interrupt mechanism

The mic button is a **push-to-talk** control.

- **Press while idle**: starts recording (`audio_start`).
- **Release**: stops recording (`audio_end`), triggers the full pipeline.
- **Press while AI is speaking**: sends both `interrupt` + `audio_start`.  
  The server stops generating / sending TTS chunks and immediately transitions to `listening`.
  The client also calls `audio.pause()` to stop local playback instantly.
- A yellow **⚡ Unterbrechen** button in the voice overlay also triggers the interrupt
  without starting a new recording.

---

## 4. Event-creation idempotency

### Problem

Without idempotency, a user who confirms "yes" twice (network hiccup, double-tap)
would create duplicate calendar events.

### Solution

Every `create_calendar_event` execution computes a **SHA-256 request_id** deterministically:

```
request_id = SHA256( user_id | title | start_datetime | end_datetime | timezone )
```

**First request:**
1. Hash computed, not in store → HTTP POST to integration endpoint.
2. API returns `event_id` (e.g. Google's event ID).
3. `_CALENDAR_IDEMPOTENCY_STORE[request_id] = event_id`.
4. Success returned to user.

**Duplicate request (same user, same event details):**
1. Hash computed, **found in store** → skip HTTP call entirely.
2. Return cached `event_id` with `"idempotent": true`.
3. No duplicate created.

The `request_id` is also included in the API payload (`payload["request_id"]`) so
providers that support server-side deduplication can use it.

> **Note:** The store is in-process (`_CALENDAR_IDEMPOTENCY_STORE` dict).  
> For multi-instance deployments, replace with Redis or a shared DB.

### Truthfulness check

Even on a `2xx` response, if the provider does **not** return an `event_id` (the `id`
field in the response body), the agent treats it as a **failure** and preserves the
pending action so the user can retry:

```
2xx + event_id present  →  ✅ success ("calendar_created")
2xx + event_id absent   →  ❌ failure ("event_id missing from API response")
4xx / 5xx               →  ❌ failure, pending_action preserved for retry
```

---

## 5. Running unit tests

```bash
cd backend
# Install test deps once:
pip install pytest pytest-asyncio

# Run calendar event creation tests:
python -m pytest tests/test_calendar_event_creation.py -v
```

Expected output:
```
PASSED  test_success_when_event_id_exists
PASSED  test_failure_when_event_id_missing
PASSED  test_failure_on_http_error_preserves_pending
PASSED  test_idempotent_duplicate_returns_same_event_id
PASSED  test_no_pending_action_guard_prevents_phantom_success
PASSED  test_same_inputs_produce_same_hash
PASSED  test_different_users_produce_different_hash
PASSED  test_different_titles_produce_different_hash
PASSED  test_hash_is_valid_sha256
```

---

## 6. Debug panel

### Activating

Click **🔧 Debug** button (bottom-right of the Executive Agent view or inside the
voice overlay).

### What it shows

| Field | Description |
|-------|-------------|
| `session` | Last 8 chars of the current session_id |
| `ws` | WebSocket status (`connecting` / `open` / `disconnected` / `error`) |
| `ai=Nms` | Time from transcript→AI response (requires `VOICE_DEBUG=true`) |
| `tts=Nms` | Time from AI response→TTS file ready (requires `VOICE_DEBUG=true`) |
| `rt=Nms` | Total round-trip: mic-release → TTS ready (requires `VOICE_DEBUG=true`) |
| Event log | Timestamped ring-buffer of WS events (last 80 entries) |

### Enabling server latency data

```
# backend/.env
VOICE_DEBUG=true
```

Restart the backend. The server will emit `{"type": "debug", "data": {...}}` frames
that populate the latency fields in the debug panel.

---

## 7. Architecture overview

```
User speaks  →  MediaRecorder (webm/opus)  →  WS binary chunks
                                                      │
                                              voice_mode.py (FastAPI WS)
                                                      │
                                              STT (Whisper – lazy loaded)
                                                      │
                                              ExecutiveAgent.process_message()
                                              (shares session with text chat)
                                                      │
                                              TTS (gTTS → MP3 file)
                                                      │
                                              WS: tts.audio {audio_url}
                                                      │
                                    Client plays MP3  ←  Audio(<url>)
```

Voice and text chat share the **same `ExecutiveAgent` session** (via `session_id`),
so the conversation context is preserved regardless of whether the user speaks or types.

---

## 8. Known limitations / future work

- **TTS streaming**: gTTS generates the full MP3 before sending.  A streaming TTS
  (e.g. ElevenLabs, Azure TTS) would reduce time-to-first-audio significantly.
- **Whisper is synchronous**: For production scale, offload to a dedicated STT service.
- **Idempotency store is in-process**: For multi-instance, replace with Redis TTL keys.
- **Language**: The frontend UI is German-labelled. The TTS language is tracked
  per session and owned by the **user**: it starts German and only switches when
  the user's transcript carries strong evidence of the other language
  (`utils/lang_tracking.py`, shared with the phone path). AI replies are never
  language-detected, so short acknowledgements like "Okay." cannot flip the
  voice mid-session. Only German/English are tracked; other languages fall back
  to the session language.
