"""
Data models for YouTube transcription endpoints.
Defines request and response models for YouTube-to-text transcription.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Literal


class YoutubeTranscribeRequest(BaseModel):
    """Request model for YouTube video transcription."""
    url: HttpUrl = Field(
        ...,
        description="YouTube video URL to transcribe",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
    )
    quality_mode: Literal["fast", "accurate"] = Field(
        default="accurate",
        description="Quality mode: 'fast' (lower quality, faster) or 'accurate' (higher quality, slower)"
    )


class YoutubeTranscribeResponse(BaseModel):
    """Response model for YouTube video transcription."""
    url: str = Field(..., description="Original YouTube URL")
    transcript: str = Field(..., description="Transcribed text from the video")
