"""
Speech-to-Text service module.
Handles audio file validation, transcription using OpenAI Whisper, and metadata extraction.
Supports chunking for large files and caching for efficiency.
"""

import logging
import tempfile
import os
from pathlib import Path
from fastapi import UploadFile
from typing import Tuple, Optional, List
import whisper
import time
from core.config import config
from core.error_handling import AppError
from utils.audio import split_audio, merge_transcripts, cleanup_chunks, get_audio_duration
from utils.cache import get_cache, compute_file_hash

logger = logging.getLogger(__name__)

# File size threshold for chunking (15MB)
CHUNK_THRESHOLD_BYTES = 15 * 1024 * 1024

# Maximum retries for transcription
MAX_RETRIES = 3

# Load Whisper model (using medium model for better accuracy)
# Model is loaded once at module import to avoid reloading on each request
# Available models: tiny, base, small, medium, large
# Medium model provides much better accuracy for English and German
_whisper_model = None

def get_whisper_model():
    """
    Lazy-loads and returns the Whisper model.
    Uses medium model for better accuracy with English and German.
    """
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper model (medium)...")
        _whisper_model = whisper.load_model("medium")
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


def transcribe_chunk_with_retry(chunk_path: str, chunk_index: int, model, language: Optional[str] = None) -> Optional[str]:
    """
    Transcribe a single audio chunk with retry logic.
    
    Args:
        chunk_path: Path to the audio chunk
        chunk_index: Index of the chunk
        model: Whisper model instance
        language: Optional language hint (e.g., 'en', 'de')
        
    Returns:
        Transcribed text or None if all retries fail
    """
    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Transcribing chunk {chunk_index}, attempt {attempt + 1}/{MAX_RETRIES}")
            
            # Transcribe with language hint if provided
            transcribe_options = {}
            if language:
                transcribe_options['language'] = language
                logger.info(f"Using language hint: {language}")
            
            result = model.transcribe(chunk_path, **transcribe_options)
            transcript = result["text"].strip()
            logger.info(f"Chunk {chunk_index} transcribed successfully: {len(transcript)} characters")
            return transcript
            
        except Exception as e:
            logger.error(f"Chunk {chunk_index} transcription attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                # Wait before retry (exponential backoff)
                wait_time = 2 ** attempt
                logger.info(f"Retrying chunk {chunk_index} in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"All retries failed for chunk {chunk_index}")
                return None


def transcribe_audio_chunked(filepath: str, language: Optional[str] = None) -> Tuple[str, Optional[str], Optional[float]]:
    """
    Transcribe large audio files by splitting into chunks.
    
    Args:
        filepath: Path to the audio file
        language: Optional language hint (e.g., 'en', 'de')
        
    Returns:
        Tuple containing transcript, language, and duration
        
    Raises:
        AppError: If chunking or transcription fails
    """
    chunk_paths = []
    try:
        logger.info(f"Starting chunked transcription for: {filepath}")
        if language:
            logger.info(f"Using language hint: {language}")
        
        # Get audio duration
        duration = get_audio_duration(filepath)
        logger.info(f"Audio duration: {duration:.2f}s")
        
        # Split audio into chunks
        chunk_paths = split_audio(filepath, chunk_duration_minutes=5)
        logger.info(f"Split audio into {len(chunk_paths)} chunks")
        
        # Load Whisper model
        model = get_whisper_model()
        
        # Transcribe each chunk
        transcripts = []
        detected_language = None
        
        for i, chunk_path in enumerate(chunk_paths):
            transcript_text = transcribe_chunk_with_retry(chunk_path, i, model, language)
            
            if transcript_text:
                transcripts.append((i, transcript_text))
            else:
                logger.warning(f"Skipping chunk {i} due to transcription failure")
        
        if not transcripts:
            raise AppError(
                code="ALL_CHUNKS_FAILED",
                message="All audio chunks failed to transcribe",
                http_status=500
            )
        
        # Merge transcripts
        merged_transcript = merge_transcripts(transcripts)
        
        # Try to detect language from first successful chunk if not provided
        if not language and transcripts:
            try:
                first_chunk = chunk_paths[transcripts[0][0]]
                result = model.transcribe(first_chunk)
                detected_language = result.get("language")
            except Exception as e:
                logger.warning(f"Failed to detect language: {e}")
        else:
            detected_language = language
        
        logger.info(f"Chunked transcription complete: {len(merged_transcript)} total characters")
        
        return merged_transcript, detected_language, duration
        
    except AppError:
        raise
    except Exception as e:
        logger.error(f"Chunked transcription failed: {e}", exc_info=True)
        raise AppError(
            code="CHUNKED_TRANSCRIPTION_FAILED",
            message=f"Failed to transcribe chunked audio: {str(e)}",
            http_status=500
        )
    finally:
        # Clean up chunks
        if chunk_paths:
            cleanup_chunks(chunk_paths)


async def transcribe_audio(file: UploadFile, use_cache: bool = True, language: Optional[str] = None) -> Tuple[str, Optional[str], Optional[float]]:
    """
    Transcribes audio file to text using OpenAI Whisper.
    Automatically uses chunking for large files (>15MB).
    Supports caching to avoid re-processing the same files.
    
    Process:
    1. Validates the uploaded file
    2. Checks cache if enabled
    3. Saves to temporary file
    4. Determines if chunking is needed
    5. Transcribes (chunked or whole)
    6. Caches result if enabled
    7. Cleans up temporary files
    
    Args:
        file: Uploaded audio file (MP3 or other supported format)
        use_cache: Whether to use caching (default: True)
        language: Optional language hint (e.g., 'en' for English, 'de' for German)
        
    Returns:
        Tuple containing:
        - transcript (str): The transcribed text
        - language (str | None): Detected language code
        - duration (float | None): Audio duration in seconds
        
    Raises:
        AppError: If transcription fails
    """
    logger.info(f"Starting audio transcription for file: {file.filename}")
    if language:
        logger.info(f"Using language hint: {language}")
    
    # Validate the audio file
    validate_audio_file(file, max_size_mb=500)  # Increased limit with chunking
    
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
        
        file_size = len(file_contents)
        logger.info(f"File size: {file_size / (1024*1024):.2f}MB")
        
        # Create temporary file with appropriate extension
        file_ext = Path(file.filename).suffix
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_file.write(file_contents)
        temp_file.close()
        
        logger.info(f"Audio file saved to temporary location: {temp_file.name}")
        
        # Check cache if enabled
        if use_cache:
            file_hash = compute_file_hash(temp_file.name)
            cache = get_cache()
            cached_data = cache.get(file_hash)
            
            if cached_data:
                logger.info("Returning cached transcription")
                return (
                    cached_data['transcript'],
                    cached_data.get('metadata', {}).get('language'),
                    cached_data.get('metadata', {}).get('duration')
                )
        
        # Determine if chunking is needed
        needs_chunking = file_size > CHUNK_THRESHOLD_BYTES
        
        if needs_chunking:
            logger.info(f"File size ({file_size / (1024*1024):.2f}MB) exceeds threshold, using chunked transcription")
            transcript, detected_language, duration = transcribe_audio_chunked(temp_file.name, language)
        else:
            logger.info("Using standard transcription")
            # Load Whisper model
            model = get_whisper_model()
            
            # Transcribe audio with language hint if provided
            logger.info("Starting Whisper transcription...")
            transcribe_options = {}
            if language:
                transcribe_options['language'] = language
            
            result = model.transcribe(temp_file.name, **transcribe_options)
            
            # Extract results
            transcript = result["text"].strip()
            detected_language = result.get("language") if not language else language
            
            # Get audio duration if available
            duration = None
            if "segments" in result and result["segments"]:
                last_segment = result["segments"][-1]
                duration = last_segment.get("end")
        
        logger.info(f"Transcription complete. Language: {detected_language}, Duration: {duration}s")
        logger.info(f"Transcript length: {len(transcript)} characters")
        
        # Cache the result if enabled
        if use_cache:
            cache.set(
                file_hash,
                transcript,
                metadata={
                    'language': detected_language,
                    'duration': duration,
                    'filename': file.filename,
                    'file_size': file_size,
                    'chunked': needs_chunking
                }
            )
        
        return transcript, detected_language, duration
        
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
