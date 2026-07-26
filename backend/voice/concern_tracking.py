"""
concern_tracking.py — small per-call tracker for multiple caller concerns
mentioned in one call.

Plays the same narrow-bridge role as the other per-call dialogue modules
(voice/human_handoff_dialogue.py, voice/caller_resolution_dialogue.py,
voice/scheduler_dialogue.py): per-call state created fresh via new_state(),
no cross-call leakage, no persistence.

This is deliberately NOT a general task manager. Detection is conservative
and explicit-trigger only, in two additive modes: (1) a short fixed marker
phrase ("und außerdem", "zusätzlich", "noch etwas", English equivalents)
splits off the text after the marker; (2) an explicit TRAILING enumeration
("… das sind drei Dinge") splits the utterance's sentences into concerns,
but ONLY when the sentence count exactly matches the stated number — any
mismatch falls back to mode 1. No free semantic sentence-splitting, no LLM
classification.

A LEADING enumeration ("ich habe drei Dinge, …") is deliberately NOT split:
there the count is a promise about concerns still to come, not a summary of
concerns already spoken, so the sentences that follow it are the caller
starting on concern #1 — see _analyse_enumeration() for the live call that
made this distinction necessary. Only the stated count is remembered
(ConcernState.expected_concern_count); the concerns themselves are picked up
by mode 1 as the call proceeds. Categories are never fabricated to make the
tracker's contents add up to the promised number.

Priority reuses voice/human_handoff_dialogue.py's existing EMERGENCY /
TIME_CRITICAL / COMPLAINT keyword sets (via classify_category()) instead of
duplicating them, plus one small local keyword set to recognise an
appointment/callback concern by the caller's own words — this module never
reads or touches scheduling code, it only classifies caller text.
"""
from __future__ import annotations

import logging
import re
from typing import List, NamedTuple, Optional, TypedDict

from voice.caller_resolution_dialogue import redact_phone_like
from voice.human_handoff_dialogue import (
    _COMPLAINT_KEYWORDS,
    _EMERGENCY_KEYWORDS,
    _TIME_CRITICAL_KEYWORDS,
)

logger = logging.getLogger(__name__)

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

# ── enumeration detection (additive to the marker approach above) ────────────
# A caller who OPENS with several concerns and only then says "das sind drei
# Dinge" is invisible to marker-tail splitting: the count phrase comes after
# the concerns, so the tail is empty. This second, equally conservative mode
# handles exactly that shape: it fires only when a count word + enumeration
# noun appear AND the number of remaining sentences exactly matches the
# stated count (no guessing which sentences are separate concerns — on any
# mismatch we fall back to the marker approach unchanged). "Roughly matches"
# is deliberately implemented as EXACT equality: with a mismatch there is no
# deterministic way to know which sentences to merge or drop.
_COUNT_WORDS = {
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "two": 2, "three": 3, "four": 4, "five": 5,
    "2": 2, "3": 3, "4": 4, "5": 5,
}

_ENUMERATION_RE = re.compile(
    r"\b(zwei|drei|vier|fünf|fuenf|two|three|four|five|[2-5])\s+"
    r"(dinge|anliegen|punkte|fragen|sachen|themen|"
    r"things|points|questions|issues|matters)\b"
)

_TERMINAL_PUNCTUATION = ".!?"
_ELLIPSIS_RE = re.compile(r"(\.\.\.|…)\s*$")


def _sentences(utterance: str) -> List[str]:
    return [
        s.strip(" ,;:-")
        for s in re.split(r"[.!?]+", utterance)
        if s.strip(" ,;:-")
    ]


def _final_fragment_is_incomplete(utterance: str) -> bool:
    """
    True when the transcription's LAST sentence looks like STT cut the caller
    off mid-thought rather than a finished sentence: a trailing ellipsis
    ("Die Lichter sind alle…") or no terminal punctuation at all.

    Only the final sentence can be affected — everything before it is
    terminated by the punctuation that split it off.
    """
    stripped = utterance.rstrip()
    if not stripped:
        return True
    if _ELLIPSIS_RE.search(stripped):
        return True
    return stripped[-1] not in _TERMINAL_PUNCTUATION


class _Enumeration(NamedTuple):
    """Result of reading an explicit count phrase out of one utterance.

    *concerns* is None whenever the utterance's shape does not license
    sentence-splitting; *stated_count* is still reported in that case, since
    the number the caller said is reliable information even when which
    sentences it refers to is not.
    """
    stated_count: int
    concerns: Optional[List[str]]


def _analyse_enumeration(utterance: str) -> Optional[_Enumeration]:
    """
    Read an explicit count phrase ("das sind drei Dinge", "I have three
    things") out of *utterance* and decide whether its sentences may be split
    into concern records.

    Splitting is licensed ONLY for the TRAILING shape — the count phrase in
    the last sentence, summarising concerns the caller has already finished
    saying ("Internet weg. Anlage defekt. Frage zur Rechnung. Das sind drei
    Dinge."). Then, if exactly the stated number of content sentences remain
    after dropping the meta count sentence, every sentence AFTER the first is
    returned as an additional concern (the first is the topic currently being
    handled, which this tracker never stores).

    Returns concerns=None — count only — for every other shape:

    * LEADING count phrase ("Ich habe drei Dinge, die ich besprechen möchte.
      Zum einen … Wir haben … Die Lichter sind alle…"). Here the count
      promises concerns still to come, and the sentences that follow are the
      caller describing concern #1. Live call 2026-07-25 18:26 proved the
      exact-count guard cannot catch this on its own: STT punctuated a single
      Internet complaint into exactly three sentences, the guard passed by
      coincidence, and two fragments of one topic were stored as two separate
      "concerns" — which then surfaced as a vague "die weiteren Fragen" in the
      pre-transfer question while the caller's actual second and third topics
      were never tracked at all.
    * A final sentence STT cut off mid-thought, unless that fragment is the
      meta count sentence itself (which is discarded anyway). A truncated
      sentence must never become a concern record, and its presence also
      means the sentence count is not the caller's real concern count.
    * Any mismatch between the stated count and the content-sentence count.

    On None-concerns, observe_turn falls back to the marker-tail approach
    unchanged.
    """
    match = _ENUMERATION_RE.search(utterance.lower())
    if not match:
        return None
    stated_count = _COUNT_WORDS[match.group(1)]
    sentences = _sentences(utterance)
    if not sentences:
        return _Enumeration(stated_count, None)

    last_is_count_phrase = bool(_ENUMERATION_RE.search(sentences[-1].lower()))

    # Never build a concern out of a sentence STT truncated. Harmless only
    # when the truncated tail is the meta count sentence, which is dropped
    # from `content` below either way.
    if _final_fragment_is_incomplete(utterance) and not last_is_count_phrase:
        return _Enumeration(stated_count, None)

    # Leading count phrase — a promise, not a summary. Remember the number,
    # split nothing.
    if not last_is_count_phrase:
        return _Enumeration(stated_count, None)

    # The sentence containing the count phrase is meta ("das sind drei
    # Dinge"), not a concern — drop it before comparing counts.
    content = [s for s in sentences if not _ENUMERATION_RE.search(s.lower())]
    if len(content) != stated_count:
        return _Enumeration(stated_count, None)
    return _Enumeration(stated_count, content[1:])


class ConcernRecord(TypedDict):
    text: str       # short caller-facing snippet, already redacted
    category: str   # one of _PRIORITY_ORDER
    priority: int   # index into _PRIORITY_ORDER (0 = most urgent)
    status: str      # "open" | "resolved" | "handed_off"


class ConcernState(List[ConcernRecord]):
    """The per-call concern list.

    A plain list of ConcernRecord in every respect — every reader in this
    module and in esl_call_handler.py iterates/len()s it exactly as before —
    plus one scalar the list itself cannot carry: how many concerns the
    caller SAID they have ("ich habe drei Dinge"). That number is recorded
    even when the utterance's shape forbids splitting it into records, so the
    pre-transfer question can tell "nothing else is open" apart from "the
    caller announced three topics and we only ever tracked one".

    Never fabricates records to reach the promised count — see
    final_note_labels() for the only thing the number is used for.
    """
    expected_concern_count: int = 0


def new_state() -> ConcernState:
    """Create a fresh per-call concern list (no cross-call leakage)."""
    return ConcernState()


def expected_count(state: List[ConcernRecord]) -> int:
    """How many concerns the caller explicitly announced (0 when they never
    stated a number). Tolerates a plain list, so callers and tests that build
    state by hand keep working.
    """
    return getattr(state, "expected_concern_count", 0)


def _note_expected_count(state: List[ConcernRecord], count: int) -> None:
    """Record a stated concern count, keeping the highest seen this call —
    a caller who says "drei Dinge" and later "zwei Punkte" has raised at
    least three topics, and hedging is the safe direction.
    """
    try:
        state.expected_concern_count = max(expected_count(state), count)
    except AttributeError:
        # Plain list passed in by a caller/test — the count is optional
        # context, never required for concern tracking itself.
        pass


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
        # Ranked least urgent so an unknown category can never jump the queue
        # ahead of a real emergency — but say so, rather than silently
        # burying a concern classify_category() grew without _PRIORITY_ORDER
        # (and _CATEGORY_LABELS_DE) growing with it.
        logger.warning(
            "Unknown concern category %r — ranked least urgent. Add it to "
            "_PRIORITY_ORDER and _CATEGORY_LABELS_DE in voice/concern_tracking.py.",
            category,
        )
        return len(_PRIORITY_ORDER) - 1


def _find_marker(text: str) -> Optional[str]:
    lowered = text.lower()
    for marker in _MULTI_INTENT_MARKERS:
        if marker in lowered:
            return marker
    return None


def _add_concern(state: List[ConcernRecord], raw_text: str) -> Optional[ConcernRecord]:
    """Redact, trim, dedup, classify and store one additional-concern text.
    Returns the new record, or None when the text is empty or a duplicate.
    """
    sanitized, _ = redact_phone_like(raw_text)
    snippet = sanitized.strip()[:160]
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


def observe_turn(state: List[ConcernRecord], utterance: str) -> Optional[ConcernRecord]:
    """
    Deterministically check one RAW caller utterance for multiple concerns,
    in two additive modes:

    1. Trailing enumeration — a count phrase in the LAST sentence whose
       stated number exactly matches the remaining sentence count ("Internet
       geht nicht. Telefonanlage muss inspiziert werden. Frage zur Rechnung.
       Das sind drei Dinge."): every sentence after the first is stored as an
       additional concern. A LEADING count phrase ("Ich habe drei Dinge …")
       stores no records at all — only the stated number, on
       state.expected_concern_count — because the concerns it promises have
       not been spoken yet (see _analyse_enumeration).
    2. Marker tail (the original mode) — an explicit multi-intent join
       marker ("und außerdem …"): the text after the marker is stored as one
       additional concern.

    Returns the first newly stored record (None when nothing was stored).
    Call with the raw utterance (not history-sanitized text) — the stored
    text is redacted via the same redact_phone_like() every other dialogue
    module uses, so a phone number spoken as part of a second concern is
    never captured raw.
    """
    if not utterance:
        return None

    # Record the stated count even when the shape forbids splitting — the
    # number is reliable, the sentence boundaries are not.
    enumeration = _analyse_enumeration(utterance)
    enumerated = None
    if enumeration is not None:
        _note_expected_count(state, enumeration.stated_count)
        enumerated = enumeration.concerns
    if enumerated:
        first_new: Optional[ConcernRecord] = None
        for text in enumerated:
            record = _add_concern(state, text)
            if record is not None and first_new is None:
                first_new = record
        if first_new is not None:
            return first_new
        # Every enumerated sentence was empty/duplicate — fall through to
        # the marker approach rather than swallowing a possible "und
        # außerdem …" in the same utterance.

    marker = _find_marker(utterance)
    if marker is None:
        return None
    idx = utterance.lower().find(marker)
    tail = utterance[idx + len(marker):].strip(" ,.:;-")
    if not tail:
        return None
    return _add_concern(state, tail)


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


# Caller-facing German labels per category (singular, plural). Spoken lines
# built from tracker state use these instead of the stored raw caller-text
# snippets — an arbitrary caller fragment does not compose grammatically
# mid-sentence (see acknowledgement_for_new_concern below), category labels
# always do. German only: both call sites (the pre-escalation handover
# summary and the final-note question) live in the escalation sequence,
# which is always German (legal/compliance requirement — see
# esl_call_handler.py's consent step).
_CATEGORY_LABELS_DE = {
    "emergency":     ("der Notfall", "die Notfälle"),
    "outage":        ("die Störung", "die Störungen"),
    "operational":   ("die Beschwerde", "die Beschwerden"),
    "appointment":   ("die Terminanfrage", "die Terminanfragen"),
    "informational": ("die weitere Frage", "die weiteren Fragen"),
}


def _joined_labels_de(records: List[ConcernRecord]) -> str:
    """Join the category labels of *records* into one spoken German fragment,
    most urgent first, deduplicated per category (plural label when a
    category occurs more than once): "die Terminanfrage und die weitere Frage".
    """
    counts: dict[str, int] = {}
    for c in records:
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    parts = []
    # Driven by the records actually tracked, not by _PRIORITY_ORDER: iterating
    # the constant would silently omit any category missing from it, dropping a
    # real caller concern out of the spoken line with no trace. sorted() is
    # stable and dicts keep insertion order, so same-rank categories stay in
    # first-seen order.
    for category in sorted(counts, key=_priority_rank):
        label = _CATEGORY_LABELS_DE.get(category)
        if label is None:
            logger.warning(
                "Concern category %r has no caller-facing label — omitted from the "
                "spoken line (%d concern(s) affected). Add it to _CATEGORY_LABELS_DE "
                "in voice/concern_tracking.py.",
                category, counts[category],
            )
            continue
        singular, plural = label
        parts.append(plural if counts[category] > 1 else singular)
    if len(parts) <= 1:
        return parts[0] if parts else ""
    return ", ".join(parts[:-1]) + " und " + parts[-1]


def open_category_labels(state: List[ConcernRecord]) -> Optional[str]:
    """Spoken German fragment naming the still-open concerns by category
    label ("die Terminanfrage und die weitere Frage"), or None when nothing
    is open. Used by the final-note question so it can name what is being
    handed over without quoting raw caller text.
    """
    open_ = open_concerns(state)
    if not open_:
        return None
    return _joined_labels_de(open_)


def final_note_labels(state: List[ConcernRecord]) -> Optional[str]:
    """open_category_labels(), except it withholds the specific list when the
    tracker is demonstrably incomplete.

    A caller who announced "ich habe drei Dinge" and was then only ever asked
    about one of them must not hear the pre-transfer question confidently name
    a single category as though that were everything outstanding — naming a
    short list implies the list is complete. Returning None makes the call
    site ask its plain catch-all question instead ("Gibt es noch etwas, das
    der Kollege oder die Kollegin wissen sollte?"), which invites the caller
    to supply what the tracker missed.

    The +1 is the concern currently being handled: the enumeration splitter
    never stores it (see _analyse_enumeration), so a call where the caller
    said "drei Dinge" and two were tracked is complete, not short.

    Deliberately separate from open_category_labels(): the handover summary
    (which describes what IS known, and is spoken to the caller as a
    statement rather than a question) keeps naming every tracked category.
    """
    stated = expected_count(state)
    if stated and len(state) + 1 < stated:
        logger.info(
            "Caller announced %d concerns but only %d were tracked — asking the "
            "open-ended pre-transfer question instead of naming categories.",
            stated, len(state),
        )
        return None
    return open_category_labels(state)


def handover_summary_sentence(state: List[ConcernRecord]) -> Optional[str]:
    """One deterministic German sentence for the escalation sequence, spoken
    BEFORE the recording-consent question: what is already settled vs. what
    the Mitarbeiter takes over. Built from tracker categories only (never raw
    snippets). Returns None when the tracker holds no records — a
    single-concern call needs no handover summary.
    """
    resolved = [c for c in state if c["status"] == "resolved"]
    open_ = open_concerns(state)
    if not resolved and not open_:
        return None
    if resolved and open_:
        sentence = (
            f"{_joined_labels_de(resolved)} haben wir bereits geklärt — "
            f"{_joined_labels_de(open_)} gebe ich mit an den Mitarbeiter weiter."
        )
    elif open_:
        noun = "Ihre weiteren Anliegen" if len(open_) > 1 else "Ihr weiteres Anliegen"
        sentence = (
            f"{noun} — {_joined_labels_de(open_)} — "
            "gebe ich mit an den Mitarbeiter weiter."
        )
    else:
        sentence = (
            f"{_joined_labels_de(resolved)} haben wir bereits geklärt — "
            "alles Weitere übernimmt der Mitarbeiter."
        )
    return sentence[0].upper() + sentence[1:]


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
