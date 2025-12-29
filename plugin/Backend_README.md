# OrganAIzer Service

A browser-based AI media utility suite with multiple tools for working with audio, video, text, and images.

## Features

- **YouTube Downloader**: Download videos from YouTube URLs (may be limited by YouTube's anti-bot measures).
- **Text to Speech**: Convert markdown-formatted text into speech with language auto-detection.
- **Speech to Text**: Transcribe audio files or URLs into text using OpenAI Whisper.
- **Video to Text**: Extract spoken content from videos or YouTube links as text.
- **Text to Image**: Generate AI-powered image descriptions using Google Gemini API with visual output.
- **LLM Interaction**: Interact with different language models to get responses from a prompt.

## Architecture

### Frontend
- React SPA with Vite build tool
- Tailwind CSS for styling
- Single-page layout with persistent top navigation

### Backend
- Python FastAPI REST API
- Modular services for each AI tool
- Structured logging and error handling

## Quick Start

### First Time Setup
Run the setup script to install all dependencies:

```bash
# Make sure you're in the project root directory
./setup.sh
```

This will:
- Create a Python virtual environment
- Install Python dependencies
- Install Node.js dependencies

### Start the Application
After setup, start both servers with:

```bash
./start.sh
```

This will automatically start both the backend and frontend servers. Open your browser and visit `http://localhost:5173`.

## Developer Setup

### Prerequisites
- Python 3.8+ with venv support
- Node.js 16+ and npm
- ffmpeg (for video processing)

### Manual Setup

#### Backend
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
3. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On macOS/Linux: `source venv/bin/activate`
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the development server:
   ```bash
   python main.py
   ```
   Or with uvicorn:
   ```bash
   uvicorn main:app --reload
   ```

#### Frontend
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```

### Running Both Services
After setup, you can run both services simultaneously:

```bash
# From the project root
./start.sh
```

Or manually:
```bash
# Terminal 1 - Backend
cd backend && source venv/bin/activate && python main.py

# Terminal 2 - Frontend
cd frontend && npm run dev
```

### Testing the API
Run the comprehensive API test suite to verify all endpoints:

```bash
# Make sure the backend is running first
./test_api.sh
```

This will test all API endpoints including:
- Root endpoint health check
- Text-to-Speech generation and audio download
- Speech-to-Text transcription
- Text-to-Image generation
- YouTube video download
- Video-to-Text transcription

## API Overview

### YouTube Downloader
- `POST /api/youtube/download` - Download video from URL

### Text to Speech
- `POST /api/tts/generate` - Generate speech from markdown text
- `GET /api/tts/audio/{id}` - Download generated audio

### Speech to Text
- `POST /api/stt/transcribe` - Transcribe audio file or URL

### Video to Text
- `POST /api/video-text/transcribe` - Transcribe video file or YouTube URL

### Text to Image
- `POST /api/text-image/generate` - Generate images from prompt

### LLM Interaction
- `POST /api/llm` - Get a response from a language model

## Licensing

This project code is licensed under the MIT License.

Note: youtube-dl is licensed under the Unlicense. Whisper and other AI models have their respective licenses.

## Limitations and Legal Notes

- YouTube download must comply with YouTube's Terms of Service.
- Usage constraints for external AI APIs apply.
