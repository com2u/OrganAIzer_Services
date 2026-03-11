"""
Text-to-Speech service module.
Handles markdown normalization, language detection, text preprocessing, and speech synthesis.

TTS BACKEND PRIORITY:
  1. edge-tts  (Microsoft Edge TTS — free, no API key, ~200ms latency)
  2. gTTS      (Google TTS — fallback only, 5-7 s latency)
"""

import asyncio
import concurrent.futures
import re
import uuid
import logging
from pathlib import Path
from typing import Tuple, Optional
from langdetect import detect, LangDetectException
from core.config import config
from core.error_handling import AppError

logger = logging.getLogger(__name__)


# ===========================================================================
# EDGE-TTS VOICE MAP
# Maps ISO 639-1 language codes -> Microsoft Edge TTS neural voice names.
# Only primary voices are listed; all others fall back to DEFAULT_EDGE_TTS_VOICE.
# ===========================================================================
EDGE_TTS_VOICE_MAP: dict = {
    "en": "en-US-AriaNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "es": "es-ES-ElviraNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "nl": "nl-NL-ColetteNeural",
    "pl": "pl-PL-ZofiaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "ar": "ar-SA-ZariyahNeural",
    "tr": "tr-TR-EmelNeural",
    "sv": "sv-SE-SofieNeural",
    "da": "da-DK-ChristelNeural",
    "fi": "fi-FI-NooraNeural",
    "nb": "nb-NO-PernilleNeural",
    "cs": "cs-CZ-VlastaNeural",
    "sk": "sk-SK-ViktoriaNeural",
    "hu": "hu-HU-NoemiNeural",
    "ro": "ro-RO-AlinaNeural",
    "bg": "bg-BG-KalinaNeural",
    "hr": "hr-HR-GabrijelaNeural",
    "uk": "uk-UA-PolinaNeural",
    "el": "el-GR-AthinaNeural",
    "he": "he-IL-HilaNeural",
    "vi": "vi-VN-HoaiMyNeural",
    "th": "th-TH-PremwadeeNeural",
    "id": "id-ID-GadisNeural",
    "ms": "ms-MY-YasminNeural",
}

DEFAULT_EDGE_TTS_VOICE = "en-US-AriaNeural"


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
    
    # Strip emoji and other pictographic symbols (covers all Unicode emoji blocks)
    text = re.sub(
        u"[\U00002600-\U000027BF"
        u"\U0001F300-\U0001F9FF"
        u"\U0001FA00-\U0001FAFF"
        u"\U0000FE00-\U0000FE0F"
        u"\U0000200D]+",
        "",
        text,
    )

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
    processed_text = re.sub(r'€\s*(\d+(?:[.,]\d+)?)', r'\1 euros', processed_text)
    processed_text = re.sub(r'\$\s*(\d+(?:[.,]\d+)?)', r'\1 dollars', processed_text)
    processed_text = re.sub(r'£\s*(\d+(?:[.,]\d+)?)', r'\1 pounds', processed_text)
    
    # Handle percentages: 50% -> 50 percent
    processed_text = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', r'\1 percent', processed_text)
    
    # Handle times: 3:30 PM -> 3 30 PM (numbers will be read separately)
    processed_text = re.sub(r'(\d+):(\d+)', r'\1 \2', processed_text)
    
    # Clean up multiple spaces that might have been introduced
    processed_text = re.sub(r' +', ' ', processed_text)
    
    logger.info(f"Text preprocessing complete, final text length: {len(processed_text)} characters")
    return processed_text.strip()


# ===========================================================================
# EDGE-TTS SYNTHESIS (primary — fast path)
# ===========================================================================

def _run_edge_tts_in_thread(text: str, voice: str, file_path: str) -> None:
    """
    Execute edge-tts synthesis in a dedicated OS thread so it can safely
    create its own asyncio event loop without interfering with the FastAPI
    / uvicorn event loop running on the main thread.

    This is the correct pattern for calling async libraries from within
    sync code that may itself be invoked from an async server context.
    """
    async def _async_synthesize() -> None:
        import edge_tts  # lazy import — keeps startup clean if not installed
        communicate = edge_tts.Communicate(text=text, voice=voice)
        await communicate.save(file_path)

    # asyncio.run() always creates a *new* event loop — safe inside a thread
    asyncio.run(_async_synthesize())


def _synthesize_with_edge_tts(text: str, language: str, file_path: str) -> None:
    """
    Synthesize speech using Microsoft Edge TTS and write MP3 to *file_path*.

    Voice selection: EDGE_TTS_VOICE_MAP[language] or DEFAULT_EDGE_TTS_VOICE.
    Execution: spawns a ThreadPoolExecutor worker so asyncio.run() won't clash
    with the running server event loop.

    Raises on any failure so the caller can fall back to gTTS.
    """
    # Resolve voice — use primary language tag (before any '-' suffix)
    lang_primary = language.split("-")[0].lower()
    voice = EDGE_TTS_VOICE_MAP.get(lang_primary, DEFAULT_EDGE_TTS_VOICE)
    logger.info("[EDGE_TTS] Using voice '%s' for language '%s'", voice, language)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_edge_tts_in_thread, text, voice, file_path)
        # Raise immediately if synthesis failed
        future.result(timeout=15)  # 15-second hard cap


# ===========================================================================
# GTTS FALLBACK (only if edge-tts fails)
# ===========================================================================

def _synthesize_with_gtts(text: str, language: str, file_path: str) -> None:
    """Synthesize speech using gTTS (slow fallback — 5–7 s)."""
    from gtts import gTTS  # lazy import
    tts = gTTS(text=text, lang=language, slow=False)
    tts.save(file_path)


# ===========================================================================
# PUBLIC API
# ===========================================================================

def synthesize_speech_to_mp3(text: str, language: str) -> str:
    """
    Synthesize speech from *text* and save as MP3.

    Backend priority:
      1. edge-tts  (~200 ms, Microsoft Edge TTS — free, no API key)
      2. gTTS      (~5-7 s,  fallback only)

    Markdown and emoji stripping MUST have been applied to *text* before
    calling this function (see normalize_markdown_to_text).

    Args:
        text:     Preprocessed plain text (no markdown, no emoji).
        language: ISO 639-1 language code (e.g. 'en', 'de').

    Returns:
        UUID string — use to retrieve the generated .mp3 file.

    Raises:
        AppError: when both backends fail.
    """
    logger.info("[TTS] synthesize_speech_to_mp3 — language=%s, len=%d", language, len(text))

    if not text or not text.strip():
        raise AppError(
            code="INVALID_INPUT",
            message="Text is empty, cannot generate speech",
            http_status=400,
        )

    # Generate unique ID and file path
    audio_id = str(uuid.uuid4())
    temp_dir = Path(config.TTS_TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)
    file_path = str(temp_dir / f"{audio_id}.mp3")

    # ── PRIMARY: edge-tts ────────────────────────────────────────────────────
    edge_error: Optional[Exception] = None
    try:
        logger.info("[TTS] Attempting edge-tts synthesis (%d chars)", len(text))
        _synthesize_with_edge_tts(text, language, file_path)
        logger.info("[TTS] edge-tts synthesis complete → audio_id=%s", audio_id)
        return audio_id
    except Exception as exc:
        edge_error = exc
        logger.warning(
            "[TTS] edge-tts failed (%s: %s) — falling back to gTTS",
            type(exc).__name__, exc,
        )

    # ── FALLBACK: gTTS ───────────────────────────────────────────────────────
    try:
        logger.info("[TTS] Attempting gTTS synthesis (%d chars)", len(text))
        _synthesize_with_gtts(text, language, file_path)
        logger.info("[TTS] gTTS synthesis complete (fallback) → audio_id=%s", audio_id)
        return audio_id
    except Exception as gtts_exc:
        logger.error(
            "[TTS] Both backends failed. edge-tts: %s | gTTS: %s",
            edge_error, gtts_exc,
        )
        raise AppError(
            code="TTS_GENERATION_FAILED",
            message=f"Failed to generate speech (edge-tts: {edge_error}; gTTS: {gtts_exc})",
            http_status=500,
        )
