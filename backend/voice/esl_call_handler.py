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
import re
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
# FS record app args: <max_seconds> <silence_threshold_ms> <silence_hits>
#   silence_threshold_ms: energy level below which audio counts as silence
#   silence_hits: consecutive 20-ms frames of silence required to stop recording
#
# All three knobs come from voice.config (AI_RECORD_*). Defaults were tightened
# from the legacy 20 s / 60-hits values so short utterances end faster after
# the caller stops speaking, without enabling barge-in.
_RECORD_MAX_SECS        = config.AI_RECORD_MAX_SECONDS
_RECORD_SILENCE_THRESH  = config.AI_RECORD_SILENCE_THRESHOLD_MS
_RECORD_SILENCE_TIMEOUT = max(
    1, int(round(config.AI_RECORD_SILENCE_SECONDS * 1000 / 20))
)

_PLAYBACK_TIMEOUT       = 60.0  # s — max wait for TTS playback to complete
_RECORD_TIMEOUT         = (
    _RECORD_MAX_SECS + float(config.AI_RECORD_INITIAL_TIMEOUT_SECONDS)
)   # s — execute() timeout (max_seconds + slack for FS flush)


# ── garbage transcription detection ───────────────────────────────────────────
# Whisper occasionally returns single-character artefacts ("."), pure
# punctuation, or empty strings on noisy lines. Treat these as "did not catch
# that" so we never send them to the LLM. Real short utterances like "Ja" or
# "Nein" are 2+ chars and pass through normally.
_GARBAGE_TRANSCRIPTION_RE = re.compile(r"^[\s\.,;:!\?\-_'\"\(\)\[\]…·]+$")


def _is_garbage_transcription(text: str) -> bool:
    """True if a transcription is too short or noisy to be a real utterance."""
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) < 2:
        return True
    if _GARBAGE_TRANSCRIPTION_RE.match(stripped):
        return True
    return False


# ── unfinished-utterance detection ────────────────────────────────────────────
# Real callers often pause while still explaining ("…und, äh, also…").
# When the trailing word is a hesitation marker or a conjunction the speaker
# is almost certainly mid-sentence, so we want to give them more think-time
# instead of triggering the LLM on a half-formed thought.
#
# Detection is conservative: clear short answers like "Ja", "Nein", "OK",
# "Hallo" must NOT be classified as unfinished.
_UNFINISHED_TRAILING_TOKENS = frozenset({
    # German hesitation / discourse markers
    "äh", "ähm", "öh", "öhm", "hm", "hmm", "mh", "mhm",
    # German trailing conjunctions / mid-thought words
    "und", "oder", "weil", "also", "aber", "dass", "denn", "doch",
    "warte", "moment", "dann",
    # German trailing modal/aux verbs — a caller cut off after these is almost
    # always still forming the request ("Ich wollte…", "Ich möchte…").
    "wollte", "möchte", "hätte", "würde", "könnte", "sollte", "müsste",
    # English hesitation / conjunctions
    "uh", "uhm", "um", "er", "erm",
    "and", "or", "because", "but", "so", "well",
})

_UNFINISHED_TRAILING_PHRASES = (
    "ich meine",
    "ich glaube also",
    "ich wollte",
    "ich möchte",
    "und dann",
    "let me",
    "i mean",
    "you know",
    "kind of",
)


def _is_likely_unfinished_utterance(text: str) -> bool:
    """
    True when the transcription looks like a mid-sentence pause rather than a
    complete utterance — trailing hesitation marker ("äh", "ähm"), trailing
    conjunction ("und", "oder", "because"), or a comma-like incomplete phrase.

    Used to delay the LLM call and offer a gentle "I'm still listening"
    continuation prompt instead of jumping in too early on annoyed/hesitant
    callers.
    """
    if not text:
        return False
    t = text.strip()
    if not t:
        return False

    lowered = t.lower()
    # Phrase-level trailing markers ("ich meine", "let me")
    stripped_for_phrase = lowered.rstrip(" .!?…,;:-")
    for phrase in _UNFINISHED_TRAILING_PHRASES:
        if stripped_for_phrase.endswith(phrase):
            return True

    # Comma-ended / dash-ended incomplete phrase (only when there is something
    # before the comma, so "," alone — already filtered as garbage — never
    # reaches here).
    last_meaningful = t[-1]
    if last_meaningful in {",", ";", "-", "–", "—"}:
        return True

    # Strip trailing punctuation, then inspect the final token.
    cleaned = lowered.rstrip(" .!?…,;:-–—\"'")
    if not cleaned:
        return False
    tokens = cleaned.split()
    if not tokens:
        return False
    last = tokens[-1]
    if last in _UNFINISHED_TRAILING_TOKENS:
        return True

    # Single-word fragment that is purely a hesitation marker
    # (e.g. "ähm.", "uh"). "Ja"/"Nein"/"OK"/"Hallo" are not in the set so they
    # pass through.
    if len(tokens) == 1 and tokens[0] in _UNFINISHED_TRAILING_TOKENS:
        return True

    return False


# ── continuation prompts (varied) ─────────────────────────────────────────────
# Played when the caller paused mid-sentence ("…äh", "…und") so the AI signals
# "I'm still listening" without jumping in. The unfinished streak can fire this
# several times in a row, so the phrases are rotated to avoid the robotic effect
# of repeating the exact same sentence each time. Deterministic (indexed by the
# attempt count) so it stays unit-testable and introduces no global state.
# The first entry preserves the original wording so attempt 1 is unchanged.
_CONTINUATION_PROMPTS: dict[str, tuple[str, ...]] = {
    "de": (
        "Ja, ich höre zu — bitte fahren Sie fort.",
        "Ich bin noch dran — sagen Sie ruhig.",
        "Kein Problem, nehmen Sie sich Zeit.",
    ),
    "en": (
        "Yes, I'm listening — please go ahead.",
        "I'm still here — take your time.",
        "No problem, go ahead whenever you're ready.",
    ),
}


def _rotating_continuation(lang: str, attempt: int) -> str:
    """Return a continuation prompt for *lang*, rotating by the 1-based *attempt*.

    attempt 1 → the original wording (unchanged behaviour); later consecutive
    attempts cycle through the pool so the caller never hears the identical
    sentence twice in a row.
    """
    pool = _CONTINUATION_PROMPTS.get(lang, _CONTINUATION_PROMPTS["de"])
    return pool[(max(1, attempt) - 1) % len(pool)]


# ── natural call ending after a spoken goodbye ────────────────────────────────
# When the AI's reply is a farewell ("… Auf Wiederhören.") the conversation is
# over — without this the loop keeps recording and eventually asks "Sind Sie
# noch da?" AFTER it already said goodbye. Detection is on the AI reply (not the
# caller utterance) so a caller merely mentioning "Wiederhören" mid-sentence
# never ends the call; the LLM only says it when closing.
_FAREWELL_MARKERS = ("auf wiederhören", "auf wiederhoeren", "goodbye")


def _is_farewell_reply(reply: str) -> bool:
    """True when the AI reply is a closing farewell — the call should end."""
    if not reply:
        return False
    lowered = reply.lower()
    return any(marker in lowered for marker in _FAREWELL_MARKERS)


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
    dialogue_state: Optional[dict] = None,
) -> bool:
    """
    Core record → transcribe → LLM → speak loop.

    Returns True if an escalation was triggered, False otherwise.
    Exits when the call hangs up or max duration is reached.
    """
    from voice.escalation import handle_escalation
    from voice import scheduler_dialogue

    audio_dir = _audio_dir()
    turn = 0
    # Track conversation language so TTS and STT stay in sync after a switch.
    # Starts at initial_lang (passed from call context); updates each turn.
    conv_lang = initial_lang
    # Prevent infinite loops when the caller is silent or audio is lost.
    _empty_turns = 0
    _MAX_EMPTY_TURNS = 8  # 8 silent turns before ending the call
    # How many consecutive unintelligible turns we've seen. Drives the
    # soft → repeat → farewell escalation. Resets on any real reply.
    _unclear_count = 0
    # Consecutive mid-sentence utterances ("…äh", "…und"). Counted separately
    # from garbage/empty so callers who are simply hesitating are not treated
    # as misunderstood. A safety cap still applies to avoid infinite loops.
    _unfinished_streak = 0
    _MAX_UNFINISHED_STREAK = 3

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
        _proc: dict = {
            "text": "", "reply": "", "wav": "", "lang": conv_lang,
            "unfinished": False,
        }
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
            # Skip the LLM call for garbage transcriptions — the main loop
            # handles them with a one-time polite "could you repeat?" prompt.
            if _is_garbage_transcription(t):
                _proc["text"] = t
                _proc["lang"] = stt_lang
                _proc_done.set()
                return
            # Mid-sentence pause ("…äh", "…und, also,") — skip the LLM and let
            # the main loop offer a gentle continuation prompt instead.
            if _is_likely_unfinished_utterance(t):
                _proc["text"] = t
                _proc["lang"] = stt_lang
                _proc["unfinished"] = True
                _proc_done.set()
                return
            # ── appointment scheduling (deterministic; slots come from Scheduler) ──
            # A per-call state machine handles appointment intent WITHOUT the LLM
            # inventing availability. It returns None when the turn is not part of
            # an appointment flow, so every other call behaves exactly as before.
            if dialogue_state is not None:
                try:
                    _sched = scheduler_dialogue.handle_turn(
                        dialogue_state, t,
                        call_id=uuid, phone=caller, caller_name=_cn,
                    )
                except Exception as exc:  # never let scheduling break a live call
                    logger.error("Scheduler dialogue error: %s", exc, exc_info=True)
                    _sched = None
                if _sched is not None:
                    _proc["text"] = t
                    _proc["reply"] = _sched.reply
                    _proc["lang"] = "de"
                    # Keep the LLM history coherent for turns after the flow ends.
                    history.append({"role": "user", "content": t})
                    history.append({"role": "assistant", "content": _sched.reply})
                    if not _sched.reply.upper().startswith("ESCALATE:"):
                        _proc["wav"] = speak_to_file(_sched.reply, lang="de")
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

        if _proc.get("unfinished"):
            # Caller paused mid-sentence — no LLM call. Offer a gentle "still
            # listening" prompt and record again. Counted separately from
            # garbage/empty so this is not treated as a misunderstanding.
            logger.info(
                "Unfinished utterance detected: %r (lang=%s)",
                _proc["text"], conv_lang,
            )
            _unfinished_streak += 1
            if _unfinished_streak <= _MAX_UNFINISHED_STREAK:
                # Rotate the wording so repeated mid-sentence pauses don't get
                # the identical sentence each time (Priority: reduce repetition).
                continuation_msg = _rotating_continuation(conv_lang, _unfinished_streak)
                _speak_and_play(handler, continuation_msg, lang=conv_lang)
                if handler.is_hung_up:
                    break
                continue
            # Safety cap: if the caller has only produced hesitations for
            # several turns in a row, fall through to the unclear path so the
            # call can wind down gracefully.
            logger.info(
                "Unfinished streak exceeded cap (%d) — escalating to unclear path.",
                _unfinished_streak,
            )

        if _is_garbage_transcription(_proc["text"]) or _proc.get("unfinished"):
            # STT returned a noisy/short artefact (or we exhausted the
            # unfinished safety cap). No LLM call was made in the background.
            # First unclear turn gets a soft "still listening" prompt — annoyed
            # callers are not yet asked to repeat. Subsequent unclear turns
            # ask politely to repeat. Persistent unclear turns end the call.
            logger.info(
                "Garbage/unclear transcription discarded: %r (lang=%s, count=%d)",
                _proc["text"], conv_lang, _unclear_count + 1,
            )
            _unclear_count += 1
            if _unclear_count == 1:
                soft_msg = (
                    "I'm listening — please go ahead."
                    if conv_lang == "en"
                    else "Ich höre Ihnen zu — bitte fahren Sie fort."
                )
                _speak_and_play(handler, soft_msg, lang=conv_lang)
            elif _unclear_count == 2:
                repeat_msg = (
                    "Sorry, I didn't catch that. Could you please repeat?"
                    if conv_lang == "en"
                    else "Entschuldigung, ich habe Sie nicht ganz verstanden. "
                         "Könnten Sie das bitte wiederholen?"
                )
                _speak_and_play(handler, repeat_msg, lang=conv_lang)
            if handler.is_hung_up:
                break
            _empty_turns += 1
            if _empty_turns >= _MAX_EMPTY_TURNS:
                logger.info(
                    "Too many consecutive unintelligible turns (%d), ending call.",
                    _empty_turns,
                )
                farewell = (
                    "I haven't been able to understand you. I'll end the call now. Goodbye!"
                    if conv_lang == "en"
                    else "Ich konnte Sie leider nicht verstehen. "
                         "Ich beende das Gespräch. Auf Wiederhören!"
                )
                _speak_and_play(handler, farewell, lang=conv_lang)
                break
            continue

        _empty_turns = 0  # reset on any real utterance
        _unclear_count = 0  # reset so a later unclear burst gets the soft prompt first
        _unfinished_streak = 0  # reset on any real, complete utterance

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
            # IMPORTANT: Escalation consent is always German (legal/compliance requirement).
            # Do not condition on conv_lang — consent wording must be stable and professional.
            consent_question = (
                "Bevor ich Sie weiterleite — sind Sie damit einverstanden, "
                "dass dieses Gespräch zu Qualitätszwecken aufgezeichnet wird? "
                "Bitte sagen Sie Ja oder Nein."
            )
            _speak_and_play(handler, consent_question, lang="de")

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

            # IMPORTANT: Escalation transfer message is always German (Teleprofi requirement).
            # Do not condition on conv_lang — professional consistency during handoff.
            hold_msg = "Einen Moment bitte, ich leite Sie an einen Mitarbeiter weiter."
            _speak_and_play(handler, hold_msg, lang="de")

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
            # After deflect the caller hears COMtrexx's native waiting music until
            # a technician picks up MANUALLY. COMtrexx park orbit 778 does NOT
            # return the call to the AI on timeout, so there is NO automatic
            # voicemail fallback after parking. Enabling voicemail after deflect
            # would require COMtrexx to be configured to forward the timed-out
            # orbit back to 003010 plus orbit-return detection (not implemented).
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

        # ── natural end after goodbye ─────────────────────────────────────────
        # The AI just said its farewell — end the call instead of recording on
        # and asking "Sind Sie noch da?" after having said goodbye.
        if _is_farewell_reply(reply):
            logger.info("Farewell spoken — ending call naturally.")
            break

    return False


# ── Missed-call voicemail (retained, NOT wired to escalation) ─────────────────
# Escalation parks the caller in the COMtrexx waiting room via SIP REFER
# (deflect) — see _conversation_loop — where a technician picks up MANUALLY.
# COMtrexx orbit 778 does NOT return the call to the AI on timeout, so there is
# NO automatic voicemail fallback after parking. The voicemail helpers below are
# kept in the repository but are deliberately not invoked from the escalation
# path. Wiring them up would require COMtrexx to be configured to forward the
# timed-out orbit back to extension 003010 plus orbit-return detection (not
# implemented).

_VOICEMAIL_PROMPT_DE = (
    "Leider können wir Ihren Anruf derzeit nicht persönlich entgegennehmen. "
    "Bitte hinterlassen Sie nach dem Signalton Ihren Namen, Ihre Rückrufnummer "
    "und kurz Ihr Anliegen. Wir melden uns schnellstmöglich bei Ihnen zurück."
)
_VOICEMAIL_PROMPT_EN = (
    "Unfortunately we cannot take your call in person right now. "
    "Please leave your name, your callback number, and a short message after the tone. "
    "We will get back to you as soon as possible. Thank you for calling."
)


def _wav_duration_seconds(path) -> int:
    """Best-effort duration of a recorded WAV in whole seconds. Returns 0 on error."""
    try:
        import wave
        with wave.open(str(path), "rb") as w:
            rate = w.getframerate() or 8000
            return int(w.getnframes() / rate)
    except Exception:
        try:
            size = Path(path).stat().st_size
            # s16le, 8 kHz, mono → 16000 bytes/sec; minus the 44-byte header.
            return max(0, int((size - 44) / 16000))
        except Exception:
            return 0


def _run_voicemail(
    handler, caller, caller_name, uuid, started_at,
    conv_lang: str = "de", escalation_reason: str = "",
) -> dict:
    """Play the voicemail prompt + beep, record the caller, email the recording.

    Returns structured voicemail info for the call summary. Never raises.
    """
    info = {
        "caller_number": caller,
        "voicemail_received": False,
        "voicemail_duration": 0,
        "voicemail_file": None,
    }
    if handler.is_hung_up:
        return info

    prompt = _VOICEMAIL_PROMPT_EN if conv_lang == "en" else _VOICEMAIL_PROMPT_DE
    _speak_and_play(handler, prompt, lang=conv_lang)
    if handler.is_hung_up:
        return info

    # Beep (signal tone) before recording.
    try:
        handler.execute("playback", "tone_stream://%(500,0,800)", timeout=5.0)
    except Exception:
        pass

    vm_path = _audio_dir() / f"{uuid}_voicemail.wav"
    silence_hits = max(1, int(config.VOICEMAIL_SILENCE_SECONDS / 0.02))
    record_arg = (
        f"{_fs_path(vm_path)} "
        f"{config.AI_VOICEMAIL_MAX_SECONDS} "
        f"{_RECORD_SILENCE_THRESH} "
        f"{silence_hits}"
    )
    handler.execute("record", record_arg, timeout=float(config.AI_VOICEMAIL_MAX_SECONDS) + 10.0)

    if not vm_path.exists():
        logger.info("Voicemail: no recording captured for uuid=%s", uuid)
        return info

    duration = _wav_duration_seconds(vm_path)
    info.update({
        "voicemail_received": True,
        "voicemail_duration": duration,
        "voicemail_file": str(vm_path),
    })
    logger.info("Voicemail captured uuid=%s duration=%ss", uuid, duration)

    # Optional transcription — reuse the existing STT mechanism if it works.
    transcript = ""
    try:
        transcript, _ = transcribe_file(str(vm_path), lang=conv_lang)
    except Exception as exc:
        logger.warning("Voicemail transcription failed (left out of email): %s", exc)
        transcript = ""

    # Email the Teleprofi escalation mailbox with the recording attached.
    try:
        from voice.escalation import send_voicemail_notification
        send_voicemail_notification(
            caller=caller,
            caller_name=caller_name,
            call_uuid=uuid,
            started_at=started_at,
            duration_seconds=duration,
            recording_path=str(vm_path),
            transcript=transcript or None,
            escalation_reason=escalation_reason,
        )
    except Exception as exc:
        logger.error("Voicemail email notification failed: %s", exc)

    if not handler.is_hung_up:
        closing = (
            "Thank you, we will get back to you. Goodbye."
            if conv_lang == "en"
            else "Vielen Dank, wir melden uns bei Ihnen. Auf Wiederhören."
        )
        _speak_and_play(handler, closing, lang=conv_lang)

    return info


def _ensure_min_hold(handler, remaining_seconds: float) -> None:
    """Hold the caller for the remaining minimum hold time before voicemail.

    No-op when already satisfied or the caller hung up. Plays the configured
    Teleprofi hold music when set, otherwise bounded silence — never an
    artificial ringback tone and never an AI voice. With hold music used as
    bridge ringback the caller is already on music for the window, so this
    padding is rarely reached.
    """
    if remaining_seconds <= 0 or handler.is_hung_up:
        return
    hold_music = (config.AI_ESCALATION_HOLD_MUSIC or "").strip()
    if hold_music:
        # Company hold music (not a tone). Played once to fill the remaining hold.
        waiting_audio = hold_music
    else:
        # No music configured → bounded silence (never an artificial ring tone).
        waiting_audio = f"silence_stream://{max(1, int(remaining_seconds * 1000))}"
    logger.info("Min-hold: %.0fs of waiting audio before voicemail", remaining_seconds)
    try:
        handler.execute("playback", waiting_audio, timeout=remaining_seconds + 10.0)
    except Exception:
        pass


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
    from voice import scheduler_dialogue

    started_at  = datetime.now(timezone.utc)
    uuid        = handler.get_uuid()
    caller      = handler.get_caller_id()
    turn_count  = 0
    history     = new_history()
    # Per-call appointment dialogue state (in-memory, never persisted, no cross-call
    # leakage). Drives the deterministic Scheduler flow inside _conversation_loop.
    appointment_state = scheduler_dialogue.new_state()

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
                dialogue_state=appointment_state,
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
            dialogue_state=appointment_state,
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
