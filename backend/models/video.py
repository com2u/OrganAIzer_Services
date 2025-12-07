"""
Data models for unified video transcription endpoints.
Supports YouTube URLs, generic video URLs, and file uploads.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Literal, Optional


class VideoTranscribeRequest(BaseModel):
    """Request model for unified video transcription."""
    source_type: Literal["youtube", "url", "upload"] = Field(
        ...,
        description="Type of video source: 'youtube', 'url', or 'upload'"
    )
    video_url: Optional[str] = Field(
        None,
        description="Video URL (required for 'youtube' and 'url' types)"
    )
    language_preference: str = Field(
        default="auto",
        description="Language preference for transcription (e.g., 'en', 'de', 'auto')"
    )
    quality_mode: Literal["fast", "accurate"] = Field(
        default="accurate",
        description="Quality mode: 'fast' (lower quality, faster) or 'accurate' (higher quality, slower)"
    )


class VideoTranscribeResponse(BaseModel):
    """Response model for unified video transcription."""
    source_type: str = Field(..., description="Type of video source used")
    source_url: Optional[str] = Field(None, description="Original video URL (if applicable)")
    transcript: str = Field(..., description="Transcribed text from the video")
    detected_language: Optional[str] = Field(None, description="Detected language code")
