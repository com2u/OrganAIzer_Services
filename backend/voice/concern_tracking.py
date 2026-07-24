"""
concern_tracking.py — small per-call tracker for multiple caller concerns
mentioned in one call.

Plays the same narrow-bridge role as the other per-call dialogue modules
(voice/human_handoff_dialogue.py, voice/caller_resolution_dialogue.py,
voice/scheduler_dialogue.py): per-call state created fresh via new_state(),
no cross-call leakage, no persistence.

This is deliberately NOT a general task manager. Detection is conservative
and explicit-trigger only — an utterance is treated as raising an
ADDITIONAL concern only when it contains one of a short fixed marker phrase
("und außerdem", "zusätzlich", "noch etwas", "ich habe zwei/drei Punkte",
English equivalents). No semantic sentence-splitting, no LLM classification.

Priority reuses voice/human_handoff_dialogue.py's existing EMERGENCY /
TIME_CRITICAL / COMPLAINT keyword sets (via classify_category()) instead of
duplicating them, plus one small local keyword set to recognise an
appointment/callback concern by the caller's own words — this module never
reads or touches scheduling code, it only classifies caller text.
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from voice.caller_resolution_dialogue import redact_phone_like
from voice.human_handoff_dialogue import (
    _COMPLAINT_KEYWORDS,
    _EMERGENCY_KEYWORDS,
    _TIME_CRITICAL_KEYWORDS,
)

# Ordered most to least urgent — index doubles as priority rank (0 = most
# urgent). Matches the caller-visible ordering requested for this batch:
# emergency > total outage > current operational issue > appointment/
# callback > informational question.
_PRIORITY_ORDER = ("emergency", "outage", "operational", "appointment", "informational")

_APPOINTMENT_KEYWORDS = (
    "termin", "vor-ort-termin", "rückruf", "rueckruf",
    "appointment", "callback", "call back", "book a", "schedule a",
)

# Explicit, conservative multi-intent join markers. A second concern is only
# ever split off when one of these literally appears in the utterance —
# never from general sentence-splitting or inferring intent from ordinary
# "und" inside one sentence.
_MULTI_INTENT_MARKERS = (
    "und außerdem", "und ausserdem", "außerdem", "ausserdem",
    "zusätzlich", "zusaetzlich", "auch noch", "noch etwas", "und noch etwas",
    "ich habe zwei punkte", "ich habe drei punkte", "und dazu",
    "and also", "in addition", "one more thing",
    "i have two things", "i have three things", "i also",
)


class ConcernRecord(TypedDict):
    text: str       # short caller-facing snippet, already redacted
    category: str   # one of _PRIORITY_ORDER
    priority: int   # index into _PRIORITY_ORDER (0 = most urgent)
    status: str      # "open" | "resolved" | "handed_off"


def new_state() -> List[ConcernRecord]:
    """Create a fresh per-call concern list (no cross-call leakage)."""
    return []


def classify_category(text: str) -> str:
    """Deterministic keyword classification. Reuses human_handoff_dialogue's
    EMERGENCY/TIME_CRITICAL/COMPLAINT keyword sets so the two modules' notion
    of urgency can never silently drift apart.
    """
    lowered = text.lower()
    if any(k in lowered for k in _EMERGENCY_KEYWORDS):
        return "emergency"
    if any(k in lowered for k in _TIME_CRITICAL_KEYWORDS):
        return "outage"
    if any(k in lowered for k in _APPOINTMENT_KEYWORDS):
        return "appointment"
    if any(k in lowered for k in _COMPLAINT_KEYWORDS):
        return "operational"
    return "informational"


def _priority_rank(category: str) -> int:
    try:
        return _PRIORITY_ORDER.index(category)
    except ValueError:
        return len(_PRIORITY_ORDER) - 1


def _find_marker(text: str) -> Optional[str]:
    lowered = text.lower()
    for marker in _MULTI_INTENT_MARKERS:
        if marker in lowered:
            return marker
    return None


def observe_turn(state: List[ConcernRecord], utterance: str) -> Optional[ConcernRecord]:
    """
    Deterministically check one RAW caller utterance for an explicit
    multi-intent join marker. If found, split off the text AFTER the marker
    as a new ADDITIONAL concern, classify it, store it, and return the new
    record — otherwise return None.

    Call with the raw utterance (not history-sanitized text) — the stored
    text is redacted here via the same redact_phone_like() every other
    dialogue module uses, so a phone number spoken as part of a second
    concern is never captured raw.
    """
    if not utterance:
        return None
    marker = _find_marker(utterance)
    if marker is None:
        return None
    idx = utterance.lower().find(marker)
    tail = utterance[idx + len(marker):].strip(" ,.:;-")
    if not tail:
        return None
    sanitized_tail, _ = redact_phone_like(tail)
    snippet = sanitized_tail.strip()[:160]
    if not snippet:
        return None
    # Cheap prefix dedup — avoid re-adding the same concern if the caller
    # repeats themselves in a later turn. No semantic comparison.
    for existing in state:
        if existing["text"][:40].lower() == snippet[:40].lower():
            return None
    category = classify_category(snippet)
    record: ConcernRecord = {
        "text": snippet,
        "category": category,
        "priority": _priority_rank(category),
        "status": "open",
    }
    state.append(record)
    return record


def open_concerns(state: List[ConcernRecord]) -> List[ConcernRecord]:
    return [c for c in state if c["status"] == "open"]


def mark_resolved(state: List[ConcernRecord], text_prefix: str) -> bool:
    """Mark the first open concern whose text starts with *text_prefix* as
    resolved. Purely explicit — never inferred by parsing later turns.
    Returns True if a concern was updated.
    """
    for c in state:
        if c["status"] == "open" and c["text"].lower().startswith(text_prefix.lower()):
            c["status"] = "resolved"
            return True
    return False


def mark_all_handed_off(state: List[ConcernRecord]) -> None:
    """Mark every currently-open concern as handed_off. Called once
    escalation has actually included them, so a later escalation in the same
    call (if one somehow occurred) would not duplicate them.
    """
    for c in state:
        if c["status"] == "open":
            c["status"] = "handed_off"


def build_prompt_extra(state: List[ConcernRecord]) -> Optional[str]:
    """Short deterministic reminder folded into system_extra so the LLM does
    not silently drop an open secondary concern. Factual reminder only — no
    new business rule — mirrors identity_extra/handoff_extra's pattern in
    esl_call_handler.py.
    """
    open_ = open_concerns(state)
    if not open_:
        return None
    if len(open_) == 1:
        return (
            "[Weiteres offenes Anliegen des Anrufers, noch nicht bearbeitet: "
            f"{open_[0]['text']}]"
        )
    listed = "; ".join(c["text"] for c in open_)
    return (
        f"[Weitere offene Anliegen des Anrufers, noch nicht bearbeitet ({len(open_)}): "
        f"{listed}]"
    )


def acknowledgement_for_new_concern(open_count: int, lang: str = "de") -> str:
    """Short, deterministic caller-facing line for when a SECOND (or later)
    concern was just detected via an explicit multi-intent marker.

    Deliberately does not quote the caller's own raw text back to them —
    inserting an arbitrary caller-supplied fragment mid-sentence does not
    compose grammatically in German or English, and the system prompt
    already discourages this kind of restatement (see llm_bridge.py's
    "active listening, not parroting" rule) — so this only confirms the
    current topic is handled first and that nothing else is forgotten.
    """
    plural = open_count > 1
    if lang == "en":
        noun = "those points" if plural else "that point"
        return f"Got it — I'll take {noun} after we finish this one."
    noun = "die weiteren Punkte" if plural else "das zweite Anliegen"
    return f"Verstanden — {noun} behalte ich im Blick, gleich nach diesem hier."
