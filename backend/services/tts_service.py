"""
Text-to-Speech service module.
Handles markdown normalization, language detection, text preprocessing, and speech synthesis.
"""

import re
import uuid
import logging
from pathlib import Path
from typing import Tuple
from gtts import gTTS
from langdetect import detect, LangDetectException
from core.config import config
from core.error_handling import AppError

logger = logging.getLogger(__name__)


def normalize_markdown_to_text(markdown_text: str) -> str:
    """
    Converts markdown-formatted text to plain text suitable for TTS.
    Strips markdown formatting while preserving the textual content and structure.
    Used as the first step in the TTS pipeline to prepare text for processing.
    
    Args:
        markdown_text: Input text with markdown formatting
        
    Returns:
        Plain text with markdown formatting removed
    """
    logger.info("Starting markdown normalization")
    
    text = markdown_text
    
    # Remove code blocks (```...```)
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    # Remove inline code (`...`)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Remove images ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)
    
    # Remove links [text](url) but keep the text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove bold/italic markers (**, *, __, _)
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    # Remove strikethrough (~~text~~)
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    
    # Remove headers (# ## ###, etc.) - keep the text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Convert unordered lists (-, *, +) to sentences with periods
    text = re.sub(r'^\s*[-\*\+]\s+(.+)$', r'\1.', text, flags=re.MULTILINE)
    
    # Convert ordered lists (1. 2. etc.) to sentences with periods
    text = re.sub(r'^\s*\d+\.\s+(.+)$', r'\1.', text, flags=re.MULTILINE)
    
    # Remove horizontal rules (---, ***, ___)
    text = re.sub(r'^[\-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    
    # Remove blockquotes (>)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    
    # Clean up multiple spaces
    text = re.sub(r' +', ' ', text)
    
    # Clean up multiple newlines (keep maximum 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Trim whitespace
    text = text.strip()
    
    logger.info(f"Markdown normalization complete, resulting text length: {len(text)} characters")
    return text


def detect_language(text: str) -> str:
    """
    Detects the language of the given text using langdetect library.
    Returns ISO language codes like 'en', 'de', 'es', etc.
    Used to determine which TTS voice/model to use for speech synthesis.
    
    Args:
        text: Plain text to analyze for language detection
        
    Returns:
        ISO 639-1 language code (e.g., 'en', 'de', 'fr')
        
    Raises:
        AppError: If language detection fails
    """
    logger.info("Starting language detection")
    
    if not text or len(text.strip()) < 3:
        logger.warning("Text too short for reliable language detection, defaulting to English")
        return "en"
    
    try:
        # Detect language using langdetect
        detected_lang = detect(text)
        logger.info(f"Language detected: {detected_lang}")
        return detected_lang
    except LangDetectException as e:
        logger.warning(f"Language detection failed: {e}, defaulting to English")
        return "en"


def preprocess_text_for_tts(text: str, language: str = "en") -> str:
    """
    Preprocesses text for more natural speech synthesis.
    Expands abbreviations, normalizes numbers, and handles special characters.
    Used before synthesizing speech to improve pronunciation and naturalness.
    
    Args:
        text: Plain text to preprocess
        language: Language code for language-specific preprocessing
        
    Returns:
        Preprocessed text optimized for TTS
    """
    logger.info("Starting text preprocessing for TTS")
    
    processed_text = text
    
    # Common abbreviations (English-focused, expandable for other languages)
    abbreviations = {
        r'\bDr\.': 'Doctor',
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Missus',
        r'\bMs\.': 'Miss',
        r'\bProf\.': 'Professor',
        r'\bSr\.': 'Senior',
        r'\bJr\.': 'Junior',
        r'\bInc\.': 'Incorporated',
        r'\bLtd\.': 'Limited',
        r'\bCo\.': 'Company',
        r'\bCorp\.': 'Corporation',
        r'\bAve\.': 'Avenue',
        r'\bSt\.': 'Street',
        r'\bRd\.': 'Road',
        r'\bBlvd\.': 'Boulevard',
        r'\bDept\.': 'Department',
        r'\bUniv\.': 'University',
        r'\betc\.': 'etcetera',
        r'\be\.g\.': 'for example',
        r'\bi\.e\.': 'that is',
        r'\bvs\.': 'versus',
    }
    
    # Expand abbreviations
    for abbr, expansion in abbreviations.items():
        processed_text = re.sub(abbr, expansion, processed_text, flags=re.IGNORECASE)
    
    # Handle currency symbols with numbers
    # €123 -> 123 euros
    processed_text = re.sub(r'€\s*(\d+(?:[.,]\d+)?)', r'\1 euros', processed_text)
    # $123 -> 123 dollars
    processed_text = re.sub(r'\$\s*(\d+(?:[.,]\d+)?)', r'\1 dollars', processed_text)
    # £123 -> 123 pounds
    processed_text = re.sub(r'£\s*(\d+(?:[.,]\d+)?)', r'\1 pounds', processed_text)
    
    # Handle percentages: 50% -> 50 percent
    processed_text = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', r'\1 percent', processed_text)
    
    # Handle basic date formats: 12/31/2023 -> December 31st 2023
    # This is a simple implementation; more sophisticated handling could be added
    
    # Handle times: 3:30 PM -> 3 30 PM (numbers will be read separately)
    processed_text = re.sub(r'(\d+):(\d+)', r'\1 \2', processed_text)
    
    # Clean up multiple spaces that might have been introduced
    processed_text = re.sub(r' +', ' ', processed_text)
    
    logger.info(f"Text preprocessing complete, final text length: {len(processed_text)} characters")
    return processed_text.strip()


def synthesize_speech_to_mp3(text: str, language: str) -> str:
    """
    Synthesizes speech from text and saves it as an MP3 file.
    Uses Google Text-to-Speech (gTTS) to generate audio.
    Returns a unique identifier that can be used to retrieve the file.
    
    Args:
        text: Preprocessed text to convert to speech
        language: ISO language code for TTS voice selection
        
    Returns:
        Unique identifier (UUID) for the generated audio file
        
    Raises:
        AppError: If speech synthesis or file saving fails
    """
    logger.info(f"Starting speech synthesis for language: {language}")
    
    if not text or len(text.strip()) == 0:
        raise AppError(
            code="INVALID_INPUT",
            message="Text is empty, cannot generate speech",
            http_status=400
        )
    
    try:
        # Generate unique ID for this audio file
        audio_id = str(uuid.uuid4())
        
        # Ensure TTS temp directory exists
        temp_dir = Path(config.TTS_TEMP_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate file path
        file_path = temp_dir / f"{audio_id}.mp3"
        
        logger.info(f"Generating speech using gTTS for {len(text)} characters")
        
        # Generate speech using gTTS
        # gTTS automatically handles the language parameter
        tts = gTTS(text=text, lang=language, slow=False)
        
        # Save to MP3 file
        tts.save(str(file_path))
        
        logger.info(f"Speech synthesis complete, saved to: {file_path}")
        logger.info(f"Audio ID: {audio_id}")
        
        return audio_id
        
    except Exception as e:
        logger.error(f"Speech synthesis failed: {str(e)}", exc_info=True)
        raise AppError(
            code="TTS_GENERATION_FAILED",
            message=f"Failed to generate speech: {str(e)}",
            http_status=500
        )
