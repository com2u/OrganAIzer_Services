"""
phone.py — phone-facing German helper text for the appointment simulation.

The phone AI may *offer* and *note down* (vormerken) appointments. It must never
imply a guaranteed booking or that anything was written into a real calendar.
This module builds only safe, simulation-honest wording and provides a guard
(:func:`assert_phrase_safe`) that rejects forbidden claims.

Nothing here places a call, sends audio, or contacts a model — it just formats
strings for the voice layer to speak.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from .models import Appointment, Slot

# Phrases the AI is allowed to use (simulation-honest).
ALLOWED_PHRASES = (
    "Ich kann Ihnen einen Termin vormerken.",
    "Am Montag könnte ich Ihnen 9 Uhr oder 10 Uhr anbieten.",
    "Perfekt, ich habe den Termin unverbindlich vorgemerkt.",
)

# Phrases the AI must NEVER use — they imply a guarantee or a real calendar write.
# Matching is case-insensitive and substring-based. Note we intentionally do NOT
# ban the bare word "garantiert": the safe wording legitimately says
# "kein garantierter Termin" (NO guaranteed appointment).
FORBIDDEN_PHRASES = (
    "Termin ist garantiert",
    "kommt sicher",
    "im echten Kalender eingetragen",
    "im Kalender eingetragen",
    "fest eingetragen",
    "garantiert Ihnen",
    "Termin ist gebucht",
    "fest gebucht",
    "verbindlich gebucht",
)

# German weekday names, Monday-first (datetime.weekday()).
_WEEKDAYS_DE = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)

# German month names (index 0 = Januar) for natural spoken dates.
_MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)

# Human-friendly German labels for the v0.1 appointment types.
APPOINTMENT_TYPE_LABELS_DE = {
    "callback": "Rückruf",
    "remote_support": "Fernwartung",
    "technical_consultation": "technische Beratung",
    "on_site_visit_request": "Vor-Ort-Termin",
    "sales_consultation": "Vertriebsberatung",
    "maintenance_request": "Wartungstermin",
}


class UnsafePhoneWording(Exception):
    """Raised when generated phone wording contains a forbidden guarantee phrase."""


def assert_phrase_safe(text: str) -> str:
    """
    Return *text* unchanged if safe; raise :class:`UnsafePhoneWording` if it
    contains a forbidden phrase. Use this on any wording before it is spoken.
    """
    lowered = text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in lowered:
            raise UnsafePhoneWording(f"Forbidden phone phrase detected: {phrase!r}")
    return text


def _format_time_de(start: datetime) -> str:
    """e.g. '9 Uhr' / '9:30 Uhr' — no leading zeros, so TTS reads it naturally."""
    if start.minute == 0:
        return f"{start.hour} Uhr"
    return f"{start.hour}:{start.minute:02d} Uhr"


def _format_day_de(start: datetime) -> str:
    """e.g. 'Dienstag, den 1. Juli' — spoken date, no year (offers are ≤ 14 days out)."""
    weekday = _WEEKDAYS_DE[start.weekday()]
    return f"{weekday}, den {start.day}. {_MONTHS_DE[start.month - 1]}"


def _format_slot_de(start: datetime) -> str:
    """e.g. 'Dienstag, den 1. Juli um 9 Uhr'."""
    return f"{_format_day_de(start)} um {_format_time_de(start)}"


def _slot_start(slot) -> datetime:
    """Accept a Slot dataclass or a plain (start, end) tuple."""
    if isinstance(slot, Slot):
        return slot.start
    return slot[0]


def _join_oder(parts: list[str]) -> str:
    """'9 Uhr' | '9 Uhr oder 10 Uhr' | '9 Uhr, 9:30 Uhr oder 10 Uhr'."""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + f" oder {parts[-1]}"


def format_slot_offer(slots: Iterable) -> str:
    """
    Build a safe German sentence offering the given slots. Accepts :class:`Slot`
    objects (as returned by the service) or ``(start, end)`` tuples. If no slots
    are available, returns an honest "no slots" sentence.

    The result is ONE natural spoken sentence (never a bullet list — it is read
    aloud by TTS), e.g. "Am Montag, den 6. Juli könnte ich Ihnen 9 Uhr,
    9:30 Uhr oder 10 Uhr anbieten."
    """
    slots = list(slots)
    if not slots:
        return assert_phrase_safe(
            "Aktuell kann ich Ihnen leider keine passenden Zeiten anbieten."
        )
    starts = [_slot_start(slot) for slot in slots]
    if len({s.date() for s in starts}) == 1:
        times = _join_oder([_format_time_de(s) for s in starts])
        sentence = f"Am {_format_day_de(starts[0])} könnte ich Ihnen {times} anbieten."
    else:
        when = _join_oder([_format_slot_de(s) for s in starts])
        sentence = f"Ich könnte Ihnen {when} anbieten."
    return assert_phrase_safe(sentence)


def build_confirmation_summary(
    appointment: Optional[Appointment] = None,
    *,
    appointment_type: Optional[str] = None,
    selected_slot_start: Optional[datetime] = None,
    duration_minutes: Optional[int] = None,
) -> str:
    """
    Build the safe German confirmation summary for a vorgemerkter (noted) slot.

    Pass either an :class:`Appointment` or the individual fields. The wording
    explicitly frames the result as a *Vormerkung* (a note), never a guarantee.
    """
    if appointment is not None:
        appointment_type = appointment.appointment_type
        selected_slot_start = datetime.fromisoformat(appointment.selected_slot_start)
        end = datetime.fromisoformat(appointment.selected_slot_end)
        duration_minutes = int((end - selected_slot_start).total_seconds() // 60)

    if appointment_type is None or selected_slot_start is None:
        raise ValueError("appointment or (appointment_type + selected_slot_start) required")

    label = APPOINTMENT_TYPE_LABELS_DE.get(appointment_type, appointment_type)
    when = _format_slot_de(selected_slot_start)
    duration_part = f" ({duration_minutes} Minuten)" if duration_minutes else ""

    summary = (
        f"Perfekt, ich habe den Termin unverbindlich vorgemerkt: "
        f"{label} am {when}{duration_part}. "
        "Unser Team bestätigt ihn anschließend."
    )
    return assert_phrase_safe(summary)
