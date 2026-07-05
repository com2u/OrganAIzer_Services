"""
config.py — the single source of truth for what the Scheduler *owns*.

Business hours, the appointment-type catalogue (durations + resources), the
resource list, the slot grid granularity, and the storage location all live
here. Nothing in this module performs I/O beyond resolving a path from the
environment; it is pure data so it can be imported anywhere without side effects.

Scheduler v0.1 is a SIMULATION. See docs/scheduler-architecture.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

# ── Versioning / status ──────────────────────────────────────────────────────
# Bump when the on-disk record shape changes. String so "0.1" reads clearly
# alongside the "Scheduler v0.1" milestone.
SCHEMA_VERSION = "0.1"

# The ONLY status a v0.1 record may carry — there is no real booking path yet.
STATUS_SIMULATED = "simulated"

# Default provenance stamped on records created without an explicit source.
DEFAULT_SOURCE = "phone_ai_simulation"

# Slot grid granularity in minutes. 30 divides every v0.1 duration (30 / 60).
SLOT_GRANULARITY_MINUTES = 30


# ── Resources ────────────────────────────────────────────────────────────────
# Simulated resources — placeholders, not real people or calendars.
RESOURCES: tuple[str, ...] = (
    "technician_sim_1",
    "remote_support_queue",
    "sales_queue",
)


# ── Appointment catalogue ────────────────────────────────────────────────────
@dataclass(frozen=True)
class AppointmentTypeSpec:
    """Duration (minutes) and the resource that serves a given appointment type."""

    duration_minutes: int
    resource: str


# Keep in sync with docs/scheduler-architecture.md and docs/appointment-simulation.md.
APPOINTMENT_TYPES: dict[str, AppointmentTypeSpec] = {
    "callback": AppointmentTypeSpec(30, "remote_support_queue"),
    "remote_support": AppointmentTypeSpec(30, "remote_support_queue"),
    "technical_consultation": AppointmentTypeSpec(30, "technician_sim_1"),
    "on_site_visit_request": AppointmentTypeSpec(60, "technician_sim_1"),
    "sales_consultation": AppointmentTypeSpec(30, "sales_queue"),
    "maintenance_request": AppointmentTypeSpec(60, "technician_sim_1"),
}

# Every resource referenced by a type must be a known simulated resource.
assert all(spec.resource in RESOURCES for spec in APPOINTMENT_TYPES.values()), (
    "APPOINTMENT_TYPES references an unknown resource"
)


# ── Business hours (local Teleprofi time) ────────────────────────────────────
# weekday() -> (open, close). Missing weekdays (5 Sat, 6 Sun) are closed.
#   Monday–Thursday 08:00–16:00, Friday 08:00–13:00, weekend closed.
BUSINESS_HOURS: dict[int, tuple[time, time]] = {
    0: (time(8, 0), time(16, 0)),  # Monday
    1: (time(8, 0), time(16, 0)),  # Tuesday
    2: (time(8, 0), time(16, 0)),  # Wednesday
    3: (time(8, 0), time(16, 0)),  # Thursday
    4: (time(8, 0), time(13, 0)),  # Friday
    # Saturday (5) and Sunday (6): closed — intentionally absent.
}


# ── Storage location ─────────────────────────────────────────────────────────
# Default JSONL store. backend/data/ is gitignored, so simulated appointment
# data never enters git. Override with the SCHEDULER_STORE_PATH env var (or the
# path argument on store/service functions, used by tests).
_DEFAULT_STORE = Path(__file__).parent.parent / "data" / "scheduler" / "appointments.jsonl"


def default_store_path() -> Path:
    """Resolve the default JSONL store path (env var wins over the built-in default)."""
    env = os.environ.get("SCHEDULER_STORE_PATH")
    return Path(env) if env else _DEFAULT_STORE
