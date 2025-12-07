# YouTube → Text Transcription Setup

This feature allows you to transcribe YouTube videos by pasting a URL into the frontend.

## Overview

The YouTube transcription feature:
1. Downloads audio from a YouTube video using `yt-dlp`
2. Sends the audio to OpenRouter API (using audio-capable GPT-4o model)
3. Returns the transcript to display in the frontend

## Backend Implementation

### Dependencies
- `yt-dlp==2024.12.3` - For downloading YouTube audio
- `requests==2.31.0` - For making HTTP requests to OpenRouter API

### Files Created
- `backend/models/youtube.py` - Pydantic models for request/response
- `backend/services/youtube_service.py` - Core transcription logic
- `backend/api/youtube.py` - FastAPI route handlers
- `backend/main.py` - Updated to register YouTube router

### API Endpoint
- **POST** `/api/youtube/transcribe`
  - Request body: `{ "url": "https://www.youtube.com/watch?v=..." }`
  - Response: `{ "url": "...", "transcript": "..." }`

## Frontend Implementation

### Files Created
- `frontend/src/pages/YouTubePage.tsx` - YouTube transcription page component

### Files Modified
- `frontend/src/App.tsx` - Added YouTube tab and routing

## Configuration

### Environment Variables
The backend requires the `OPENROUTER_API_KEY` environment variable to be set in `backend/.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-...
```

**Important:** The API key is only read on the backend and never exposed to the frontend.

## Usage

1. Ensure both backend and frontend services are running:
   ```bash
   .\start_services.bat
   ```

2. Navigate to http://localhost:5173 in your browser

3. Click on the "YouTube → Text" tab

4. Paste a YouTube URL (supports youtube.com, youtu.be, m.youtube.com)

5. Click "Transcribe" button

6. Wait for the transcription to complete (may take a few minutes depending on video length)

7. View and copy the transcript from the text area

## Features

- **Automatic audio download** - Uses yt-dlp to download audio from YouTube
- **High-quality transcription** - Uses OpenRouter's GPT-4o audio preview model
- **Original language support** - Transcribes in the video's original language
- **Error handling** - Clear error messages for invalid URLs, network errors, etc.
- **Loading states** - Visual feedback during transcription process
- **Copy to clipboard** - Easy copying of transcribed text

## Limitations

- Requires FFmpeg to be installed for audio conversion (yt-dlp dependency)
- Transcription time depends on video length and API response time
- Audio file size limits may apply based on OpenRouter API constraints
- May not work with age-restricted or private YouTube videos

## Troubleshooting

### "Failed to transcribe video" error
- Check that OPENROUTER_API_KEY is set in `backend/.env`
- Verify the YouTube URL is valid and accessible
- Check backend logs for detailed error messages
- Ensure FFmpeg is installed for audio conversion

### "Failed to download YouTube audio" error
- Verify the YouTube URL is valid
- Check your internet connection
- The video may be restricted (age-restricted, private, etc.)
- Try updating yt-dlp: `pip install --upgrade yt-dlp`

### API key not found
- Ensure `OPENROUTER_API_KEY` is set in `backend/.env`
- Restart the backend service after adding the key
- Verify the key is valid on OpenRouter

## Notes

- The feature uses the `openai/gpt-4o-audio-preview` model via OpenRouter
- Audio files are temporarily stored during processing and automatically cleaned up
- The backend auto-reloads when code changes are detected
