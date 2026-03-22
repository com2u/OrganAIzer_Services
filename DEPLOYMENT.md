# OrganAIzer Services – Deployment Guide

## Environment Variables

All configuration is managed via `backend/.env`. Copy the template and fill in your values.

### Core AI Keys

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | ✅ | OpenRouter API key — powers all LLM interactions (Gemini, GPT, open-source models, etc.) |
| `GEMINI_API_KEY` | Optional | Google AI Studio API key (legacy / image generation fallback) |

### Google OAuth (required if using Gmail / Google Calendar)

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_CLIENT_ID` | ✅ | OAuth 2.0 Client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | ✅ | OAuth 2.0 Client Secret from Google Cloud Console |
| `FRONTEND_URL` | ✅ | Frontend URL for OAuth redirect (e.g. `http://localhost:5173`) |
| `OAUTH_REDIRECT_BASE_URL` | Optional | Backend base URL (default: `http://localhost:8000`) |

The backend auto-generates `backend/credentials.json` from these env vars at startup. Do **not** commit `credentials.json` to source control.

### Microsoft OAuth (required if using Outlook / Outlook Calendar)

| Variable | Required | Description |
|---|---|---|
| `MICROSOFT_CLIENT_ID` | ✅ | App registration Client ID from Azure Portal |
| `MICROSOFT_CLIENT_SECRET` | ✅ | App registration Client Secret from Azure Portal |

### Token Encryption (required for production)

| Variable | Required | Description |
|---|---|---|
| `TOKEN_ENCRYPTION_KEY` | ✅ | Fernet symmetric key for encrypting stored OAuth tokens at rest |

Generate a key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> ⚠️ If you change this key after users have connected accounts, all stored tokens become unreadable. Users will need to re-authenticate.

### Application Settings

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Host address to bind the backend server |
| `API_PORT` | `8000` | Port for the backend server |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FILE_PATH` | _(none)_ | Optional path to write log file |
| `TTS_TEMP_DIR` | `./data/tts` | Directory for generated TTS audio files |
| `IMAGE_GEN_TEMP_DIR` | `./data/images` | Directory for generated images |

### Frontend Environment

Create `frontend/.env`:

```
VITE_API_BASE_URL=http://localhost:8000
```

---

## Required Services

| Service | Purpose | Required |
|---|---|---|
| Python 3.10+ | Backend runtime | ✅ |
| Node.js 18+ | Frontend dev server / build | ✅ |
| OpenRouter account | LLM access | ✅ |
| Google Cloud project | OAuth + Calendar + Gmail + STT/TTS | For Google features |
| Azure App Registration | OAuth + Outlook + Calendar | For Microsoft features |
| FFmpeg | Audio/video processing (STT, transcription) | For voice/video features |

---

## OAuth Configuration

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable these APIs:
   - Google Calendar API
   - Gmail API
   - Cloud Speech-to-Text API
   - Cloud Text-to-Speech API
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Set application type: **Web application**
6. Add authorized redirect URIs:
   - `http://localhost:8000/api/integrations/google/auth/callback` (development)
   - `https://yourdomain.com/api/integrations/google/auth/callback` (production)
7. Copy Client ID and Client Secret → add to `backend/.env`
8. Go to **APIs & Services → OAuth consent screen**:
   - Add required scopes: `gmail.readonly`, `gmail.send`, `calendar.events`, `calendar.readonly`
   - Add test users (while in "Testing" mode)

### Microsoft OAuth Setup

1. Go to [Azure Portal](https://portal.azure.com/) → **Azure Active Directory → App registrations → New registration**
2. Name your app, select **Accounts in any organizational directory and personal Microsoft accounts**
3. Set redirect URI (Web):
   - `http://localhost:8000/api/integrations/outlook/auth/callback` (development)
   - `https://yourdomain.com/api/integrations/outlook/auth/callback` (production)
4. Under **Certificates & secrets** → create a new client secret → copy value immediately
5. Under **API permissions** → add:
   - `Mail.Read`, `Mail.Send`, `Calendars.ReadWrite`, `User.Read`, `offline_access`
6. Copy **Application (client) ID** and the client secret → add to `backend/.env`

---

## Token Storage

OAuth tokens are stored as **Fernet-encrypted** `.enc` files in `backend/data/tokens/`.

The encryption is handled by `backend/utils/token_storage.py` using the `TOKEN_ENCRYPTION_KEY` environment variable. All access tokens and refresh tokens are encrypted at rest before being written to disk.

**For production hardening**, consider also:
- Storing tokens in a database (PostgreSQL, Redis) instead of the local filesystem
- Using a secrets manager (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault) for the encryption key itself
- Enabling filesystem encryption on the server where `backend/data/` lives

**Do not commit** `backend/data/tokens/` to source control. This directory is git-ignored.

---

## CORS Configuration

Current setting in `backend/main.py` allows all origins (development mode):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # ⚠️ Change for production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**For production**, replace `["*"]` with your specific frontend domain:

```python
allow_origins=["https://app.yourcompany.com"],
allow_credentials=True,
```

> Note: When `allow_credentials=True`, `allow_origins` cannot be `["*"]`. You must specify explicit origins.

---

## Production Checklist

### Security
- [ ] Set `allow_origins` to specific frontend domain (not `"*"`)
- [ ] Move token storage from filesystem to encrypted database
- [ ] Rotate all API keys and OAuth secrets before go-live
- [ ] Enable HTTPS — backend and frontend must be served over TLS
- [ ] Set `GOOGLE_CLIENT_SECRET` and `MICROSOFT_CLIENT_SECRET` via environment (never hardcode)
- [ ] Add authentication/authorization to protect API endpoints
- [ ] Implement rate limiting (FastAPI `slowapi` or nginx rate limiting)
- [ ] Validate and restrict OAuth redirect URIs to production domains

### Infrastructure
- [ ] Configure `API_HOST` and `API_PORT` appropriately for your deployment environment
- [ ] Ensure `data/tts/` and `data/images/` directories are writable with sufficient disk space
- [ ] Configure log rotation (if `LOG_FILE_PATH` is set)
- [ ] Set up healthcheck monitoring on `GET /health`
- [ ] Consider session persistence (current sessions are in-memory — restart clears them)

### OAuth Redirect URIs
When deploying to production, update redirect URIs in:
1. **Google Cloud Console** → OAuth 2.0 Client → Authorized redirect URIs
2. **Azure App Registration** → Authentication → Redirect URIs
3. **`OAUTH_REDIRECT_BASE_URL`** env var → set to your production backend URL
4. **`FRONTEND_URL`** env var → set to your production frontend URL

### Session Management (Important)
Executive AI sessions are currently stored **in-memory**. If the backend restarts, all active sessions are lost. For production:
- Consider using Redis for session storage
- Implement session persistence to a database

---

## Starting the Services

### Development (Quick Start)

```bash
# Start both backend and frontend
start_services.bat          # Windows

# Or individually
start_backend_venv.bat      # Backend with venv activation
start_frontend.bat          # Frontend dev server
```

### Manual Start

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux/macOS
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev
```

### Production Build

```bash
# Build frontend for production
cd frontend
npm run build
# Outputs to frontend/dist/ — serve via nginx or CDN

# Run backend with production ASGI server
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Service URLs

| Service | Development URL |
|---|---|
| Backend API | http://localhost:8000 |
| Interactive API Docs (Swagger) | http://localhost:8000/docs |
| ReDoc API Docs | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |
| Frontend App | http://localhost:5173 |
