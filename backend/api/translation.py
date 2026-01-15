"""
API endpoints for Universal Translator.
"""

import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from models.translation import (
    TextTranslationRequest,
    TextTranslationResponse,
    AudioTranslationResponse,
    FileTranslationResponse,
    LanguageDetectionResponse,
    SupportedLanguagesResponse,
    LanguageInfo
)
from services.translation_service import get_translation_service
from core.error_handling import AppError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate", tags=["translation"])


@router.post("/text", response_model=TextTranslationResponse)
async def translate_text(request: TextTranslationRequest):
    """
    Translate text to target language.
    
    Features:
    - Auto-detects source language if not provided
    - High-quality LLM-based translation
    - Supports 30+ languages
    
    The translation uses context-aware LLM processing for natural,
    accurate translations.
    """
    try:
        logger.info(f"Text translation request: {len(request.text)} chars to {request.target_language}")
        
        service = get_translation_service()
        translated_text, source_language = await service.translate_text(
            text=request.text,
            target_language=request.target_language,
            source_language=request.source_language
        )
        
        return TextTranslationResponse(
            translated_text=translated_text,
            source_language=source_language,
            target_language=request.target_language,
            original_text=None  # Can include if needed
        )
        
    except AppError as e:
        logger.error(f"Text translation failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in text translation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.post("/audio", response_model=AudioTranslationResponse)
async def translate_audio(
    file: UploadFile = File(..., description="Audio file to translate"),
    target_language: str = Form(..., description="Target language code (e.g., 'en', 'de')"),
    generate_audio: bool = Form(False, description="Generate TTS audio of translation")
):
    """
    Translate audio file to target language.
    
    Process:
    1. Transcribe audio (STT)
    2. Detect source language
    3. Translate to target language
    4. Optionally generate TTS audio
    
    This integrates OrganAIzer's STT, translation, and TTS capabilities
    into a complete audio translation pipeline.
    """
    try:
        logger.info(f"Audio translation request: {file.filename} to {target_language}")
        
        service = get_translation_service()
        result = await service.translate_audio(
            audio_file=file,
            target_language=target_language,
            generate_audio=generate_audio
        )
        
        return AudioTranslationResponse(
            transcript=result["transcript"],
            translated_text=result["translated_text"],
            source_language=result["source_language"],
            target_language=result["target_language"],
            audio_url=result.get("audio_url")
        )
        
    except AppError as e:
        logger.error(f"Audio translation failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in audio translation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.post("/file", response_model=FileTranslationResponse)
async def translate_file(
    file: UploadFile = File(..., description="Text file to translate (.txt, .md)"),
    target_language: str = Form(..., description="Target language code")
):
    """
    Translate text file to target language.
    
    Supports:
    - .txt files
    - .md (Markdown) files
    
    Returns translated text with detected source language.
    """
    try:
        logger.info(f"File translation request: {file.filename} to {target_language}")
        
        service = get_translation_service()
        result = await service.translate_file(
            file=file,
            target_language=target_language
        )
        
        return FileTranslationResponse(
            translated_text=result["translated_text"],
            source_language=result["source_language"],
            target_language=result["target_language"],
            filename=result["filename"]
        )
        
    except AppError as e:
        logger.error(f"File translation failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in file translation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.post("/detect", response_model=LanguageDetectionResponse)
async def detect_language(request: TextTranslationRequest):
    """
    Detect the language of given text.
    
    Uses langdetect library for fast, accurate language detection.
    Supports 50+ languages.
    """
    try:
        logger.info(f"Language detection request: {len(request.text)} chars")
        
        service = get_translation_service()
        language, confidence = service.detect_language_detailed(request.text)
        
        return LanguageDetectionResponse(
            detected_language=language,
            confidence=confidence,
            text_preview=request.text[:100] + "..." if len(request.text) > 100 else request.text
        )
        
    except Exception as e:
        logger.error(f"Language detection failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DETECTION_FAILED",
                "message": "Failed to detect language",
                "details": {"error": str(e)}
            }
        )


@router.get("/languages", response_model=SupportedLanguagesResponse)
async def get_supported_languages():
    """
    Get list of supported languages.
    
    Returns language codes and names for all supported languages.
    Use these codes for the target_language and source_language parameters.
    """
    try:
        logger.info("Supported languages request")
        
        service = get_translation_service()
        languages_list = service.get_supported_languages()
        
        language_infos = [
            LanguageInfo(code=lang["code"], name=lang["name"])
            for lang in languages_list
        ]
        
        return SupportedLanguagesResponse(
            languages=language_infos,
            total=len(language_infos)
        )
        
    except Exception as e:
        logger.error(f"Failed to get supported languages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Failed to get supported languages",
                "details": {"error": str(e)}
            }
        )
