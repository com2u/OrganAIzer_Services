import markdown
import re
from gtts import gTTS
from langdetect import detect
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

def normalize_markdown(text_md: str) -> str:
    """
    Converts markdown to plain text by stripping formatting.
    """
    # Convert markdown to HTML, then strip HTML tags
    html = markdown.markdown(text_md)
    # Simple HTML tag removal
    plain_text = re.sub(r'<[^>]+>', '', html)
    # Clean up extra whitespace
    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
    return plain_text

def generate_tts(text_md: str) -> dict:
    """
    Generates TTS from markdown text using Google Text-to-Speech.
    Returns dict with normalized_text, language, audio_path
    """
    try:
        normalized_text = normalize_markdown(text_md)
        if not normalized_text:
            raise ValueError("No text content found")

        language = detect(normalized_text)

        logger.info(f"Generating TTS for language: {language}")

        # Map detected language to gTTS supported language
        # gTTS supports many languages, but we need to map them properly
        lang_map = {
            'en': 'en',
            'es': 'es',
            'fr': 'fr',
            'de': 'de',
            'it': 'it',
            'pt': 'pt',
            'ru': 'ru',
            'ja': 'ja',
            'ko': 'ko',
            'zh': 'zh-cn',
            'ar': 'ar',
            'hi': 'hi',
            'nl': 'nl'
        }

        # Default to English if language not supported
        tts_lang = lang_map.get(language[:2], 'en')

        # Create TTS object
        tts = gTTS(text=normalized_text, lang=tts_lang, slow=False)

        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.close()  # Close so gTTS can write to it

        tts.save(temp_file.name)

        # Verify file was created and has content
        if not os.path.exists(temp_file.name) or os.path.getsize(temp_file.name) == 0:
            raise Exception("TTS file was not created or is empty")

        logger.info(f"TTS generated: {temp_file.name} (size: {os.path.getsize(temp_file.name)} bytes)")

        return {
            "text_normalized": normalized_text,
            "language": language,
            "audio_path": temp_file.name
        }
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        raise Exception(f"Failed to generate TTS: {str(e)}")
