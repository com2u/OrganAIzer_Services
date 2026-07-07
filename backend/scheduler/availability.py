"""
availability.py — deterministic business-hours and slot generation.

Business hours come from :data:`config.BUSINESS_HOURS`:

    Monday–Thursday 08:00–16:00
    Friday          08:00–13:00
    Saturday/Sunday closed

Slot generation is fully deterministic: the same ``(date, duration, now)`` always
yields the same list. Slots sit on a fixed 30-minute grid starting at opening
time and must fit entirely inside business hours. There is **no randomness** and
no hidden clock — callers inject ``now`` (a datetime) to exclude past slots;
omitting it means "generate the whole day".
"""
from __future__ import annotations

from datetime import date as date_cls, datetime, timedelta
from typing import Iterable, Optional

from .config import BUSINESS_HOURS, SLOT_GRANULARITY_MINUTES
from .models import Slot, validate_appointment_type


def business_hours_for(day: date_cls):
    """Return ``(open, close)`` times for *day*, or ``None`` if closed (weekend)."""
    return BUSINESS_HOURS.get(day.weekday())


def is_open(day: date_cls) -> bool:
    """True if the business is open at all on *day*."""
    return business_hours_for(day) is not None


def generate_slots(
    day: date_cls,
    duration_minutes: int,
    *,
    granularity_minutes: int = SLOT_GRANULARITY_MINUTES,
    now: Optional[datetime] = None,
) -> list[Slot]:
    """
    Deterministically generate every candidate :class:`Slot` on *day* for an
    appointment of *duration_minutes*.

    Empty on weekends or when the duration cannot fit inside business hours.
    Slots that would run past closing are excluded (a 60-minute slot on Friday
    cannot start after 12:00). If *now* is given, slots starting before *now* are
    excluded (so "today" never offers times already in the past).
    """
    hours = business_hours_for(day)
    if hours is None:
        return []
    open_t, close_t = hours

    open_dt = datetime.combine(day, open_t)
    close_dt = datetime.combine(day, close_t)
    step = timedelta(minutes=granularity_minutes)
    duration = timedelta(minutes=duration_minutes)

    slots: list[Slot] = []
    cursor = open_dt
    while cursor + duration <= close_dt:
        if now is None or cursor >= now:
            slots.append(Slot(cursor, cursor + duration))
        cursor += step
    return slots


def slots_overlap(
    a_start: datetime,
    a_end: datetime,
    b_start: datetime,
    b_end: datetime,
) -> bool:
    """True if half-open intervals ``[a_start, a_end)`` and ``[b_start, b_end)`` overlap."""
    return a_start < b_end and b_start < a_end


def _parse(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str)


def available_slots(
    day: date_cls,
    appointment_type: str,
    existing_records: Iterable[dict] = (),
    *,
    now: Optional[datetime] = None,
) -> list[Slot]:
    """
    Deterministic list of free :class:`Slot` on *day* for *appointment_type*,
    excluding any slot that would overlap an existing simulated appointment
    already assigned to that type's resource.

    *existing_records* are stored-record dicts (as produced by
    :meth:`Appointment.to_record`).
    """
    spec = validate_appointment_type(appointment_type)
    candidates = generate_slots(day, spec.duration_minutes, now=now)
    if not candidates:
        return []

    busy: list[tuple[datetime, datetime]] = []
    for rec in existing_records:
        if rec.get("assigned_resource") != spec.resource:
            continue
        if rec.get("status") != "simulated":
            continue
        try:
            busy.append((_parse(rec["selected_slot_start"]), _parse(rec["selected_slot_end"])))
        except (KeyError, ValueError):
            # A malformed record must not silently free up the calendar; skip it —
            # it simply provides no blocking window.
            continue

    return [
        slot
        for slot in candidates
        if not any(slots_overlap(slot.start, slot.end, b_start, b_end) for b_start, b_end in busy)
    ]


def filter_by_time_window(
    slots: list[Slot],
    time_window: Optional[tuple] = None,
) -> list[Slot]:
    """
    Filter slots by preferred time window (morning, afternoon, etc.).

    If *time_window* is (start_time, end_time), returns only slots that start
    within that window. Used by scheduler_dialogue to respect caller preferences
    like "morgens" or "nachmittags".

    Example:
        morning_slots = filter_by_time_window(all_slots, (time(8,0), time(12,0)))
    """
    if not time_window:
        return slots

    start_time, end_time = time_window
    return [
        slot
        for slot in slots
        if start_time <= slot.start.time() < end_time
    ]
