"""
human_handoff_dialogue.py — deterministic per-call "caller wants a person"
bridge for the phone AI.

Plays the same narrow-bridge role as voice/caller_resolution_dialogue.py and
voice/scheduler_dialogue.py: a per-call ``state`` dict (created fresh via
:func:`new_state`, no cross-call leakage) that deterministically decides what
should happen when a caller asks to speak with a human, in two stages:

STAGE 1 — human-request understanding (:func:`observe_turn` / :func:`build_prompt_extra`)
  1. Whether the reason for wanting a person is already known (from this turn
     or an earlier one in the same call).
  2. If unknown, instruct the LLM to ask naturally what it concerns.
  3. If known and the situation allows it, instruct the LLM to offer to help
     itself — exactly once.
  4. If the caller repeats the request or insists, stop offering and move to
     a deterministic escalation (:func:`should_escalate_now`).
  5. Emergencies and time-critical situations bypass all of the above.

STAGE 2 — transfer preparation (:func:`should_ask_final_note` / :func:`record_final_note_response`)
  Once a handoff is confirmed, ask at most once whether the colleague should
  know anything else, skipping the question when it would be redundant, would
  delay an emergency, or the caller has already said not to ask more. Silence,
  refusal, or a failed transcription must never block the transfer.

Safety design (mirrors the rest of the voice stack):
  - The LLM never decides WHEN to ask/offer/escalate for this trigger — this
    module does. build_prompt_extra() only asks llm_bridge for the wording.
  - The escalation category (EMERGENCY / TIME_CRITICAL / COMPLAINT /
    STANDARD_HUMAN_REQUEST) is computed here from deterministic keyword and
    conversation-state signals, independent of whatever free-text reason the
    LLM eventually writes after "ESCALATE:". Once a caller has insisted or an
    urgent/emergency signal is seen, the module returns "ESCALATE_NOW" so the
    call handler escalates deterministically — it never waits for or depends
    on the LLM choosing to emit ESCALATE: on its own for this trigger.
  - The category only ever moves UP in priority
    (STANDARD_HUMAN_REQUEST < COMPLAINT < TIME_CRITICAL < EMERGENCY) as new
    turns arrive; it is recomputed every turn and never downgraded.
  - Any callback-style number spoken during this dialogue is captured via the
    same redact_phone_like() used by caller_resolution_dialogue: the raw
    value goes ONLY into state["callback_number_current_call"] (current-call
    only, never persisted, never written to customers.jsonl or
    callback_numbers.jsonl), and any free text this module stores
    (reason_text, final_note_text) is sanitized through redact_phone_like()
    before being kept, so it is always safe to later feed into an LLM prompt
    or an after-call summary. Callers of this module MUST still use their own
    already-sanitized text (e.g. voice/caller_resolution_dialogue's) for
    conversation history — this module never returns history text itself.
"""
from __future__ import annotations

import re
from typing import Optional

from voice.caller_resolution_dialogue import redact_phone_like
from voice.llm_bridge import build_human_handoff_instruction, human_handoff_fallback_reply

# Priority order for escalation category — higher rank wins and a category can
# only move up, never down, as new turns/signals arrive.
_CATEGORY_RANK = {
    None: 0,
    "STANDARD_HUMAN_REQUEST": 1,
    "COMPLAINT": 2,
    "TIME_CRITICAL": 3,
    "EMERGENCY": 4,
}

_FINAL_NOTE_QUESTION = "Gibt es noch etwas, das der Kollege oder die Kollegin wissen sollte?"


def new_state() -> dict:
    """Create a fresh per-call human-handoff dialogue state."""
    return {
        "human_requested": False,
        "reason_known": False,
        "reason_text": None,
        "reason_asked": False,
        "ai_help_offered": False,
        "caller_insisted": False,
        "handoff_confirmed": False,
        "final_note_asked": False,
        "final_note_already_collected": False,
        "final_note_text": None,
        # Current-call-only. Never persisted; never written to customers.jsonl
        # or callback_numbers.jsonl; never fed into an LLM prompt raw.
        "callback_number_current_call": None,
        "category": None,
        "no_more_questions": False,
        # Per-turn output of observe_turn(): None | "ASK_REASON" | "OFFER_HELP"
        # | "ESCALATE_NOW".
        "action": None,
    }


# ── Stage 1 — human-request understanding ─────────────────────────────────────

def observe_turn(state: dict, utterance: str) -> None:
    """
    Deterministically update the handoff state from one caller utterance and
    compute this turn's action (state["action"]). Call with the RAW
    transcribed utterance (not a text already stripped of numbers) so any
    callback number spoken can be captured — this function never returns
    text, so it never becomes a second source of truth for what enters
    history; that stays owned by the caller's own sanitizer
    (voice/caller_resolution_dialogue.process_utterance).
    """
    if not utterance:
        state["action"] = None
        return

    _, raw_number = redact_phone_like(utterance)
    if raw_number:
        state["callback_number_current_call"] = raw_number

    text = utterance.strip().lower()

    if _contains(text, _EMERGENCY_KEYWORDS):
        _upgrade_category(state, "EMERGENCY")
    elif _contains(text, _TIME_CRITICAL_KEYWORDS):
        _upgrade_category(state, "TIME_CRITICAL")
    elif _contains(text, _COMPLAINT_KEYWORDS):
        _upgrade_category(state, "COMPLAINT")

    if _contains(text, _NO_MORE_QUESTIONS_KEYWORDS):
        state["no_more_questions"] = True

    # The reason can become known from ANY turn, before or after the caller
    # actually asks for a person — "already known from conversation state/
    # history" (stage 1, rule #1).
    if not state["reason_known"]:
        reason = _extract_reason(text, utterance, state["reason_asked"])
        if reason:
            sanitized_reason, _ = redact_phone_like(reason)
            cleaned = sanitized_reason.strip()
            if cleaned:
                state["reason_text"] = cleaned
                state["reason_known"] = True

    if _is_human_request(text):
        if state["human_requested"]:
            # A repeated request — at any later turn, not only immediately
            # after an offer — counts as insistence (stage 1, rule #4).
            state["caller_insisted"] = True
        else:
            state["human_requested"] = True
        if state["category"] is None:
            _upgrade_category(state, "STANDARD_HUMAN_REQUEST")

    state["action"] = _advance_stage1(state)


def _advance_stage1(state: dict) -> Optional[str]:
    if not state["human_requested"] or state["handoff_confirmed"]:
        return None

    # Urgency/emergency bypasses the rest of stage 1 unconditionally, on
    # whichever turn it is first (or newly) detected (stage 1, rule #5).
    if state["category"] in ("EMERGENCY", "TIME_CRITICAL"):
        return "ESCALATE_NOW"

    if state["no_more_questions"] or state["caller_insisted"]:
        return "ESCALATE_NOW"

    if not state["reason_known"]:
        state["reason_asked"] = True
        return "ASK_REASON"

    # Complaint callers get one clarification if needed (above) but never the
    # self-service offer — go straight to preparing the handoff.
    if state["category"] == "COMPLAINT":
        return "ESCALATE_NOW"

    if not state["ai_help_offered"]:
        state["ai_help_offered"] = True
        return "OFFER_HELP"

    # Help was already offered once and the caller neither insisted nor
    # explicitly refused — the caller's earlier "I want a person" is still
    # sitting in conversation history, so an empty instruction here is not
    # neutral: without a reminder the LLM tends to fall back on its own
    # judgement and re-escalate for that original request even though the
    # caller is actively being helped. CONTINUE_HELPING keeps telling it
    # that request is being handled until the caller insists again.
    return "CONTINUE_HELPING"


def should_escalate_now(state: dict) -> bool:
    """True when the call handler must deterministically escalate THIS turn,
    without depending on (or waiting for) the LLM to emit ESCALATE: itself."""
    return state.get("action") == "ESCALATE_NOW"


def mark_handoff_confirmed(state: dict) -> None:
    """Call once the call handler has committed to escalating — idempotent,
    safe to call from both the deterministic and LLM-triggered ESCALATE paths."""
    state["handoff_confirmed"] = True
    state["action"] = None


def escalation_reason_text(state: dict) -> str:
    """Short human-readable reason for the deterministic ESCALATE_NOW path —
    mirrors the "<reason> — <key detail>" shape of an LLM-emitted ESCALATE line."""
    category = state.get("category") or "STANDARD_HUMAN_REQUEST"
    detail = state.get("reason_text") or "Anrufer möchte mit einer Person sprechen"
    return f"{category} — {detail}"


def build_prompt_extra(state: dict) -> Optional[str]:
    """
    Return the system_extra fragment for this turn's stage-1 action, or None
    when no extra instruction applies (nothing to ask/offer, or the action is
    ESCALATE_NOW — handled deterministically, never phrased by the LLM).
    Delegates wording to llm_bridge.build_human_handoff_instruction — this
    module only decides WHICH action applies.
    """
    return build_human_handoff_instruction(state.get("action"), state.get("reason_text"))


def fallback_reply_if_llm_escalated_prematurely(state: dict, llm_reply: str) -> Optional[str]:
    """
    Guard for ASK_REASON/OFFER_HELP: those two steps are mandatory (stage 1,
    rules #2-#3) and must never be skipped, but the LLM can still ignore the
    system_extra instruction and reply with ESCALATE anyway (e.g. via an
    unrelated "annoyed caller" trigger it decides on its own). Returns a
    deterministic fallback line to use INSTEAD of llm_reply when that
    happens, or None when llm_reply should be used as-is (the normal,
    compliant case, or any action other than ASK_REASON/OFFER_HELP).
    """
    action = state.get("action")
    if action not in ("ASK_REASON", "OFFER_HELP"):
        return None
    if not llm_reply or not llm_reply.upper().startswith("ESCALATE:"):
        return None
    return human_handoff_fallback_reply(action)


# ── Stage 2 — transfer preparation ────────────────────────────────────────────

def should_ask_final_note(state: dict) -> bool:
    """
    Whether to ask the "anything else?" question. Skips it for: an emergency
    (never delay one), information already collected some other way, having
    already asked this call, or an explicit caller request for no more
    questions. Deliberately independent of reason_known — a known escalation
    reason is not the same information as a final note for the colleague.
    """
    if state.get("category") == "EMERGENCY":
        return False
    if state.get("no_more_questions"):
        return False
    if state.get("final_note_already_collected"):
        return False
    if state.get("final_note_asked"):
        return False
    return True


def final_note_question() -> str:
    return _FINAL_NOTE_QUESTION


def mark_final_note_asked(state: dict) -> None:
    state["final_note_asked"] = True


def record_final_note_response(state: dict, utterance: Optional[str]) -> None:
    """
    Record the caller's answer to the final-note question, if any. Silence,
    a refusal, or a failed transcription (utterance falsy) are all treated as
    "nothing else" and must NEVER block the transfer — this function never
    raises and always marks the note as collected either way.
    """
    state["final_note_already_collected"] = True
    if not utterance:
        return
    sanitized, raw_number = redact_phone_like(utterance)
    if raw_number:
        state["callback_number_current_call"] = raw_number
    text = sanitized.strip().lower()
    if not text:
        return
    if _contains(text, _NO_MORE_QUESTIONS_KEYWORDS) or _contains(text, _FINAL_NOTE_NEGATIVE_KEYWORDS):
        return
    state["final_note_text"] = sanitized.strip()


def build_handoff_context(state: dict) -> dict:
    """
    Single structured summary of this call's handoff dialogue, meant to be
    passed as the one ``handoff_context`` kwarg to
    voice.escalation.handle_escalation() rather than several independent
    kwargs. callback_number_current_call is the raw number (current-call-only
    metadata) — callers of THIS function must add it to the escalation email/
    metadata directly and must never forward it into an LLM prompt.
    """
    return {
        "human_requested": state.get("human_requested", False),
        "category": state.get("category"),
        "reason_known": state.get("reason_known", False),
        "reason_text": state.get("reason_text"),
        "ai_help_offered": state.get("ai_help_offered", False),
        "caller_insisted": state.get("caller_insisted", False),
        "handoff_confirmed": state.get("handoff_confirmed", False),
        "final_note_asked": state.get("final_note_asked", False),
        "final_note_text": state.get("final_note_text"),
        "callback_number_current_call": state.get("callback_number_current_call"),
    }


# ── category helpers ──────────────────────────────────────────────────────────

def _upgrade_category(state: dict, category: str) -> None:
    if _CATEGORY_RANK.get(category, 0) > _CATEGORY_RANK.get(state.get("category"), 0):
        state["category"] = category


# ── keyword classification (German-first, mirrors caller_resolution_dialogue.py) ─

def _contains(text: str, needles) -> bool:
    return any(n in text for n in needles)


_HUMAN_REQUEST_KEYWORDS = (
    "mit jemandem sprechen", "mit einer person sprechen", "mit einem mitarbeiter",
    "mit einer mitarbeiterin", "einen mitarbeiter sprechen", "eine mitarbeiterin sprechen",
    "verbinden sie mich", "können sie mich verbinden", "koennen sie mich verbinden",
    "zu einem mitarbeiter", "kollegen sprechen", "kollegin sprechen",
    "echten menschen sprechen", "echte person sprechen", "mit einem menschen sprechen",
    "mit einem menschen reden", "geben sie mich weiter", "stellen sie mich durch",
    # Negative-form phrasing — the caller frames the request as a refusal of
    # the AI rather than a positive ask for a person; must still register.
    "nicht mit einer maschine", "nicht mit einem bot", "nicht mit der ki",
    "nicht mit einem computer sprechen", "kein interesse an einem bot",
    "ich rede nicht mit einem computer",
)

_EMERGENCY_KEYWORDS = (
    "notfall", "es brennt", "feuer", "brand", "wasser läuft", "wasser laeuft",
    "lebensgefahr", "medizinischer notfall", "rettungsdienst",
    "gefahr für leib und leben", "gefahr fuer leib und leben", "jemand ist verletzt",
    "es ist ein notfall",
)

_TIME_CRITICAL_KEYWORDS = (
    "kompletter ausfall", "totalausfall", "alles tot", "komplett ausgefallen",
    "nichts funktioniert mehr", "gar nichts geht mehr", "alles ist tot",
    "praxis ist nicht erreichbar", "arztpraxis nicht erreichbar",
    "so schnell wie möglich", "so schnell wie moeglich", "es ist dringend",
    "sehr dringend", "jetzt sofort",
)

_COMPLAINT_KEYWORDS = (
    "das ist nicht in ordnung", "ich bin verärgert", "ich bin veraergert",
    "ich bin sauer", "das dauert schon viel zu lange", "zum wiederholten mal",
    "beschwerde", "das kann doch nicht sein", "ich warte schon seit",
    "enttäuscht", "enttaeuscht", "das ist eine frechheit", "ich bin genervt",
)

_NO_MORE_QUESTIONS_KEYWORDS = (
    "keine weiteren fragen", "verbinden sie mich bitte einfach",
    "verbinden sie mich einfach", "stellen sie keine weiteren fragen",
    "keine fragen mehr", "einfach verbinden", "bitte einfach verbinden",
    "keine weiteren informationen", "ich habe keine weiteren fragen",
)

_FINAL_NOTE_NEGATIVE_KEYWORDS = (
    "nein danke", "nichts weiter", "das wäre alles", "das waere alles",
    "das ist alles", "nichts mehr", "das war's", "das wars",
)

_REASON_HINT_KEYWORDS = (
    "geht nicht", "funktioniert nicht", "kaputt", "defekt", "ausfall",
    "störung", "stoerung", "rechnung", "vertrag", "kündigung", "kuendigung",
    "termin", "reklamation", "problem mit", "frage zu", "angebot",
)

_REASON_TRIGGER_RE = re.compile(
    r"(?:es geht um|es geht dabei um|und zwar wegen|wegen|bezüglich|bezueglich|betreffend)\s+(.+)",
    re.IGNORECASE,
)


def _is_human_request(text: str) -> bool:
    return _contains(text, _HUMAN_REQUEST_KEYWORDS)


def _extract_reason(text: str, utterance: str, reason_already_asked: bool) -> Optional[str]:
    """
    Best-effort, deterministic reason extraction — no LLM. Tries an explicit
    "wegen/bezüglich ..." phrase first, then falls back to whole-utterance
    capture when a reason-hint or category keyword is present, and finally
    (only once the caller has just been asked "what does this concern?")
    treats whatever they say next as the reason, even without a recognised
    keyword.
    """
    m = _REASON_TRIGGER_RE.search(utterance)
    if m:
        candidate = m.group(1).strip().rstrip(".,!?")
        if candidate:
            return candidate

    # Deliberately NOT keyed on _EMERGENCY_KEYWORDS/_TIME_CRITICAL_KEYWORDS/
    # _COMPLAINT_KEYWORDS: those already bypass the reason-known check
    # entirely for EMERGENCY/TIME_CRITICAL (see _advance_stage1), and a purely
    # emotional complaint phrase ("Das ist eine Frechheit!") does not by
    # itself describe WHAT the complaint concerns — see stage 1 rule #3
    # ("ask one concise clarification only when the reason is unknown").
    if _contains(text, _REASON_HINT_KEYWORDS):
        return utterance.strip()

    if reason_already_asked:
        cleaned = utterance.strip()
        return cleaned or None

    return None
