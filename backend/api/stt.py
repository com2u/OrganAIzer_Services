"""
Speech-to-Text API endpoints.
Provides endpoints for transcribing audio files to text.
"""

import logging
from fastapi import APIRouter, UploadFile, File, status
from models.stt import STTTranscribeResponse
from services.stt_service import transcribe_audio
from core.error_handling import AppError

logger = logging.getLogger(__name__)

# Create router for STT endpoints
router = APIRouter(prefix="/stt", tags=["Speech-to-Text"])


@router.post("/transcribe", response_model=STTTranscribeResponse)
async def transcribe_speech(
    file: UploadFile = File(..., description="Audio file to transcribe (MP3, WAV, M4A, OGG, FLAC)")
) -> STTTranscribeResponse:
    """
    Transcribes an audio file to text using OpenAI Whisper.
    
    Processes the uploaded audio through:
    1. File validation (format and size checks)
    2. Audio transcription using Whisper model
    3. Language detection
    4. Duration extraction
    
    Used by the frontend to convert audio files into text transcripts.
    
    Args:
        file: Uploaded audio file (supports MP3, WAV, M4A, OGG, FLAC formats)
        
    Returns:
        Response with transcribed text, detected language, and audio duration
        
    Raises:
        AppError: If file validation or transcription fails
    """
    logger.info(f"Received STT transcription request for file: {file.filename}")
    
    try:
        # Validate that a file was uploaded
        if not file:
            raise AppError(
                code="NO_FILE",
                message="No audio file provided",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        # Transcribe the audio file
        transcript, language, duration = await transcribe_audio(file)
        
        logger.info(f"Successfully transcribed audio: {file.filename}")
        
        return STTTranscribeResponse(
            transcript=transcript,
            language=language,
            duration_seconds=duration
        )
        
    except AppError:
        # Re-raise AppError to be handled by error handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error during STT transcription: {str(e)}", exc_info=True)
        raise AppError(
            code="STT_TRANSCRIPTION_FAILED",
            message=f"Failed to transcribe audio: {str(e)}",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
