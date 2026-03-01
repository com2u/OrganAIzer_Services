"""
Universal Translation Service.
Handles text, audio, and file translation using LLM and existing STT/TTS capabilities.
"""

import logging
import tempfile
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from fastapi import UploadFile

# Internal services and utilities
from utils.text_processing import detect_language, clean_text
from services.chat_service import get_chat_service
from services.stt_service import transcribe_audio
from core.error_handling import AppError
from models.chat import ChatRequest

logger = logging.getLogger(__name__)


# Language mapping: code -> name
LANGUAGE_NAMES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh': 'Chinese',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'nl': 'Dutch',
    'pl': 'Polish',
    'tr': 'Turkish',
    'sv': 'Swedish',
    'da': 'Danish',
    'fi': 'Finnish',
    'no': 'Norwegian',
    'cs': 'Czech',
    'el': 'Greek',
    'he': 'Hebrew',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'id': 'Indonesian',
    'ms': 'Malay',
    'uk': 'Ukrainian',
    'ro': 'Romanian',
    'hu': 'Hungarian',
    'bg': 'Bulgarian',
    'ca': 'Catalan'
}


class TranslationService:
    """
    Translation service leveraging existing OrganAIzer capabilities.
    
    Architecture:
    - Text translation: LLM-based (high quality, context-aware)
    - Audio translation: STT → Translation → Optional TTS
    - File translation: Extract text → Translation
    - Language detection: langdetect library
    
    Design Decision: Using LLM for translation because:
    1. Better context understanding than basic translation APIs
    2. Already available via OpenRouter
    3. Consistent with OrganAIzer's AI-first approach
    4. Can handle nuanced, conversational translation
    """
    
    def __init__(self):
        """Initialize the translation service."""
        self.chat_service = get_chat_service()
        logger.info("TranslationService initialized")
    
    def detect_language_detailed(self, text: str) -> Tuple[str, float]:
        """
        Detect language with confidence score.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (language_code, confidence)
        """
        language = detect_language(text)
        if not language:
            # Default to English if detection fails
            logger.warning("Language detection failed, defaulting to English")
            return 'en', 0.5
        
        # langdetect doesn't provide confidence, so we estimate
        confidence = 0.9 if len(text) > 100 else 0.7
        return language, confidence
    
    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Translate text using LLM.
        
        Process:
        1. Detect source language if not provided
        2. Build translation prompt
        3. Use LLM for high-quality translation
        4. Return translated text
        
        Args:
            text: Text to translate
            target_language: Target language code
            source_language: Source language code (auto-detected if None)
            
        Returns:
            Tuple of (translated_text, detected_source_language)
        """
        logger.info(f"Translating text to {target_language}")
        
        # Clean input text
        text = clean_text(text)
        
        if not text:
            raise AppError(
                code="EMPTY_TEXT",
                message="No text provided for translation",
                http_status=400
            )
        
        # Detect source language if not provided
        if not source_language:
            source_language, _ = self.detect_language_detailed(text)
            logger.info(f"Detected source language: {source_language}")
        
        # Check if source and target are the same
        if source_language == target_language:
            logger.info("Source and target languages are the same, returning original")
            return text, source_language
        
        # Get language names for better translation
        source_name = LANGUAGE_NAMES.get(source_language, source_language)
        target_name = LANGUAGE_NAMES.get(target_language, target_language)
        
        # Build translation prompt
        prompt = f"""Translate the following text from {source_name} to {target_name}.
Provide ONLY the translation, without any explanations or additional text.

Text to translate:
{text}

Translation:"""
        
        # Use LLM for translation
        try:
            request = ChatRequest(
                prompt=prompt,
                temperature=0.3,  # Lower temperature for more accurate translation
                max_tokens=2000
            )
            
            response = await self.chat_service.chat_completion(request)
            translated_text = response.response.strip()
            
            logger.info(f"Translation complete: {len(text)} -> {len(translated_text)} chars")
            return translated_text, source_language
            
        except Exception as e:
            logger.error(f"Translation failed: {e}", exc_info=True)
            raise AppError(
                code="TRANSLATION_FAILED",
                message=f"Failed to translate text: {str(e)}",
                http_status=500
            )
    
    async def translate_audio(
        self,
        audio_file: UploadFile,
        target_language: str,
        generate_audio: bool = False
    ) -> Dict[str, Any]:
        """
        Translate audio file.
        
        Process:
        1. Transcribe audio (STT)
        2. Detect source language from transcription
        3. Translate text to target language
        4. Optionally generate TTS audio of translation
        
        Args:
            audio_file: Audio file to translate
            target_language: Target language code
            generate_audio: Whether to generate TTS audio
            
        Returns:
            Dictionary with transcript, translation, and optional audio URL
        """
        logger.info(f"Translating audio to {target_language}")
        
        try:
            # Step 1: Transcribe audio
            transcript, source_language, duration = await transcribe_audio(audio_file)
            logger.info(f"Audio transcribed: {len(transcript)} chars, language: {source_language}")
            
            # Step 2: Translate transcript
            translated_text, detected_source = await self.translate_text(
                text=transcript,
                target_language=target_language,
                source_language=source_language
            )
            
            # Step 3: Generate TTS audio if requested
            # Note: TTS generation feature disabled - can be implemented by calling /api/tts/speak separately
            audio_url = None
            if generate_audio:
                logger.info("TTS audio generation requested but not implemented in this service")
                logger.info("Use /api/tts/speak endpoint separately for TTS audio generation")
            
            return {
                "transcript": transcript,
                "translated_text": translated_text,
                "source_language": detected_source or source_language,
                "target_language": target_language,
                "audio_url": audio_url
            }
            
        except AppError:
            raise
        except Exception as e:
            logger.error(f"Audio translation failed: {e}", exc_info=True)
            raise AppError(
                code="AUDIO_TRANSLATION_FAILED",
                message=f"Failed to translate audio: {str(e)}",
                http_status=500
            )
    
    async def translate_file(
        self,
        file: UploadFile,
        target_language: str
    ) -> Dict[str, Any]:
        """
        Translate text file.
        
        Args:
            file: Text file to translate
            target_language: Target language code
            
        Returns:
            Dictionary with translated text and metadata
        """
        logger.info(f"Translating file: {file.filename}")
        
        # Validate file type
        if not file.filename:
            raise AppError(
                code="INVALID_FILE",
                message="No filename provided",
                http_status=400
            )
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in {'.txt', '.md'}:
            raise AppError(
                code="INVALID_FILE_FORMAT",
                message=f"Unsupported file format: {file_ext}. Only .txt and .md supported",
                http_status=400
            )
        
        # Read file content
        try:
            file_contents = await file.read()
            text = file_contents.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = file_contents.decode('latin-1')
            except Exception as e:
                raise AppError(
                    code="FILE_DECODE_ERROR",
                    message="Failed to decode file content",
                    http_status=400
                )
        
        if not text or len(text.strip()) < 1:
            raise AppError(
                code="EMPTY_FILE",
                message="File is empty",
                http_status=400
            )
        
        # Translate text
        translated_text, source_language = await self.translate_text(
            text=text,
            target_language=target_language
        )
        
        return {
            "translated_text": translated_text,
            "source_language": source_language,
            "target_language": target_language,
            "filename": file.filename
        }
    
    def get_supported_languages(self) -> list[Dict[str, str]]:
        """
        Get list of supported languages.
        
        Returns:
            List of language dictionaries with code and name
        """
        return [
            {"code": code, "name": name}
            for code, name in sorted(LANGUAGE_NAMES.items(), key=lambda x: x[1])
        ]


# Global service instance
_translation_service = None


def get_translation_service() -> TranslationService:
    """Get or create the global TranslationService instance."""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service
