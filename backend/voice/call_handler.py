"""
call_handler.py — orchestrates a single phone call from answer to hangup.

Called by sip_client._on_call() in a dedicated thread (never in the
asyncio event loop).  Uses asyncio.run() for the async LLM call.

Flow:
  answer → greet → [listen → transcribe → LLM → speak] loop → log → hangup
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from pyVoIP.VoIP import VoIPCall, CallState

from voice import call_log, contacts as _contacts
from voice.audio_bridge import is_silence, speak, transcribe
from voice.llm_bridge import get_response, new_history
from voice import config

logger = logging.getLogger(__name__)

# ── VAD tuning ────────────────────────────────────────────────────────────────
# pyVoIP delivers 160 samples @ 8 kHz = 20 ms per read_audio(160) call
_CHUNK_MS          = 20
_SILENCE_TIMEOUT_MS = 700   # ms of silence after speech before transcribing
_MIN_SPEECH_MS     = 200    # ms of speech needed before we bother transcribing
_MAX_CALL_MS       = config.AI_MAX_CALL_SECONDS * 1000

_SILENCE_CHUNKS    = _SILENCE_TIMEOUT_MS // _CHUNK_MS   # 35 chunks
_MIN_SPEECH_CHUNKS = _MIN_SPEECH_MS      // _CHUNK_MS   # 10 chunks


def _write_pcm(call: VoIPCall, pcm: bytes) -> None:
    """Write PCM bytes to the call in 160-byte RTP-sized chunks."""
    chunk_size = 320  # 160 samples × 2 bytes
    for i in range(0, len(pcm), chunk_size):
        if call.state == CallState.ENDED:
            break
        call.write_audio(pcm[i: i + chunk_size])


def handle_call(call: VoIPCall, phone_state: dict) -> None:
    """
    Handle a single inbound call end-to-end.
    Runs in its own thread — do NOT call from the asyncio event loop.

    Args:
        call:        pyVoIP VoIPCall object (state=RINGING on entry)
        phone_state: shared state dict from api/phone.py — updated here
    """
    started_at  = datetime.now(timezone.utc)
    caller      = ""
    caller_name: Optional[str] = None
    turn_count  = 0
    history     = new_history()

    try:
        # ── identify caller ───────────────────────────────────────────────────
        try:
            caller = call.request.headers.get("From", "")
            # SIP From header: "Display Name" <sip:number@domain>;tag=...
            # Extract the number part
            if "<sip:" in caller:
                caller = caller.split("<sip:")[1].split("@")[0].split(">")[0]
            elif "sip:" in caller:
                caller = caller.split("sip:")[1].split("@")[0]
        except Exception:
            caller = "unknown"

        contact = _contacts.lookup_by_number(caller)
        caller_name = contact["name"] if contact else None

        display = caller_name or caller
        logger.info("Inbound call from %s (%s)", caller, caller_name or "unknown")

        # ── update shared phone state ─────────────────────────────────────────
        phone_state["active_call"] = {
            "caller":      caller,
            "caller_name": caller_name,
            "started_at":  started_at.isoformat(),
        }

        # ── answer ────────────────────────────────────────────────────────────
        call.answer()
        logger.info("Call answered")

        # ── greet ─────────────────────────────────────────────────────────────
        greeting = config.AI_GREETING
        if caller_name:
            greeting = f"Hallo {caller_name}, " + greeting.lstrip("Hallo, ")
        _write_pcm(call, speak(greeting, lang=config.AI_LANGUAGE))

        # ── VAD + conversation loop ───────────────────────────────────────────
        speech_chunks:  list[bytes] = []
        silent_streak   = 0
        total_ms        = 0

        while call.state != CallState.ENDED:
            # Hard timeout — protect against runaway calls
            if total_ms >= _MAX_CALL_MS:
                logger.info("Max call duration reached (%ds), hanging up", config.AI_MAX_CALL_SECONDS)
                _write_pcm(call, speak(
                    "Die maximale Gesprächsdauer wurde erreicht. Auf Wiederhören!",
                    lang=config.AI_LANGUAGE,
                ))
                break

            chunk = call.read_audio(160, blocking=True)
            total_ms += _CHUNK_MS

            if is_silence(chunk):
                silent_streak += 1
                # If we had speech and now enough silence: transcribe
                if (silent_streak >= _SILENCE_CHUNKS
                        and len(speech_chunks) >= _MIN_SPEECH_CHUNKS):
                    text = transcribe(speech_chunks, lang=config.AI_LANGUAGE)
                    speech_chunks = []
                    silent_streak = 0

                    if text:
                        turn_count += 1
                        logger.info("[Turn %d] Caller: %s", turn_count, text)
                        try:
                            reply = asyncio.run(
                                get_response(history, text, caller_name=caller_name)
                            )
                        except Exception as exc:
                            logger.error("LLM error: %s", exc)
                            reply = "Entschuldigung, es gab einen technischen Fehler."

                        logger.info("[Turn %d] AI: %s", turn_count, reply)
                        _write_pcm(call, speak(reply, lang=config.AI_LANGUAGE))
                elif silent_streak >= _SILENCE_CHUNKS:
                    # Pure silence with no speech buffer — reset streak
                    # to avoid re-triggering; keep listening
                    silent_streak = 0
            else:
                silent_streak = 0
                speech_chunks.append(chunk)

    except Exception as exc:
        logger.error("Unhandled error in call_handler: %s", exc, exc_info=True)

    finally:
        # ── hangup and clean up ───────────────────────────────────────────────
        try:
            if call.state != CallState.ENDED:
                call.hangup()
        except Exception:
            pass

        phone_state["active_call"] = None
        ended_at = datetime.now(timezone.utc)

        call_log.record(
            caller=caller,
            caller_name=caller_name,
            direction="inbound",
            started_at=started_at,
            ended_at=ended_at,
            turn_count=turn_count,
        )
        logger.info(
            "Call ended: %s  duration=%ds  turns=%d",
            display if 'display' in dir() else caller,
            int((ended_at - started_at).total_seconds()),
            turn_count,
        )
