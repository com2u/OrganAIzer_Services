"""
service.py — the Scheduler's internal API.

This is the layer the rest of the system (including the phone AI) must call. It
ties together the catalogue (:mod:`.config`), the record model (:mod:`.models`),
deterministic availability (:mod:`.availability`) and the JSONL store
(:mod:`.store_jsonl`), and enforces the two safety checks:

    * conflict prevention — a resource cannot hold two overlapping appointments
    * duplicate prevention — the same caller + topic + type + start time cannot
      be booked twice

Public API
----------
    list_available_slots(day, appointment_type, *, limit=None, now=None, path=None)
    create_simulated_appointment(*, appointment_type, slot_start, ...)
    list_appointments(*, path=None, appointment_type=None, resource=None, call_id=None)

Everything produced here is a SIMULATION: records are stamped
``status = "simulated"`` and nothing is written to a real calendar, email, or
database. The AI must NOT invent availability — it must ask
:func:`list_available_slots` and only confirm a slot returned here.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timezone
from typing import Optional

from core.phone_mask import mask_number

from .availability import available_slots, generate_slots, slots_overlap
from .config import DEFAULT_SOURCE, STATUS_SIMULATED
from .models import Appointment, Slot, validate_appointment_type
from .store_jsonl import PathLike, append_appointment, read_appointments

logger = logging.getLogger(__name__)


@dataclass
class BookingResult:
    """Outcome of a :func:`create_simulated_appointment` call."""

    ok: bool
    # "booked" | "conflict" | "duplicate" | "invalid_type" | "invalid_slot" | "in_past"
    reason: str
    appointment: Optional[Appointment] = None
    conflicting_id: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _duplicate_key(
    phone_masked: Optional[str],
    caller_name: Optional[str],
    topic: Optional[str],
    appointment_type: str,
    slot_start_iso: str,
) -> str:
    """
    Deterministic key identifying "the same booking": caller (masked phone if
    available, else lower-cased name) + topic + type + start time. Never
    incorporates a raw phone number.
    """
    identity = (phone_masked or (caller_name or "").strip().lower() or "anon")
    topic_norm = (topic or "").strip().lower()
    payload = f"{identity}|{topic_norm}|{appointment_type}|{slot_start_iso}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _mask(phone: Optional[str]) -> Optional[str]:
    """
    Mask a raw phone number using the canonical masking helper so the scheduler
    never stores or returns a raw number. Returns ``None`` for empty input.

    Uses :mod:`core.phone_mask` (a neutral utility) — the scheduler must never
    depend on the voice stack.
    """
    if not phone:
        return None
    return mask_number(phone)


def list_available_slots(
    day: date_cls,
    appointment_type: str,
    *,
    limit: Optional[int] = None,
    now: Optional[datetime] = None,
    path: Optional[PathLike] = None,
) -> list[Slot]:
    """
    Return free :class:`Slot`s on *day* for *appointment_type*, honouring existing
    simulated appointments. Deterministic given (day, type, store contents, now).

    *limit* caps the number returned (``None`` = all). *now* excludes past slots.
    """
    validate_appointment_type(appointment_type)
    existing = read_appointments(path)
    free = available_slots(day, appointment_type, existing, now=now)
    return free[:limit] if limit is not None else free


def create_simulated_appointment(
    *,
    appointment_type: str,
    slot_start: datetime,
    caller_name: Optional[str] = None,
    company: Optional[str] = None,
    phone: Optional[str] = None,
    topic: Optional[str] = None,
    notes: Optional[str] = None,
    source: str = DEFAULT_SOURCE,
    call_id: Optional[str] = None,
    confirmation_summary: Optional[str] = None,
    now: Optional[datetime] = None,
    path: Optional[PathLike] = None,
) -> BookingResult:
    """
    Simulate booking an appointment and append it to the JSONL store.

    *phone* may be a raw number; only its masked form is ever stored. *slot_start*
    must correspond to a real slot on that day's business-hours grid, must not lie
    in the past (when *now* is supplied), must not conflict with an existing
    appointment on the same resource, and must not duplicate an existing booking
    for the same caller + topic + type.
    """
    try:
        spec = validate_appointment_type(appointment_type)
    except ValueError:
        return BookingResult(ok=False, reason="invalid_type")

    if now is not None and slot_start < now:
        return BookingResult(ok=False, reason="in_past")

    day = slot_start.date()
    slot_end = None
    # The start must be a valid generated slot for this type/day — this enforces
    # business hours, weekends, Friday's early close, and grid alignment.
    for slot in generate_slots(day, spec.duration_minutes):
        if slot.start == slot_start:
            slot_end = slot.end
            break
    if slot_end is None:
        return BookingResult(ok=False, reason="invalid_slot")

    start_iso = slot_start.isoformat()
    end_iso = slot_end.isoformat()
    phone_masked = _mask(phone)

    existing = read_appointments(path)
    dup_key = _duplicate_key(phone_masked, caller_name, topic, appointment_type, start_iso)

    for rec in existing:
        if rec.get("status") != STATUS_SIMULATED:
            continue
        rec_key = _duplicate_key(
            rec.get("phone_masked"),
            rec.get("caller_name"),
            rec.get("topic"),
            rec.get("appointment_type", ""),
            rec.get("selected_slot_start", ""),
        )
        if rec_key == dup_key:
            return BookingResult(ok=False, reason="duplicate", conflicting_id=rec.get("id"))

        if rec.get("assigned_resource") == spec.resource:
            try:
                r_start = datetime.fromisoformat(rec["selected_slot_start"])
                r_end = datetime.fromisoformat(rec["selected_slot_end"])
            except (KeyError, ValueError):
                continue
            if slots_overlap(slot_start, slot_end, r_start, r_end):
                return BookingResult(ok=False, reason="conflict", conflicting_id=rec.get("id"))

    appointment = Appointment(
        id=str(uuid.uuid4()),
        created_at=_now_iso(),
        source=source,
        caller_name=caller_name,
        company=company,
        phone_masked=phone_masked,
        topic=topic,
        appointment_type=appointment_type,
        selected_slot_start=start_iso,
        selected_slot_end=end_iso,
        assigned_resource=spec.resource,
        notes=notes,
        confirmation_summary=confirmation_summary,
        call_id=call_id,
    )
    append_appointment(appointment.to_record(), path)
    logger.info(
        "Simulated appointment booked: type=%s resource=%s start=%s (id=%s)",
        appointment_type,
        spec.resource,
        start_iso,
        appointment.id,
    )
    return BookingResult(ok=True, reason="booked", appointment=appointment)


def list_appointments(
    *,
    path: Optional[PathLike] = None,
    appointment_type: Optional[str] = None,
    resource: Optional[str] = None,
    call_id: Optional[str] = None,
) -> list[dict]:
    """
    Read stored simulated appointments, optionally filtered by type, resource, or
    call_id. Returns record dicts in stored (chronological append) order.
    """
    records = read_appointments(path)
    if appointment_type is not None:
        records = [r for r in records if r.get("appointment_type") == appointment_type]
    if resource is not None:
        records = [r for r in records if r.get("assigned_resource") == resource]
    if call_id is not None:
        records = [r for r in records if r.get("call_id") == call_id]
    return records
