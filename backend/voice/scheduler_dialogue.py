"""
scheduler_dialogue.py — deterministic per-call appointment dialogue for the phone AI.

This is the narrow bridge between the live voice loop and the backend Scheduler
(``backend/scheduler``). It is a pure state machine over strings: given the
per-call ``state`` dict and the caller's latest (already-transcribed) utterance,
it returns either:

  * ``None``  → this turn is NOT part of an appointment flow; the caller path
                should fall through to the normal LLM. (Zero behaviour change.)
  * a :class:`TurnResult` → the engine is handling this turn; speak ``reply``.

Safety design (mirrors the rest of the voice stack):
  - The AI NEVER invents availability. Every offered time comes from
    ``scheduler.list_available_slots`` and every spoken sentence comes from
    ``scheduler.phone`` (guarded by ``assert_phrase_safe``).
  - Nothing is booked until the caller explicitly confirms a specific offered
    slot. Booking is a SIMULATION (``status = "simulated"``); no real calendar.
  - Emergencies / high-risk requests are never booked — the engine emits the
    existing ``ESCALATE:`` directive so the loop's escalation path handles them.
  - Raw phone numbers are never logged here; the Scheduler masks before storage.

The engine holds no global state — everything lives in the ``state`` dict the
caller owns (created fresh per call), so there is no cross-call leakage.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timedelta
from typing import Optional

from scheduler import (
    APPOINTMENT_TYPES,
    Slot,
    create_simulated_appointment,
    is_open,
    list_available_slots,
)
from scheduler import phone as sched_phone
from scheduler.availability import filter_by_time_window
from voice.time_preferences import parse_time_preference

logger = logging.getLogger(__name__)

# How far ahead to look for the first day with free slots.
_HORIZON_DAYS = 14
# Max slots to offer at once (task: 1–3).
_MAX_OFFER = 3
# Give up and hand back to the LLM after this many failed parse attempts.
_MAX_ATTEMPTS = 2

# ── intent / classification keyword sets (German-first) ──────────────────────
_INTENT_KEYWORDS = (
    "termin", "vereinbaren", "buchen", "vormerken", "rückruf", "rueckruf",
    "zurückrufen", "zurueckrufen", "fernwartung", "wartung", "vor ort",
    "vor-ort", "vorort", "techniker", "beratung", "appointment", "callback",
    "schedule",
)

_EMERGENCY_KEYWORDS = (
    "notfall", "notaufnahme", "notarzt", "dringend", "sofort", "feuer",
    "brennt", "wasser läuft", "wasserschaden", "kompletter ausfall",
    "totalausfall", "stromausfall", "emergency", "urgent",
)

# Ordered by specificity — first match wins.
_TYPE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("remote_support", ("fernwartung", "fernzugriff", "remote", "teamviewer")),
    ("on_site_visit_request", (
        "vor ort", "vor-ort", "vorort", "techniker", "installation",
        "vorbeikommen", "monteur", "einbau",
    )),
    ("maintenance_request", ("wartung", "maintenance", "instandhaltung")),
    ("callback", ("rückruf", "rueckruf", "zurückrufen", "zurueckrufen", "callback")),
    ("sales_consultation", (
        "vertrieb", "angebot", "kaufen", "preis", "verkauf", "sales",
        "vertriebsberatung", "neukunde",
    )),
    ("technical_consultation", (
        "technische beratung", "technikberatung", "beratung", "consultation",
    )),
)

_WEEKDAYS_DE = {
    "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
    "freitag": 4, "samstag": 5, "sonntag": 6,
}

# Natural spoken acknowledgement of the understood request (with article), so
# the engine never reads a bare category label ("Alles klar, Rückruf.") aloud.
_TYPE_ACK_DE = {
    "callback": "einen Rückruf",
    "remote_support": "eine Fernwartung",
    "technical_consultation": "eine technische Beratung",
    "on_site_visit_request": "einen Vor-Ort-Termin",
    "sales_consultation": "eine Vertriebsberatung",
    "maintenance_request": "einen Wartungstermin",
}

_NEGATIVE_WORDS = (
    "nein", "ne ", "nö", "passt nicht", "anderer", "anderen", "andere",
    "lieber", "nicht gut", "geht nicht", "keine davon", "keins",
)
_AFFIRM_WORDS = (
    "ja", "passt", "gut", "gerne", "okay", "ok", "in ordnung", "nehmen wir",
    "nehme", "einverstanden", "genau",
)


@dataclass
class TurnResult:
    """A turn the engine is handling. ``reply`` is spoken; the rest is for tests."""

    reply: str
    booked: bool = False
    appointment: object = None  # scheduler.Appointment when booked


def new_state() -> dict:
    """Create a fresh per-call appointment state."""
    return {
        "stage": "idle",                           # idle | collecting | offered | booked
        "appointment_type": None,
        "topic": None,
        "preferred_day": None,                     # date
        "offered_slots": [],                       # list[Slot]
        "offer_day": None,                         # date the offered slots belong to
        "classify_attempts": 0,
        "select_attempts": 0,
        # ── Memory to prevent repetition ──
        "last_asked_question": None,               # "reason" | "day" | "confirmation"
        "have_time_preference": False,             # Did caller mention a time?
        "reason_clarification_attempts": 0,        # How many times asked for reason?
        "inferred_from": None,                     # "keywords" or "clarification_response"
        "time_window": None,                       # (start, end) time-of-day preference
        "auto_offer_done": False,                  # earliest-slot fallback already used?
    }


# ── keyword helpers ──────────────────────────────────────────────────────────
def _contains(text: str, needles) -> bool:
    return any(n in text for n in needles)


def _has_appointment_intent(text: str) -> bool:
    # Either an explicit scheduling word, or a clearly named service type
    # (Fernwartung, Wartung, Vor-Ort, Rückruf, Beratung, Vertrieb/Angebot …).
    return _contains(text, _INTENT_KEYWORDS) or _classify_type(text) is not None


def _is_emergency(text: str) -> bool:
    return _contains(text, _EMERGENCY_KEYWORDS)


def _classify_type(text: str) -> Optional[str]:
    for appt_type, keywords in _TYPE_KEYWORDS:
        if _contains(text, keywords):
            return appt_type
    return None


def _parse_preferred_day(text: str, today: date_cls) -> Optional[date_cls]:
    """Parse a rough German day preference into a concrete date, or None."""
    if "übermorgen" in text or "uebermorgen" in text:
        return today + timedelta(days=2)
    if "morgen" in text:
        return today + timedelta(days=1)
    if "heute" in text:
        return today
    for name, wd in _WEEKDAYS_DE.items():
        if name in text:
            delta = (wd - today.weekday()) % 7
            return today + timedelta(days=delta)
    return None


def _resolve_preferred_day(time_pref, text: str, today: date_cls) -> Optional[date_cls]:
    """Turn a parsed time preference (plus the raw text) into a concrete date.

    Also resolves the vaguer answers callers actually give: "nächste Woche" →
    next Monday, "diese Woche" → first available from today.
    """
    if time_pref.days_offset is not None:
        return today + timedelta(days=time_pref.days_offset)
    if time_pref.target_day == "next_week":
        return today + timedelta(days=7 - today.weekday())  # next Monday
    if time_pref.target_day == "this_week":
        return today
    return _parse_preferred_day(text, today)


def _first_available(
    appt_type: str, start: date_cls, now: datetime, path
) -> tuple[Optional[date_cls], list[Slot]]:
    """Return the first day at/after *start* (within the horizon) that has slots."""
    for offset in range(_HORIZON_DAYS + 1):
        day = start + timedelta(days=offset)
        if not is_open(day):
            continue
        slots = list_available_slots(day, appt_type, limit=_MAX_OFFER, now=now, path=path)
        if slots:
            return day, slots
    return None, []


def _match_selection(text: str, slots: list[Slot]) -> Optional[Slot]:
    """Map an utterance to one of the offered slots by ordinal or time, else None."""
    # Note: no bare "eine" — it substring-matches "einen"/"keine" and would
    # falsely select a slot when the caller is actually declining.
    ordinals = {
        0: ("erste", "erster", "ersten", "eins", "1.", " 1 "),
        1: ("zweite", "zweiten", "zwei", "2.", " 2 "),
        2: ("dritte", "dritten", "drei", "3.", " 3 "),
    }
    padded = f" {text} "
    for idx, words in ordinals.items():
        if idx < len(slots) and any(w in padded for w in words):
            return slots[idx]
    # Time match: "10 uhr", "10:30", "10.30 uhr"
    m = re.search(r"(\d{1,2})[:.]?(\d{2})?\s*uhr", text) or re.search(r"(\d{1,2}):(\d{2})", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else None
        for slot in slots:
            if slot.start.hour == hour and (minute is None or slot.start.minute == minute):
                return slot
    return None


def _ack(appt_type: str) -> str:
    """Spoken acknowledgement with article: 'einen Rückruf', 'eine Fernwartung'."""
    return _TYPE_ACK_DE.get(appt_type, "einen Termin")


# ── context-aware inference (non-menu) ────────────────────────────────────
def _infer_appointment_type_from_context(text: str, state: dict) -> Optional[str]:
    """
    Infer appointment type from caller's language + context.
    Does NOT ask a menu; maps natural caller speech to internal types.

    Maps:
    - "Rechnung", "Zahlung", "berechnet" → callback (billing follow-up)
    - "neue Anlage", "Installation", "Umzug" → sales_consultation
    - "Fernwartung", "Remote", "TeamViewer" → remote_support (explicit)
    - "vor Ort", "Techniker", "vorbeikommen" → on_site_visit_request
    - "Wartung", "Vertrag", "regelmäßig" → maintenance_request
    - "Rückruf", "ruft an", "anrufen" (no other details) → callback
    - "Problem", "kaputt", "nicht" + urgency marker → remote_support or on_site_visit_request

    Returns appointment type or None (unknown/unclear).
    """
    lowered = text.lower()

    # Billing / invoice follow-up
    if _contains(lowered, ("rechnung", "mahnung", "zahlung", "berechnet", "rechnungsfrage")):
        return "callback"  # Not a technical appointment; callback for billing

    # New system / installation / sales
    has_neue = "neue" in lowered or "neuer" in lowered or "neuanlage" in lowered
    has_system = any(word in lowered for word in ("anlage", "installation", "system", "telefon"))
    if has_neue and has_system:
        return "sales_consultation"
    if _contains(lowered, ("umzug", "neukunde", "kaufen", "anschaffen")):
        return "sales_consultation"

    # Explicit remote support
    if _contains(lowered, ("fernwartung", "fernzugriff", "remote", "teamviewer", "remote support")):
        return "remote_support"

    # On-site / technician visit
    if _contains(lowered, ("vor ort", "vor-ort", "vorort", "techniker", "vorbeikommen",
                           "monteur", "einbau", "vorbeischauen")):
        return "on_site_visit_request"

    # Maintenance contract / routine service
    if _contains(lowered, ("wartung", "maintenance", "instandhaltung", "wartungsvertrag",
                           "regelmäßig", "routine")):
        return "maintenance_request"

    # Explicit callback request
    if _contains(lowered, ("rückruf", "rueckruf", "zurückrufen", "zurueckrufen", "ruft mich an",
                           "anrufen", "callback")):
        # Only if no other appointment intent mixed in
        if not _contains(lowered, ("techniker", "installation", "monteur")):
            return "callback"

    # Problem context: could be remote_support or on_site_visit_request
    # We infer based on context clues, not exact keywords
    # Must have "problem"/"kaputt"/"funktioniert"/"down"/"ausfall"/"fehler" + "nicht"
    # Not just "nicht" alone (which would match "weiß nicht", "keine ahnung", etc.)
    has_problem_word = _contains(lowered, ("problem", "kaputt", "ausfall", "fehler", "down",
                                            "funktioniert nicht", "funktioniert nicht mehr",
                                            "geht nicht", "geht nicht mehr"))
    if has_problem_word:
        # If caller mentions sending someone or on-site, prefer on_site_visit_request
        if _contains(lowered, ("vor ort", "vor-ort", "techniker vorbeischicken")):
            return "on_site_visit_request"
        # Otherwise assume remote_support is possible (diagnostics first)
        return "remote_support"

    # Generic consultation (not enough context to infer a specific type)
    if _contains(lowered, ("beratung", "consultation", "erklär", "einweisung")):
        return "technical_consultation"

    # Nothing matched
    return None


def _ask_reason_clarification_question(state: dict) -> TurnResult:
    """
    Ask a natural follow-up about appointment reason (never a menu).
    Varies by attempt so it doesn't sound robotic. Callers guard the attempt
    cap (``_MAX_ATTEMPTS``) and fall back to a callback offer beyond it.
    """
    attempt = state.get("reason_clarification_attempts", 0)

    if attempt == 0:
        # First attempt: open question
        return TurnResult(sched_phone.assert_phrase_safe(
            "Worum geht es denn genau — ist es ein technisches Problem, "
            "oder eher etwas anderes?"
        ))
    # Second attempt: rephrase, never the identical question again
    return TurnResult(sched_phone.assert_phrase_safe(
        "Was möchten Sie klären lassen — geht es um eine Fernwartung, "
        "um eine Beratung, oder um etwas ganz anderes?"
    ))


def _fallback_to_callback(state: dict, now: datetime, path) -> TurnResult:
    """
    The reason stayed unclear after one rephrase — keep the conversation moving
    with a callback a Mitarbeiter can pick up, instead of restarting or dropping
    the caller back to the LLM mid-flow. Nothing is booked here; the caller
    still has to confirm a concrete offered slot.
    """
    state["appointment_type"] = "callback"
    state["inferred_from"] = "unclear_fallback"
    if state.get("preferred_day") is not None:
        return _offer_slots(
            state, now, path,
            intro="Das klärt am besten ein Mitarbeiter direkt mit Ihnen — "
                  "ich kann Ihnen einen Rückruf vormerken. ",
        )
    state["last_asked_question"] = "day"
    return TurnResult(sched_phone.assert_phrase_safe(
        "Das klärt am besten ein Mitarbeiter direkt mit Ihnen. "
        "An welchem Tag passt Ihnen ein Rückruf?"
    ))


# ── main entry point ─────────────────────────────────────────────────────────
def handle_turn(
    state: dict,
    utterance: str,
    *,
    call_id: Optional[str] = None,
    phone: Optional[str] = None,
    caller_name: Optional[str] = None,
    company: Optional[str] = None,
    now: Optional[datetime] = None,
    path=None,
) -> Optional[TurnResult]:
    """
    Advance the appointment dialogue by one caller turn.

    Returns ``None`` when the turn is not part of an appointment flow (the caller
    path should fall through to the normal LLM), or a :class:`TurnResult` when the
    engine handled it.
    """
    if not utterance or not utterance.strip():
        return None
    now = now or datetime.now()
    today = now.date()
    text = utterance.lower().strip()
    stage = state.get("stage", "idle")

    # High-risk / emergency requests are never booked — defer to escalation.
    if _is_emergency(text) and (stage != "idle" or _has_appointment_intent(text)):
        _reset(state)
        return TurnResult(
            reply="ESCALATE: Terminwunsch mit möglichem Notfall — bitte Mitarbeiter"
        )

    if stage == "idle":
        if not _has_appointment_intent(text):
            return None
        state["stage"] = "collecting"
        state["topic"] = utterance.strip()[:200]

        # Try both inference methods on the first utterance
        state["appointment_type"] = _infer_appointment_type_from_context(text, state) or _classify_type(text)

        # A day may already be in the first utterance ("Rückruf morgen bitte").
        time_pref = parse_time_preference(text, now)
        state["preferred_day"] = _resolve_preferred_day(time_pref, text, today)
        if state["preferred_day"] is not None:
            state["have_time_preference"] = True

        # Store time window preference if present (morning, afternoon, etc.)
        if time_pref.time_window:
            state["time_window"] = time_pref.time_window

        return _advance_collecting(state, now, path)

    if stage == "collecting":
        return _collecting_turn(state, text, now, path)

    if stage == "offered":
        return _offered_turn(
            state, text, now, path,
            call_id=call_id, phone=phone, caller_name=caller_name, company=company,
        )

    # stage == "booked" (or unknown): release control back to the LLM.
    return None


# ── stage handlers ───────────────────────────────────────────────────────────
def _advance_collecting(state: dict, now: datetime, path) -> TurnResult:
    """
    Called on entry to collecting stage (from idle).
    Decide what to ask first: reason (type) or day?
    Never expose the appointment-type menu, never ask for something already said.
    """
    # Type AND day already in the first utterance ("Rückruf morgen bitte") →
    # nothing left to collect, offer real slots straight away.
    if state.get("appointment_type") is not None and state.get("preferred_day") is not None:
        return _offer_slots(state, now, path)

    # If type was already inferred from the first utterance, ask for day
    if state.get("appointment_type") is not None:
        state["last_asked_question"] = "day"
        return TurnResult(sched_phone.assert_phrase_safe(
            f"Alles klar, dann {_ack(state['appointment_type'])}. "
            "An welchem Tag würde es Ihnen passen?"
        ))

    # If time preference was detected in the first utterance, ask for reason
    if state.get("have_time_preference"):
        state["last_asked_question"] = "reason"
        state["reason_clarification_attempts"] = 0
        return _ask_reason_clarification_question(state)

    # Default: ask what the appointment is about (natural question, not a menu)
    state["last_asked_question"] = "reason"
    state["reason_clarification_attempts"] = 0
    return TurnResult(sched_phone.assert_phrase_safe(
        "Gerne, das kann ich für Sie vormerken. Worum geht es denn?"
    ))


def _collecting_turn(state: dict, text: str, now: datetime, path) -> TurnResult:
    """
    Handle a turn while collecting appointment details.
    Allow info in any order; never re-ask something already answered.
    """
    today = now.date()
    last_asked = state.get("last_asked_question")

    # ── Absorb a day / time window from this utterance first (any order) ──────
    # Even an answer to the *reason* question may carry the day ("Morgen bitte")
    # — remember it so it is never asked again.
    if state.get("preferred_day") is None:
        time_pref = parse_time_preference(text, now)
        day = _resolve_preferred_day(time_pref, text, today)
        if day is not None:
            state["preferred_day"] = day
            state["have_time_preference"] = True
        if time_pref.time_window:
            state["time_window"] = time_pref.time_window

    # ── Try to infer appointment type if missing ──────────────────────────────
    if state.get("appointment_type") is None:
        # Context-aware inference first, then keyword matching
        appt_type = _infer_appointment_type_from_context(text, state) or _classify_type(text)

        if appt_type is None:
            state["reason_clarification_attempts"] += 1
            if state["reason_clarification_attempts"] >= _MAX_ATTEMPTS:
                # Still unclear after one rephrase — continue as a callback
                # offer instead of restarting or dropping to the LLM mid-flow.
                return _fallback_to_callback(state, now, path)
            # Ask a clarifying question (varies by attempt, never repeated)
            state["last_asked_question"] = "reason"
            return _ask_reason_clarification_question(state)

        state["appointment_type"] = appt_type
        state["inferred_from"] = "caller_utterance"

    # ── We have enough info → offer real slots ────────────────────────────────
    if state.get("preferred_day") is not None:
        return _offer_slots(state, now, path)

    # ── Type known, day still open → ask for the day exactly once ─────────────
    if last_asked != "day":
        state["last_asked_question"] = "day"
        return TurnResult(sched_phone.assert_phrase_safe(
            f"Gut, dann {_ack(state['appointment_type'])}. "
            "An welchem Tag passt es Ihnen am besten?"
        ))

    # The day question was already asked and the answer contained no usable day —
    # don't repeat it (and never fall back to the reason question, which was
    # already answered). Keep the conversation moving with the earliest times.
    if not state.get("auto_offer_done"):
        state["auto_offer_done"] = True
        state["preferred_day"] = today
        return _offer_slots(
            state, now, path,
            intro="Dann schaue ich einfach, was als Nächstes frei ist. ",
        )

    # The earliest times were already tried too — a human sorts this out faster.
    _reset(state)
    return TurnResult(
        reply="ESCALATE: Terminwunsch — Zeitabsprache bitte durch Mitarbeiter"
    )


def _offer_slots(state: dict, now: datetime, path, intro: str = "") -> TurnResult:
    appt_type = state["appointment_type"]
    start = state.get("preferred_day") or now.date()
    day, slots = _first_available(appt_type, start, now, path)
    if not slots:
        _reset(state)
        return TurnResult(sched_phone.assert_phrase_safe(
            "Aktuell kann ich Ihnen leider keine passenden Zeiten anbieten. "
            "Ein Mitarbeiter kann sich bei Ihnen melden."
        ))

    # Apply time window preference if available (morning, afternoon, etc.)
    time_window = state.get("time_window")
    if time_window:
        filtered_slots = filter_by_time_window(slots, time_window)
        # If filtering eliminates all slots, fall back to unfiltered
        # (prefer some slots to none)
        if filtered_slots:
            slots = filtered_slots

    state["stage"] = "offered"
    state["offered_slots"] = slots
    state["offer_day"] = day
    state["select_attempts"] = 0
    offer = sched_phone.format_slot_offer(slots)
    # One natural follow-up question, phrased for the number of options.
    if len(slots) == 1:
        tail = " Passt das für Sie? Ich merke die Zeit dann unverbindlich vor."
    elif len(slots) == 2:
        tail = " Was passt Ihnen besser? Ich merke die Zeit dann unverbindlich vor."
    else:
        tail = " Was passt Ihnen am besten? Ich merke die Zeit dann unverbindlich vor."
    return TurnResult(sched_phone.assert_phrase_safe(intro + offer + tail))


def _offered_turn(
    state: dict, text: str, now: datetime, path,
    *, call_id, phone, caller_name, company,
) -> TurnResult:
    slots: list[Slot] = state.get("offered_slots", [])

    # Caller rejects the offered times → ask for another day.
    if _contains(text, _NEGATIVE_WORDS) and not _match_selection(text, slots):
        state["stage"] = "collecting"
        state["preferred_day"] = None
        state["offered_slots"] = []
        state["last_asked_question"] = "day"
        return TurnResult(sched_phone.assert_phrase_safe(
            "Kein Problem. An welchem anderen Tag würde es Ihnen passen?"
        ))

    chosen = _match_selection(text, slots)
    if chosen is None:
        # Generic "ja/passt" with exactly one offered slot → take it.
        if len(slots) == 1 and _contains(text, _AFFIRM_WORDS):
            chosen = slots[0]
        else:
            state["select_attempts"] += 1
            if state["select_attempts"] >= _MAX_ATTEMPTS:
                _reset(state)
                return None  # hand back to the LLM (safety valve)
            # Re-ask once, matched to how many times were actually offered.
            if len(slots) == 1:
                ask = ("Passt die genannte Zeit für Sie? "
                       "Sonst schaue ich gern nach einem anderen Tag.")
            elif len(slots) == 2:
                ask = ("Welche der beiden Zeiten passt Ihnen besser — "
                       "die erste oder die zweite?")
            else:
                ask = ("Welche der genannten Zeiten passt Ihnen — "
                       "die erste, die zweite oder die dritte?")
            return TurnResult(sched_phone.assert_phrase_safe(ask))

    # Explicit confirmation of a concrete slot → simulate the booking.
    duration = int((chosen.end - chosen.start).total_seconds() // 60)
    summary = sched_phone.build_confirmation_summary(
        appointment_type=state["appointment_type"],
        selected_slot_start=chosen.start,
        duration_minutes=duration,
    )
    result = create_simulated_appointment(
        appointment_type=state["appointment_type"],
        slot_start=chosen.start,
        caller_name=caller_name,
        company=company,
        phone=phone,
        topic=state.get("topic"),
        call_id=call_id,
        confirmation_summary=summary,
        now=now,
        path=path,
    )
    if result.ok:
        state["stage"] = "booked"
        return TurnResult(
            reply=sched_phone.assert_phrase_safe(
                summary + " Kann ich sonst noch etwas für Sie tun?"
            ),
            booked=True,
            appointment=result.appointment,
        )
    if result.reason == "duplicate":
        state["stage"] = "booked"
        return TurnResult(sched_phone.assert_phrase_safe(
            "Diesen Termin habe ich Ihnen bereits vorgemerkt. "
            "Kann ich sonst noch etwas für Sie tun?"
        ), booked=False)
    if result.reason == "conflict":
        # Slot no longer free — re-offer from the same day.
        state["stage"] = "collecting"
        state["offered_slots"] = []
        return _offer_slots(state, now, path)
    # invalid_slot / invalid_type / in_past — should not happen with offered slots.
    _reset(state)
    return TurnResult(sched_phone.assert_phrase_safe(
        "Das hat leider nicht geklappt. Ein Mitarbeiter meldet sich bei Ihnen."
    ))


def _reset(state: dict) -> None:
    state.update(new_state())
