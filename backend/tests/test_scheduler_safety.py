"""
Scheduler v0.1 — safety tests.

Guards the non-negotiable invariants:
  - raw phone numbers are never stored (only masked, or null)
  - every stored record has status == "simulated"
  - no real calendar / external API / network dependency is imported or used
  - phone-facing German wording is simulation-honest (no guarantee / real-calendar
    claims)

All writes go to a pytest tmp file.
"""
import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scheduler import (  # noqa: E402
    Appointment,
    SCHEMA_VERSION,
    STATUS_SIMULATED,
    create_simulated_appointment,
    generate_slots,
    read_appointments,
)
from scheduler import phone as sched_phone  # noqa: E402

MONDAY = date(2026, 7, 6)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "appointments.jsonl"


class TestPhonePrivacy:
    def test_raw_phone_never_stored(self, store):
        raw = "+491701234567"
        res = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 11, 0),
            caller_name="Max", phone=raw, path=store,
        )
        assert res.ok
        blob = store.read_text(encoding="utf-8")
        assert raw not in blob
        assert "1701234567" not in blob  # digits-only form absent too
        rec = read_appointments(store)[0]
        assert rec["phone_masked"] and "*" in rec["phone_masked"]

    def test_no_phone_stores_null(self, store):
        res = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 11, 0), path=store,
        )
        assert res.ok
        assert read_appointments(store)[0]["phone_masked"] is None


class TestSimulatedInvariant:
    def test_all_records_simulated(self, store):
        for hour in (8, 9, 10):
            create_simulated_appointment(
                appointment_type="callback", slot_start=datetime(2026, 7, 6, hour, 0),
                caller_name=f"c{hour}", path=store,
            )
        records = read_appointments(store)
        assert records
        assert all(r["status"] == STATUS_SIMULATED for r in records)
        assert all(r["schema_version"] == SCHEMA_VERSION for r in records)


class TestNoExternalSideEffects:
    def test_source_has_no_calendar_or_network_imports(self):
        import scheduler
        pkg_dir = os.path.dirname(scheduler.__file__)
        banned = (
            "googleapiclient", "google.oauth2", "google_auth", "office365",
            "msal", "outlook", "smtplib", "requests", "httpx", "urllib.request",
            "sqlite3", "sqlalchemy", "aiohttp", "socket.socket",
        )
        for fname in os.listdir(pkg_dir):
            if not fname.endswith(".py"):
                continue
            text = open(os.path.join(pkg_dir, fname), encoding="utf-8").read()
            for token in banned:
                assert token not in text, f"{fname} references banned dependency {token!r}"

    def test_booking_works_without_network(self, store, monkeypatch):
        import socket

        def _no_net(*args, **kwargs):
            raise AssertionError("network access attempted during simulation")

        monkeypatch.setattr(socket, "socket", _no_net)
        res = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 12, 0),
            caller_name="Offline", phone="+491234567890", path=store,
        )
        assert res.ok
        assert read_appointments(store)[0]["status"] == STATUS_SIMULATED


class TestPhoneWording:
    def test_offer_lists_slots_safely(self):
        slots = generate_slots(MONDAY, 30)[:3]
        text = sched_phone.format_slot_offer(slots)
        # One natural spoken sentence — an offer ("anbieten"), never a bullet list
        assert "könnte ich Ihnen" in text
        assert "anbieten" in text
        assert "8 Uhr" in text
        assert "\n" not in text
        for bad in sched_phone.FORBIDDEN_PHRASES:
            assert bad.lower() not in text.lower()

    def test_offer_accepts_tuples_too(self):
        text = sched_phone.format_slot_offer([(datetime(2026, 7, 6, 8, 0), datetime(2026, 7, 6, 8, 30))])
        assert "8 Uhr" in text

    def test_empty_offer_is_honest(self):
        assert "keine passenden Zeiten" in sched_phone.format_slot_offer([])

    def test_confirmation_summary_is_a_vormerkung(self):
        appt = Appointment(
            id="x", created_at="2026-07-06T08:00:00Z", source="s",
            caller_name=None, company=None, phone_masked=None, topic=None,
            appointment_type="callback",
            selected_slot_start="2026-07-06T09:00:00",
            selected_slot_end="2026-07-06T09:30:00",
            assigned_resource="remote_support_queue",
        )
        summary = sched_phone.build_confirmation_summary(appt)
        # Simulation-honest framing: noted non-bindingly, confirmed by the team —
        # never "gebucht", never a guarantee.
        assert "unverbindlich vorgemerkt" in summary
        assert "gebucht" not in summary.lower()
        for bad in sched_phone.FORBIDDEN_PHRASES:
            assert bad.lower() not in summary.lower()

    def test_guard_blocks_forbidden(self):
        for bad in (
            "Der Termin ist garantiert.",
            "Ich habe es im echten Kalender eingetragen.",
            "Patrick kommt sicher morgen.",
        ):
            with pytest.raises(sched_phone.UnsafePhoneWording):
                sched_phone.assert_phrase_safe(bad)

    def test_allowed_phrases_pass_guard(self):
        for phrase in sched_phone.ALLOWED_PHRASES:
            assert sched_phone.assert_phrase_safe(phrase) == phrase
