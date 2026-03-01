"""
Pydantic models for Speech-to-Text API endpoints.
Contains request and response schemas for STT operations.
"""

from pydantic import BaseModel, Field
from typing import Optional


class STTTranscribeResponse(BaseModel):
    """
    Response model for POST /api/stt/transcribe endpoint.
    Returns the transcribed text and optional metadata.
    """
    transcript: str = Field(
        ...,
        description="Transcribed text from the audio file"
    )
    language: Optional[str] = Field(
        None,
        description="Detected language code (e.g., 'en', 'de', 'es')"
    )
    duration_seconds: Optional[float] = Field(
        None,
        description="Duration of the audio file in seconds"
    )
