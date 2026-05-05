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


# ── filler phrase cache ───────────────────────────────────────────────────────
# Pre-generated WAV files played immediately after recording ends, while the
# STT + LLM + TTS pipeline runs in the background. Eliminates the silence gap
# the caller hears during processing.
# Multiple phrases per language are rotated round-robin so the caller never
# hears the same phrase twice in a row.
_FILLER_TEXTS: dict[str, list[str]] = {
    "de": [
        "Einen Moment bitte.",
        "Ich schaue das kurz nach.",
        "Einen Augenblick.",
        "Kurz Geduld bitte.",
        "Ich bin gleich bei Ihnen.",
    ],
    "en": [
        "One moment please.",
        "Let me check that for you.",
        "Just a moment.",
        "Bear with me.",
        "Right with you.",
    ],
}

_filler_wavs:  dict[str, list[str]] = {}  # lang → list of WAV paths
_filler_index: dict[str, int]       = {}  # lang → next index
_filler_lock = threading.Lock()


def _build_filler_pool(lang: str) -> None:
    """Generate all WAVs for *lang* and store them. Called from background thread."""
    texts = _FILLER_TEXTS.get(lang, _FILLER_TEXTS["de"])
    paths = []
    for text in texts:
        path = speak_to_file(text, lang=lang)
        if path:
            paths.append(path)
    with _filler_lock:
        _filler_wavs[lang] = paths
        _filler_index[lang] = 0
    logger.debug("Filler pool ready for lang=%s (%d phrases)", lang, len(paths))


def _get_filler_wav(lang: str) -> str:
    """Return the next filler WAV path for *lang*, rotating through the pool."""
    with _filler_lock:
        pool = _filler_wavs.get(lang)
        if pool is None:
            # Pool not ready yet — fall back silently (background thread will fix it)
            return ""
        if not pool:
            return ""
        idx = _filler_index.get(lang, 0)
        _filler_index[lang] = (idx + 1) % len(pool)
        return pool[idx]


def prewarm_fillers() -> None:
    """Pre-generate filler WAVs for all languages at startup.
    Call once from the server startup path so language switches never block."""
    for lang in _FILLER_TEXTS:
        threading.Thread(
            target=_build_filler_pool,
            args=(lang,),
            daemon=True,
            name=f"filler-prewarm-{lang}",
        ).start()


# ── recording parameters ──────────────────────────────────────────────────────
# FS record app args: <max_seconds> <silence_threshold_ms> <silence_timeout_ms>
# silence_threshold_ms: energy level below which audio counts as silence (200 = default)
# silence_timeout_ms: consecutive silence needed to stop recording (1500ms)
_RECORD_MAX_SECS        = 20
_RECORD_SILENCE_THRESH  = config.AI_RECORD_SILENCE_THRESHOLD_MS
_RECORD_SILENCE_TIMEOUT = 60    # silence_hits × 20 ms/frame = 1200 ms of silence
                                # 1.2 s gives callers time to start speaking after
                                # the AI finishes — tighter values cut off responses
                                # on slow-reacting or mobile VoIP connections.

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
    initial_lang: str = "de",
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
    # Starts at initial_lang (passed from call context); updates each turn.
    conv_lang = initial_lang
    # Prevent infinite loops when the caller is silent or audio is lost.
    _empty_turns = 0
    _MAX_EMPTY_TURNS = 8  # 8 silent turns before ending the call

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

        # ── background: STT + LLM + TTS while filler plays ───────────────────
        # Start processing immediately after recording ends. The filler phrase
        # plays on the channel while Whisper + LLM + edge-tts run in parallel,
        # eliminating most of the silence gap the caller would otherwise hear.
        _proc: dict = {"text": "", "reply": "", "wav": "", "lang": conv_lang}
        _proc_done = threading.Event()

        def _process_turn(
            _rec=str(rec_path),
            _cn=caller_name,
            _sp=system_prompt,
        ) -> None:
            t, stt_lang = "", conv_lang
            if Path(_rec).exists():
                # Pass the current conversation language so Whisper doesn't
                # misidentify German phone audio as English (common on noisy lines).
                t, stt_lang = transcribe_file(_rec, lang=conv_lang)
            _cleanup(_rec)
            if not t:
                _proc_done.set()
                return
            _proc["text"] = t
            # Update language from STT detection immediately — the filler for
            # this turn is already playing, but the NEXT turn's filler will use
            # the correct language.
            _proc["lang"] = stt_lang
            extra = _drain_whisper_queue()
            try:
                r = asyncio.run(
                    get_response(
                        history, t,
                        caller_name=_cn,
                        system_prompt=_sp,
                        system_extra=extra,
                    )
                )
            except Exception as exc:
                logger.error("LLM error: %s", exc)
                r = (
                    "Es tut mir leid, es gab ein technisches Problem. Bitte versuchen Sie es erneut."
                    if stt_lang == "de"
                    else "I'm sorry, there was a technical issue. Please try again."
                )
            _proc["reply"] = r
            # Refine language from LLM reply (handles mixed-language edge cases)
            _proc["lang"] = _detect_lang(r)
            # Pre-generate TTS unless the LLM triggered a special action
            # (ESCALATE replies are never spoken directly to the caller)
            if not r.upper().startswith("ESCALATE:"):
                wav = speak_to_file(r, lang=_proc["lang"])
                _proc["wav"] = wav
            _proc_done.set()

        threading.Thread(
            target=_process_turn, daemon=True, name=f"proc-t{turn}"
        ).start()

        # Play filler immediately — caller hears "Einen Moment bitte." instead
        # of silence while the heavy processing runs in the background.
        filler = _get_filler_wav(conv_lang)
        if filler and not handler.is_hung_up:
            handler.execute("playback", _fs_path(Path(filler)), timeout=10.0)

        # Wait for background thread (usually already done by the time
        # the filler finishes playing)
        _proc_done.wait(timeout=20.0)

        if handler.is_hung_up:
            if _proc.get("wav"):
                _cleanup(_proc["wav"])
            break

        if not _proc["text"]:
            # Silent / empty recording — record again, but bail after too many
            _empty_turns += 1
            if _empty_turns == 2:
                # Prompt the caller mid-silence before they give up waiting
                check_in = (
                    "Are you still there?"
                    if conv_lang == "en"
                    else "Sind Sie noch da?"
                )
                _speak_and_play(handler, check_in, lang=conv_lang)
                if handler.is_hung_up:
                    break
            if _empty_turns >= _MAX_EMPTY_TURNS:
                logger.info("Too many consecutive silent turns (%d), ending call.", _empty_turns)
                farewell = (
                    "I haven't heard anything for a while. I'll end the call now. Goodbye!"
                    if conv_lang == "en"
                    else "Ich konnte Sie leider nicht verstehen. Ich beende das Gespräch. Auf Wiederhören!"
                )
                _speak_and_play(handler, farewell, lang=conv_lang)
                break
            continue
        _empty_turns = 0  # reset on any real utterance

        turn_count_ref[0] += 1
        turn += 1
        text  = _proc["text"]
        reply = _proc["reply"]
        conv_lang = _proc["lang"]

        logger.info("[Turn %d] Caller: %s", turn_count_ref[0], text)
        logger.info("[Turn %d] AI: %s", turn_count_ref[0], reply)

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
                    consent_text, _ = transcribe_file(str(consent_path), lang=conv_lang)
                    consent_text = consent_text.lower()
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

            # Generate LLM summary + send escalation email with recording attached.
            # Pass esl_handler so handle_escalation skips its own transfer attempt —
            # the transfer below (outbound socket, "ext XML default") is the
            # single authoritative handoff.
            rec_file = str(call_rec_path) if call_rec_path and call_rec_path.exists() else None
            esc_result = handle_escalation(
                caller, caller_name, history, reason, started_at,
                call_uuid=uuid, esl_handler=handler,
                recording_consent=recording_consent,
                recording_path=rec_file,
            )

            # Notify the operator via phone_state so the frontend shows an alert.
            # This is the only reliable notification path when email is not configured.
            try:
                from api.phone import phone_state as _ps
                from datetime import timezone as _tz
                _ps["last_escalation"] = {
                    "caller":      caller,
                    "caller_name": caller_name,
                    "reason":      reason,
                    "summary":     esc_result.get("summary", ""),
                    "email_sent":  esc_result.get("email_sent", False),
                    "at":          datetime.now(_tz.utc).isoformat(),
                }
            except Exception as _e:
                logger.warning("Could not set last_escalation in phone_state: %s", _e)

            # Park the call at COMtrexx orbit 778/779 using SIP REFER (deflect).
            # Since 003010 is an internal COMtrexx extension, a REFER to a park
            # orbit is accepted. A direct bridge INVITE to 778 is rejected by
            # COMtrexx (cause 88 INCOMPATIBLE_DESTINATION) — deflect is the
            # correct mechanism.
            # COMtrexx must be configured: park orbit 778 timeout = 10 min,
            # on-timeout forward → 003010 (so the AI can handle the fallback).
            transferred = False
            for ext in filter(None, [
                config.AI_WAITING_ROOM_PRIMARY,
                config.AI_WAITING_ROOM_SECONDARY,
            ]):
                logger.info("Parking call at COMtrexx orbit %s via SIP REFER", ext)
                completed = handler.execute(
                    "deflect", f"sip:{ext}@{config.COMTREXX_IP}", timeout=15.0
                )
                if completed or handler.is_hung_up:
                    transferred = True
                    logger.info("Deflect to park orbit %s succeeded", ext)
                    break
                logger.warning("Deflect to orbit %s did not complete, trying next", ext)

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

        # ── speak reply (WAV already generated in background thread) ─────────
        if _proc.get("wav"):
            try:
                handler.execute(
                    "playback", _fs_path(Path(_proc["wav"])),
                    timeout=_PLAYBACK_TIMEOUT,
                )
            finally:
                _cleanup(_proc["wav"])

    return False


def handle_esl_call(handler, phone_state: dict) -> None:
    """
    Handle an inbound or outbound ESL call end-to-end.
    Called by ESLOutboundServer._handle_connection in a dedicated daemon thread.

    Outbound calls (originated via voice/outbound.py) are identified by UUID
    match against the pending context table.  All other calls are treated as
    inbound from COMtrexx.

    Args:
        handler:     ESLOutboundHandler for this call.
        phone_state: Shared state dict from api/phone.py.
    """
    from datetime import datetime, timezone
    from api.phone import wait_for_ring_decision
    from voice.outbound import pop_outbound_context

    started_at  = datetime.now(timezone.utc)
    uuid        = handler.get_uuid()
    caller      = handler.get_caller_id()
    turn_count  = 0
    history     = new_history()

    # ── check if this is an outbound call we originated ───────────────────────
    outbound_ctx = pop_outbound_context(uuid)
    is_outbound  = outbound_ctx is not None

    # ── store handler so the API can hang up at any time ─────────────────────
    phone_state["esl_handler"] = handler

    # ── reject if already busy ────────────────────────────────────────────────
    if phone_state.get("active_call") is not None or phone_state.get("ringing_call") is not None:
        logger.info("Already busy — rejecting call uuid=%s", uuid)
        handler.hangup()
        return

    # ── resolve caller name ───────────────────────────────────────────────────
    if is_outbound:
        # For outbound, "caller" is the number we dialled
        number = outbound_ctx["number"]
        contact = _contacts.lookup_by_number(number)
        caller_name: Optional[str] = contact["name"] if contact else outbound_ctx.get("display_name")
        caller = number
    else:
        contact = _contacts.lookup_by_number(caller)
        caller_name = contact["name"] if contact else None
        if not caller_name:
            fs_name = handler.get_caller_name()
            if fs_name and fs_name.upper() not in ("UNKNOWN", "ANONYMOUS", ""):
                from urllib.parse import unquote
                caller_name = unquote(fs_name)

    display = caller_name or caller

    logger.info(
        "%s ESL call: uuid=%s number=%s (%s)",
        "Outbound" if is_outbound else "Inbound",
        uuid, caller, caller_name or "unknown",
    )

    try:
        if is_outbound:
            # ── outbound: answer immediately, AI speaks first ─────────────────
            phone_state["active_call"] = {
                "caller":      caller,
                "caller_name": caller_name,
                "started_at":  started_at.isoformat(),
                "mode":        "ai",
                "direction":   "outbound",
            }

            ok = handler.execute("answer", timeout=10.0)
            if not ok or handler.is_hung_up:
                return

            handler.execute("set", "suppress_cng=true", timeout=5.0)
            handler.execute("set", "bridge_generate_comfort_noise=-1", timeout=5.0)

            call_rec_path = _audio_dir() / f"{uuid}_call.wav"
            handler.execute("record_session", _fs_path(call_rec_path), timeout=5.0)

            greeting_lang = outbound_ctx.get("lang", "de")
            _speak_and_play(handler, outbound_ctx["opening_line"], lang=greeting_lang)

            if handler.is_hung_up:
                return

            # Seed history so the LLM knows what it already said.
            # Without this the LLM receives an empty history on turn 1 and
            # re-introduces itself from the system prompt role definition.
            history.append({"role": "assistant", "content": outbound_ctx["opening_line"]})

            turn_ref = [turn_count]
            _conversation_loop(
                handler, history,
                caller=caller, caller_name=caller_name, started_at=started_at,
                system_prompt=outbound_ctx["system_prompt"],
                turn_count_ref=turn_ref,
                uuid=uuid, call_rec_path=call_rec_path,
                initial_lang=greeting_lang,
            )
            turn_count = turn_ref[0]
            return

        # ── inbound: advertise ringing + wait for operator decision ───────────
        phone_state["ringing_call"] = {
            "caller":        caller,
            "caller_name":   caller_name,
            "ringing_since": started_at.isoformat(),
            "direction":     "inbound",
        }
        threading.Thread(
            target=_notify_ring_webhook,
            args=(caller, caller_name, started_at),
            daemon=True,
            name="ring-webhook",
        ).start()

        decision = wait_for_ring_decision(timeout=float(config.AI_RING_TIMEOUT_SECONDS))
        phone_state["ringing_call"] = None

        if decision == "human":
            logger.info("Operator takes call from %s — answering and parking.", display)
            handler.execute("answer", timeout=10.0)
            phone_state["active_call"] = {
                "caller":      caller,
                "caller_name": caller_name,
                "started_at":  started_at.isoformat(),
                "mode":        "human",
            }
            phone_state["bridge_call"] = handler
            handler.wait_for_hangup()
            return

        if handler.is_hung_up:
            return

        # ── AI answers inbound call ───────────────────────────────────────────
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
        phone_state["esl_handler"]  = None

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
