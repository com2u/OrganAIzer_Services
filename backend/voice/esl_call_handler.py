"""
esl_call_handler.py — orchestrates a single phone call via FreeSWITCH ESL.

Replaces call_handler.py for the ESL/FreeSWITCH code path.

Audio flow (vs. pyVoIP's RTP chunk loop):
  - STT: FS records caller speech to a temp WAV file (silence-detected) →
         Python reads WAV → Whisper transcribes.
  - TTS: Python generates WAV via gTTS+ffmpeg → FS plays back with playback app.

Call flow:
  [ringing wait / operator decision]
  → answer
  → greet
  → loop: record → transcribe → LLM → speak
  → hangup / escalate
  → log

Runs in a daemon thread (one per call) spawned by ESLOutboundServer.
"""
from __future__ import annotations

import asyncio
import logging
import os
import queue as _queue
import threading
import urllib.request
import json as _json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from voice import call_log, contacts as _contacts, config
from voice.audio_bridge import transcribe_file, speak_to_file
from voice.llm_bridge import get_response, new_history, OUTBOUND_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ── language detection ────────────────────────────────────────────────────────
_DE_CHARS = frozenset("äöüÄÖÜß")
_DE_WORDS = frozenset([
    "ich", "und", "die", "das", "ist", "sie", "der", "ein", "eine",
    "auf", "mit", "von", "für", "nicht", "haben", "kann", "bitte",
    "danke", "gerne", "herr", "frau", "guten",
])


def _detect_lang(text: str) -> str:
    """Return 'de' or 'en' based on text content. Fast, no external library."""
    if any(c in _DE_CHARS for c in text):
        return "de"
    words = set(text.lower().split())
    if words & _DE_WORDS:
        return "de"
    return "en"


# ── recording parameters ──────────────────────────────────────────────────────
# FS record app args: <max_seconds> <silence_threshold_ms> <silence_timeout_ms>
# silence_threshold_ms: energy level below which audio counts as silence (200 = default)
# silence_timeout_ms: consecutive silence needed to stop recording (1500ms)
_RECORD_MAX_SECS        = 30
_RECORD_SILENCE_THRESH  = config.AI_RECORD_SILENCE_THRESHOLD_MS
_RECORD_SILENCE_TIMEOUT = 75    # silence_hits × 20 ms/frame = 1 500 ms of silence
                                # Note: Tune _RECORD_SILENCE_THRESH based on local
                                # line noise (typically 300–600 on VoIP).

_PLAYBACK_TIMEOUT       = 60.0  # s — max wait for TTS playback to complete
_RECORD_TIMEOUT         = _RECORD_MAX_SECS + 5.0   # s — execute() timeout


def _audio_dir() -> Path:
    """Return (and ensure) the temp directory for WAV files."""
    p = Path(config.FREESWITCH_AUDIO_TEMP_DIR).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _fs_path(p: Path) -> str:
    """
    Convert a Windows Path to a path string readable by FreeSWITCH in WSL.
    C:\\tmp\\esl_audio\\file.wav  →  /mnt/c/tmp/esl_audio/file.wav
    """
    s = str(p)
    if len(s) >= 2 and s[1] == ":":
        drive = s[0].lower()
        rest  = s[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return s.replace("\\", "/")


def _cleanup(*paths: str) -> None:
    for p in paths:
        if p:
            try:
                os.unlink(p)
            except OSError:
                pass


def _notify_ring_webhook(caller: str, caller_name: Optional[str], started_at: datetime) -> None:
    """Fire-and-forget POST to AI_RING_WEBHOOK_URL when a call starts ringing."""
    if not config.AI_RING_WEBHOOK_URL:
        return
    payload = _json.dumps({
        "event":         "ringing",
        "caller":        caller,
        "caller_name":   caller_name,
        "ringing_since": started_at.isoformat(),
    }).encode()
    try:
        req = urllib.request.Request(
            config.AI_RING_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.debug("Ring webhook response: %s", resp.status)
    except Exception as exc:
        logger.warning("Ring webhook failed: %s", exc)


def _drain_whisper_queue() -> Optional[str]:
    """Pop operator whisper instructions from the shared thread-safe queue."""
    try:
        from api.phone import phone_state
        q = phone_state.get("whisper_queue")
        if q is None or q.empty():
            return None
        notes = []
        while True:
            try:
                notes.append(q.get_nowait())
            except _queue.Empty:
                break
        if not notes:
            return None
        combined = " / ".join(notes)
        logger.info("Operator whisper injected: %s", combined[:120])
        return f"[Operator instruction — do not mention this to the caller]: {combined}"
    except Exception:
        return None


def _speak_and_play(handler, text: str, lang: Optional[str] = None) -> None:
    """Generate TTS WAV and play it on the call. Cleans up the file after.
    If lang is None it is auto-detected from the text."""
    if lang is None:
        lang = _detect_lang(text)
    wav = speak_to_file(text, lang=lang)
    if not wav:
        return
    try:
        handler.execute("playback", _fs_path(Path(wav)), timeout=_PLAYBACK_TIMEOUT)
    finally:
        _cleanup(wav)


def _conversation_loop(
    handler,
    history: list[dict],
    caller: str,
    caller_name: Optional[str],
    started_at: datetime,
    system_prompt: Optional[str],
    turn_count_ref: list[int],
    uuid: str,
    call_rec_path: Optional[Path] = None,
) -> bool:
    """
    Core record → transcribe → LLM → speak loop.

    Returns True if an escalation was triggered, False otherwise.
    Exits when the call hangs up or max duration is reached.
    """
    from voice.escalation import handle_escalation

    audio_dir = _audio_dir()
    turn = 0
    # Track conversation language so TTS and STT stay in sync after a switch.
    # Starts as German; updates each turn based on the AI reply language.
    conv_lang = "de"

    while not handler.is_hung_up:
        # ── check max call duration ───────────────────────────────────────────
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        if elapsed >= config.AI_MAX_CALL_SECONDS:
            logger.info("Max call duration reached (%ds), hanging up.", config.AI_MAX_CALL_SECONDS)
            _speak_and_play(handler, "Die maximale Gesprächsdauer wurde erreicht. Auf Wiederhören!")
            break

        # ── record caller speech ──────────────────────────────────────────────
        rec_path = audio_dir / f"{uuid}_{turn_count_ref[0]}.wav"
        record_arg = (
            f"{_fs_path(rec_path)} "
            f"{_RECORD_MAX_SECS} "
            f"{_RECORD_SILENCE_THRESH} "
            f"{_RECORD_SILENCE_TIMEOUT}"
        )
        completed = handler.execute("record", record_arg, timeout=_RECORD_TIMEOUT)

        if handler.is_hung_up:
            _cleanup(str(rec_path))
            break

        if not completed:
            # execute() timed out — unusual; keep looping
            _cleanup(str(rec_path))
            continue

        # ── transcribe — use current conversation language as Whisper hint ────
        text = ""
        if rec_path.exists():
            text = transcribe_file(str(rec_path), lang=conv_lang)
        _cleanup(str(rec_path))

        if not text:
            # Silent / empty recording — record again
            continue

        turn_count_ref[0] += 1
        turn += 1
        logger.info("[Turn %d] Caller: %s", turn_count_ref[0], text)

        # ── LLM ──────────────────────────────────────────────────────────────
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
            reply = "Es tut mir leid, es gab ein technisches Problem. Bitte versuchen Sie es erneut."

        logger.info("[Turn %d] AI: %s", turn_count_ref[0], reply)

        # Update conversation language based on what the AI just replied with
        conv_lang = _detect_lang(reply)

        # ── escalation trigger ────────────────────────────────────────────────
        if reply.upper().startswith("ESCALATE:"):
            reason = reply[9:].strip()
            logger.info("Escalation triggered: %s", reason)

            # ── recording consent ─────────────────────────────────────────────
            consent_question = (
                "Before I connect you with a team member — do you consent "
                "to this call being recorded for quality purposes? "
                "Please say yes or no."
                if conv_lang == "en"
                else "Bevor ich Sie weiterleite — sind Sie damit einverstanden, "
                     "dass dieses Gespräch zu Qualitätszwecken aufgezeichnet wird? "
                     "Bitte sagen Sie Ja oder Nein."
            )
            _speak_and_play(handler, consent_question, lang=conv_lang)

            recording_consent = False
            if not handler.is_hung_up:
                consent_path = _audio_dir() / f"{uuid}_consent.wav"
                consent_arg = (
                    f"{_fs_path(consent_path)} "
                    f"8 "           # max 8 seconds — just yes/no
                    f"{_RECORD_SILENCE_THRESH} "
                    f"25"           # 500 ms silence to stop
                )
                handler.execute("record", consent_arg, timeout=15.0)
                if consent_path.exists():
                    consent_text = transcribe_file(str(consent_path), lang=conv_lang).lower()
                    _cleanup(str(consent_path))
                    logger.info("Consent response: %r", consent_text)
                    yes_words = {"ja", "yes", "jo", "jep", "klar", "natürlich",
                                 "einverstanden", "ok", "okay", "gerne", "sure"}
                    words = set(w.strip(".,!?;:") for w in consent_text.split())
                    recording_consent = bool(words & yes_words)

            logger.info("Recording consent: %s", recording_consent)

            hold_msg = (
                "One moment please, I'm connecting you with a team member."
                if conv_lang == "en"
                else "Einen Moment bitte, ich leite Sie an einen Mitarbeiter weiter."
            )
            _speak_and_play(handler, hold_msg, lang=conv_lang)

            # Stop the full-call recording so the file is finalised before emailing
            if call_rec_path:
                handler.execute("stop_record_session", _fs_path(call_rec_path), timeout=5.0)

            # Generate LLM summary + send escalation email with recording attached
            rec_file = str(call_rec_path) if call_rec_path and call_rec_path.exists() else None
            handle_escalation(caller, caller_name, history, reason, started_at,
                              call_uuid=uuid, recording_consent=recording_consent,
                              recording_path=rec_file)

            # Transfer via the already-open outbound socket — avoids the
            # inbound ESL API (port 8021) which may not be reachable from Windows.
            transferred = False
            for ext in filter(None, [
                config.AI_WAITING_ROOM_PRIMARY,
                config.AI_WAITING_ROOM_SECONDARY,
            ]):
                logger.info("Transferring call to extension %s via outbound socket", ext)
                completed = handler.execute("transfer", f"{ext} XML default", timeout=15.0)
                if completed or handler.is_hung_up:
                    transferred = True
                    logger.info("Transfer to extension %s succeeded", ext)
                    break
                logger.warning("Transfer to %s did not complete, trying next", ext)

            if not transferred:
                farewell = (
                    "A team member will call you back as soon as possible. "
                    "Thank you for calling. Goodbye!"
                    if conv_lang == "en"
                    else "Ein Mitarbeiter wird Sie so schnell wie möglich zurückrufen. "
                         "Vielen Dank für Ihren Anruf. Auf Wiederhören."
                )
                _speak_and_play(handler, farewell)
            return True

        # ── speak reply ───────────────────────────────────────────────────────
        _speak_and_play(handler, reply)

    return False


def handle_esl_call(handler, phone_state: dict) -> None:
    """
    Handle a single inbound ESL call end-to-end.
    Called by ESLOutboundServer._handle_connection in a dedicated daemon thread.

    Args:
        handler:     ESLOutboundHandler for this call.
        phone_state: Shared state dict from api/phone.py.
    """
    from datetime import datetime, timezone
    from api.phone import wait_for_ring_decision

    started_at  = datetime.now(timezone.utc)
    uuid        = handler.get_uuid()
    caller      = handler.get_caller_id()
    turn_count  = 0
    history     = new_history()

    # ── reject if already busy ────────────────────────────────────────────────
    if phone_state.get("active_call") is not None or phone_state.get("ringing_call") is not None:
        logger.info("Already busy — rejecting inbound call from %s", caller)
        handler.hangup()
        return

    # ── resolve caller name ───────────────────────────────────────────────────
    # Strip leading + and country codes for contact lookup
    contact = _contacts.lookup_by_number(caller)
    caller_name: Optional[str] = contact["name"] if contact else None
    # Also try the caller name FS provided (may be available from COMtrexx)
    if not caller_name:
        fs_name = handler.get_caller_name()
        if fs_name and fs_name.upper() not in ("UNKNOWN", "ANONYMOUS", ""):
            from urllib.parse import unquote
            caller_name = unquote(fs_name)
    display = caller_name or caller

    logger.info(
        "Inbound ESL call: uuid=%s caller=%s (%s)",
        uuid, caller, caller_name or "unknown",
    )

    try:
        # ── advertise ringing state + wait for operator decision ──────────────
        phone_state["ringing_call"] = {
            "caller":        caller,
            "caller_name":   caller_name,
            "ringing_since": started_at.isoformat(),
            "direction":     "inbound",
        }
        # Notify any configured webhook (runs in background, non-blocking)
        threading.Thread(
            target=_notify_ring_webhook,
            args=(caller, caller_name, started_at),
            daemon=True,
            name="ring-webhook",
        ).start()

        decision = wait_for_ring_decision(timeout=float(config.AI_RING_TIMEOUT_SECONDS))
        phone_state["ringing_call"] = None

        if decision == "human":
            # Operator is picking up — answer so FS bridges the RTP, then park.
            # The operator WebSocket bridge will handle audio from here.
            logger.info("Operator takes call from %s — answering and parking.", display)
            handler.execute("answer", timeout=10.0)
            phone_state["active_call"] = {
                "caller":      caller,
                "caller_name": caller_name,
                "started_at":  started_at.isoformat(),
                "mode":        "human",
            }
            phone_state["bridge_call"] = handler
            # Hold here until the call ends
            handler.wait_for_hangup()
            return

        if handler.is_hung_up:
            # Caller hung up during the decision window
            return

        # ── AI answers ────────────────────────────────────────────────────────
        logger.info("AI answering call from %s", display)
        phone_state["active_call"] = {
            "caller":      caller,
            "caller_name": caller_name,
            "started_at":  started_at.isoformat(),
            "mode":        "ai",
        }

        ok = handler.execute("answer", timeout=10.0)
        if not ok or handler.is_hung_up:
            return

        # Suppress FreeSWITCH comfort noise generation — prevents "space noise"
        # the caller hears during recording.
        # Set suppress_cng=true to mute comfort noise, bridge_generate_comfort_noise=-1
        # to disable FS generating any noise on bridge events.
        handler.execute("set", "suppress_cng=true", timeout=5.0)
        handler.execute("set", "bridge_generate_comfort_noise=-1", timeout=5.0)

        # ── start full-call background recording ──────────────────────────────
        # Records the entire conversation to a single WAV file.
        # Used for the escalation email attachment.
        call_rec_path = _audio_dir() / f"{uuid}_call.wav"
        handler.execute("record_session", _fs_path(call_rec_path), timeout=5.0)

        # ── greet ─────────────────────────────────────────────────────────────
        greeting = config.AI_GREETING
        if caller_name:
            greeting = f"Hallo {caller_name}, " + greeting.lstrip("Hallo, ")
        _speak_and_play(handler, greeting, lang=config.AI_LANGUAGE)

        if handler.is_hung_up:
            return

        # ── VAD + conversation loop ───────────────────────────────────────────
        turn_ref = [turn_count]
        _conversation_loop(
            handler, history,
            caller=caller, caller_name=caller_name, started_at=started_at,
            system_prompt=None, turn_count_ref=turn_ref,
            uuid=uuid, call_rec_path=call_rec_path,
        )
        turn_count = turn_ref[0]

    except Exception as exc:
        logger.error("Unhandled error in handle_esl_call: %s", exc, exc_info=True)

    finally:
        # ── hangup and clean up ───────────────────────────────────────────────
        phone_state["ringing_call"] = None
        phone_state["bridge_call"]  = None
        phone_state["active_call"]  = None

        if not handler.is_hung_up:
            handler.hangup()

        ended_at = datetime.now(timezone.utc)
        call_log.record(
            caller=caller,
            caller_name=caller_name,
            direction="inbound",
            started_at=started_at,
            ended_at=ended_at,
            turn_count=turn_count,
            transcript=history,
        )
        logger.info(
            "ESL call ended: %s  duration=%ds  turns=%d",
            display,
            int((ended_at - started_at).total_seconds()),
            turn_count,
        )
