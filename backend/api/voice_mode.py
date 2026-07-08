"""
Realtime Voice Mode WebSocket endpoint for Executive AI.

WebSocket URL: /api/voice/stream?session_id=...&user_id=...&calendar_provider=...&mail_provider=...

Protocol (client → server):
  {"type": "audio_start"}            user pressed mic button
  {"type": "audio_end"}              user released mic button
  {"type": "interrupt"}              stop TTS, resume listening immediately
  {"type": "ping"}                   keepalive
  <binary bytes>                     raw audio chunk (webm/opus from MediaRecorder)

Protocol (server → client):
  {"type": "state",            "state": "idle|listening|thinking|speaking"}
  {"type": "stt.partial",      "text": "..."}
  {"type": "stt.final",        "text": "..."}
  {"type": "ai.response.text", "text": "..."}
  {"type": "tts.audio",        "audio_url": "...", "audio_id": "..."}
  {"type": "stt",              "status": "no_speech|no_audio"}
  {"type": "error",            "message": "..."}
  {"type": "pong"}
  {"type": "debug",            "data": {...}}  (dev-mode only)

Observability (structured log fields per event):
  session_id, thread_id, state, latency_ms (time_to_first_transcript,
  time_to_first_audio, total_round_trip_ms)
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from services.executive_agent_service import ExecutiveAgent
from services.tts_service import (
    normalize_markdown_to_text,
    preprocess_text_for_tts,
    synthesize_speech_to_mp3,
)
from services.stt_service import get_voice_whisper_model
from utils.lang_tracking import update_conversation_language

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Voice Mode"])

# ── Configuration ─────────────────────────────────────────────────────────────
# PARTIAL_INTERVAL removed: partial STT was blocking the event loop and causing
# repeated STT runs. STT now fires exactly once per utterance on audio_end.
MIN_AUDIO_BYTES = 4096  # ignore tiny/empty recordings (4 KB minimum)
DEV_MODE        = os.getenv("VOICE_DEBUG", "false").lower() in ("true", "1", "yes")

# Thread pool for CPU-bound and blocking-I/O work (ffmpeg + Whisper).
# Using a dedicated pool avoids starving asyncio tasks on the default executor.
#
# LATENCY SPIKE ROOT CAUSES (Bug #7):
#   1. max_workers=2 means a second concurrent STT request queues behind the first.
#      With Whisper base on CPU (~10-14 s) + ffmpeg (~1-5 s on Windows due to AV
#      scanning of temp files), a queued request can see 14+ s BEFORE ffmpeg even
#      starts.  Increasing to 4 workers halves the likely queue depth.
#   2. Windows AV tools scan every NamedTemporaryFile write — slow on large webm.
#   3. Repeated reconnects (each AudioRecorder starts fresh) pile up STT tasks in
#      the same pool.  The interrupt + clear logic mitigates this at the WS layer,
#      but the worker threads still finish their inflight work.
#   4. Whisper's first call after startup pays the torch warm-up penalty even with
#      preload — subsequent calls on the same thread are faster.
_cpu_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="voice-worker")

# ── Session registry for interrupt + language support ────────────────────────
# Maps session_id → {"interrupted": bool, "lang": "de"|"en"}
_session_registry: dict = {}

# Conversation language for TTS — owned by the USER, mirroring the phone-path
# fix in voice/esl_call_handler.py: the session starts German and only switches
# when the user's transcript carries strong evidence of the other language
# (see utils.lang_tracking). AI replies are never language-detected — a short
# reply like "Okay." has no German markers and used to flip the TTS voice to
# English mid-session (the "two receptionists" bug).
DEFAULT_SESSION_LANG = "de"


# ── Helpers ───────────────────────────────────────────────────────────────────

class _AudioFileWrapper:
    """Wraps raw bytes as a minimal UploadFile-compatible object for stt_service."""

    def __init__(self, data: bytes, filename: str = "voice.webm"):
        self.filename = filename
        self.size     = len(data)
        self._data    = data

    async def read(self) -> bytes:
        return self._data


async def _send(ws: WebSocket, event_type: str, **kwargs) -> None:
    payload  = {"type": event_type, **kwargs}
    msg_str  = json.dumps(payload)
    logger.debug("[VOICE] ws_send type=%s bytes=%d", event_type, len(msg_str))
    await ws.send_text(msg_str)


async def _send_debug(ws: WebSocket, data: dict) -> None:
    if DEV_MODE:
        await _send(ws, "debug", data=data)


def _run_ffmpeg_blocking(webm_bytes: bytes) -> Optional[bytes]:
    """
    Synchronous ffmpeg conversion of webm/opus → 16 kHz mono WAV.
    Runs in a thread pool executor to avoid blocking the asyncio event loop.

    asyncio.create_subprocess_exec raises NotImplementedError on Windows
    (ProactorEventLoop) — this approach works on all platforms.
    """
    tmp_in_path  = None
    tmp_out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
            tmp_in.write(webm_bytes)
            tmp_in_path = tmp_in.name
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
            tmp_out_path = tmp_out.name

        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i",  tmp_in_path,
                "-ac", "1",
                "-ar", "16000",
                "-f",  "wav",
                tmp_out_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr_text = result.stderr.decode(errors="replace")[:300]
            logger.warning(
                "[VOICE-STT] ffmpeg rc=%d stderr=%r", result.returncode, stderr_text,
            )
            return None

        with open(tmp_out_path, "rb") as f:
            wav_bytes = f.read()
        logger.info(
            "[VOICE-STT] ffmpeg→wav OK  in=%d B  out=%d B", len(webm_bytes), len(wav_bytes),
        )
        return wav_bytes

    except FileNotFoundError:
        logger.warning("[VOICE-STT] ffmpeg not found on PATH – skipping conversion")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("[VOICE-STT] ffmpeg timed out")
        return None
    except Exception as exc:
        logger.warning("[VOICE-STT] ffmpeg error %s: %s", type(exc).__name__, exc)
        return None
    finally:
        for p in (tmp_in_path, tmp_out_path):
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass


async def _convert_webm_to_wav(webm_bytes: bytes) -> Optional[bytes]:
    """Run ffmpeg conversion in thread executor (non-blocking, cross-platform)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_cpu_executor, _run_ffmpeg_blocking, webm_bytes)


async def _run_stt(audio_bytes: bytes, ws_session_id: str = "") -> str:
    """
    Run Whisper STT on the given audio bytes.

    Pipeline with granular latency instrumentation:
      audio_end → [ffmpeg conversion] → stt_start → [whisper base] → transcript_ready

    Uses the pre-loaded voice model (base by default) — NOT the heavier medium
    upload model.  The model is pre-warmed at startup by preload_voice_model(),
    so this call should not pay the torch/model-load penalty.
    """
    if not audio_bytes or len(audio_bytes) < MIN_AUDIO_BYTES:
        return ""

    t0 = time.monotonic()

    # Log EBML header for diagnostics
    header_hex = audio_bytes[:16].hex().upper()
    is_ebml    = audio_bytes[:4] == b"\x1a\x45\xdf\xa3"
    logger.info(
        "[VOICE-STT] header_hex=%s  is_webm_ebml=%s  size=%d  ws=%s",
        header_hex, is_ebml, len(audio_bytes), ws_session_id,
    )
    if not is_ebml:
        logger.warning(
            "[VOICE-STT] audio does NOT start with EBML magic (1A45DFA3) – "
            "file may not be valid webm  ws=%s", ws_session_id,
        )

    # ── 1. ffmpeg: webm → 16kHz mono WAV (in thread executor) ────────────────
    wav_bytes    = await _convert_webm_to_wav(audio_bytes)
    t_ffmpeg     = time.monotonic()
    logger.info(
        "[VOICE-STT] [LAT] audio_end→ffmpeg_done=%.0f ms  ok=%s  ws=%s",
        (t_ffmpeg - t0) * 1000, wav_bytes is not None, ws_session_id,
    )

    # Choose audio data: prefer converted WAV; fall back to raw for Whisper
    if wav_bytes:
        audio_data = wav_bytes
        suffix     = ".wav"
    else:
        logger.warning(
            "[VOICE-STT] ffmpeg unavailable/failed – passing raw webm to Whisper  ws=%s",
            ws_session_id,
        )
        audio_data = audio_bytes
        suffix     = ".webm"

    # ── 2. Write to temp file and run Whisper in thread executor ─────────────
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_data)
            tmp_path = f.name

        t_stt_start = time.monotonic()
        logger.info(
            "[VOICE-STT] [LAT] ffmpeg_done→stt_start=%.0f ms  audio_size=%d B  ws=%s",
            (t_stt_start - t_ffmpeg) * 1000, len(audio_data), ws_session_id,
        )

        # get_voice_whisper_model() returns the pre-loaded base model.
        # Transcribe runs in the thread pool so it doesn't block asyncio.
        model  = get_voice_whisper_model()
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _cpu_executor, model.transcribe, tmp_path
        )

        t_done     = time.monotonic()
        transcript = (result.get("text") or "").strip()
        logger.info(
            "[VOICE-STT] [LAT] stt_start→transcript_ready=%.0f ms  "
            "total_stt=%.0f ms  len=%d  ws=%s",
            (t_done - t_stt_start) * 1000,
            (t_done - t0) * 1000,
            len(transcript),
            ws_session_id,
        )
        return transcript

    except Exception as exc:
        logger.warning("[VOICE-STT] STT error: %s  ws=%s", exc, ws_session_id)
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _is_interrupted(session_id: str) -> bool:
    return _session_registry.get(session_id, {}).get("interrupted", False)


def _clear_interrupt(session_id: str) -> None:
    if session_id in _session_registry:
        _session_registry[session_id]["interrupted"] = False


def _set_interrupt(session_id: str) -> None:
    if session_id not in _session_registry:
        _session_registry[session_id] = {}
    _session_registry[session_id]["interrupted"] = True


def _get_session_lang(session_id: str) -> str:
    """Current conversation language for the session (user-owned)."""
    return _session_registry.get(session_id, {}).get("lang", DEFAULT_SESSION_LANG)


def _update_session_lang(session_id: str, transcript: str) -> str:
    """Update the session language from USER input only and return it.

    Called once per turn with the accepted STT transcript, BEFORE the AI
    reply exists — so AI-generated text can never steer the TTS voice.
    Short or ambiguous utterances keep the current language.
    """
    entry = _session_registry.setdefault(session_id, {})
    entry["lang"] = update_conversation_language(
        transcript, entry.get("lang", DEFAULT_SESSION_LANG)
    )
    return entry["lang"]


# ── Low-information / partial transcript guard (Fix #6) ──────────────────────

_FILLER_WORDS = frozenset({
    "uh", "um", "hmm", "hm", "erm", "er", "ah", "oh",
    "so", "well", "like", "okay", "right", "yeah",
})

def _is_low_information_transcript(transcript: str) -> bool:
    """
    Return True when the transcript is too fragmentary to warrant a full AI call.

    Catches:
    - Pure filler: "uh", "um", "hmm"
    - Incomplete trailing filler: "Hello, can you uh"  (≤ 6 words, ends with filler)
    - All-filler utterances: "well uh um"

    Does NOT filter:
    - Valid short commands: "yes", "no", "cancel", "hello"
    - Sentences that end with a meaningful word even if short
    """
    if not transcript:
        return True
    words = transcript.split()
    cleaned = [w.lower().rstrip(".,!?;:") for w in words]

    # Pure filler word(s) only
    informative = [w for w in cleaned if w not in _FILLER_WORDS]
    if not informative:
        logger.info("[VOICE] ⚠ all-filler transcript: %r — skipping AI", transcript)
        return True

    # Ends with a filler AND the full utterance is short → incomplete fragment
    if cleaned and cleaned[-1] in _FILLER_WORDS and len(words) <= 6:
        logger.info("[VOICE] ⚠ trailing-filler transcript: %r — skipping AI", transcript)
        return True

    return False


# ── Main WebSocket handler ────────────────────────────────────────────────────

@router.websocket("/stream")
async def voice_stream(
    websocket:         WebSocket,
    session_id:        str = Query("default"),
    user_id:           str = Query("default_user"),
    calendar_provider: Optional[str] = Query(None),  # None → agent asks user
    mail_provider:     Optional[str] = Query(None),   # None → agent asks user
):
    """
    WebSocket endpoint: realtime voice conversation with Executive AI.

    Shares the same session_id / conversation thread as the text chat so
    voice and text messages appear in the same thread.  The frontend should
    pass the same session_id used in agentChat() calls.
    """
    await websocket.accept()

    ws_session_id = str(uuid.uuid4())[:8]   # short id for log correlation
    _session_registry[session_id] = {"interrupted": False, "lang": DEFAULT_SESSION_LANG}

    logger.info(
        "[VOICE] ▶ WS connected  ws=%s  session=%s  user=%s",
        ws_session_id, session_id, user_id,
    )

    audio_buffer:    bytearray = bytearray()
    is_recording:    bool      = False
    turn_start_time: float     = 0.0   # latency: mic-release → first transcript

    try:
        # Immediately acknowledge the connection so the frontend can transition
        # from "connecting" to "ready" without waiting for any other message.
        await _send(websocket, "ready")
        await _send(websocket, "state", state="idle")
        await _send_debug(websocket, {
            "ws_session_id": ws_session_id,
            "session_id": session_id,
            "user_id": user_id,
            "calendar_provider": calendar_provider,
            "mail_provider": mail_provider,
            "dev_mode": DEV_MODE,
        })

        while True:
            # ── Disconnect-safe receive ───────────────────────────────────────
            try:
                msg = await websocket.receive()
            except WebSocketDisconnect:
                logger.info(
                    "[VOICE] ◀ WS disconnected (recv exception)  ws=%s  session=%s",
                    ws_session_id, session_id,
                )
                break

            # Starlette also delivers disconnect as a typed message
            if msg.get("type") == "websocket.disconnect":
                logger.info(
                    "[VOICE] ◀ WS disconnect message  ws=%s  session=%s",
                    ws_session_id, session_id,
                )
                break

            # ── Binary audio chunk ────────────────────────────────────────────
            # Accumulate raw bytes only; STT runs exactly once on audio_end.
            # Partial STT was removed because it called `await _run_stt()` inline,
            # blocking the event loop for the entire Whisper duration and preventing
            # audio_end from being processed in time — causing repeated STT runs.
            if msg.get("bytes"):
                if is_recording:
                    audio_buffer.extend(msg["bytes"])
                continue

            # ── Text / JSON control messages ──────────────────────────────────
            raw = msg.get("text", "")
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            kind = data.get("type", "")

            # ── ping ──────────────────────────────────────────────────────────
            if kind == "ping":
                await _send(websocket, "pong")

            # ── interrupt: stop playback, resume listening ────────────────────
            elif kind == "interrupt":
                _set_interrupt(session_id)
                logger.info("[VOICE] ⚡ interrupt  ws=%s  session=%s", ws_session_id, session_id)
                await _send(websocket, "state", state="idle")
                await _send_debug(websocket, {"event": "interrupted", "session_id": session_id})

            # ── audio_start: begin recording ──────────────────────────────────
            elif kind == "audio_start":
                # If AI is speaking, interrupt it first
                _set_interrupt(session_id)
                audio_buffer    = bytearray()
                is_recording    = True
                turn_start_time = time.monotonic()
                await _send(websocket, "state", state="listening")
                logger.info("[VOICE] 🎤 audio_start  ws=%s", ws_session_id)

            # ── audio_end: finalize STT → AI → TTS ───────────────────────────
            elif kind == "audio_end":
                is_recording = False
                _clear_interrupt(session_id)

                buf_bytes = len(audio_buffer)
                logger.info(
                    "[VOICE] 🛑 audio_end  ws=%s  buf_bytes=%d", ws_session_id, buf_bytes,
                )

                # Guard – skip STT for empty / too-short recordings
                if buf_bytes < MIN_AUDIO_BYTES:
                    audio_buffer = bytearray()
                    await _send(websocket, "stt", status="no_audio",
                                reason=f"buf_bytes={buf_bytes} < {MIN_AUDIO_BYTES}")
                    await _send(websocket, "state", state="idle")
                    logger.info(
                        "[VOICE] ⚠ buf too small (%d < %d bytes) – STT skipped  ws=%s",
                        buf_bytes, MIN_AUDIO_BYTES, ws_session_id,
                    )
                    continue

                await _send(websocket, "state", state="thinking")

                # ── STT (runs exactly once per utterance) ─────────────────────
                t0_stt     = time.monotonic()
                transcript = await _run_stt(bytes(audio_buffer), ws_session_id)
                audio_buffer = bytearray()   # clear buffer immediately after use
                t_stt_done  = time.monotonic()
                time_to_first_transcript_ms = round((t_stt_done - t0_stt) * 1000)

                logger.info(
                    "[VOICE] [LAT] time_to_first_transcript=%dms  ws=%s",
                    time_to_first_transcript_ms, ws_session_id,
                )

                if not transcript:
                    # No speech detected – return to idle quietly
                    await _send(websocket, "stt", status="no_speech")
                    await _send(websocket, "state", state="idle")
                    logger.info("[VOICE] ⚠ no speech detected  ws=%s", ws_session_id)
                    continue

                # ── Fix #6: Discard low-information / trailing-filler transcripts ─
                # "Hello, can you uh" → skip AI, return to idle cleanly.
                # This prevents unstable state from partial utterances while still
                # forwarding real short commands like "yes", "no", "cancel".
                if _is_low_information_transcript(transcript):
                    logger.info(
                        "[VOICE] ⚠ low-info transcript skipped: %r  ws=%s",
                        transcript[:60], ws_session_id,
                    )
                    await _send(websocket, "stt", status="no_speech",
                                reason="low_information_transcript")
                    await _send(websocket, "state", state="idle")
                    continue

                logger.info(
                    "[VOICE] transcript_ready len=%d preview=%r  ws=%s",
                    len(transcript), transcript[:40], ws_session_id,
                )
                await _send(websocket, "stt.final", text=transcript)

                # ── Conversation language (user-owned) ────────────────────────
                # Update from the USER transcript, before the AI reply exists.
                # The reply's TTS voice below uses this value — never a
                # re-detection of AI-generated text, so short acknowledgements
                # like "Okay." can no longer flip the voice mid-session.
                conv_lang = _update_session_lang(session_id, transcript)

                await _send_debug(websocket, {
                    "event": "stt_complete",
                    "transcript": transcript,
                    "latency_ms": time_to_first_transcript_ms,
                    "lang": conv_lang,
                })

                # ── Executive AI ──────────────────────────────────────────────
                if _is_interrupted(session_id):
                    await _send(websocket, "state", state="idle")
                    logger.info("[VOICE] ⚡ interrupted before AI  ws=%s", ws_session_id)
                    continue

                logger.info(
                    "[VOICE] forwarding_to_executive session=%s  ws=%s",
                    session_id, ws_session_id,
                )
                t0_ai = time.monotonic()
                try:
                    agent   = ExecutiveAgent(session_id=session_id)
                    # FIX #3: WebSocket URL params (calendar_provider / mail_provider)
                    # are treated as *connection context hints* only — not as forced
                    # provider values. The agent resolves the provider through:
                    #   1. Explicit mention in the user's message
                    #   2. session memory.preferred_provider (set on first confirmed action)
                    #   3. Ask the user — "Which account, Google or Microsoft?"
                    # Passing them here as API params would silently pre-fill the slot
                    # and bypass the "ask user" requirement, making voice behavior
                    # differ from text mode.  They remain available in `calendar_provider`
                    # / `mail_provider` locals for logging (Section 8 below).
                    ai_resp = await agent.process_message(
                        user_message=transcript,
                        user_id=user_id,
                        # calendar_provider and mail_provider intentionally NOT forwarded.
                        # preferred_provider from session memory is used instead.
                    )
                    reply_text = ai_resp.get("message", "") or ""
                except Exception as exc:
                    logger.error("[VOICE] ❌ AI error  ws=%s  err=%s", ws_session_id, exc, exc_info=True)
                    await _send(websocket, "error", message=f"AI error: {exc}")
                    await _send(websocket, "state", state="idle")
                    continue

                t_ai_done        = time.monotonic()
                time_to_ai_ms    = round((t_ai_done - t0_ai) * 1000)
                total_latency_ms = round((t_ai_done - turn_start_time) * 1000)

                logger.info(
                    "[VOICE] [LAT] ai_response=%dms  total_so_far=%dms  ws=%s",
                    time_to_ai_ms, total_latency_ms, ws_session_id,
                )
                logger.info(
                    "[VOICE] executive_reply_ready len=%d  ws=%s",
                    len(reply_text), ws_session_id,
                )

                await _send(websocket, "ai.response.text", text=reply_text)

                # ── SECTION 8: Voice structured logging ───────────────────────
                # FIX #1: _active_task may be None when no task is present (e.g.,
                # after a completed action or a pure chat response).  All accesses
                # must be null-guarded to prevent AttributeError crashes.
                _voice_intent = ai_resp.get("intent", "UNKNOWN")
                _active_task  = agent.memory.get_active_task()
                _voice_task_state = (
                    _active_task.get("status", "IDLE").upper()
                    if _active_task else "IDLE"
                )
                # FIX #1: safe two-step extraction — (_active_task or {}) safely
                # handles None; the inner (.get("data") or {}) handles missing key
                # and explicit None stored in the "data" field.
                _task_data     = (_active_task or {}).get("data") or {}
                _voice_provider = (
                    _task_data.get("provider")
                    or agent.memory.preferred_provider
                    or (calendar_provider or mail_provider or "unresolved")
                )

                logger.info(
                    "[VOICE_TRANSCRIPT] session=%s ws=%s text=%r",
                    session_id, ws_session_id, transcript[:200],
                )
                logger.info(
                    "[VOICE_INTENT] session=%s ws=%s intent=%s",
                    session_id, ws_session_id, _voice_intent,
                )
                logger.info(
                    "[VOICE_TASK_STATE] session=%s ws=%s state=%s task_type=%s",
                    session_id, ws_session_id, _voice_task_state,
                    _active_task.get("type", "none") if _active_task else "none",
                )
                logger.info(
                    "[VOICE_PROVIDER_DECISION] session=%s ws=%s provider=%s"
                    " calendar_param=%s mail_param=%s preferred=%s",
                    session_id, ws_session_id, _voice_provider,
                    calendar_provider, mail_provider,
                    agent.memory.preferred_provider,
                )
                # ── End Section 8 logging ─────────────────────────────────────

                await _send_debug(websocket, {
                    "event": "ai_complete",
                    "reply_preview": reply_text[:120],
                    "ai_latency_ms": time_to_ai_ms,
                    "total_latency_ms": total_latency_ms,
                    "response_type": ai_resp.get("type"),
                    "intent": _voice_intent,
                    "task_state": _voice_task_state,
                    "provider": _voice_provider,
                })

                if _is_interrupted(session_id):
                    await _send(websocket, "state", state="idle")
                    logger.info("[VOICE] ⚡ interrupted after AI  ws=%s", ws_session_id)
                    continue

                # ── TTS ───────────────────────────────────────────────────────
                await _send(websocket, "state", state="speaking")
                t0_tts = time.monotonic()
                try:
                    normalized   = normalize_markdown_to_text(reply_text)
                    # Speak in the session's user-owned language. The AI reply
                    # is deliberately NOT language-detected (see
                    # _update_session_lang / utils.lang_tracking).
                    lang         = conv_lang
                    preprocessed = preprocess_text_for_tts(normalized, lang)
                    audio_id     = synthesize_speech_to_mp3(preprocessed, lang)
                    audio_url    = f"/api/tts/audio/{audio_id}"

                    t_tts_done          = time.monotonic()
                    time_to_first_audio = round((t_tts_done - t0_tts) * 1000)
                    total_round_trip_ms = round((t_tts_done - turn_start_time) * 1000)

                    logger.info(
                        "[VOICE] [LAT] time_to_first_audio=%dms  total_round_trip=%dms  "
                        "ws=%s  session=%s  audio_url=%s",
                        time_to_first_audio, total_round_trip_ms,
                        ws_session_id, session_id, audio_url,
                    )

                    await _send(
                        websocket, "tts.audio",
                        audio_url=audio_url,
                        audio_id=audio_id,
                    )
                    await _send_debug(websocket, {
                        "event": "tts_complete",
                        "audio_url": audio_url,
                        "tts_latency_ms": time_to_first_audio,
                        "total_round_trip_ms": total_round_trip_ms,
                    })

                except Exception as exc:
                    logger.error("[VOICE] ❌ TTS error  ws=%s  err=%s", ws_session_id, exc)
                    await _send(websocket, "error", message=f"TTS unavailable: {exc}")

                # If interrupted during TTS playback the interrupt handler already
                # transitioned state; otherwise return to idle now.
                if not _is_interrupted(session_id):
                    await _send(websocket, "state", state="idle")
                _clear_interrupt(session_id)

    except WebSocketDisconnect:
        logger.info("[VOICE] ◀ WS disconnected  ws=%s  session=%s", ws_session_id, session_id)
    except Exception as exc:
        logger.error("[VOICE] ❌ fatal WS error  ws=%s  err=%s", ws_session_id, exc, exc_info=True)
        try:
            await _send(websocket, "error", message=str(exc))
        except Exception:
            pass
    finally:
        _session_registry.pop(session_id, None)
        logger.info("[VOICE] 🧹 session cleaned up  ws=%s  session=%s", ws_session_id, session_id)
