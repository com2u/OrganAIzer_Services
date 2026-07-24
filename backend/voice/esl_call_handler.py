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

from utils.lang_tracking import (
    DE_CHARS as _DE_CHARS,
    DE_WORDS as _DE_WORDS,
    update_conversation_language as _update_conversation_language,
)
from voice import call_log, caller_resolution_dialogue, contacts as _contacts, config
from voice import concern_tracking
from voice import human_handoff_dialogue
from voice.audio_bridge import transcribe_file, speak_to_file
from voice.llm_bridge import get_response, new_history, OUTBOUND_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ── language detection ────────────────────────────────────────────────────────
# Marker sets live in utils.lang_tracking, shared with the browser voice mode
# (api/voice_mode.py) so both surfaces apply identical switching rules.


def _detect_lang(text: str) -> str:
    """Return 'de' or 'en' based on text content. Fast, no external library.

    Only used as the last-resort fallback in _speak_and_play when no explicit
    language is passed. The conversation language itself is owned by the CALLER
    and tracked via _caller_language — never re-derived from AI-generated text
    (a short LLM reply like "Okay." has no German markers and would otherwise
    flip the TTS voice to English mid-call).
    """
    if any(c in _DE_CHARS for c in text):
        return "de"
    words = set(text.lower().split())
    if words & _DE_WORDS:
        return "de"
    return "en"


def _caller_language(text: str, current: str) -> str:
    """Return the conversation language after hearing caller *text*.

    The conversation language belongs to the caller: it only changes when a
    sufficiently long caller utterance carries unambiguous markers of the
    other language. Anything short or ambiguous keeps *current* — so the AI
    speaks with one consistent voice for the whole call.

    Delegates to the shared tracker in utils.lang_tracking so the phone path
    and the browser voice mode can never drift apart.
    """
    return _update_conversation_language(text, current)


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

# Consent recording (escalation yes/no) and human-handoff final-note recording
# each get their own silence window — same 20 ms-frame conversion as the main
# loop above, but config-driven instead of hardcoded, so a short breath-pause
# no longer truncates either recording.
_CONSENT_MAX_SECS        = config.AI_RECORD_CONSENT_MAX_SECONDS
_CONSENT_SILENCE_TIMEOUT = max(
    1, int(round(config.AI_RECORD_CONSENT_SILENCE_SECONDS * 1000 / 20))
)
_CONSENT_TIMEOUT         = _CONSENT_MAX_SECS + float(config.AI_RECORD_INITIAL_TIMEOUT_SECONDS)

_FINAL_NOTE_MAX_SECS        = config.AI_RECORD_FINAL_NOTE_MAX_SECONDS
_FINAL_NOTE_SILENCE_TIMEOUT = max(
    1, int(round(config.AI_RECORD_FINAL_NOTE_SILENCE_SECONDS * 1000 / 20))
)
_FINAL_NOTE_TIMEOUT         = _FINAL_NOTE_MAX_SECS + float(config.AI_RECORD_INITIAL_TIMEOUT_SECONDS)


# ── garbage transcription detection ───────────────────────────────────────────
# Whisper occasionally returns single-character artefacts ("."), pure
# punctuation, or empty strings on noisy lines. Treat these as "did not catch
# that" so we never send them to the LLM. Real short utterances like "Ja" or
# "Nein" are 2+ chars and pass through normally.
_GARBAGE_TRANSCRIPTION_RE = re.compile(r"^[\s\.,;:!\?\-_'\"\(\)\[\]…·]+$")


# ── personalized greeting ─────────────────────────────────────────────────────
# Matches a leading generic salutation ("Hallo," / "Guten Tag," / "Guten
# Morgen," / "Guten Abend,") so it can be swapped for a personal one when the
# caller is a known contact.
_GREETING_SALUTATION_RE = re.compile(
    r"^(Hallo|Guten Tag|Guten Morgen|Guten Abend)[,]?\s*", re.IGNORECASE
)


def _personalize_greeting(greeting: str, caller_name: str) -> str:
    """Return *greeting* prefixed with a personal "Hallo <name>," salutation.

    Strips any leading generic salutation from *greeting* first so a known
    caller name never produces a doubled greeting. The previous
    implementation used `greeting.lstrip("Hallo, ")`, which strips a
    CHARACTER SET (H/a/l/o/,/space) from the left, not the literal prefix
    "Hallo, " — so the default AI_GREETING ("Guten Tag, Sie sprechen mit dem
    digitalen Assistenten von Teleprofi Fulda. ...") starts with "G", was
    left completely untouched, and every recognised caller heard
    "Hallo <Name>, Guten Tag, Sie sprechen mit ..." — a robotic double
    salutation no human receptionist would say.
    """
    rest = _GREETING_SALUTATION_RE.sub("", greeting, count=1)
    return f"Hallo {caller_name}, {rest}"


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


# ── escalation consent matching ───────────────────────────────────────────────
# Deterministic keyword match for the "Ja oder Nein" consent question asked
# before an escalation transfer. Deliberately conservative: only clearly
# unambiguous affirmatives are added as standalone words. "ordnung" is
# intentionally NOT a standalone yes-word — "nicht in Ordnung" is a common way
# to DECLINE, and a bare word-set match has no reliable way to tell that apart
# from an affirmative "in Ordnung", so that phrase is deliberately left out
# rather than risking a false positive on a consent gate.
_CONSENT_YES_WORDS = frozenset({
    "ja", "yes", "jo", "jep", "jup", "klar", "natürlich",
    "einverstanden", "ok", "okay", "gerne", "sure",
    "passt", "meinetwegen", "jawohl", "yep", "yeah", "fine", "alright",
})


def _is_consent_yes(consent_text: str) -> bool:
    """True when *consent_text* (already lower-cased) reads as an affirmative
    answer to the recording-consent question.

    Matches individual words against _CONSENT_YES_WORDS — so "Ja klar",
    "Alles klar", "Geht klar", "Passt schon", and "Sure thing" all match via
    the single shared word ("klar"/"passt"/"sure") already in the set — plus
    the fixed idiom "kein problem" ("kein" alone means "no"/"none" and must
    never be a standalone yes-word, but the idiom itself is unambiguously
    affirmative, unlike "ordnung" — see module note above).
    """
    words = set(w.strip(".,!?;:") for w in consent_text.split())
    if words & _CONSENT_YES_WORDS:
        return True
    return "kein problem" in consent_text


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
    # German trailing subordinating conjunctions — "ob"/"wenn" cannot
    # grammatically end a complete German sentence/answer, so they are safe:
    # a caller cut off right after either is always still mid-clause
    # ("Ich wollte fragen, ob…", "Falls Sie Zeit haben, wenn…").
    "ob", "wenn",
    # German trailing modal/aux verbs — a caller cut off after these is almost
    # always still forming the request ("Ich wollte…", "Ich möchte…").
    "wollte", "möchte", "hätte", "würde", "könnte", "sollte", "müsste",
    # English hesitation / conjunctions
    "uh", "uhm", "um", "er", "erm",
    "and", "or", "because", "but", "so", "well",
    # "if" cannot grammatically end a complete English sentence/answer either
    # — same reasoning as German "ob"/"wenn" above.
    "if",
})

_UNFINISHED_TRAILING_PHRASES = (
    "ich meine",
    "ich glaube also",
    "ich wollte",
    "ich möchte",
    "und dann",
    # "und zwar" ("...namely / specifically") is a very common German
    # incomplete-clause bridge — a caller is always about to add detail after
    # it, never ends a thought there.
    "und zwar",
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


# ── hesitation-streak → unclear-path bridge (one-time) ────────────────────────
# Fired exactly once, the moment `_unfinished_streak` first exceeds
# `_MAX_UNFINISHED_STREAK` and the loop falls through into the shared
# garbage/unclear-transcription handling. Without this, that fall-through's
# first message ("Ich höre Ihnen zu…") and second message ("...ich habe Sie
# nicht ganz verstanden, könnten Sie das wiederholen?") read as the AI having
# suddenly stopped following a caller who has, in fact, been coherently mid-
# explanation the entire time — just slowly. This bridges the transition by
# naming what is actually happening (still gathering their thoughts) and
# asking for a short summary, instead of implying the audio was unclear.
_HESITATION_STREAK_BRIDGE: dict[str, str] = {
    "de": (
        "Lassen Sie sich Zeit — sagen Sie mir am besten kurz in ein, zwei "
        "Sätzen, worum es geht."
    ),
    "en": (
        "Take your time — if it's easier, just tell me in a sentence or two "
        "what this is about."
    ),
}


def _hesitation_streak_bridge(lang: str) -> str:
    """Return the one-time bridging message for *lang* (falls back to German)."""
    return _HESITATION_STREAK_BRIDGE.get(lang, _HESITATION_STREAK_BRIDGE["de"])


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
    identity_state: Optional[dict] = None,
    handoff_state: Optional[dict] = None,
    concern_state: Optional[list] = None,
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
    # Conversation language — owned by the CALLER, not the AI. Starts at
    # initial_lang (from call context) and only changes when a caller utterance
    # carries strong evidence of a language switch (see _caller_language).
    # It is never derived from AI-generated replies, so the TTS voice stays
    # consistent for the whole call.
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
            # The old wording literally named the internal call-duration limit
            # to the caller — no human receptionist would say that out loud.
            # Close the way a person naturally would, and (like every other
            # farewell in this loop) speak it in the caller's own conversation
            # language instead of always German.
            max_duration_farewell = (
                "I need to wrap up the call now — thank you for calling. Goodbye!"
                if conv_lang == "en"
                else "Ich muss das Gespräch jetzt leider beenden — vielen Dank für Ihren Anruf. Auf Wiederhören!"
            )
            _speak_and_play(handler, max_duration_farewell, lang=conv_lang)
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
            "unfinished": False, "stt_failed": False, "tts_failed": False,
        }
        _proc_done = threading.Event()

        def _process_turn(
            _rec=str(rec_path),
            _cn=caller_name,
            _sp=system_prompt,
        ) -> None:
            t = ""
            if Path(_rec).exists():
                # Pass the current conversation language so Whisper doesn't
                # misidentify German phone audio as English (common on noisy lines).
                try:
                    t, _ = transcribe_file(_rec, lang=conv_lang)
                except Exception as exc:
                    # faster-whisper OOM / model load failure / corrupt WAV, etc.
                    # Must not propagate: this runs on a background daemon
                    # thread with no caller-side exception handler, so an
                    # unhandled error here would be printed only via Python's
                    # default threading.excepthook (never through `logger`,
                    # never in structured logs) and — critically — would skip
                    # _proc_done.set() below, stalling the main loop for the
                    # full 20 s wait(timeout=20.0) before it even notices.
                    logger.error(
                        "STT failure on upcoming turn %d (file=%s): %s: %s",
                        turn_count_ref[0] + 1, _rec, type(exc).__name__, exc,
                        exc_info=True,
                    )
                    _proc["stt_failed"] = True
            _cleanup(_rec)
            if not t:
                _proc_done.set()
                return
            # Skip the LLM call for garbage transcriptions — the main loop
            # handles them with a one-time polite "could you repeat?" prompt.
            # _proc["lang"] stays at conv_lang: noise carries no language signal.
            if _is_garbage_transcription(t):
                _proc["text"] = t
                _proc_done.set()
                return
            # Mid-sentence pause ("…äh", "…und, also,") — skip the LLM and let
            # the main loop offer a gentle continuation prompt instead.
            if _is_likely_unfinished_utterance(t):
                _proc["text"] = t
                _proc["unfinished"] = True
                _proc_done.set()
                return
            # ── sanitize BEFORE anything below can append this utterance to
            # history / send it to the LLM / archive it in a transcript /
            # hand it to escalation. Any phone-like number the caller just
            # spoke is replaced with a neutral placeholder in `sanitized_t`;
            # the raw value is preserved ONLY in `identity_state` (inbound
            # calls) — never in text. Outbound calls have no identity_state
            # (see handle_esl_call) but still get the same redaction via
            # redact_phone_like() directly, since a callback number spoken
            # mid-call must not leak either way. This MUST run before the
            # scheduler-dialogue branch below, which also writes to history.
            sanitized_t = t
            if identity_state is not None:
                try:
                    sanitized_t = caller_resolution_dialogue.process_utterance(identity_state, t)
                except Exception as exc:  # never let identification break a live call
                    logger.error("Caller resolution error: %s", exc, exc_info=True)
                    sanitized_t = t
            else:
                try:
                    sanitized_t, _ = caller_resolution_dialogue.redact_phone_like(t)
                except Exception as exc:
                    logger.error("Utterance sanitization error: %s", exc, exc_info=True)
                    sanitized_t = t

            # ── human handoff (deterministic; "caller wants a person" flow) ──────
            # voice/human_handoff_dialogue.py tracks whether the caller has asked
            # for a person, whether the reason is known, and offers AI help at
            # most once before a deterministic escalation. Runs on the RAW
            # utterance `t` (not sanitized_t) so it can capture any callback
            # number the caller states into STATE ONLY — never into text/history
            # — via the same redact_phone_like() caller_resolution_dialogue uses.
            # Checked BEFORE the scheduler block: if the caller insists on a
            # person mid-flow, handoff takes priority over appointment booking.
            if handoff_state is not None:
                try:
                    human_handoff_dialogue.observe_turn(handoff_state, t)
                except Exception as exc:  # never let handoff tracking break a live call
                    logger.error("Human handoff dialogue error: %s", exc, exc_info=True)
                if human_handoff_dialogue.should_escalate_now(handoff_state):
                    # Deterministic handoff — never depends on the LLM choosing to
                    # emit ESCALATE: itself once the caller has insisted or an
                    # urgent/emergency signal was seen.
                    human_handoff_dialogue.mark_handoff_confirmed(handoff_state)
                    reason = human_handoff_dialogue.escalation_reason_text(handoff_state)
                    _proc["text"] = sanitized_t
                    _proc["reply"] = f"ESCALATE: {reason}"
                    _proc["lang"] = conv_lang
                    history.append({"role": "user", "content": sanitized_t})
                    history.append({"role": "assistant", "content": _proc["reply"]})
                    _proc_done.set()
                    return

            # ── multi-intent concern tracking (deterministic; see
            # voice/concern_tracking.py) ──────────────────────────────────────
            # Runs on every turn that reaches this point (even ones that will
            # short-circuit into scheduling below) so a second concern raised
            # in the same breath as an appointment request is still tracked.
            # Explicit-marker detection only ("und außerdem", "zusätzlich",
            # ...) — never general sentence-splitting. `_new_concern` is used
            # below, after the LLM reply is computed, to prepend a brief
            # acknowledgement — never to change WHAT the LLM answers.
            _new_concern = None
            if concern_state is not None:
                try:
                    _new_concern = concern_tracking.observe_turn(concern_state, t)
                except Exception as exc:  # never let concern tracking break a live call
                    logger.error("Concern tracking error: %s", exc, exc_info=True)

            # ── appointment scheduling (deterministic; slots come from Scheduler) ──
            # A per-call state machine handles appointment intent WITHOUT the LLM
            # inventing availability. It returns None when the turn is not part of
            # an appointment flow, so every other call behaves exactly as before.
            if dialogue_state is not None:
                try:
                    _sched = scheduler_dialogue.handle_turn(
                        dialogue_state, sanitized_t,
                        call_id=uuid, phone=caller, caller_name=_cn,
                    )
                except Exception as exc:  # never let scheduling break a live call
                    logger.error("Scheduler dialogue error: %s", exc, exc_info=True)
                    _sched = None
                if _sched is not None:
                    _proc["text"] = sanitized_t
                    _proc["reply"] = _sched.reply
                    _proc["lang"] = "de"
                    # Keep the LLM history coherent for turns after the flow ends.
                    history.append({"role": "user", "content": sanitized_t})
                    history.append({"role": "assistant", "content": _sched.reply})
                    if not _sched.reply.upper().startswith("ESCALATE:"):
                        try:
                            _proc["wav"] = speak_to_file(_sched.reply, lang="de")
                        except Exception as exc:
                            # edge-tts network hiccup / ffmpeg missing, etc. The
                            # scheduler reply text is already in history — only
                            # the audio failed. Must still set _proc_done below.
                            logger.error(
                                "TTS failure on upcoming turn %d (scheduler reply, lang=de): %s: %s",
                                turn_count_ref[0] + 1, type(exc).__name__, exc,
                                exc_info=True,
                            )
                            _proc["wav"] = ""
                            _proc["tts_failed"] = True
                    _proc_done.set()
                    return
            _proc["text"] = sanitized_t
            # The conversation language belongs to the CALLER. It only changes
            # when this utterance carries strong evidence of a language switch;
            # short/ambiguous utterances keep the current language. AI replies
            # are never used for detection — a short LLM acknowledgement like
            # "Okay." must not flip the TTS voice mid-call. Language detection
            # uses the raw transcription (redaction never changes language cues).
            _proc["lang"] = _caller_language(t, conv_lang)
            extra = _drain_whisper_queue()
            # ── caller/customer identification (deterministic; the LLM only
            # phrases whatever question this decides is needed). Raw phone
            # numbers never leave this block — build_prompt_extra only
            # returns customer/location display labels. State was already
            # updated by process_utterance() above; only the prompt fragment
            # is computed here. ──
            identity_extra = None
            if identity_state is not None:
                try:
                    identity_extra = caller_resolution_dialogue.build_prompt_extra(identity_state)
                except Exception as exc:  # never let identification break a live call
                    logger.error("Caller resolution error: %s", exc, exc_info=True)
            # ── human handoff stage-1 wording (ASK_REASON / OFFER_HELP only —
            # ESCALATE_NOW already returned early above and is never phrased
            # by the LLM). State was already updated by observe_turn() above.
            handoff_extra = None
            if handoff_state is not None:
                try:
                    handoff_extra = human_handoff_dialogue.build_prompt_extra(handoff_state)
                except Exception as exc:  # never let handoff tracking break a live call
                    logger.error("Human handoff dialogue error: %s", exc, exc_info=True)
            # ── open secondary concerns reminder (see voice/concern_tracking.py) ──
            concern_extra = None
            if concern_state is not None:
                try:
                    concern_extra = concern_tracking.build_prompt_extra(concern_state)
                except Exception as exc:  # never let concern tracking break a live call
                    logger.error("Concern tracking error: %s", exc, exc_info=True)
            combined_extra_parts = [
                p for p in (extra, identity_extra, handoff_extra, concern_extra) if p
            ]
            combined_extra = "\n".join(combined_extra_parts) if combined_extra_parts else None
            try:
                r = asyncio.run(
                    get_response(
                        history, sanitized_t,
                        caller_name=_cn,
                        system_prompt=_sp,
                        system_extra=combined_extra,
                    )
                )
            except Exception as exc:
                logger.error("LLM error: %s", exc)
                r = (
                    "Es tut mir leid, es gab ein technisches Problem. Bitte versuchen Sie es erneut."
                    if _proc["lang"] == "de"
                    else "I'm sorry, there was a technical issue. Please try again."
                )
            # ── guard: ASK_REASON/OFFER_HELP are mandatory (stage 1, rules
            # #2-#3) — the LLM can still ignore the instruction above and
            # reply with ESCALATE anyway (e.g. via an unrelated "annoyed
            # caller" trigger it decides on its own). Override with a
            # deterministic fallback rather than letting that premature
            # escalation through, and fix up history to match what is
            # actually said (get_response() already appended the raw reply).
            if handoff_state is not None:
                try:
                    fallback = human_handoff_dialogue.fallback_reply_if_llm_escalated_prematurely(handoff_state, r)
                except Exception as exc:
                    logger.error("Human handoff dialogue error: %s", exc, exc_info=True)
                    fallback = None
                if fallback:
                    logger.warning(
                        "LLM emitted ESCALATE during mandatory handoff step (action=%s) — "
                        "overriding with deterministic fallback reply.",
                        handoff_state.get("action"),
                    )
                    r = fallback
                    if history and history[-1].get("role") == "assistant":
                        history[-1]["content"] = r
            # ── multi-intent acknowledgement (deterministic, see
            # voice/concern_tracking.py) ──────────────────────────────────────
            # A second concern was just detected via an explicit marker this
            # turn — prepend a short, fixed acknowledgement so the caller
            # hears that it was heard and will not be dropped, without
            # quoting their own words back to them (that doesn't compose
            # grammatically from an arbitrary fragment) and without an extra
            # TTS call — folded into the same reply that is about to be
            # spoken and stored in history.
            if _new_concern is not None and not r.upper().startswith("ESCALATE:"):
                open_count = len(concern_tracking.open_concerns(concern_state))
                ack = concern_tracking.acknowledgement_for_new_concern(open_count, lang=_proc["lang"])
                r = f"{ack} {r}"
                if history and history[-1].get("role") == "assistant":
                    history[-1]["content"] = r
            _proc["reply"] = r
            # Pre-generate TTS in the caller's conversation language, unless the
            # LLM triggered a special action (ESCALATE replies are never spoken
            # directly to the caller).
            if not r.upper().startswith("ESCALATE:"):
                try:
                    _proc["wav"] = speak_to_file(r, lang=_proc["lang"])
                except Exception as exc:
                    # edge-tts network hiccup / ffmpeg missing or broken, etc.
                    # `r` (the LLM reply text) already exists and is already in
                    # history via get_response() — only the audio failed. The
                    # main loop below recovers with a spoken apology instead of
                    # leaving the caller in silence. Must still set _proc_done.
                    logger.error(
                        "TTS failure on upcoming turn %d (lang=%s, reply_len=%d): %s: %s",
                        turn_count_ref[0] + 1, _proc["lang"], len(r),
                        type(exc).__name__, exc, exc_info=True,
                    )
                    _proc["wav"] = ""
                    _proc["tts_failed"] = True
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
            if _proc.get("stt_failed"):
                # transcribe_file() raised — this is an infrastructure failure
                # (Whisper OOM/model load, corrupt WAV, etc.), not caller
                # silence. Saying nothing here would leave the caller wondering
                # why the AI suddenly went quiet, only to be told "still there?"
                # two turns later for a reason unrelated to them. Speak an
                # honest, short apology immediately, then fall through to the
                # existing empty-turn counter/farewell logic below so repeated
                # failures still end the call gracefully instead of looping
                # forever. This _speak_and_play() call runs on the MAIN thread
                # (unlike the background _process_turn thread, which never
                # touches `handler` itself), so it cannot race with any other
                # handler.execute() call; wrapped defensively in case TTS is
                # also broken, so an apology failure can't crash the call loop.
                logger.warning(
                    "STT failure surfaced to caller (turn %d, empty_turns=%d) — "
                    "speaking apology instead of silent retry.",
                    turn_count_ref[0] + 1, _empty_turns + 1,
                )
                stt_apology = (
                    "Sorry, I had a brief technical problem. Could you please repeat that?"
                    if conv_lang == "en"
                    else "Entschuldigung, ich hatte kurz ein technisches Problem. "
                         "Könnten Sie das bitte wiederholen?"
                )
                try:
                    _speak_and_play(handler, stt_apology, lang=conv_lang)
                except Exception as exc:
                    logger.error(
                        "Apology playback after STT failure also failed (turn %d): %s: %s",
                        turn_count_ref[0] + 1, type(exc).__name__, exc, exc_info=True,
                    )
                if handler.is_hung_up:
                    break
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
                # This is the SILENCE path (no speech captured at all), not the
                # unclear-transcription path below — the German wording used to
                # say "Ich konnte Sie leider nicht verstehen" ("I couldn't
                # understand you"), which claims the caller said something
                # unclear when in fact nothing was heard at all. The English
                # variant already said the honest thing ("I haven't heard
                # anything for a while"); align the German wording with it so
                # both languages describe the same real situation.
                farewell = (
                    "I haven't heard anything for a while. I'll end the call now. Goodbye!"
                    if conv_lang == "en"
                    else "Ich habe leider länger nichts von Ihnen gehört. Ich beende das Gespräch. Auf Wiederhören!"
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
            # The turn where the unfinished-streak cap was JUST exceeded
            # (_unfinished_streak == _MAX_UNFINISHED_STREAK + 1, i.e. the first
            # time this hesitation run falls through without a `continue`
            # above) is not the same situation as noisy/unintelligible audio —
            # the caller has been coherently trying to say something the whole
            # time, just slowly. Dropping straight into "I didn't catch that"
            # here would wrongly read as the AI suddenly giving up on
            # understanding them. Bridge once with wording that acknowledges
            # the hesitation instead, then merge into the shared unclear-turn
            # counter/farewell bookkeeping below as normal.
            if _proc.get("unfinished") and _unfinished_streak == _MAX_UNFINISHED_STREAK + 1:
                _speak_and_play(handler, _hesitation_streak_bridge(conv_lang), lang=conv_lang)
            elif _unclear_count == 1:
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

            # Idempotent — already True when this ESCALATE: line came from the
            # deterministic human-handoff short-circuit above; sets it for the
            # LLM-triggered path too, so should_ask_final_note() etc. below see
            # a confirmed handoff either way.
            if handoff_state is not None:
                human_handoff_dialogue.mark_handoff_confirmed(handoff_state)

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
                    f"{_CONSENT_MAX_SECS} "
                    f"{_RECORD_SILENCE_THRESH} "
                    f"{_CONSENT_SILENCE_TIMEOUT}"
                )
                handler.execute("record", consent_arg, timeout=_CONSENT_TIMEOUT)
                if consent_path.exists():
                    consent_text, _ = transcribe_file(str(consent_path), lang=conv_lang)
                    consent_text = consent_text.lower()
                    _cleanup(str(consent_path))
                    logger.info("Consent response: %r", consent_text)
                    recording_consent = _is_consent_yes(consent_text)

            logger.info("Recording consent: %s", recording_consent)

            # ── Stage 2 — final pre-transfer note (human_handoff_dialogue) ─────
            # Deliberately AFTER the recording-consent step above — consent must
            # be captured before we record the caller's final pre-transfer
            # answer. should_ask_final_note() skips this for an emergency,
            # already-collected information, an already-asked note, or an
            # explicit "no more questions" from the caller. Silence, refusal, or
            # a failed transcription must never block the transfer —
            # record_final_note_response() always marks the note collected.
            if handoff_state is not None and human_handoff_dialogue.should_ask_final_note(handoff_state):
                human_handoff_dialogue.mark_final_note_asked(handoff_state)
                _speak_and_play(handler, human_handoff_dialogue.final_note_question(), lang="de")
                final_note_text = None
                if not handler.is_hung_up:
                    note_path = _audio_dir() / f"{uuid}_final_note.wav"
                    note_arg = (
                        f"{_fs_path(note_path)} "
                        f"{_FINAL_NOTE_MAX_SECS} "
                        f"{_RECORD_SILENCE_THRESH} "
                        f"{_FINAL_NOTE_SILENCE_TIMEOUT}"
                    )
                    handler.execute("record", note_arg, timeout=_FINAL_NOTE_TIMEOUT)
                    if note_path.exists():
                        final_note_text, _ = transcribe_file(str(note_path), lang=conv_lang)
                        _cleanup(str(note_path))
                        logger.info("Final pre-transfer note: %r", final_note_text)
                human_handoff_dialogue.record_final_note_response(handoff_state, final_note_text)

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
            # Other concerns the caller raised earlier in this same call that
            # are still open (see voice/concern_tracking.py) — captured here,
            # BEFORE marking them handed_off below, so the escalation email
            # never silently drops a secondary topic.
            _open_concern_texts = (
                [c["text"] for c in concern_tracking.open_concerns(concern_state)]
                if concern_state is not None else []
            )
            # Single structured handoff_context dict (never several loose kwargs)
            # — see voice/human_handoff_dialogue.build_handoff_context(). None
            # for calls that never had a handoff_state (outbound calls today).
            handoff_context = (
                human_handoff_dialogue.build_handoff_context(
                    handoff_state, concerns=_open_concern_texts
                )
                if handoff_state is not None else None
            )
            if concern_state is not None:
                concern_tracking.mark_all_handed_off(concern_state)
            esc_result = handle_escalation(
                caller, caller_name, history, reason, started_at,
                call_uuid=uuid, esl_handler=handler,
                recording_consent=recording_consent,
                recording_path=rec_file,
                handoff_context=handoff_context,
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
                _speak_and_play(handler, farewell, lang=conv_lang)
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
        elif _proc.get("tts_failed"):
            # speak_to_file() raised in the background thread — the LLM reply
            # text exists (and is already in `history`) but could never be
            # synthesised to audio. Leaving `_proc["wav"]` empty is already
            # safe (the block above just does nothing), but silently skipping
            # straight to the next recording leaves the caller in the same
            # confusing dead-air situation the STT-failure path above avoids.
            # Attempt one apology playback for symmetry with the STT recovery;
            # if TTS is broken globally this may fail too, so it is wrapped —
            # a second failure here must degrade to a graceful continue, not
            # a crash of the whole call loop.
            logger.warning(
                "TTS failure surfaced to caller (turn %d) — attempting apology playback.",
                turn_count_ref[0],
            )
            tts_apology = (
                "Sorry, I had a brief technical problem there. Could you say that again?"
                if conv_lang == "en"
                else "Entschuldigung, ich hatte kurz ein technisches Problem. "
                     "Könnten Sie das bitte noch einmal sagen?"
            )
            try:
                _speak_and_play(handler, tts_apology, lang=conv_lang)
            except Exception as exc:
                logger.error(
                    "Apology playback after TTS failure also failed (turn %d): %s: %s",
                    turn_count_ref[0], type(exc).__name__, exc, exc_info=True,
                )

        # ── natural end after goodbye ─────────────────────────────────────────
        # The AI just said its farewell — end the call instead of recording on
        # and asking "Sind Sie noch da?" after having said goodbye. Skipped
        # when TTS just failed for this turn: the caller never actually heard
        # the farewell (only the apology above), so ending the call now would
        # look like an abrupt hangup rather than a natural goodbye.
        if _is_farewell_reply(reply) and not _proc.get("tts_failed"):
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
    # Per-call tracker for multiple caller concerns mentioned in one call
    # (in-memory, never persisted, no cross-call leakage). See
    # voice/concern_tracking.py. Present for both inbound and outbound calls,
    # same as appointment_state.
    concern_state = concern_tracking.new_state()
    # Per-call caller/customer identification state (in-memory, never persisted).
    # Populated below for inbound calls only — outbound calls already know who
    # they dialled via outbound_ctx. See voice/caller_resolution_dialogue.py.
    identity_state: Optional[dict] = None
    # Per-call human-handoff dialogue state (in-memory, never persisted).
    # Populated below for inbound calls only, same scope as identity_state —
    # see voice/human_handoff_dialogue.py.
    handoff_state: Optional[dict] = None

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

        # Caller/customer resolution — separate from the contacts.py person
        # lookup above (that resolves a display name; this resolves a
        # customer/location record). See voice/caller_resolution_dialogue.py.
        identity_state = caller_resolution_dialogue.new_state()
        caller_resolution_dialogue.init_from_call(identity_state, caller)
        handoff_state = human_handoff_dialogue.new_state()

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
                concern_state=concern_state,
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
            greeting = _personalize_greeting(greeting, caller_name)
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
            initial_lang=config.AI_LANGUAGE,
            dialogue_state=appointment_state,
            identity_state=identity_state,
            handoff_state=handoff_state,
            concern_state=concern_state,
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
        # Concerns still "open" at this point were never resolved AND never
        # handed off (escalation marks them handed_off — see the escalation
        # block above) — surfaces a silently-dropped secondary concern even
        # for calls that never escalated.
        _open_concern_texts = [c["text"] for c in concern_tracking.open_concerns(concern_state)]
        call_log.record(
            caller=caller,
            caller_name=caller_name,
            direction="inbound",
            started_at=started_at,
            ended_at=ended_at,
            turn_count=turn_count,
            transcript=history,
            unresolved_concerns=_open_concern_texts,
        )
        logger.info(
            "ESL call ended: %s  duration=%ds  turns=%d",
            display,
            int((ended_at - started_at).total_seconds()),
            turn_count,
        )
