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

_TYPE_LABELS_DE = sched_phone.APPOINTMENT_TYPE_LABELS_DE

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
        "stage": "idle",           # idle | collecting | offered | booked
        "appointment_type": None,
        "topic": None,
        "preferred_day": None,     # date
        "offered_slots": [],       # list[Slot]
        "offer_day": None,         # date the offered slots belong to
        "classify_attempts": 0,
        "select_attempts": 0,
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


def _label(appt_type: str) -> str:
    return _TYPE_LABELS_DE.get(appt_type, appt_type)


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
        state["appointment_type"] = _classify_type(text)
        # A day may already be in the first utterance ("Rückruf morgen bitte").
        state["preferred_day"] = _parse_preferred_day(text, today)
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
    """Ask the next single missing detail, or move to offering when ready."""
    if state.get("appointment_type") is None:
        return TurnResult(sched_phone.assert_phrase_safe(
            "Gerne, das kann ich für Sie vormerken. Geht es um einen Rückruf, "
            "eine Fernwartung, einen Vor-Ort-Termin, eine Beratung oder eine Wartung?"
        ))
    if state.get("preferred_day") is None:
        return TurnResult(sched_phone.assert_phrase_safe(
            f"Alles klar, {_label(state['appointment_type'])}. An welchem Tag "
            "würde es Ihnen am besten passen?"
        ))
    return _offer_slots(state, now, path)


def _collecting_turn(state: dict, text: str, now: datetime, path) -> TurnResult:
    today = now.date()
    if state.get("appointment_type") is None:
        appt_type = _classify_type(text)
        if appt_type is None:
            state["classify_attempts"] += 1
            if state["classify_attempts"] >= _MAX_ATTEMPTS:
                _reset(state)
                return TurnResult(sched_phone.assert_phrase_safe(
                    "Ich verbinde Sie dazu am besten mit einem Mitarbeiter."
                ))
            return TurnResult(sched_phone.assert_phrase_safe(
                "Damit ich das richtig vormerke: Rückruf, Fernwartung, "
                "Vor-Ort-Termin, Beratung oder Wartung?"
            ))
        state["appointment_type"] = appt_type

    if state.get("preferred_day") is None:
        day = _parse_preferred_day(text, today)
        if day is None:
            # No parseable day — default to the next open day rather than loop.
            day = today
        state["preferred_day"] = day

    return _offer_slots(state, now, path)


def _offer_slots(state: dict, now: datetime, path) -> TurnResult:
    appt_type = state["appointment_type"]
    start = state.get("preferred_day") or now.date()
    day, slots = _first_available(appt_type, start, now, path)
    if not slots:
        _reset(state)
        return TurnResult(sched_phone.assert_phrase_safe(
            "Aktuell kann ich Ihnen leider keine passenden Zeiten anbieten. "
            "Ein Mitarbeiter kann sich bei Ihnen melden."
        ))
    state["stage"] = "offered"
    state["offered_slots"] = slots
    state["offer_day"] = day
    state["select_attempts"] = 0
    offer = sched_phone.format_slot_offer(slots)
    return TurnResult(sched_phone.assert_phrase_safe(
        offer + " Welche Zeit passt Ihnen? Ich merke sie Ihnen dann unverbindlich vor."
    ))


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
                return None  # hand back to the LLM
            return TurnResult(sched_phone.assert_phrase_safe(
                "Welche der genannten Zeiten passt Ihnen — die erste, zweite "
                "oder dritte?"
            ))

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
