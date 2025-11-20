"""
Text-to-Speech API endpoints.
Provides endpoints for generating speech from markdown text and downloading audio files.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from models.tts import TTSGenerateRequest, TTSGenerateResponse
from services.tts_service import (
    normalize_markdown_to_text,
    detect_language,
    preprocess_text_for_tts,
    synthesize_speech_to_mp3
)
from core.config import config
from core.error_handling import AppError

logger = logging.getLogger(__name__)

# Create router for TTS endpoints
router = APIRouter(prefix="/tts", tags=["Text-to-Speech"])


@router.post("/generate", response_model=TTSGenerateResponse)
async def generate_speech(request: TTSGenerateRequest) -> TTSGenerateResponse:
    """
    Generates speech from markdown-formatted text.
    
    Processes the input through the following steps:
    1. Normalizes markdown to plain text
    2. Detects language
    3. Preprocesses text for natural speech
    4. Synthesizes speech and saves as MP3
    
    Used by the frontend to convert user-provided markdown text into downloadable audio.
    
    Args:
        request: Request containing markdown text
        
    Returns:
        Response with normalized text, detected language, and audio download URL
        
    Raises:
        AppError: If any step in the TTS pipeline fails
    """
    logger.info(f"Received TTS generation request, text length: {len(request.text_md)} characters")
    
    try:
        # Validate input
        if not request.text_md or len(request.text_md.strip()) == 0:
            raise AppError(
                code="INVALID_INPUT",
                message="Text input is required and cannot be empty",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        # Step 1: Normalize markdown to plain text
        normalized_text = normalize_markdown_to_text(request.text_md)
        
        if not normalized_text or len(normalized_text.strip()) == 0:
            raise AppError(
                code="INVALID_INPUT",
                message="After removing markdown formatting, no text remains",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        # Step 2: Detect language
        language = detect_language(normalized_text)
        
        # Step 3: Preprocess text for TTS
        preprocessed_text = preprocess_text_for_tts(normalized_text, language)
        
        # Step 4: Synthesize speech to MP3
        audio_id = synthesize_speech_to_mp3(preprocessed_text, language)
        
        # Build audio URL
        audio_url = f"/api/tts/audio/{audio_id}"
        
        logger.info(f"Successfully generated speech, audio_id: {audio_id}, language: {language}")
        
        return TTSGenerateResponse(
            text_normalized=normalized_text,
            language=language,
            audio_url=audio_url
        )
        
    except AppError:
        # Re-raise AppError to be handled by error handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error during TTS generation: {str(e)}", exc_info=True)
        raise AppError(
            code="TTS_GENERATION_FAILED",
            message=f"Failed to generate speech: {str(e)}",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@router.get("/audio/{audio_id}")
async def get_audio(audio_id: str) -> FileResponse:
    """
    Downloads a generated MP3 audio file by its ID.
    
    Retrieves the MP3 file from temporary storage and returns it with appropriate headers.
    Used by the frontend to download or play generated audio files.
    
    Args:
        audio_id: Unique identifier of the audio file (UUID)
        
    Returns:
        FileResponse containing the MP3 audio file
        
    Raises:
        AppError: If the audio file is not found
    """
    logger.info(f"Audio download request for ID: {audio_id}")
    
    try:
        # Construct file path
        temp_dir = Path(config.TTS_TEMP_DIR)
        file_path = temp_dir / f"{audio_id}.mp3"
        
        # Check if file exists
        if not file_path.exists():
            logger.warning(f"Audio file not found: {audio_id}")
            raise AppError(
                code="AUDIO_NOT_FOUND",
                message="Audio file not found",
                http_status=status.HTTP_404_NOT_FOUND
            )
        
        logger.info(f"Serving audio file: {file_path}")
        
        # Return file with appropriate headers
        return FileResponse(
            path=str(file_path),
            media_type="audio/mpeg",
            filename=f"tts-{audio_id}.mp3",
            headers={
                "Content-Disposition": f'attachment; filename="tts-{audio_id}.mp3"'
            }
        )
        
    except AppError:
        # Re-raise AppError to be handled by error handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error serving audio file: {str(e)}", exc_info=True)
        raise AppError(
            code="AUDIO_RETRIEVAL_FAILED",
            message=f"Failed to retrieve audio file: {str(e)}",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
