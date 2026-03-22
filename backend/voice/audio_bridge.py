"""
audio_bridge.py — STT and TTS pipeline for phone calls.

  transcribe(pcm_chunks, lang)  — list of raw PCM bytes → transcript string
  speak(text, lang)             — text → raw PCM bytes (ready for RTP)
  is_silence(pcm_chunk)        — energy check for a single RTP packet

Audio contract (matches pyVoIP G.711 decoded output):
  Input  PCM: 8 000 Hz, 16-bit signed, mono (little-endian)
  Output PCM: 8 000 Hz, 16-bit signed, mono (little-endian)

STT: openai-whisper 'base' model (loaded lazily, kept in memory)
TTS: gTTS (MP3) converted to raw PCM via ffmpeg
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

import numpy as np
import whisper
from gtts import gTTS

from voice.config import AI_LANGUAGE

logger = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────
_SIP_SAMPLE_RATE   = 8_000   # Hz — pyVoIP / G.711
_WHISPER_RATE      = 16_000  # Hz — Whisper requirement
_SILENCE_THRESHOLD = 0.005   # RMS below this → treat as silence
_WHISPER_MODEL     = "base"  # base.pt already cached at ~/.cache/whisper/

# ── lazy model handle ─────────────────────────────────────────────────────────
_model: Optional[whisper.Whisper] = None


def _get_model() -> whisper.Whisper:
    """Load the Whisper model on first call; reuse on subsequent calls."""
    global _model
    if _model is None:
        logger.info("Loading Whisper model '%s' (first call)…", _WHISPER_MODEL)
        _model = whisper.load_model(_WHISPER_MODEL)
        logger.info("Whisper model ready.")
    return _model


def _ffmpeg() -> str:
    """Return the path to ffmpeg, raising RuntimeError if not found."""
    ff = shutil.which("ffmpeg")
    if not ff:
        raise RuntimeError(
            "ffmpeg not found in PATH. "
            "Ensure ffmpeg is installed and accessible."
        )
    return ff


# ── silence detection ─────────────────────────────────────────────────────────

def is_silence(pcm_chunk: bytes, threshold: float = _SILENCE_THRESHOLD) -> bool:
    """
    Return True if the RMS energy of a single PCM chunk is below threshold.
    Use this on every incoming RTP packet to detect when a caller has stopped
    speaking before calling transcribe().
    """
    if not pcm_chunk:
        return True
    samples = np.frombuffer(pcm_chunk, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(samples ** 2)))
    return rms < threshold


# ── STT ───────────────────────────────────────────────────────────────────────

def _concat_and_resample(pcm_chunks: list[bytes]) -> np.ndarray:
    """
    Concatenate raw 8 kHz PCM chunks and upsample to 16 kHz float32
    for Whisper.
    """
    raw = b"".join(pcm_chunks)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    # Linear interpolation: 8 k -> 16 k
    x_old = np.arange(len(samples))
    x_new = np.linspace(0, len(samples) - 1, len(samples) * 2)
    return np.interp(x_new, x_old, samples).astype(np.float32)


def transcribe(
    pcm_chunks: list[bytes],
    lang: str = AI_LANGUAGE,
) -> str:
    """
    Transcribe a list of raw 8 kHz 16-bit PCM chunks to text.

    Args:
        pcm_chunks: Accumulated RTP audio packets from one speech segment.
        lang:       BCP-47 language code passed to Whisper (default from config).

    Returns:
        Transcribed text string, or "" if the buffer is empty or silent.
    """
    if not pcm_chunks:
        return ""

    raw = b"".join(pcm_chunks)
    if not raw:
        return ""

    # Skip Whisper if the whole buffer is silence (avoids hallucinations)
    samples_check = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(samples_check ** 2)))
    if rms < _SILENCE_THRESHOLD:
        logger.debug("transcribe: buffer is silent (RMS=%.4f), skipping", rms)
        return ""

    audio = _concat_and_resample(pcm_chunks)
    model = _get_model()

    logger.debug(
        "transcribe: %.2f s of audio (RMS=%.4f), lang=%s",
        len(audio) / _WHISPER_RATE, rms, lang,
    )

    result = model.transcribe(
        audio,
        language=lang,
        fp16=False,          # fp16 off — no GPU required
        temperature=0.0,     # deterministic
    )
    text: str = result.get("text", "").strip()
    logger.info("Transcribed: %r", text[:120])
    return text


# ── TTS ───────────────────────────────────────────────────────────────────────

def speak(
    text: str,
    lang: str = AI_LANGUAGE,
) -> bytes:
    """
    Convert text to raw 8 kHz 16-bit mono PCM bytes using gTTS + ffmpeg.

    Args:
        text: The string to synthesise.
        lang: BCP-47 language code for gTTS (default from config).

    Returns:
        Raw PCM bytes ready to write into a pyVoIP RTP audio stream,
        or b"" if text is blank.

    Raises:
        RuntimeError: if gTTS or ffmpeg fails.
    """
    text = text.strip()
    if not text:
        return b""

    mp3_path = ""
    pcm_path = ""
    try:
        # gTTS → MP3
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3_path = f.name
        pcm_path = mp3_path[:-4] + ".pcm"

        gTTS(text=text, lang=lang, slow=False).save(mp3_path)

        # ffmpeg: MP3 → raw PCM  (8 kHz, 16-bit signed LE, mono)
        subprocess.run(
            [
                _ffmpeg(), "-y",
                "-i", mp3_path,
                "-ar", str(_SIP_SAMPLE_RATE),
                "-ac", "1",
                "-f", "s16le",
                pcm_path,
            ],
            check=True,
            capture_output=True,
        )

        with open(pcm_path, "rb") as f:
            pcm = f.read()

        duration_ms = int(len(pcm) / 2 / _SIP_SAMPLE_RATE * 1000)
        logger.debug("speak: %d chars -> %d bytes PCM (%d ms)", len(text), len(pcm), duration_ms)
        return pcm

    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffmpeg conversion failed: {exc.stderr.decode(errors='replace')[:300]}"
        ) from exc
    finally:
        for path in (mp3_path, pcm_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
