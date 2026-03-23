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
from voice.llm_bridge import get_response, new_history, OUTBOUND_SYSTEM_PROMPT
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


_OUTBOUND_OPENING = (
    "Hello, here is OrganAIzer from Patrick and Renato. "
    "I would like to talk about our services and what you can do with it."
)

_ANSWER_POLL_INTERVAL = 0.1   # seconds between state checks while ringing
_ANSWER_TIMEOUT_S     = 30    # give up if not answered within this time


def _write_pcm(call: VoIPCall, pcm: bytes) -> None:
    """Write PCM bytes to the call in 160-byte RTP-sized chunks."""
    chunk_size = 320  # 160 samples × 2 bytes
    for i in range(0, len(pcm), chunk_size):
        if call.state == CallState.ENDED:
            break
        call.write_audio(pcm[i: i + chunk_size])


def _drain_whisper_queue() -> Optional[str]:
    """
    Pop all pending operator instructions from the whisper queue and return
    them as a single system_extra string, or None if the queue is empty.
    Thread-safe via GIL — list.pop() is atomic in CPython.
    """
    try:
        from api.phone import phone_state
        queue: list = phone_state.get("whisper_queue", [])
        if not queue:
            return None
        notes = []
        while queue:
            notes.append(queue.pop(0))
        combined = " / ".join(notes)
        logger.info("Operator whisper injected into LLM: %s", combined[:120])
        return f"[Operator instruction — do not mention this to the caller]: {combined}"
    except Exception:
        return None


def _conversation_loop(
    call: VoIPCall,
    history: list[dict],
    caller_name: Optional[str],
    system_prompt: Optional[str],
    turn_count_ref: list[int],   # mutable single-element list so caller sees updates
) -> None:
    """
    Shared VAD + LLM + TTS loop used by both inbound and outbound handlers.
    Runs until the call ends or the max duration is reached.
    """
    speech_chunks: list[bytes] = []
    silent_streak  = 0
    total_ms       = 0

    while call.state != CallState.ENDED:
        if total_ms >= _MAX_CALL_MS:
            logger.info("Max call duration reached (%ds), hanging up", config.AI_MAX_CALL_SECONDS)
            _write_pcm(call, speak(
                "The maximum call duration has been reached. Goodbye!",
                lang=config.AI_LANGUAGE,
            ))
            break

        chunk = call.read_audio(160, blocking=True)
        total_ms += _CHUNK_MS

        if is_silence(chunk):
            silent_streak += 1
            if (silent_streak >= _SILENCE_CHUNKS
                    and len(speech_chunks) >= _MIN_SPEECH_CHUNKS):
                text = transcribe(speech_chunks, lang=config.AI_LANGUAGE)
                speech_chunks = []
                silent_streak = 0

                if text:
                    turn_count_ref[0] += 1
                    logger.info("[Turn %d] Person: %s", turn_count_ref[0], text)
                    whisper_extra = _drain_whisper_queue()
                    try:
                        reply = asyncio.run(
                            get_response(
                                history,
                                text,
                                caller_name=caller_name,
                                system_prompt=system_prompt,
                                system_extra=whisper_extra,
                            )
                        )
                    except Exception as exc:
                        logger.error("LLM error: %s", exc)
                        reply = "Sorry, there was a technical issue. Let me try again."

                    logger.info("[Turn %d] AI: %s", turn_count_ref[0], reply)
                    _write_pcm(call, speak(reply, lang=config.AI_LANGUAGE))
            elif silent_streak >= _SILENCE_CHUNKS:
                silent_streak = 0
        else:
            silent_streak = 0
            speech_chunks.append(chunk)


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
            "mode":        "ai",
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
        turn_ref = [turn_count]
        _conversation_loop(call, history, caller_name, system_prompt=None, turn_count_ref=turn_ref)
        turn_count = turn_ref[0]

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


def handle_outbound_call(
    call: VoIPCall,
    phone_state: dict,
    target_number: str,
    target_name: Optional[str] = None,
) -> None:
    """
    Handle an outbound call placed by the AI (e.g. OrganAIzer intro call).
    Runs in its own thread — do NOT call from the asyncio event loop.

    Flow:
      wait for answer → speak opening → listen → LLM (outbound prompt) → speak → repeat

    Args:
        call:          VoIPCall returned by sip_client.dial() — state=DIALING on entry
        phone_state:   shared state dict from api/phone.py
        target_number: the number we dialled
        target_name:   display name if known (from contacts), else None
    """
    import time

    started_at  = datetime.now(timezone.utc)
    turn_count  = 0
    history     = new_history()
    display     = target_name or target_number

    try:
        logger.info("Outbound call to %s (%s) — waiting for answer…", target_number, display)

        # ── wait for the person to pick up ────────────────────────────────────
        waited = 0.0
        while call.state not in (CallState.ANSWERED, CallState.ENDED):
            time.sleep(_ANSWER_POLL_INTERVAL)
            waited += _ANSWER_POLL_INTERVAL
            if waited >= _ANSWER_TIMEOUT_S:
                logger.info("No answer from %s after %ds — giving up.", target_number, _ANSWER_TIMEOUT_S)
                return

        if call.state == CallState.ENDED:
            logger.info("Call to %s ended before answer (busy / rejected).", target_number)
            return

        logger.info("Outbound call answered by %s — waiting for operator decision…", display)

        # ── give operator a chance to take over ───────────────────────────────
        from api.phone import wait_for_ring_decision
        phone_state["ringing_call"] = {
            "caller":        target_number,
            "caller_name":   target_name,
            "ringing_since": datetime.now(timezone.utc).isoformat(),
            "direction":     "outbound",
        }
        decision = wait_for_ring_decision(timeout=float(config.AI_RING_TIMEOUT_SECONDS))
        phone_state["ringing_call"] = None

        if decision == "human":
            logger.info("Operator takes the outbound call to %s — bridging audio.", display)
            import time as _time
            phone_state["active_call"] = {
                "caller":      target_number,
                "caller_name": target_name,
                "started_at":  started_at.isoformat(),
                "mode":        "human",
            }
            phone_state["bridge_call"] = call
            # Keep thread alive; WebSocket bridge does the audio
            while call.state != CallState.ENDED:
                _time.sleep(0.5)
            # fall through to finally for cleanup
            return

        logger.info("AI handling outbound call to %s", display)

        # ── update shared phone state ─────────────────────────────────────────
        phone_state["active_call"] = {
            "caller":      target_number,
            "caller_name": target_name,
            "started_at":  started_at.isoformat(),
            "mode":        "ai",
        }

        # ── speak the opening line ────────────────────────────────────────────
        # Seed the history so the LLM knows what we already said
        history.append({"role": "assistant", "content": _OUTBOUND_OPENING})
        _write_pcm(call, speak(_OUTBOUND_OPENING, lang="en"))

        # ── VAD + conversation loop (outbound system prompt) ──────────────────
        turn_ref = [turn_count]
        _conversation_loop(
            call,
            history,
            caller_name=target_name,
            system_prompt=OUTBOUND_SYSTEM_PROMPT,
            turn_count_ref=turn_ref,
        )
        turn_count = turn_ref[0]

    except Exception as exc:
        logger.error("Unhandled error in handle_outbound_call: %s", exc, exc_info=True)

    finally:
        try:
            if call.state != CallState.ENDED:
                call.hangup()
        except Exception:
            pass

        phone_state["active_call"] = None
        phone_state["bridge_call"] = None
        ended_at = datetime.now(timezone.utc)

        call_log.record(
            caller=target_number,
            caller_name=target_name,
            direction="outbound",
            started_at=started_at,
            ended_at=ended_at,
            turn_count=turn_count,
        )
        logger.info(
            "Outbound call ended: %s  duration=%ds  turns=%d",
            display,
            int((ended_at - started_at).total_seconds()),
            turn_count,
        )
