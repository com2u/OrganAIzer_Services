"""
YouTube transcription API endpoints.
Provides endpoints for transcribing YouTube videos to text.
"""

import logging
from fastapi import APIRouter, status
from models.youtube import YoutubeTranscribeRequest, YoutubeTranscribeResponse
from services.video_service import transcribe_video
from core.error_handling import AppError

logger = logging.getLogger(__name__)

# Create router for YouTube endpoints
router = APIRouter(prefix="/youtube", tags=["YouTube"])


@router.post("/transcribe", response_model=YoutubeTranscribeResponse)
async def transcribe_youtube(
    body: YoutubeTranscribeRequest
) -> YoutubeTranscribeResponse:
    """
    Transcribes a YouTube video to text.
    
    Downloads the audio from the provided YouTube URL and transcribes it
    using OpenRouter's audio-capable AI model.
    
    Process:
    1. Downloads audio from YouTube using yt-dlp
    2. Transcribes audio using OpenRouter API (gpt-4o-audio-preview)
    3. Returns the transcript
    
    Quality Modes:
    - fast: Lower audio quality (64kbps), smaller files, faster processing
    - accurate: Higher audio quality (128kbps), better transcription accuracy
    
    Used by the frontend to convert YouTube videos into text transcripts.
    
    Args:
        body: Request containing the YouTube URL and quality mode
        
    Returns:
        Response with the original URL and transcribed text
        
    Raises:
        AppError: If download or transcription fails
    """
    logger.info(f"Received YouTube transcription request for URL: {body.url} (mode: {body.quality_mode})")
    
    try:
        # Use unified video transcription pipeline with source_type="youtube"
        # This maintains backwards compatibility while using the new unified system
        transcript, detected_language = await transcribe_video(
            source_type="youtube",
            video_url=str(body.url),
            language_preference="auto",
            quality_mode=body.quality_mode
        )
        
        logger.info(f"Successfully transcribed YouTube video: {body.url}")
        
        return YoutubeTranscribeResponse(
            url=str(body.url),
            transcript=transcript
        )
        
    except AppError:
        # Re-raise AppError to be handled by error handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error during YouTube transcription: {str(e)}", exc_info=True)
        raise AppError(
            code="YOUTUBE_TRANSCRIPTION_FAILED",
            message=f"Failed to transcribe YouTube video: {str(e)}",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
