"""
Data models for Universal Translator feature.
"""

from typing import Optional
from pydantic import BaseModel, Field


class LanguageInfo(BaseModel):
    """Information about a supported language."""
    code: str = Field(..., description="Language code (e.g., 'en', 'de', 'fr')")
    name: str = Field(..., description="Language name (e.g., 'English', 'German')")


class LanguageDetectionResponse(BaseModel):
    """Response for language detection."""
    detected_language: str = Field(..., description="Detected language code")
    confidence: Optional[float] = Field(None, description="Detection confidence (0-1)")
    text_preview: str = Field(..., description="Preview of analyzed text")


class TextTranslationRequest(BaseModel):
    """Request for text translation."""
    text: str = Field(..., description="Text to translate")
    target_language: str = Field(..., description="Target language code (e.g., 'en', 'de')")
    source_language: Optional[str] = Field(
        None,
        description="Source language code (auto-detected if not provided)"
    )


class TextTranslationResponse(BaseModel):
    """Response from text translation."""
    translated_text: str = Field(..., description="Translated text")
    source_language: str = Field(..., description="Detected/specified source language")
    target_language: str = Field(..., description="Target language")
    original_text: Optional[str] = Field(None, description="Original text (if requested)")


class AudioTranslationRequest(BaseModel):
    """Request for audio translation (processed via form data)."""
    target_language: str = Field(..., description="Target language code")
    generate_audio: bool = Field(
        default=False,
        description="Whether to generate TTS audio of translation"
    )


class AudioTranslationResponse(BaseModel):
    """Response from audio translation."""
    transcript: str = Field(..., description="Transcribed text from audio")
    translated_text: str = Field(..., description="Translated text")
    source_language: str = Field(..., description="Detected source language")
    target_language: str = Field(..., description="Target language")
    audio_url: Optional[str] = Field(None, description="URL to translated audio (if generated)")


class FileTranslationResponse(BaseModel):
    """Response from file translation."""
    translated_text: str = Field(..., description="Translated text")
    source_language: str = Field(..., description="Detected source language")
    target_language: str = Field(..., description="Target language")
    filename: str = Field(..., description="Original filename")


class SupportedLanguagesResponse(BaseModel):
    """Response with supported languages."""
    languages: list[LanguageInfo] = Field(..., description="List of supported languages")
    total: int = Field(..., description="Total number of supported languages")
