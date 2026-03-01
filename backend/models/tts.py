"""
Pydantic models for Text-to-Speech API endpoints.
Contains request and response schemas for TTS operations.
"""

from pydantic import BaseModel, Field


class TTSGenerateRequest(BaseModel):
    """
    Request model for POST /api/tts/generate endpoint.
    Accepts markdown-formatted text to be converted to speech.
    """
    text_md: str = Field(
        ...,
        min_length=1,
        description="Markdown-formatted text to convert to speech"
    )


class TTSGenerateResponse(BaseModel):
    """
    Response model for POST /api/tts/generate endpoint.
    Returns normalized text, detected language, and URL to download the generated audio.
    """
    text_normalized: str = Field(
        ...,
        description="Plain text extracted from markdown, used for speech synthesis"
    )
    language: str = Field(
        ...,
        description="Detected language code (e.g., 'en', 'de', 'es')"
    )
    audio_url: str = Field(
        ...,
        description="URL to download the generated MP3 audio file"
    )
