"""
Unified video transcription service.
Handles YouTube URLs, generic video URLs, and uploaded video files.
"""

import logging
import tempfile
import os
import time
import subprocess
import requests
from pathlib import Path
from typing import Tuple, Optional
from services.youtube_service import (
    download_youtube_audio_with_retry,
    transcribe_with_openrouter,
    CHUNK_THRESHOLD_BYTES,
    MAX_DOWNLOAD_RETRIES
)
from services.stt_service import transcribe_audio_chunked
from core.error_handling import AppError
from utils.cache import get_cache

logger = logging.getLogger(__name__)


def download_video_from_url(video_url: str) -> str:
    """
    Downloads a video from a generic URL (not YouTube).
    
    Args:
        video_url: Direct URL to video file (.mp4, .mov, .mkv, etc.)
        
    Returns:
        Path to the downloaded video file
        
    Raises:
        AppError: If download fails
    """
    logger.info(f"Downloading video from URL: {video_url}")
    
    for attempt in range(MAX_DOWNLOAD_RETRIES):
        try:
            logger.info(f"Download attempt {attempt + 1}/{MAX_DOWNLOAD_RETRIES}")
            
            # Create temporary file
            tmpdir = tempfile.mkdtemp()
            
            # Determine file extension from URL
            url_path = video_url.split('?')[0]  # Remove query params
            ext = Path(url_path).suffix or '.mp4'
            video_path = os.path.join(tmpdir, f"video{ext}")
            
            # Download the video with streaming
            logger.info(f"Starting download...")
            response = requests.get(video_url, stream=True, timeout=300)
            response.raise_for_status()
            
            # Write to file
            with open(video_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Validate file size
            file_size_bytes = os.path.getsize(video_path)
            if file_size_bytes == 0:
                raise Exception("Downloaded file is empty")
            
            file_size_mb = file_size_bytes / (1024 * 1024)
            logger.info(f"Video downloaded: {video_path} ({file_size_mb:.2f} MB)")
            logger.info(f"Download successful on attempt {attempt + 1}")
            
            return video_path
            
        except Exception as e:
            logger.error(f"Download attempt {attempt + 1} failed: {e}")
            
            # Clean up failed download
            if 'tmpdir' in locals() and os.path.exists(tmpdir):
                try:
                    import shutil
                    shutil.rmtree(tmpdir)
                except:
                    pass
            
            if attempt < MAX_DOWNLOAD_RETRIES - 1:
                wait_time = 2 ** attempt
                logger.info(f"Retrying download in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"All {MAX_DOWNLOAD_RETRIES} download attempts failed")
                raise AppError(
                    code="DOWNLOAD_FAILED",
                    message=f"Failed to download video from URL after {MAX_DOWNLOAD_RETRIES} attempts: {str(e)}",
                    http_status=500
                )


def extract_audio_with_ffmpeg(video_path: str) -> str:
    """
    Extracts audio from video file using ffmpeg.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Path to the extracted audio file (MP3)
        
    Raises:
        AppError: If audio extraction fails
    """
    logger.info(f"Extracting audio from video: {video_path}")
    
    try:
        # Create output path for audio
        audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
        
        # Run ffmpeg to extract audio
        # -i: input file
        # -vn: no video
        # -acodec libmp3lame: MP3 codec
        # -ab 128k: audio bitrate
        # -ar 16000: sample rate 16kHz (good for speech)
        # -ac 1: mono audio
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # No video
            '-acodec', 'libmp3lame',
            '-ab', '128k',
            '-ar', '16000',
            '-ac', '1',
            '-y',  # Overwrite output file
            audio_path
        ]
        
        logger.info(f"Running ffmpeg command...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            raise Exception(f"ffmpeg failed with return code {result.returncode}: {result.stderr}")
        
        # Validate output file
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            raise Exception("Audio extraction produced empty file")
        
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        logger.info(f"Audio extracted: {audio_path} ({file_size_mb:.2f} MB)")
        
        return audio_path
        
    except subprocess.TimeoutExpired:
        raise AppError(
            code="AUDIO_EXTRACTION_TIMEOUT",
            message="Audio extraction timed out after 5 minutes",
            http_status=500
        )
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}", exc_info=True)
        raise AppError(
            code="AUDIO_EXTRACTION_FAILED",
            message=f"Failed to extract audio from video: {str(e)}",
            http_status=500
        )


async def transcribe_video(
    source_type: str,
    video_url: Optional[str] = None,
    file_path: Optional[str] = None,
    language_preference: str = "auto",
    quality_mode: str = "accurate"
) -> Tuple[str, Optional[str]]:
    """
    Unified video transcription function.
    Handles YouTube URLs, generic video URLs, and uploaded files.
    
    Args:
        source_type: "youtube", "url", or "upload"
        video_url: Video URL (for youtube and url types)
        file_path: Path to uploaded file (for upload type)
        language_preference: Language hint for transcription
        quality_mode: "fast" or "accurate"
        
    Returns:
        Tuple containing:
        - transcript (str): The transcribed text
        - detected_language (str | None): Detected language code
        
    Raises:
        AppError: If transcription fails
    """
    pipeline_start = time.time()
    logger.info(f"=" * 80)
    logger.info(f"Starting unified video transcription pipeline")
    logger.info(f"Source Type: {source_type}")
    logger.info(f"Language Preference: {language_preference}")
    logger.info(f"Quality Mode: {quality_mode}")
    logger.info(f"=" * 80)
    
    video_file_path = None
    audio_path = None
    temp_dirs = []
    
    try:
        # Step 1: Get video file based on source type
        if source_type == "youtube":
            if not video_url:
                raise AppError(
                    code="INVALID_REQUEST",
                    message="video_url is required for youtube source type",
                    http_status=400
                )
            
            # Check cache first
            cache = get_cache()
            cache_key = f"{video_url}_{language_preference}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.info("Returning cached transcription")
                return cached_data['transcript'], cached_data.get('metadata', {}).get('language')
            
            logger.info(f"Processing YouTube URL: {video_url}")
            # Use existing YouTube download logic
            audio_path = download_youtube_audio_with_retry(video_url, quality_mode)
            temp_dirs.append(os.path.dirname(audio_path))
            
        elif source_type == "url":
            if not video_url:
                raise AppError(
                    code="INVALID_REQUEST",
                    message="video_url is required for url source type",
                    http_status=400
                )
            
            logger.info(f"Processing generic video URL: {video_url}")
            # Download video from URL
            video_file_path = download_video_from_url(video_url)
            temp_dirs.append(os.path.dirname(video_file_path))
            
            # Extract audio using ffmpeg
            audio_path = extract_audio_with_ffmpeg(video_file_path)
            
        elif source_type == "upload":
            if not file_path:
                raise AppError(
                    code="INVALID_REQUEST",
                    message="file_path is required for upload source type",
                    http_status=400
                )
            
            logger.info(f"Processing uploaded file: {file_path}")
            video_file_path = file_path
            
            # Extract audio using ffmpeg
            audio_path = extract_audio_with_ffmpeg(video_file_path)
            temp_dirs.append(os.path.dirname(audio_path))
            
        else:
            raise AppError(
                code="INVALID_SOURCE_TYPE",
                message=f"Invalid source_type: {source_type}",
                http_status=400
            )
        
        # Step 2: Transcribe audio
        file_size = os.path.getsize(audio_path)
        needs_chunking = file_size > CHUNK_THRESHOLD_BYTES
        
        # Prepare language parameter for Whisper
        language_param = None if language_preference == "auto" else language_preference
        
        if needs_chunking:
            logger.info(f"File size ({file_size / (1024*1024):.2f}MB) exceeds threshold, using chunked transcription with Whisper")
            transcript, detected_language, duration = transcribe_audio_chunked(audio_path, language_param)
        else:
            logger.info(f"Using OpenRouter for transcription")
            transcript = transcribe_with_openrouter(audio_path, quality_mode)
            detected_language = language_param  # OpenRouter doesn't return language detection
        
        # Cache the result for YouTube
        if source_type == "youtube":
            cache.set(
                cache_key,
                transcript,
                metadata={
                    'language': detected_language,
                    'quality_mode': quality_mode,
                    'file_size': file_size,
                    'chunked': needs_chunking
                }
            )
        
        pipeline_duration = time.time() - pipeline_start
        logger.info(f"=" * 80)
        logger.info(f"Video transcription COMPLETE!")
        logger.info(f"TOTAL PIPELINE TIME: {pipeline_duration:.2f}s ({pipeline_duration/60:.2f} minutes)")
        logger.info(f"=" * 80)
        
        return transcript, detected_language
        
    finally:
        # Clean up temporary files
        if audio_path and os.path.exists(audio_path):
            try:
                os.unlink(audio_path)
                logger.info(f"Cleaned up audio file: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to delete audio file: {e}")
        
        if video_file_path and source_type == "url" and os.path.exists(video_file_path):
            try:
                os.unlink(video_file_path)
                logger.info(f"Cleaned up video file: {video_file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete video file: {e}")
        
        # Clean up temporary directories
        for tmpdir in temp_dirs:
            if os.path.exists(tmpdir) and not os.listdir(tmpdir):
                try:
                    os.rmdir(tmpdir)
                    logger.info(f"Cleaned up temp directory: {tmpdir}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp directory: {e}")
