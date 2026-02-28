# OrganAIzer Services

> **AI-powered productivity backend** — Executive AI, Email & Calendar Management, Voice, Document Analysis, and more.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What is OrganAIzer?

OrganAIzer Services is a comprehensive AI backend platform built with **Python FastAPI**. It powers an intelligent productivity assistant that connects to your email (Gmail, Outlook), calendar (Google Calendar, Outlook), and provides AI-driven automation through a conversational interface.

The platform is consumed by:
- A **React web application** (frontend)
- The **OrganAIzer Chrome Extension**
- Any REST-capable client

---

## What Does the Executive AI Do?

The **Executive AI** is the heart of OrganAIzer. It is a single, unified conversational agent that:

- 📧 **Reads, summarizes, drafts, and sends emails** via Gmail and Outlook
- 📅 **Creates and lists calendar events** via Google Calendar and Outlook Calendar
- 🎤 **Understands voice input** (Speech-to-Text) and **speaks responses** (Text-to-Speech)
- 🧠 **Answers knowledge questions** with session memory for contextual follow-ups
- 🖼️ **Generates images** from natural language prompts
- 📋 **Produces daily digests** combining emails and calendar

All high-stakes actions (sending emails, creating events) require **explicit user confirmation** before execution.

---

## Key Features

| Feature | Description |
|---|---|
| **Executive AI** | Single stateful conversational agent with session memory |
| **Email Management** | Gmail + Outlook: read, summarize, draft, send |
| **Calendar Management** | Google + Outlook: list events, create events |
| **Voice Mode** | Full voice loop: STT → Executive AI → TTS |
| **Intent Router** | Deterministic pre-LLM intent classification (confirmations, cancellations, slots) |
| **Multi-Account** | Connect both Google and Microsoft simultaneously |
| **Chrome Extension** | Summarize, translate, and generate content on any webpage |
| **Document Analysis** | Upload PDFs/DOCX and chat with them |
| **Translation** | 30+ language translation for text and files |
| **Knowledge Base (RAG)** | Semantic search and Q&A over your own content |
| **Image Generation** | Text-to-image via Gemini/Vertex AI |
| **Video Transcription** | YouTube + file upload transcription |

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- [OpenRouter API key](https://openrouter.ai/) (for LLM access)

### 1. Clone and configure

```bash
git clone https://github.com/com2u/OrganAIzer_Services.git
cd OrganAIzer_Services

# Configure backend environment
copy backend\.env.example backend\.env
# Edit backend/.env with your OPENROUTER_API_KEY and other keys
```

### 2. Start services (Windows)

```bash
start_services.bat
```

Or manually:
```bash
# Backend
cd backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python main.py

# Frontend (new terminal)
cd frontend
npm install && npm run dev
```

### 3. Open the app

| URL | Description |
|---|---|
| http://localhost:5173 | Frontend application |
| http://localhost:8000/docs | Interactive API documentation |
| http://localhost:8000/health | API health check |

---

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, Executive AI, Intent Router, OAuth model, state machines |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Environment variables, OAuth setup, production checklist, CORS configuration |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Running locally, project structure, extending the AI, adding endpoints |
| [API_OVERVIEW.md](API_OVERVIEW.md) | All API endpoints with request/response examples |

---

## Technology Stack

### Backend
- **Python 3.10+** with **FastAPI**
- **OpenRouter** — multi-model LLM access (Gemini, Claude, GPT-4, etc.)
- **Google AI** — STT, TTS, Calendar API, Gmail API, Image Generation (Gemini)
- **Microsoft Graph API** — Outlook Calendar and Mail
- **MSAL** — Microsoft OAuth 2.0
- **google-auth-oauthlib** — Google OAuth 2.0
- **TF-IDF vectorization** — Knowledge base semantic search

### Frontend
- **React 18** + **Vite**
- **Tailwind CSS**
- **TypeScript**

---

## Project Structure

```
OrganAIzer_Services/
├── backend/           # FastAPI backend
│   ├── api/           # Route handlers
│   ├── services/      # Business logic (Executive AI, integrations)
│   ├── utils/         # Intent router, slot extraction, token storage
│   ├── models/        # Pydantic schemas
│   └── core/          # Config, logging, error handling
├── frontend/          # React/Vite SPA
├── docs/              # Additional documentation assets
├── scripts/           # Utility and test scripts
├── ARCHITECTURE.md
├── DEPLOYMENT.md
├── DEVELOPER_GUIDE.md
├── API_OVERVIEW.md
└── LICENSE
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
