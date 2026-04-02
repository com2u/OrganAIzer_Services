"""
audio_bridge.py — STT and TTS pipeline for phone calls.

  transcribe(pcm_chunks, lang)  — list of raw PCM bytes → transcript string
  speak(text, lang)             — text → raw PCM bytes (ready for RTP)
  is_silence(pcm_chunk)        — energy check for a single RTP packet

Audio contract (matches pyVoIP G.711 µ-law internal format):
  Input  PCM: 8 000 Hz, 8-bit unsigned offset binary (u8), mono
  Output PCM: 8 000 Hz, 8-bit unsigned offset binary (u8), mono

  pyVoIP's encode_pcmu/parse_pcmu use audioop width=1 (1 byte per sample).
  Silence = 0x80 (128).  Range = 0–255.  Do NOT use s16le here.

STT: openai-whisper 'base' model (loaded lazily, kept in memory)
TTS: gTTS (MP3) converted to raw PCM via ffmpeg
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import uuid as _uuid
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
    Input is 8-bit unsigned offset binary (pyVoIP u8 format, silence = 0x80).
    """
    if not pcm_chunk:
        return True
    # uint8 offset binary → float centred on zero: (x - 128) / 128
    samples = (np.frombuffer(pcm_chunk, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    rms = float(np.sqrt(np.mean(samples ** 2)))
    return rms < threshold


# ── STT ───────────────────────────────────────────────────────────────────────

def _concat_and_resample(pcm_chunks: list[bytes]) -> np.ndarray:
    """
    Concatenate raw 8 kHz u8 PCM chunks and upsample to 16 kHz float32
    for Whisper.  Input is uint8 offset binary (silence = 0x80).
    """
    raw = b"".join(pcm_chunks)
    # uint8 offset binary → float centred on zero
    samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    # Linear interpolation: 8 k -> 16 k
    x_old = np.arange(len(samples))
    x_new = np.linspace(0, len(samples) - 1, len(samples) * 2)
    return np.interp(x_new, x_old, samples).astype(np.float32)


def transcribe(
    pcm_chunks: list[bytes],
    lang: str = AI_LANGUAGE,
) -> str:
    """
    Transcribe a list of raw 8 kHz u8 PCM chunks to text.

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
    # Input is uint8 offset binary (pyVoIP u8 format, silence = 0x80)
    samples_check = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
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
    Convert text to raw 8 kHz unsigned 8-bit mono PCM bytes using gTTS + ffmpeg.

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

        # ffmpeg: MP3 → raw PCM  (8 kHz, unsigned 8-bit, mono)
        # pyVoIP encode_pcmu uses audioop with sample_width=1 (1 byte per sample).
        # u8 = unsigned 8-bit offset binary, silence = 0x80.  Do NOT use s16le.
        subprocess.run(
            [
                _ffmpeg(), "-y",
                "-i", mp3_path,
                "-ar", str(_SIP_SAMPLE_RATE),
                "-ac", "1",
                "-f", "u8",
                pcm_path,
            ],
            check=True,
            capture_output=True,
        )

        with open(pcm_path, "rb") as f:
            pcm = f.read()

        # 1 byte per sample → no /2 divisor
        duration_ms = int(len(pcm) / _SIP_SAMPLE_RATE * 1000)
        logger.debug(
            "speak: %d chars -> %d bytes u8 PCM @ %d Hz (%d ms)",
            len(text), len(pcm), _SIP_SAMPLE_RATE, duration_ms,
        )
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


# ── FreeSWITCH ESL audio helpers ──────────────────────────────────────────────

def transcribe_file(
    wav_path: str,
    lang: str = AI_LANGUAGE,
) -> str:
    """
    Transcribe a WAV file recorded by FreeSWITCH to text using Whisper.

    Whisper's load_audio() handles any sample rate — it resamples internally
    to 16 kHz.  Silent recordings are discarded without calling the model to
    avoid hallucinations.

    Args:
        wav_path: Absolute path to the WAV file produced by the FS record app.
        lang:     BCP-47 language code passed to Whisper.

    Returns:
        Transcribed text string, or "" if the file is silent or empty.
    """
    if not os.path.exists(wav_path):
        logger.warning("transcribe_file: file not found: %s", wav_path)
        return ""

    # whisper.load_audio resamples to 16 kHz float32 via ffmpeg
    audio = whisper.load_audio(wav_path)
    if audio is None or len(audio) == 0:
        return ""

    rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    if rms < _SILENCE_THRESHOLD:
        logger.debug("transcribe_file: silent recording (RMS=%.4f), skipping", rms)
        return ""

    model = _get_model()
    logger.debug(
        "transcribe_file: %.2f s of audio (RMS=%.4f), lang=%s",
        len(audio) / _WHISPER_RATE, rms, lang,
    )
    result = model.transcribe(audio, language=lang, fp16=False, temperature=0.0)
    text: str = result.get("text", "").strip()
    logger.info("Transcribed (file): %r", text[:120])
    return text


def speak_to_file(
    text: str,
    lang: str = AI_LANGUAGE,
    output_dir: Optional[str] = None,
    tld: Optional[str] = None,
) -> str:
    """
    Convert text to a WAV file suitable for FreeSWITCH playback.

    Pipeline: gTTS → MP3 temp file → ffmpeg → WAV (8 kHz, mono, PCM s16le).
    The caller is responsible for deleting the returned file after playback.

    Args:
        text:       Text to synthesise.
        lang:       gTTS language code.
        output_dir: Directory for the output WAV.  Defaults to
                    config.FREESWITCH_AUDIO_TEMP_DIR.

    Returns:
        Absolute path to the created WAV file, or "" if text is blank.
    """
    from voice.config import FREESWITCH_AUDIO_TEMP_DIR
    import pathlib

    text = text.strip()
    if not text:
        return ""

    if output_dir is None:
        output_dir = FREESWITCH_AUDIO_TEMP_DIR

    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    wav_path = str(
        (pathlib.Path(output_dir) / (_uuid.uuid4().hex + ".wav")).resolve()
    )
    mp3_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3_path = f.name

        # tld controls accent: 'de' → Hochdeutsch, 'us' → American English
        if tld is None:
            tld = "de" if lang == "de" else "us"
        gTTS(text=text, lang=lang, tld=tld, slow=False).save(mp3_path)

        # ffmpeg: MP3 → WAV (8 kHz, mono, 16-bit signed).
        # FS playback accepts standard PCM WAV and transcodes to the channel codec.
        # Use s16le (16-bit) rather than u8 — FS expects signed 16-bit WAV input.
        subprocess.run(
            [
                _ffmpeg(), "-y",
                "-i", mp3_path,
                "-ar", str(_SIP_SAMPLE_RATE),
                "-ac", "1",
                "-acodec", "pcm_s16le",
                wav_path,
            ],
            check=True,
            capture_output=True,
        )

        logger.debug("speak_to_file: %d chars → %s", len(text), wav_path)
        return wav_path

    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffmpeg WAV conversion failed: {exc.stderr.decode(errors='replace')[:300]}"
        ) from exc
    finally:
        if mp3_path:
            try:
                os.unlink(mp3_path)
            except OSError:
                pass
