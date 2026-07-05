"""
scheduler — OrganAIzer phone-AI appointment scheduling (SIMULATION ONLY, v0.1).

A core internal service that owns availability, appointment types, durations,
resources, conflict/duplicate rules, and simulated booking records. It produces
deterministic, local, in-file appointment *simulations* and intentionally does
NOT touch Google Calendar, Outlook, any external calendar API, email, a
database, COMtrexx, or FreeSWITCH. Every record carries ``status == "simulated"``.

The AI must not invent availability — it must ask :func:`list_available_slots`
and only confirm a slot returned by the service. See
``docs/scheduler-architecture.md`` and ``docs/appointment-simulation.md``.
"""
from __future__ import annotations

from .config import (
    APPOINTMENT_TYPES,
    RESOURCES,
    SCHEMA_VERSION,
    STATUS_SIMULATED,
    AppointmentTypeSpec,
    default_store_path,
)
from .models import (
    Appointment,
    Slot,
    validate_appointment_type,
    validate_record,
)
from .availability import (
    available_slots,
    business_hours_for,
    generate_slots,
    is_open,
    slots_overlap,
)
from .store_jsonl import (
    MalformedAppointmentLine,
    append_appointment,
    read_appointments,
    store_path,
)
from .service import (
    BookingResult,
    create_simulated_appointment,
    list_appointments,
    list_available_slots,
)

__all__ = [
    # config / catalogue
    "APPOINTMENT_TYPES",
    "RESOURCES",
    "SCHEMA_VERSION",
    "STATUS_SIMULATED",
    "AppointmentTypeSpec",
    "default_store_path",
    # models
    "Appointment",
    "Slot",
    "validate_appointment_type",
    "validate_record",
    # availability
    "available_slots",
    "business_hours_for",
    "generate_slots",
    "is_open",
    "slots_overlap",
    # store
    "MalformedAppointmentLine",
    "append_appointment",
    "read_appointments",
    "store_path",
    # service (internal API)
    "BookingResult",
    "create_simulated_appointment",
    "list_appointments",
    "list_available_slots",
]
