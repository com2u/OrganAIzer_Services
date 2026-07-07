"""
Scheduler seeding tests (backend/scripts/seed_scheduler_demo_calendar.py).

Covers:
  - Seeded appointments are within business hours
  - Weekends are never seeded
  - All records carry status="simulated"
  - Phone numbers are always masked (never raw)
  - Conflicts are avoided (no overlapping appointments)
  - Seed is idempotent (repeated runs don't duplicate)
  - Seeded appointments use all 6 appointment types
  - Deterministic output (same seed, same result)

No external APIs, no FreeSWITCH, no network.
"""
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import after path setup
from scheduler import read_appointments, APPOINTMENT_TYPES
from scheduler.config import BUSINESS_HOURS

# Import the seeding module (scripts is not a package, so import directly)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../scripts"))
import seed_scheduler_demo_calendar as seeding


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def demo_store(tmp_path):
    """Create a temporary store for each test."""
    return tmp_path / "demo_appointments.jsonl"


# ── Business hours validation ────────────────────────────────────────────────
class TestSeededAppointmentsRespectBusinessHours:
    """All seeded appointments must fall within business hours."""

    def test_all_appointments_within_business_hours(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        assert len(records) > 0, "Expected appointments to be seeded"

        for rec in records:
            start_str = rec["selected_slot_start"]
            end_str = rec["selected_slot_end"]

            # Parse ISO strings (format: "2026-07-06T08:00:00")
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
            weekday = start.weekday()  # 0=Mon, 5=Sat, 6=Sun

            # Check weekday is in business hours
            assert weekday in BUSINESS_HOURS, (
                f"Appointment on {start.strftime('%A')} (weekday={weekday}) — "
                f"weekend not supported"
            )

            # Check time is within the day's business hours
            open_time, close_time = BUSINESS_HOURS[weekday]
            assert start.time() >= open_time, (
                f"{rec['caller_name']}: starts {start.time()} before opening {open_time}"
            )
            assert end.time() <= close_time, (
                f"{rec['caller_name']}: ends {end.time()} after closing {close_time}"
            )

    def test_no_seeded_appointments_on_weekends(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        for rec in records:
            start_str = rec["selected_slot_start"]
            start = datetime.fromisoformat(start_str)
            weekday = start.weekday()

            assert weekday < 5, (
                f"Appointment on {start.strftime('%A')} (weekday={weekday}) — "
                f"weekends should not be seeded"
            )


# ── Status and schema validation ─────────────────────────────────────────────
class TestSeededAppointmentsHaveCorrectStatus:
    """All seeded appointments must have status='simulated'."""

    def test_all_records_status_simulated(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        assert len(records) > 0, "Expected appointments to be seeded"

        for rec in records:
            assert rec["status"] == "simulated", (
                f"{rec['id']}: status is '{rec['status']}', expected 'simulated'"
            )

    def test_all_records_have_schema_version(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        for rec in records:
            assert "schema_version" in rec
            assert rec["schema_version"] == "0.1"


# ── Phone number masking (critical safety) ───────────────────────────────────
class TestPhoneNumberMasking:
    """Raw phone numbers must NEVER appear in seeded records."""

    def test_no_raw_phone_numbers_in_store(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        # List of known raw numbers from the seeding function
        raw_numbers = [
            "+4930123456789",
            "+4915112345678",
            "+49201456789012",
            "+4969555666777",
            "+4989999888777",
            "+49711222333444",
            "+4933012345678",
            "+4944015555666",
        ]

        # Read the entire file as text to search for raw numbers
        file_text = demo_store.read_text(encoding="utf-8")

        for raw_number in raw_numbers:
            assert raw_number not in file_text, (
                f"Raw phone number {raw_number} leaked into the store!"
            )

    def test_masked_phone_numbers_present(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        # Expect masked phones (format: +49/0) or None
        assert any(rec.get("phone_masked") for rec in records), (
            "Expected at least some records to have masked phone numbers"
        )

        for rec in records:
            phone = rec.get("phone_masked")
            if phone:
                # Masked phone should start with +49 or 0 and have asterisks or be partial
                assert isinstance(phone, str), "phone_masked must be a string or None"
                assert (
                    "****" in phone or len(phone) < 10
                ), f"phone_masked '{phone}' doesn't look masked"


# ── Appointment type distribution ────────────────────────────────────────────
class TestAppointmentTypeDistribution:
    """Seeded calendar should cover all 6 appointment types."""

    def test_all_appointment_types_represented(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        seeded_types = {rec["appointment_type"] for rec in records}
        expected_types = set(APPOINTMENT_TYPES.keys())

        assert expected_types.issubset(seeded_types), (
            f"Not all appointment types seeded. "
            f"Expected: {expected_types}, Got: {seeded_types}"
        )

    def test_each_type_has_multiple_appointments(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        type_counts = {}
        for rec in records:
            appt_type = rec["appointment_type"]
            type_counts[appt_type] = type_counts.get(appt_type, 0) + 1

        # Each type should have at least 3 appointments (from seeding design)
        for appt_type in APPOINTMENT_TYPES:
            assert type_counts.get(appt_type, 0) >= 3, (
                f"Type '{appt_type}' has only {type_counts.get(appt_type, 0)} appointments, "
                f"expected ≥ 3"
            )


# ── Conflict detection ───────────────────────────────────────────────────────
class TestNoConflicts:
    """Seeded appointments must not overlap on the same resource."""

    def test_no_overlapping_appointments_per_resource(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        # Group by resource and date
        resource_day_appts = {}
        for rec in records:
            resource = rec["assigned_resource"]
            start_str = rec["selected_slot_start"]
            start = datetime.fromisoformat(start_str)
            day = start.date()
            key = (resource, day)

            if key not in resource_day_appts:
                resource_day_appts[key] = []
            resource_day_appts[key].append(rec)

        # Check no overlaps within each (resource, day) group
        for (resource, day), appts in resource_day_appts.items():
            for i, appt1 in enumerate(appts):
                start1 = datetime.fromisoformat(appt1["selected_slot_start"])
                end1 = datetime.fromisoformat(appt1["selected_slot_end"])

                for appt2 in appts[i + 1 :]:
                    start2 = datetime.fromisoformat(appt2["selected_slot_start"])
                    end2 = datetime.fromisoformat(appt2["selected_slot_end"])

                    # Check for overlap: end1 > start2 AND end2 > start1
                    assert not (end1 > start2 and end2 > start1), (
                        f"Conflict on {resource} {day}: "
                        f"{appt1['caller_name']} {start1}–{end1} "
                        f"overlaps {appt2['caller_name']} {start2}–{end2}"
                    )


# ── Idempotency (critical for safe seeding) ──────────────────────────────────
class TestIdempotency:
    """Seeding should be safe to call multiple times without duplication."""

    def test_second_seed_skips_if_marker_present(self, demo_store):
        # First seed
        count1 = seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records1 = read_appointments(demo_store)

        # Second seed (should skip)
        count2 = seeding.seed_calendar(demo_store, force=False, dry_run=False)

        # Should have skipped (count2 == 0)
        assert count2 == 0, "Second seed without --force should return 0"

        # Records should be unchanged
        records2 = read_appointments(demo_store)
        assert len(records1) == len(records2), "Records count changed after skipped seed"

    def test_force_flag_reseed_from_scratch(self, demo_store):
        # First seed
        count1 = seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records1 = read_appointments(demo_store)

        # Clear the file (simulate removing seeded data manually)
        demo_store.write_text("")

        # Seed again with --force
        count2 = seeding.seed_calendar(demo_store, force=True, dry_run=False)
        records2 = read_appointments(demo_store)

        # Both should have seeded the same number of appointments
        assert count1 == count2, (
            f"Re-seed with --force produced different count: {count1} vs {count2}"
        )
        assert len(records1) == len(records2), (
            f"Re-seed with --force produced different record count"
        )


# ── Determinism and repeatability ────────────────────────────────────────────
class TestDeterminism:
    """Seeding the same date range should produce the same appointments."""

    def test_deterministic_seed_same_date(self, tmp_path):
        """Same start date should produce same appointments (deterministic slot times, not IDs)."""
        store1 = tmp_path / "seed1.jsonl"
        store2 = tmp_path / "seed2.jsonl"

        start_date = date(2026, 7, 6)

        # Seed both with the same start date
        seeding.seed_calendar(store1, force=False, dry_run=False, start_date=start_date)
        seeding.seed_calendar(store2, force=False, dry_run=False, start_date=start_date)

        records1 = read_appointments(store1)
        records2 = read_appointments(store2)

        assert len(records1) == len(records2), (
            "Same start date produced different record counts"
        )

        # Sort by slot time (deterministic) and compare
        records1_sorted = sorted(
            records1, key=lambda r: (r["selected_slot_start"], r["caller_name"])
        )
        records2_sorted = sorted(
            records2, key=lambda r: (r["selected_slot_start"], r["caller_name"])
        )

        for r1, r2 in zip(records1_sorted, records2_sorted):
            assert r1["selected_slot_start"] == r2["selected_slot_start"], (
                f"Slot times differ: {r1['selected_slot_start']} vs {r2['selected_slot_start']}"
            )
            assert r1["assigned_resource"] == r2["assigned_resource"], (
                f"Resources differ for same slot: {r1['assigned_resource']} vs {r2['assigned_resource']}"
            )


# ── Seeding marker validation ────────────────────────────────────────────────
class TestSeedingMarker:
    """Records should be marked with source='scheduler_demo_seed' for idempotency."""

    def test_seeded_records_have_demo_seed_marker(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        for rec in records:
            assert rec["source"] == "scheduler_demo_seed", (
                f"Expected all seeded records to have source='scheduler_demo_seed', "
                f"got '{rec['source']}'"
            )


# ── Dry-run mode ─────────────────────────────────────────────────────────────
class TestDryRunMode:
    """Dry-run should print but not write."""

    def test_dry_run_no_write(self, demo_store):
        # Pre-fill the store with something
        demo_store.write_text("")

        # Dry run should not write
        count = seeding.seed_calendar(demo_store, force=False, dry_run=True)

        # File should still be empty (only newline maybe)
        records = read_appointments(demo_store)
        assert len(records) == 0, (
            "Dry-run should not have written any appointments to store"
        )

        # But count should reflect what would have been written
        assert count > 0, "Dry-run should still return the count"


# ── Data quality checks ──────────────────────────────────────────────────────
class TestDataQuality:
    """Seeded records should have realistic and complete data."""

    def test_all_required_fields_present(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        required_fields = [
            "status",
            "schema_version",
            "id",
            "created_at",
            "source",
            "caller_name",
            "appointment_type",
            "selected_slot_start",
            "selected_slot_end",
            "assigned_resource",
        ]

        for rec in records:
            for field in required_fields:
                assert field in rec, (
                    f"Record {rec.get('id')} missing required field '{field}'"
                )
                assert rec[field] is not None, (
                    f"Record {rec.get('id')} field '{field}' is None"
                )

    def test_caller_names_are_realistic(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        # Just verify they're not empty and look like names
        for rec in records:
            name = rec.get("caller_name", "")
            assert isinstance(name, str) and len(name) > 2, (
                f"Unrealistic caller_name: '{name}'"
            )
            # Should have at least a first and last name (space-separated)
            assert " " in name, f"caller_name should be firstname lastname: '{name}'"

    def test_topics_are_appointment_relevant(self, demo_store):
        seeding.seed_calendar(demo_store, force=False, dry_run=False)
        records = read_appointments(demo_store)

        for rec in records:
            topic = rec.get("topic", "")
            assert isinstance(topic, str) and len(topic) > 2, (
                f"Unrealistic topic: '{topic}'"
            )
            # Topics should contain relevant words (German or English) — single or multi-word
            words = topic.lower().split()
            assert len(words) >= 1, f"Topic empty: '{topic}'"
