"""
Services package.
Contains business logic modules for different features.
"""

from .tts_service import (
    normalize_markdown_to_text,
    detect_language,
    preprocess_text_for_tts,
    synthesize_speech_to_mp3
)

__all__ = [
    "normalize_markdown_to_text",
    "detect_language",
    "preprocess_text_for_tts",
    "synthesize_speech_to_mp3"
]
