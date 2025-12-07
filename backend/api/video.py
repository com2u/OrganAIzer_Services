"""
Unified video transcription API endpoints.
Supports YouTube URLs, generic video URLs, and file uploads.
"""

import logging
import tempfile
import os
from fastapi import APIRouter, UploadFile, File, Form, status
from typing import Optional
from models.video import VideoTranscribeRequest, VideoTranscribeResponse
from services.video_service import transcribe_video
from core.error_handling import AppError

logger = logging.getLogger(__name__)

# Create router for video endpoints
router = APIRouter(prefix="/video", tags=["Video Transcription"])


@router.post("/transcribe", response_model=VideoTranscribeResponse)
async def transcribe_video_endpoint(
    source_type: str = Form(..., description="Type of video source: 'youtube', 'url', or 'upload'"),
    video_url: Optional[str] = Form(None, description="Video URL (required for 'youtube' and 'url' source types)"),
    language_preference: str = Form("auto", description="Language preference for transcription"),
    quality_mode: str = Form("accurate", description="Quality mode: 'fast' or 'accurate'"),
    file: Optional[UploadFile] = File(None, description="Video file (required for 'upload' source type)")
) -> VideoTranscribeResponse:
    """
    Unified endpoint for transcribing videos from multiple sources.
    
    Supports three input types:
    1. YouTube URL - Downloads and transcribes YouTube videos
    2. Generic video URL - Downloads and transcribes videos from direct links
    3. File upload - Transcribes user-uploaded video files
    
    Process:
    1. Validates input based on source type
    2. Downloads/receives video file
    3. Extracts audio using ffmpeg (for URL and upload types)
    4. Transcribes audio using Whisper or OpenRouter
    5. Returns transcript and metadata
    
    Args:
        source_type: Type of video source
        video_url: URL to video (for youtube and url types)
        language_preference: Language hint for better accuracy
        quality_mode: Transcription quality mode
        file: Uploaded video file (for upload type)
        
    Returns:
        Response with transcript and detected language
        
    Raises:
        AppError: If transcription fails or invalid input provided
    """
    logger.info(f"Received video transcription request (source_type: {source_type})")
    
    try:
        # Validate input based on source type
        if source_type in ["youtube", "url"]:
            if not video_url:
                raise AppError(
                    code="INVALID_REQUEST",
                    message=f"video_url is required for source_type '{source_type}'",
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            logger.info(f"Video URL: {video_url}")
            file_path = None
            
        elif source_type == "upload":
            if not file:
                raise AppError(
                    code="INVALID_REQUEST",
                    message="file is required for source_type 'upload'",
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save uploaded file to temporary location
            logger.info(f"Uploaded file: {file.filename}")
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
            try:
                content = await file.read()
                temp_file.write(content)
                temp_file.close()
                file_path = temp_file.name
                logger.info(f"Saved uploaded file to: {file_path}")
            except Exception as e:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
                raise AppError(
                    code="FILE_UPLOAD_FAILED",  
                    message=f"Failed to save uploaded file: {str(e)}",
                    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        else:
            raise AppError(
                code="INVALID_SOURCE_TYPE",
                message=f"Invalid source_type: {source_type}. Must be 'youtube', 'url', or 'upload'",
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        # Transcribe video using unified pipeline
        transcript, detected_language = await transcribe_video(
            source_type=source_type,
            video_url=video_url,
            file_path=file_path if source_type == "upload" else None,
            language_preference=language_preference,
            quality_mode=quality_mode
        )
        
        # Clean up uploaded file if it exists
        if source_type == "upload" and file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
                logger.info(f"Cleaned up uploaded file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete uploaded file: {e}")
        
        logger.info(f"Successfully transcribed video (source_type: {source_type})")
        
        return VideoTranscribeResponse(
            source_type=source_type,
            source_url=video_url if source_type in ["youtube", "url"] else None,
            transcript=transcript,
            detected_language=detected_language
        )
        
    except AppError:
        # Re-raise AppError to be handled by error handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error during video transcription: {str(e)}", exc_info=True)
        raise AppError(
            code="VIDEO_TRANSCRIPTION_FAILED",
            message=f"Failed to transcribe video: {str(e)}",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
