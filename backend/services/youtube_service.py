"""
YouTube service module.
Handles downloading audio from YouTube videos and transcribing them.
Includes retry logic, chunking support, and caching.
"""

import logging
import tempfile
import os
import yt_dlp
from yt_dlp import YoutubeDL
import time
import base64
import json
import requests
from pathlib import Path
from typing import Tuple, Optional
from services.stt_service import get_whisper_model, transcribe_audio_chunked
from core.error_handling import AppError
from utils.cache import get_cache
from utils.audio import get_audio_duration

logger = logging.getLogger(__name__)

# Maximum retries for downloads
MAX_DOWNLOAD_RETRIES = 3

# File size threshold for chunking (15MB)
CHUNK_THRESHOLD_BYTES = 15 * 1024 * 1024


def get_openrouter_api_key():
    """Get OpenRouter API key from environment variables."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY is not set in environment variables")
        raise AppError(
            code="API_KEY_NOT_SET",
            message="OPENROUTER_API_KEY environment variable is not set",
            http_status=500
        )
    return api_key


def download_youtube_audio_with_retry(youtube_url: str, quality_mode: str = "accurate") -> str:
    """
    Downloads audio from a YouTube video using yt-dlp with retry logic.
    
    Args:
        youtube_url: The YouTube video URL to download
        quality_mode: "fast" (64kbps, faster) or "accurate" (128kbps, better quality)
        
    Returns:
        Path to the downloaded audio file (MP3 format)
        
    Raises:
        AppError: If download fails after all retries or file is empty
    """
    logger.info(f"Starting audio download from YouTube URL: {youtube_url} (mode: {quality_mode})")
    
    for attempt in range(MAX_DOWNLOAD_RETRIES):
        try:
            logger.info(f"Download attempt {attempt + 1}/{MAX_DOWNLOAD_RETRIES}")
            
            # Create temporary directory for download
            tmpdir = tempfile.mkdtemp()
            outtmpl = os.path.join(tmpdir, "audio.%(ext)s")
            
            # Configure yt-dlp options
            ydl_opts = {
                "format": "worstaudio/worst" if quality_mode == "fast" else "bestaudio/best",
                "outtmpl": outtmpl,
                "noplaylist": True,
                "no_part": True,
                "quiet": False,
                "no_warnings": False,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "64" if quality_mode == "fast" else "128",
                }],
            }
            
            logger.info(f"Starting yt-dlp download...")
            
            # Download the audio
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                logger.info(f"Video title: {info.get('title', 'Unknown')}")
                logger.info(f"Duration: {info.get('duration', 0)} seconds")
            
            # Find the downloaded audio file
            logger.info(f"Searching for audio file in: {tmpdir}")
            audio_files = [f for f in os.listdir(tmpdir) if f.startswith("audio.")]
            
            if not audio_files:
                logger.error(f"No audio file found in {tmpdir}")
                raise Exception("No audio file was created")
            
            audio_path = os.path.join(tmpdir, audio_files[0])
            logger.info(f"Found audio file: {audio_path}")
            
            # Validate file size
            file_size_bytes = os.path.getsize(audio_path)
            if file_size_bytes == 0:
                logger.error(f"Downloaded audio file is EMPTY (0 bytes): {audio_path}")
                raise Exception("Downloaded file is empty")
            
            file_size_mb = file_size_bytes / (1024 * 1024)
            logger.info(f"Audio file: {audio_path} ({file_size_mb:.2f} MB)")
            logger.info(f"Download successful on attempt {attempt + 1}")
            
            return audio_path
            
        except Exception as e:
            logger.error(f"Download attempt {attempt + 1} failed: {e}")
            
            # Clean up failed download directory
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
                    message=f"Failed to download YouTube audio after {MAX_DOWNLOAD_RETRIES} attempts: {str(e)}",
                    http_status=500
                )


def download_youtube_audio(youtube_url: str, quality_mode: str = "accurate") -> str:
    """
    Legacy wrapper for download_youtube_audio_with_retry.
    Maintained for backwards compatibility.
    """
    return download_youtube_audio_with_retry(youtube_url, quality_mode)


def transcribe_with_openrouter(audio_path: str, quality_mode: str = "accurate") -> str:
    """
    Transcribes audio file using OpenRouter API with audio-capable model.
    
    Args:
        audio_path: Path to the audio file to transcribe
        quality_mode: "fast" or "accurate" (currently same model, for future expansion)
        
    Returns:
        The transcribed text
        
    Raises:
        AppError: If transcription fails
    """
    start_time = time.time()
    logger.info(f"Starting transcription with OpenRouter: {audio_path}")
    
    # Get API key
    api_key = get_openrouter_api_key()
    
    try:
        # Read and encode audio file as base64
        logger.info(f"Encoding audio file...")
        
        with open(audio_path, "rb") as f:
            audio_data = f.read()
            b64_audio = base64.b64encode(audio_data).decode("utf-8")
        
        file_size_mb = len(audio_data) / (1024 * 1024)
        logger.info(f"Audio size: {file_size_mb:.2f} MB")
        
        # Determine audio format from file extension
        audio_format = "mp3" if audio_path.endswith(".mp3") else "m4a"
        
        # Prepare request headers
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "OrganAIzer",
        }
        
        # Prepare request body
        body = {
            "model": "openai/gpt-4o-audio-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Transcribe this audio in the original language. Return only the transcript text.",
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": b64_audio,
                                "format": audio_format,
                            },
                        },
                    ],
                }
            ],
        }
        
        # Make request to OpenRouter
        logger.info(f"Sending request to OpenRouter API...")
        
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(body),
            timeout=300,
        )
        
        logger.info(f"OpenRouter API response received")
        
        # Check for errors
        if not resp.ok:
            error_msg = f"OpenRouter API error: {resp.status_code}"
            try:
                error_data = resp.json()
                error_msg += f" - {error_data.get('error', {}).get('message', resp.text)}"
            except:
                error_msg += f" - {resp.text}"
            
            logger.error(error_msg)
            raise AppError(
                code="OPENROUTER_API_ERROR",
                message=error_msg,
                http_status=resp.status_code
            )
        
        # Parse response
        data = resp.json()
        
        # Extract transcript from response
        message_content = data["choices"][0]["message"]["content"]
        
        if isinstance(message_content, str):
            transcript = message_content.strip()
        else:
            # If it's a list of content blocks
            parts = []
            for block in message_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            transcript = "".join(parts).strip()
        
        total_duration = time.time() - start_time
        logger.info(f"Transcription complete in {total_duration:.2f}s")
        logger.info(f"Transcript length: {len(transcript)} characters")
        
        return transcript
        
    except AppError:
        # Re-raise AppError
        raise
    except Exception as e:
        logger.error(f"OpenRouter transcription failed: {str(e)}", exc_info=True)
        raise AppError(
            code="TRANSCRIPTION_FAILED",
            message=f"Failed to transcribe audio with OpenRouter: {str(e)}",
            http_status=500
        )


async def transcribe_youtube_video(youtube_url: str, quality_mode: str = "accurate") -> Tuple[str, str]:
    """
    Main function to download YouTube audio and transcribe it.
    Includes caching to avoid re-downloading/transcribing the same video.
    
    Args:
        youtube_url: The YouTube video URL to transcribe
        quality_mode: "fast" (lower quality, faster) or "accurate" (higher quality, slower)
        
    Returns:
        Tuple containing:
        - url (str): The original YouTube URL
        - transcript (str): The transcribed text
        
    Raises:
        AppError: If download or transcription fails
    """
    pipeline_start = time.time()
    logger.info(f"=" * 80)
    logger.info(f"Starting YouTube video transcription pipeline")
    logger.info(f"URL: {youtube_url}")
    logger.info(f"Quality Mode: {quality_mode}")
    logger.info(f"=" * 80)
    
    # Check cache first
    cache = get_cache()
    cached_data = cache.get(youtube_url)
    
    if cached_data:
        logger.info("Returning cached transcription")
        return youtube_url, cached_data['transcript']
    
    audio_path = None
    try:
        # Step 1: Download audio from YouTube (with retry logic)
        audio_path = download_youtube_audio_with_retry(youtube_url, quality_mode)
        
        # Step 2: Check if chunking is needed
        file_size = os.path.getsize(audio_path)
        needs_chunking = file_size > CHUNK_THRESHOLD_BYTES
        
        if needs_chunking:
            logger.info(f"File size ({file_size / (1024*1024):.2f}MB) exceeds threshold, using chunked transcription with Whisper")
            # Use local Whisper for chunked transcription (more reliable for long files)
            transcript, language, duration = transcribe_audio_chunked(audio_path)
        else:
            # Use OpenRouter for smaller files
            transcript = transcribe_with_openrouter(audio_path, quality_mode)
        
        # Cache the result
        cache.set(
            youtube_url,
            transcript,
            metadata={
                'quality_mode': quality_mode,
                'file_size': file_size,
                'chunked': needs_chunking
            }
        )
        
        # Calculate total pipeline time
        pipeline_duration = time.time() - pipeline_start
        
        logger.info(f"=" * 80)
        logger.info(f"YouTube video transcription COMPLETE!")
        logger.info(f"TOTAL PIPELINE TIME: {pipeline_duration:.2f}s ({pipeline_duration/60:.2f} minutes)")
        logger.info(f"=" * 80)
        
        return youtube_url, transcript
        
    finally:
        # Clean up temporary audio file and directory
        if audio_path and os.path.exists(audio_path):
            try:
                # Remove the audio file
                os.unlink(audio_path)
                
                # Remove the parent directory if it's empty
                parent_dir = os.path.dirname(audio_path)
                if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                    os.rmdir(parent_dir)
                
                logger.info(f"Temporary files cleaned up: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary files: {e}")
