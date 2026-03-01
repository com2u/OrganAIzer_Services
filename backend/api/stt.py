"""
Speech-to-Text API endpoints.
Provides endpoints for transcribing audio files to text.

whisper/torch are NOT imported at module level – they are loaded lazily on
the first transcription request.  If they are unavailable the endpoint
returns HTTP 503 with a JSON body describing the problem; all other
endpoints remain unaffected.
"""

import logging
from fastapi import APIRouter, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from typing import Optional
from models.stt import STTTranscribeResponse
from services.stt_service import transcribe_audio
from core.error_handling import AppError

logger = logging.getLogger(__name__)

# Create router for STT endpoints
router = APIRouter(tags=["Speech-to-Text"])


@router.post("/transcribe", response_model=STTTranscribeResponse)
async def transcribe_speech(
    file: UploadFile = File(..., description="Audio file to transcribe (MP3, WAV, M4A, OGG, FLAC, WEBM)"),
    language: Optional[str] = Form(None, description="Language hint (e.g., 'en' for English, 'de' for German)")
) -> STTTranscribeResponse:
    """
    Transcribes an audio file to text using OpenAI Whisper.

    whisper and torch are loaded lazily on the first call.  If they are not
    installed or fail to initialise, this endpoint returns HTTP 503:
      { "error": { "code": "STT_UNAVAILABLE", "message": "STT backend unavailable",
                   "details": { "details": "whisper/torch import failed: ..." } } }

    Args:
        file: Uploaded audio file (supports MP3, WAV, M4A, OGG, FLAC, WEBM formats)
        language: Optional language code hint (e.g., 'en', 'de', 'es', 'fr')

    Returns:
        Response with transcribed text, detected language, and audio duration

    Raises:
        HTTP 503: If whisper/torch is not available
        HTTP 4xx/500: If file validation or transcription fails
    """
    logger.info(f"Received STT transcription request for file: {file.filename}")
    if language:
        logger.info(f"Language hint provided: {language}")

    try:
        if not file:
            raise AppError(
                code="NO_FILE",
                message="No audio file provided",
                http_status=status.HTTP_400_BAD_REQUEST
            )

        # transcribe_audio will raise AppError(503) if whisper/torch is unavailable
        transcript, detected_language, duration = await transcribe_audio(file, language=language)

        logger.info(f"Successfully transcribed audio: {file.filename}")

        return STTTranscribeResponse(
            transcript=transcript,
            language=detected_language,
            duration_seconds=duration
        )

    except AppError:
        # Re-raise – the global AppError handler in main.py converts this to
        # the correct HTTP status code and JSON body.
        raise
    except Exception as e:
        logger.error(f"Unexpected error during STT transcription: {str(e)}", exc_info=True)
        raise AppError(
            code="STT_TRANSCRIPTION_FAILED",
            message=f"Failed to transcribe audio: {str(e)}",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
