"""
Realtime Voice Mode WebSocket endpoint for Executive AI.

WebSocket URL: /api/voice/stream?session_id=...&user_id=...&provider=...

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
  {"type": "error",            "message": "..."}
  {"type": "pong"}
  {"type": "debug",            "data": {...}}  (dev-mode only)

Observability (structured log fields per event):
  session_id, thread_id, state, latency_ms (time_to_first_transcript,
  time_to_first_audio, total_round_trip_ms)
"""

import json
import logging
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from services.executive_agent_service import ExecutiveAgent
from services.tts_service import (
    normalize_markdown_to_text,
    detect_language,
    preprocess_text_for_tts,
    synthesize_speech_to_mp3,
)
from services.stt_service import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Voice Mode"])

# ── Configuration ─────────────────────────────────────────────────────────────
PARTIAL_INTERVAL = 1.5   # seconds between partial-transcript STT calls
MIN_AUDIO_BYTES  = 512   # ignore tiny/empty recordings
DEV_MODE         = os.getenv("VOICE_DEBUG", "false").lower() in ("true", "1", "yes")

# ── Session registry for interrupt support ────────────────────────────────────
# Maps session_id → {"interrupted": bool}
_session_registry: dict = {}


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
    payload = {"type": event_type, **kwargs}
    await ws.send_text(json.dumps(payload))


async def _send_debug(ws: WebSocket, data: dict) -> None:
    if DEV_MODE:
        await _send(ws, "debug", data=data)


async def _run_stt(audio_bytes: bytes) -> str:
    if not audio_bytes or len(audio_bytes) < MIN_AUDIO_BYTES:
        return ""
    wrapper = _AudioFileWrapper(audio_bytes)
    try:
        transcript, _, _ = await transcribe_audio(wrapper, use_cache=False)
        return (transcript or "").strip()
    except Exception as exc:
        logger.warning("[VOICE-STT] STT error: %s", exc)
        return ""


def _is_interrupted(session_id: str) -> bool:
    return _session_registry.get(session_id, {}).get("interrupted", False)


def _clear_interrupt(session_id: str) -> None:
    if session_id in _session_registry:
        _session_registry[session_id]["interrupted"] = False


def _set_interrupt(session_id: str) -> None:
    if session_id not in _session_registry:
        _session_registry[session_id] = {}
    _session_registry[session_id]["interrupted"] = True


# ── Main WebSocket handler ────────────────────────────────────────────────────

@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    session_id: str = Query("default"),
    user_id:    str = Query("default_user"),
    provider:   str = Query("gmail"),
):
    """
    WebSocket endpoint: realtime voice conversation with Executive AI.

    Shares the same session_id / conversation thread as the text chat so
    voice and text messages appear in the same thread.  The frontend should
    pass the same session_id used in agentChat() calls.
    """
    await websocket.accept()

    ws_session_id = str(uuid.uuid4())[:8]   # short id for log correlation
    _session_registry[session_id] = {"interrupted": False}

    logger.info(
        "[VOICE] ▶ WS connected  ws=%s  session=%s  user=%s",
        ws_session_id, session_id, user_id,
    )

    audio_buffer:       bytearray  = bytearray()
    is_recording:       bool       = False
    last_partial_time:  float      = 0.0
    last_partial_text:  str        = ""
    turn_start_time:    float      = 0.0   # latency: mic-release → first transcript
    ai_start_time:      float      = 0.0   # latency: transcript ready → AI done
    tts_start_time:     float      = 0.0   # latency: AI done → TTS ready

    try:
        await _send(websocket, "state", state="idle")
        await _send_debug(websocket, {
            "ws_session_id": ws_session_id,
            "session_id": session_id,
            "user_id": user_id,
            "provider": provider,
            "dev_mode": DEV_MODE,
        })

        while True:
            msg = await websocket.receive()

            # ── Binary audio chunk ────────────────────────────────────────────
            if msg.get("bytes"):
                if is_recording:
                    audio_buffer.extend(msg["bytes"])
                    now = time.monotonic()
                    if (
                        now - last_partial_time >= PARTIAL_INTERVAL
                        and len(audio_buffer) > 4096
                    ):
                        last_partial_time = now
                        partial = await _run_stt(bytes(audio_buffer))
                        if partial and partial != last_partial_text:
                            last_partial_text = partial
                            await _send(websocket, "stt.partial", text=partial)
                            logger.debug(
                                "[VOICE] partial_transcript ws=%s text=%r", ws_session_id, partial[:60]
                            )
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

            # ── ping ─────────────────────────────────────────────────────────
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
                audio_buffer       = bytearray()
                is_recording       = True
                last_partial_text  = ""
                last_partial_time  = 0.0
                turn_start_time    = time.monotonic()
                await _send(websocket, "state", state="listening")
                logger.info("[VOICE] 🎤 audio_start  ws=%s", ws_session_id)

            # ── audio_end: finalize STT → AI → TTS ───────────────────────────
            elif kind == "audio_end":
                is_recording = False
                _clear_interrupt(session_id)
                await _send(websocket, "state", state="thinking")
                logger.info(
                    "[VOICE] 🛑 audio_end  ws=%s  buf_bytes=%d",
                    ws_session_id, len(audio_buffer),
                )

                # ── STT ───────────────────────────────────────────────────────
                t0_stt = time.monotonic()
                transcript = await _run_stt(bytes(audio_buffer))
                audio_buffer = bytearray()
                t_stt_done = time.monotonic()
                time_to_first_transcript_ms = round((t_stt_done - t0_stt) * 1000)

                logger.info(
                    "[VOICE] [LAT] time_to_first_transcript=%dms  ws=%s",
                    time_to_first_transcript_ms, ws_session_id,
                )

                if not transcript:
                    await _send(websocket, "stt.final", text="")
                    await _send(websocket, "error", message="No speech detected")
                    await _send(websocket, "state", state="idle")
                    logger.info("[VOICE] ⚠ no speech detected  ws=%s", ws_session_id)
                    continue

                await _send(websocket, "stt.final", text=transcript)
                logger.info("[VOICE] 📝 stt.final=%r…  ws=%s", transcript[:80], ws_session_id)
                await _send_debug(websocket, {
                    "event": "stt_complete",
                    "transcript": transcript,
                    "latency_ms": time_to_first_transcript_ms,
                })

                # ── Executive AI ──────────────────────────────────────────────
                if _is_interrupted(session_id):
                    await _send(websocket, "state", state="idle")
                    logger.info("[VOICE] ⚡ interrupted before AI  ws=%s", ws_session_id)
                    continue

                t0_ai = time.monotonic()
                try:
                    agent    = ExecutiveAgent(session_id=session_id)
                    ai_resp  = await agent.process_message(
                        user_message=transcript,
                        user_id=user_id,
                        provider=provider,
                    )
                    reply_text = ai_resp.get("message", "")
                except Exception as exc:
                    logger.error("[VOICE] ❌ AI error  ws=%s  err=%s", ws_session_id, exc, exc_info=True)
                    await _send(websocket, "error", message=f"AI error: {exc}")
                    await _send(websocket, "state", state="idle")
                    continue

                t_ai_done       = time.monotonic()
                time_to_ai_ms   = round((t_ai_done - t0_ai) * 1000)
                total_latency_ms = round((t_ai_done - turn_start_time) * 1000)

                logger.info(
                    "[VOICE] [LAT] ai_response=%dms  total_so_far=%dms  ws=%s",
                    time_to_ai_ms, total_latency_ms, ws_session_id,
                )

                await _send(websocket, "ai.response.text", text=reply_text)
                await _send_debug(websocket, {
                    "event": "ai_complete",
                    "reply_preview": reply_text[:120],
                    "ai_latency_ms": time_to_ai_ms,
                    "total_latency_ms": total_latency_ms,
                    "response_type": ai_resp.get("type"),
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
                    lang         = detect_language(normalized)
                    preprocessed = preprocess_text_for_tts(normalized, lang)
                    audio_id     = synthesize_speech_to_mp3(preprocessed, lang)
                    audio_url    = f"/api/tts/audio/{audio_id}"

                    t_tts_done           = time.monotonic()
                    time_to_first_audio  = round((t_tts_done - t0_tts) * 1000)
                    total_round_trip_ms  = round((t_tts_done - turn_start_time) * 1000)

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

                # Wait a moment; if interrupted during TTS play the state
                # transition will already have been handled by the interrupt handler.
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
