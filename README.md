# OrganAIzer Services - Text-to-Speech Utility

## Project Overview

This is a browser-based AI utility platform starting with Text-to-Speech (TTS) functionality. The project is designed as a modular system where additional AI tools can be added in future phases.

**Current Phase: Phase 1 – Text-to-Speech Only**

The TTS tool accepts markdown-formatted text, automatically detects the language, normalizes the markdown to plain text, and generates a downloadable MP3 audio file.

## Features (Phase 1)

### Text-to-Speech
- **Markdown Input**: Accepts markdown-formatted text from users
- **Automatic Language Detection**: Detects the language of the input text
- **Markdown Normalization**: Converts markdown to plain text suitable for speech synthesis
- **Text Preprocessing**: Expands abbreviations and normalizes numbers for natural speech
- **MP3 Generation**: Creates downloadable MP3 audio files
- **In-Browser Playback**: Embedded audio player for immediate playback

## Architecture

### Frontend
- **Technology Stack**: React + Vite + Tailwind CSS
- **Location**: `frontend/` directory
- **Type**: Single-page application (SPA)
- **Features**: 
  - Responsive UI with Tailwind CSS
  - Real-time error handling
  - Audio playback and download capabilities

### Backend
- **Technology Stack**: Python + FastAPI
- **Location**: `backend/` directory
- **Type**: REST API
- **Features**:
  - Structured logging with JSON output
  - Centralized error handling
  - Request/response logging middleware
  - Environment-based configuration

## Developer Setup

### Prerequisites
- Python 3.8 or higher
- Node.js 16 or higher
- npm or pnpm

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create and activate a virtual environment:

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
# Copy the example environment file
copy .env.envexample .  # Windows
# or
cp .env.example .env    # macOS/Linux

# Edit .env and configure:
# - TTS_TEMP_DIR: Directory for temporary audio files (e.g., ./data/tts)
# - LOG_LEVEL: Logging level (default: INFO)
# - LOG_FILE_PATH: Optional path to log file
```

5. Create the temporary directory for audio files:
```bash
mkdir -p data/tts  # macOS/Linux
# or
md data\tts        # Windows
```

6. Run the development server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
# or
pnpm install
```

3. Configure environment variables:
```bash
# Copy the example environment file
copy .env.example .env  # Windows
# or
cp .env.example .env    # macOS/Linux

# Edit .env and set:
# VITE_API_BASE_URL=http://localhost:8000
```

4. Run the development server:
```bash
npm run dev
# or
pnpm dev
```

The frontend will be available at `http://localhost:5173`

5. Build for production:
```bash
npm run build
# or
pnpm build
```

## API Overview (TTS)

### Generate Speech

**Endpoint**: `POST /api/tts/generate`

**Request**:
```json
{
  "text_md": "# Hello World\n\nThis is **markdown** text with a list:\n- Item 1\n- Item 2"
}
```

**Response**:
```json
{
  "text_normalized": "Hello World. This is markdown text with a list: Item 1. Item 2.",
  "language": "en",
  "audio_url": "/api/tts/audio/123e4567-e89b-12d3-a456-426614174000"
}
```

**Error Response**:
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Text input is required and cannot be empty",
    "details": {}
  }
}
```

### Download Audio

**Endpoint**: `GET /api/tts/audio/{id}`

**Response**: Binary MP3 file with appropriate headers
- Content-Type: `audio/mpeg`
- Content-Disposition: `attachment; filename="tts-{id}.mp3"`

**Error Response** (404):
```json
{
  "error": {
    "code": "AUDIO_NOT_FOUND",
    "message": "Audio file not found",
    "details": {}
  }
}
```

### Health Check

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "ok"
}
```

## Project Structure

```
OrganAIzer_Services/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   └── tts.py
│   ├── core/
│   │   ├── config.py
│   │   ├── error_handling.py
│   │   ├── logging_config.py
│   │   └── middleware.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   └── tts.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── tts_service.py
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AudioPlayer.tsx
│   │   │   ├── ErrorBanner.tsx
│   │   │   └── TopNav.tsx
│   │   ├── lib/
│   │   │   └── api.ts
│   │   ├── pages/
│   │   │   └── TTSPage.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── .env.example
├── README.md
└── LICENSE
```

## Licensing

This project is licensed under the MIT License - see the LICENSE file for details.

### Third-Party Dependencies

The Text-to-Speech functionality relies on external libraries that may have their own licenses:
- **gTTS (Google Text-to-Speech)**: Licensed under MIT License
- **FastAPI**: Licensed under MIT License
- **React**: Licensed under MIT License
- Other dependencies as listed in `requirements.txt` and `package.json`

## Limitations and Legal Notes

- **Audio Quality**: Generated audio depends on the capabilities of the underlying TTS engine (gTTS)
- **Language Support**: Language detection and TTS support depends on the libraries used
- **Usage Terms**: Generated audio should comply with the usage terms of the TTS provider (Google TTS)
- **No Authentication**: This is a demo application with no user authentication or access control
- **Temporary Storage**: Generated audio files are stored temporarily and may be cleaned up periodically
- **Rate Limiting**: Consider implementing rate limiting for production use to prevent abuse

## Future Enhancements

The project structure is designed to easily accommodate additional AI tools:
- Speech-to-Text (STT)
- Translation
- Summarization
- Other AI-powered utilities

Each tool will follow the same architectural pattern with dedicated API endpoints, services, and UI components.

## Contributing

This is a demonstration project. For production use, consider:
- Adding authentication and authorization
- Implementing rate limiting
- Adding persistent storage
- Implementing audio file cleanup mechanisms
- Adding comprehensive error tracking and monitoring
- Setting up CI/CD pipelines
- Adding comprehensive test coverage

## Support

For issues or questions, please refer to the project repository or documentation.
