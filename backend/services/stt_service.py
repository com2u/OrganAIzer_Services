"""
Speech-to-Text service module.
Handles audio file validation, transcription using OpenAI Whisper, and metadata extraction.
"""

import logging
import tempfile
import os
from pathlib import Path
from fastapi import UploadFile
from typing import Tuple, Optional
import whisper
from core.config import config
from core.error_handling import AppError

logger = logging.getLogger(__name__)

# Load Whisper model (using base model for balance of speed/accuracy)
# Model is loaded once at module import to avoid reloading on each request
# Available models: tiny, base, small, medium, large
_whisper_model = None

def get_whisper_model():
    """
    Lazy-loads and returns the Whisper model.
    Uses base model by default for good balance of speed and accuracy.
    """
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper model (base)...")
        _whisper_model = whisper.load_model("base")
        logger.info("Whisper model loaded successfully")
    return _whisper_model


def validate_audio_file(file: UploadFile, max_size_mb: int = 25) -> None:
    """
    Validates the uploaded audio file.
    Checks file extension and size to ensure it's a valid MP3 file.
    
    Args:
        file: Uploaded audio file from the request
        max_size_mb: Maximum allowed file size in megabytes
        
    Raises:
        AppError: If the file is invalid (wrong format or too large)
    """
    logger.info(f"Validating audio file: {file.filename}")
    
    # Check if filename exists
    if not file.filename:
        raise AppError(
            code="INVALID_FILE",
            message="No filename provided",
            http_status=400
        )
    
    # Check file extension
    allowed_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise AppError(
            code="INVALID_FILE_FORMAT",
            message=f"Unsupported file format: {file_ext}. Allowed formats: {', '.join(allowed_extensions)}",
            http_status=400
        )
    
    # Check file size (if content_length is available)
    if file.size:
        max_size_bytes = max_size_mb * 1024 * 1024
        if file.size > max_size_bytes:
            raise AppError(
                code="FILE_TOO_LARGE",
                message=f"File size exceeds maximum limit of {max_size_mb}MB",
                http_status=400
            )
    
    logger.info(f"Audio file validation passed: {file.filename}")


async def transcribe_audio(file: UploadFile) -> Tuple[str, Optional[str], Optional[float]]:
    """
    Transcribes audio file to text using OpenAI Whisper.
    
    Process:
    1. Validates the uploaded file
    2. Saves to temporary file
    3. Uses Whisper to transcribe
    4. Extracts language and duration metadata
    5. Cleans up temporary file
    
    Args:
        file: Uploaded audio file (MP3 or other supported format)
        
    Returns:
        Tuple containing:
        - transcript (str): The transcribed text
        - language (str | None): Detected language code
        - duration (float | None): Audio duration in seconds
        
    Raises:
        AppError: If transcription fails
    """
    logger.info(f"Starting audio transcription for file: {file.filename}")
    
    # Validate the audio file
    validate_audio_file(file)
    
    # Create temporary file to store the uploaded audio
    temp_file = None
    try:
        # Read file contents
        file_contents = await file.read()
        
        if not file_contents:
            raise AppError(
                code="EMPTY_FILE",
                message="Uploaded file is empty",
                http_status=400
            )
        
        # Create temporary file with appropriate extension
        file_ext = Path(file.filename).suffix
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_file.write(file_contents)
        temp_file.close()
        
        logger.info(f"Audio file saved to temporary location: {temp_file.name}")
        
        # Load Whisper model
        model = get_whisper_model()
        
        # Transcribe audio
        logger.info("Starting Whisper transcription...")
        result = model.transcribe(temp_file.name)
        
        # Extract results
        transcript = result["text"].strip()
        language = result.get("language")
        
        # Get audio duration if available (Whisper provides segments with timestamps)
        duration = None
        if "segments" in result and result["segments"]:
            # Duration is the end time of the last segment
            last_segment = result["segments"][-1]
            duration = last_segment.get("end")
        
        logger.info(f"Transcription complete. Language: {language}, Duration: {duration}s")
        logger.info(f"Transcript length: {len(transcript)} characters")
        
        return transcript, language, duration
        
    except AppError:
        # Re-raise AppError to be handled by error handler
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}", exc_info=True)
        raise AppError(
            code="TRANSCRIPTION_FAILED",
            message=f"Failed to transcribe audio: {str(e)}",
            http_status=500
        )
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
                logger.info(f"Temporary file cleaned up: {temp_file.name}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")
