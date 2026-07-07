#!/usr/bin/env python3
"""
seed_scheduler_demo_calendar.py — populate the Scheduler JSONL store with
realistic fake appointments for testing and evaluation.

Safe for repeated runs: checks for a seeding marker in the store (if records
exist with source="scheduler_demo_seed") and skips re-seeding unless --force
is passed. All appointments are marked status="simulated" and use masked phone
numbers only (never raw).

Usage:
    cd backend
    python scripts/seed_scheduler_demo_calendar.py [--force] [--path <path>]

Options:
    --force           Ignore existing seed marker, re-seed from scratch
    --path <path>     Write to a custom store path instead of the default
    --dry-run         Print what would be seeded without writing
    --help            Show this message
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, date as date_cls, timezone
from pathlib import Path

# Add backend to path so we can import scheduler modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scheduler import (
    Appointment,
    create_simulated_appointment,
    read_appointments,
    default_store_path,
    APPOINTMENT_TYPES,
)
from core.phone_mask import mask_number


# ── Fake data generators ────────────────────────────────────────────────────
_DEMO_CALLER_NAMES = [
    "Max Mustermann",
    "Erika Musterfrau",
    "Stefan Bauer",
    "Anna Schmidt",
    "Thomas Weber",
    "Julia Müller",
    "Robert Fischer",
    "Sandra Wagner",
    "Klaus Hoffmann",
    "Petra Schönberg",
]

_DEMO_COMPANIES = [
    "Acme GmbH",
    "TechStart AG",
    "Innovation Labs",
    "Digital Solutions",
    "Cloud Services Ltd.",
    "Smart Networks",
    None,  # some have no company
]

_DEMO_TOPICS = {
    "callback": [
        "Anruf bezüglich Angebot",
        "Rückruf für Beratung",
        "Terminbestätigung",
        "Folgeanruf",
    ],
    "remote_support": [
        "Fernwartung für Netzwerk",
        "Fernzugriff zur Fehlersuche",
        "Remote Troubleshooting",
        "VPN Setup Unterstützung",
    ],
    "technical_consultation": [
        "Technische Beratung zu Netzwerk",
        "System-Architektur Konsultation",
        "Optimierungsgespräch",
        "Sicherheits-Review",
    ],
    "on_site_visit_request": [
        "Vor-Ort Installation geplant",
        "Hardware-Austausch erforderlich",
        "Neue Installation am Standort",
        "Verkabelungs-Projekt",
    ],
    "sales_consultation": [
        "Anfrage zu neuen Produkten",
        "Lizenz-Upgrade Gespräch",
        "Vertriebsgespräch",
        "Angebots-Besprechung",
    ],
    "maintenance_request": [
        "Wartungsvertrag verlängern",
        "Präventive Wartung",
        "Wartungsfenster vereinbaren",
        "Support-Vertrag anpassen",
    ],
}

_DEMO_PHONE_NUMBERS = [
    "+4930123456789",
    "+4915112345678",
    "+49201456789012",
    "+4969555666777",
    "+4989999888777",
    "+49711222333444",
    "+4933012345678",
    "+4944015555666",
]


def _mask_phone(number: str) -> str:
    """Safely mask a phone number (no raw numbers in output)."""
    return mask_number(number)


def _generate_demo_appointments(
    start_date: date_cls,
    num_weeks: int = 2,
) -> list[dict]:
    """
    Generate realistic fake appointments spanning num_weeks working days.

    Each week has 5 working days (Mon–Fri). Appointments are distributed across:
    - All 6 appointment types
    - Business hours only (8–16 Mon–Thu, 8–13 Fri)
    - Staggered throughout the day to avoid all clustering at 8:00

    Returns list of dicts ready to pass to create_simulated_appointment().
    """
    from scheduler.availability import generate_slots
    from scheduler.config import APPOINTMENT_TYPES as APPT_TYPES, BUSINESS_HOURS

    appointments = []

    # Walk through num_weeks * 5 working days
    current = start_date
    appts_per_type = 3  # 3 appointments per type, distributed across the period
    appointment_type_list = list(APPT_TYPES.keys())

    # Pre-compute all available slots to pick from intelligently
    all_slots_by_day = {}
    working_days = []

    for _ in range(num_weeks * 7):  # Iterate through enough days to cover the period
        if current.weekday() in BUSINESS_HOURS:  # Working day
            working_days.append(current)
            all_slots_by_day[current] = {
                appt_type: generate_slots(current, APPT_TYPES[appt_type].duration_minutes)
                for appt_type in appointment_type_list
            }
        current += timedelta(days=1)

    # Distribute appointments: cycle through types, pick a day and slot
    slot_idx = 0
    taken: dict[date_cls, list] = {}  # day → [(start, end)] already picked
    for type_idx, appt_type in enumerate(appointment_type_list):
        for seeding_iter in range(appts_per_type):
            # Spread across working days (simple: every N days)
            day_idx = (type_idx * appts_per_type + seeding_iter) % len(working_days)
            day = working_days[day_idx]

            # Get available slots for this type on this day
            slots = all_slots_by_day.get(day, {}).get(appt_type, [])
            if not slots:
                continue  # Skip if no slots available (shouldn't happen)

            # Pick a slot (round-robin through the day to avoid all clustering
            # at 8:00), skipping any that overlaps an appointment already
            # picked for that day — the service rejects conflicts at write time.
            picked = taken.setdefault(day, [])
            slot = None
            for step in range(1, len(slots) + 1):
                cand = slots[(slot_idx + step) % len(slots)]
                if not any(cand.start < e and s < cand.end for s, e in picked):
                    slot_idx = (slot_idx + step) % len(slots)
                    slot = cand
                    break
            if slot is None:
                continue  # Day fully booked — skip rather than force a conflict
            picked.append((slot.start, slot.end))

            # Build the appointment record
            appt_dict = {
                "appointment_type": appt_type,
                "slot_start": slot.start,
                "caller_name": _DEMO_CALLER_NAMES[
                    (type_idx * appts_per_type + seeding_iter) % len(_DEMO_CALLER_NAMES)
                ],
                "company": _DEMO_COMPANIES[
                    (type_idx * appts_per_type + seeding_iter) % len(_DEMO_COMPANIES)
                ],
                "phone_idx": (type_idx * appts_per_type + seeding_iter) % len(_DEMO_PHONE_NUMBERS),
                "topic": _DEMO_TOPICS[appt_type][
                    (type_idx * appts_per_type + seeding_iter) % len(_DEMO_TOPICS[appt_type])
                ],
                "call_id": str(uuid.uuid4()),
            }
            appointments.append(appt_dict)

    return appointments


def _check_seed_marker(path: Path) -> bool:
    """Check if this store has been seeded before (looks for demo seed marker)."""
    if not path.exists():
        return False

    records = read_appointments(path)
    return any(r.get("source") == "scheduler_demo_seed" for r in records)


def seed_calendar(
    path: Path,
    force: bool = False,
    dry_run: bool = False,
    start_date: date_cls | None = None,
) -> int:
    """
    Seed the scheduler store with fake appointments.

    Args:
        path: JSONL file path
        force: If True, ignore existing seed marker and re-seed
        dry_run: If True, print but don't write
        start_date: First day to seed from (default: today)

    Returns:
        Number of appointments seeded (0 if skipped)
    """
    if start_date is None:
        start_date = datetime.now(timezone.utc).date()

    # Check for existing seed marker
    if path.exists() and not force and _check_seed_marker(path):
        print(f"ℹ️  Scheduler already seeded (found demo seed marker). Use --force to re-seed.")
        return 0

    # Generate fake appointments
    demo_appts = _generate_demo_appointments(start_date, num_weeks=2)

    if dry_run:
        print(f"\n📋 DRY RUN: would seed {len(demo_appts)} appointments to {path}\n")
        for appt_dict in demo_appts:
            print(
                f"  {appt_dict['appointment_type']:25} "
                f"{appt_dict['caller_name']:20} "
                f"{appt_dict['slot_start'].strftime('%a %H:%M')}"
            )
        print()
        return len(demo_appts)

    # Create the store directory if needed
    path.parent.mkdir(parents=True, exist_ok=True)

    # Seed appointments (using the service layer)
    seeded_count = 0
    for appt_dict in demo_appts:
        # Get the raw phone number from the pre-selected index
        raw_phone = _DEMO_PHONE_NUMBERS[appt_dict["phone_idx"]]

        result = create_simulated_appointment(
            appointment_type=appt_dict["appointment_type"],
            slot_start=appt_dict["slot_start"],
            caller_name=appt_dict["caller_name"],
            company=appt_dict["company"],
            phone=raw_phone,  # Raw number; masked internally by service
            topic=appt_dict["topic"],
            call_id=appt_dict["call_id"],
            path=path,
            source="scheduler_demo_seed",  # Marker for idempotency
        )
        if result.ok:
            seeded_count += 1
        else:
            print(f"⚠️  Failed to seed: {result.reason}")

    print(f"✅ Seeded {seeded_count} appointments to {path}")
    print(f"📁 Store size: {path.stat().st_size} bytes")

    return seeded_count


def main():
    parser = argparse.ArgumentParser(
        description="Seed the Scheduler JSONL store with realistic fake appointments."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-seed even if demo seed marker exists",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Custom store path (default: from config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be seeded without writing",
    )

    args = parser.parse_args()

    path = args.path or default_store_path()
    print(f"🌱 Seeding Scheduler demo calendar")
    print(f"📍 Store: {path}")

    count = seed_calendar(
        path=path,
        force=args.force,
        dry_run=args.dry_run,
    )

    return 0 if count >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
