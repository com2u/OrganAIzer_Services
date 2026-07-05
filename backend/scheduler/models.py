"""
models.py — appointment record model, the Slot value type, and validation.

The catalogue (types/resources/hours) lives in :mod:`.config`; this module owns
the *shape* of a stored record and the rules that keep it honest. Every record
is stamped ``status = "simulated"`` and ``schema_version = SCHEMA_VERSION``.

Raw phone numbers are never part of a record — only ``phone_masked`` (or
``None``) is stored.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional

from .config import (
    APPOINTMENT_TYPES,
    AppointmentTypeSpec,
    SCHEMA_VERSION,
    STATUS_SIMULATED,
)

__all__ = [
    "Slot",
    "Appointment",
    "RECORD_FIELDS",
    "validate_appointment_type",
    "validate_record",
]


@dataclass(frozen=True)
class Slot:
    """A concrete time window. Times are naive local datetimes in v0.1."""

    start: datetime
    end: datetime

    @property
    def start_iso(self) -> str:
        return self.start.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end.isoformat()


# Canonical field order for a stored record.
RECORD_FIELDS: tuple[str, ...] = (
    "status",
    "schema_version",
    "id",
    "created_at",
    "source",
    "caller_name",
    "company",
    "phone_masked",
    "topic",
    "appointment_type",
    "selected_slot_start",
    "selected_slot_end",
    "assigned_resource",
    "notes",
    "confirmation_summary",
    "call_id",
)


@dataclass
class Appointment:
    """
    A single simulated appointment.

    ``phone_masked`` holds the masked form ("+49******7890") or ``None`` — the
    raw number is never accepted here and never stored.
    """

    id: str
    created_at: str
    source: str
    caller_name: Optional[str]
    company: Optional[str]
    phone_masked: Optional[str]
    topic: Optional[str]
    appointment_type: str
    selected_slot_start: str
    selected_slot_end: str
    assigned_resource: str
    notes: Optional[str] = None
    confirmation_summary: Optional[str] = None
    call_id: Optional[str] = None
    status: str = STATUS_SIMULATED
    schema_version: str = SCHEMA_VERSION

    def to_record(self) -> dict:
        """Return an ordered dict matching :data:`RECORD_FIELDS`."""
        raw = asdict(self)
        return {key: raw[key] for key in RECORD_FIELDS}


def validate_appointment_type(appointment_type: str) -> AppointmentTypeSpec:
    """Return the spec for *appointment_type* or raise ``ValueError``."""
    spec = APPOINTMENT_TYPES.get(appointment_type)
    if spec is None:
        raise ValueError(
            f"Unknown appointment_type {appointment_type!r}. "
            f"Known types: {', '.join(sorted(APPOINTMENT_TYPES))}"
        )
    return spec


def validate_record(record: dict) -> None:
    """
    Validate a stored/loaded record. Raises ``ValueError`` on any problem.

    Enforces the v0.1 invariants: all required fields present, status is
    "simulated", the appointment type is known, the assigned resource matches
    that type's resource, and ``phone_masked`` is either null or actually masked
    (contains "*"). This is the last line of defence against a raw phone number
    reaching disk.
    """
    missing = [f for f in RECORD_FIELDS if f not in record]
    if missing:
        raise ValueError(f"Record missing fields: {', '.join(missing)}")

    if record["status"] != STATUS_SIMULATED:
        raise ValueError(
            f"Record status must be {STATUS_SIMULATED!r}, got {record['status']!r}"
        )

    spec = validate_appointment_type(record["appointment_type"])
    if record["assigned_resource"] != spec.resource:
        raise ValueError(
            f"assigned_resource {record['assigned_resource']!r} does not match "
            f"resource {spec.resource!r} for type {record['appointment_type']!r}"
        )

    phone_masked = record.get("phone_masked")
    if phone_masked is not None and "*" not in str(phone_masked):
        raise ValueError(
            "phone_masked must be masked (contain '*') or be null; "
            "raw phone numbers must never be stored"
        )
