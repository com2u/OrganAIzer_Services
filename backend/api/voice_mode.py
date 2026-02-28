"""
Realtime Voice Mode WebSocket endpoint for Executive AI.

Protocol (client -> server):
  - JSON {"type": "audio_start"}  : user started speaking
  - binary bytes                  : raw audio chunk (webm/opus from MediaRecorder)
  - JSON {"type": "audio_end"}    : user stopped speaking (finalize)
  - JSON {"type": "ping"}         : keepalive

Protocol (server -> client):
  - {"type": "state",            "state": "idle|listening|thinking|speaking"}
  - {"type": "stt.partial",      "text": "..."}
  - {"type": "stt.final",        "text": "..."}
  - {"type": "ai.response.text", "text": "..."}
  - {"type": "tts.audio",        "audio_url": "...", "audio_id": "..."}
  - {"type": "error",            "message": "..."}
  - {"type": "pong"}
"""

import json
import logging
import time
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

PARTIAL_INTERVAL = 1.5   # seconds between partial-transcript STT calls
MIN_AUDIO_BYTES = 512    # ignore tiny/empty recordings


class _AudioFileWrapper:
    """Wraps raw bytes as a minimal UploadFile-compatible object for stt_service."""

    def __init__(self, data: bytes, filename: str = "voice.webm"):
        self.filename = filename
        self.size = len(data)
        self._data = data

    async def read(self) -> bytes:  # noqa: D102
        return self._data


async def _send(ws: WebSocket, event_type: str, **kwargs) -> None:
    payload = {"type": event_type, **kwargs}
    await ws.send_text(json.dumps(payload))


async def _run_stt(audio_bytes: bytes) -> str:
    if not audio_bytes or len(audio_bytes) < MIN_AUDIO_BYTES:
        return ""
    wrapper = _AudioFileWrapper(audio_bytes)
    try:
        transcript, _, _ = await transcribe_audio(wrapper, use_cache=False)
        return (transcript or "").strip()
    except Exception as exc:
        logger.warning("STT error in voice mode: %s", exc)
        return ""


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    session_id: str = Query("default"),
    user_id: str = Query("default_user"),
    provider: str = Query("gmail"),
):
    """WebSocket endpoint: realtime voice conversation with Executive AI."""
    await websocket.accept()
    logger.info("Voice WS connected  session=%s  user=%s", session_id, user_id)

    audio_buffer: bytearray = bytearray()
    is_recording = False
    last_partial_time = 0.0
    last_partial_text = ""

    try:
        await _send(websocket, "state", state="idle")

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

            if kind == "ping":
                await _send(websocket, "pong")

            elif kind == "audio_start":
                audio_buffer = bytearray()
                is_recording = True
                last_partial_text = ""
                last_partial_time = 0.0
                await _send(websocket, "state", state="listening")
                logger.debug("Voice: audio_start")

            elif kind == "audio_end":
                is_recording = False
                await _send(websocket, "state", state="thinking")
                logger.debug("Voice: audio_end  buf=%d bytes", len(audio_buffer))

                # ── Final STT ─────────────────────────────────────────────────
                transcript = await _run_stt(bytes(audio_buffer))
                audio_buffer = bytearray()

                if not transcript:
                    await _send(websocket, "stt.final", text="")
                    await _send(websocket, "error", message="No speech detected")
                    await _send(websocket, "state", state="idle")
                    continue

                await _send(websocket, "stt.final", text=transcript)
                logger.info("Voice STT final: %r", transcript[:120])

                # ── Executive AI ──────────────────────────────────────────────
                try:
                    agent = ExecutiveAgent(session_id=session_id)
                    ai_resp = await agent.process_message(
                        user_message=transcript,
                        user_id=user_id,
                        provider=provider,
                    )
                    reply_text = ai_resp.get("message", "")
                except Exception as exc:
                    logger.error("Executive AI error in voice mode: %s", exc, exc_info=True)
                    await _send(websocket, "error", message=f"AI error: {exc}")
                    await _send(websocket, "state", state="idle")
                    continue

                await _send(websocket, "ai.response.text", text=reply_text)
                logger.info("Voice AI reply: %r…", reply_text[:80])

                # ── TTS ───────────────────────────────────────────────────────
                await _send(websocket, "state", state="speaking")
                try:
                    normalized = normalize_markdown_to_text(reply_text)
                    lang = detect_language(normalized)
                    preprocessed = preprocess_text_for_tts(normalized, lang)
                    audio_id = synthesize_speech_to_mp3(preprocessed, lang)
                    audio_url = f"/api/tts/audio/{audio_id}"
                    await _send(websocket, "tts.audio", audio_url=audio_url, audio_id=audio_id)
                    logger.info("Voice TTS: %s", audio_url)
                except Exception as exc:
                    logger.error("TTS error in voice mode: %s", exc)
                    await _send(websocket, "error", message=f"TTS unavailable: {exc}")

                await _send(websocket, "state", state="idle")

    except WebSocketDisconnect:
        logger.info("Voice WS disconnected  session=%s", session_id)
    except Exception as exc:
        logger.error("Voice WS fatal error: %s", exc, exc_info=True)
        try:
            await _send(websocket, "error", message=str(exc))
        except Exception:
            pass
