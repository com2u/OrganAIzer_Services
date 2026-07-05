"""
Scheduler v0.1 — internal API tests (backend/scheduler/service.py):
list_available_slots / create_simulated_appointment / list_appointments.

All writes go to a pytest tmp file.
"""
import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scheduler import (  # noqa: E402
    create_simulated_appointment,
    list_appointments,
    list_available_slots,
    read_appointments,
)

MONDAY = date(2026, 7, 6)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "appointments.jsonl"


# ── list_available_slots ─────────────────────────────────────────────────────
class TestListAvailableSlots:
    def test_limit(self, store):
        slots = list_available_slots(MONDAY, "callback", limit=3, path=store)
        assert len(slots) == 3

    def test_no_limit_returns_all(self, store):
        slots = list_available_slots(MONDAY, "callback", path=store)
        assert len(slots) == 16

    def test_excludes_booked(self, store):
        first = list_available_slots(MONDAY, "callback", limit=1, path=store)[0]
        create_simulated_appointment(
            appointment_type="callback", slot_start=first.start,
            caller_name="A", path=store,
        )
        after = list_available_slots(MONDAY, "callback", path=store)
        assert all(s.start != first.start for s in after)

    def test_now_filters_past(self, store):
        now = datetime(2026, 7, 6, 10, 0)
        slots = list_available_slots(MONDAY, "callback", now=now, path=store)
        assert all(s.start >= now for s in slots)

    def test_deterministic(self, store):
        a = list_available_slots(MONDAY, "callback", path=store)
        b = list_available_slots(MONDAY, "callback", path=store)
        assert [(s.start_iso, s.end_iso) for s in a] == [(s.start_iso, s.end_iso) for s in b]


# ── create_simulated_appointment ─────────────────────────────────────────────
class TestCreate:
    def test_happy_path(self, store):
        res = create_simulated_appointment(
            appointment_type="technical_consultation",
            slot_start=datetime(2026, 7, 6, 8, 0),
            caller_name="Erika", company="Muster AG", topic="Netzwerk",
            call_id="c1", path=store,
        )
        assert res.ok and res.reason == "booked"
        appt = res.appointment
        assert appt.assigned_resource == "technician_sim_1"
        assert appt.status == "simulated"
        assert read_appointments(store)[0]["id"] == appt.id

    def test_invalid_type(self, store):
        res = create_simulated_appointment(
            appointment_type="haircut", slot_start=datetime(2026, 7, 6, 8, 0), path=store,
        )
        assert not res.ok and res.reason == "invalid_type"

    def test_invalid_slot_off_grid(self, store):
        res = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 9, 15), path=store,
        )
        assert not res.ok and res.reason == "invalid_slot"

    def test_invalid_slot_weekend(self, store):
        res = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 11, 9, 0), path=store,
        )
        assert not res.ok and res.reason == "invalid_slot"

    def test_in_past_rejected(self, store):
        res = create_simulated_appointment(
            appointment_type="callback",
            slot_start=datetime(2026, 7, 6, 8, 0),
            now=datetime(2026, 7, 6, 12, 0),
            path=store,
        )
        assert not res.ok and res.reason == "in_past"

    def test_conflict_same_resource(self, store):
        first = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 9, 0),
            caller_name="A", path=store,
        )
        assert first.ok
        # remote_support shares remote_support_queue with callback
        second = create_simulated_appointment(
            appointment_type="remote_support", slot_start=datetime(2026, 7, 6, 9, 0),
            caller_name="B", path=store,
        )
        assert not second.ok and second.reason == "conflict"
        assert second.conflicting_id == first.appointment.id

    def test_different_resource_same_time_ok(self, store):
        a = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 9, 0),
            caller_name="A", path=store,
        )
        b = create_simulated_appointment(
            appointment_type="sales_consultation", slot_start=datetime(2026, 7, 6, 9, 0),
            caller_name="B", path=store,
        )
        assert a.ok and b.ok


class TestDuplicate:
    def test_same_caller_topic_type_slot_is_duplicate(self, store):
        kwargs = dict(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 10, 0),
            caller_name="Max", topic="Drucker", phone="+491234567890", path=store,
        )
        first = create_simulated_appointment(**kwargs)
        assert first.ok
        second = create_simulated_appointment(**kwargs)
        assert not second.ok and second.reason == "duplicate"
        assert len(read_appointments(store)) == 1

    def test_different_topic_not_duplicate(self, store):
        a = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 10, 0),
            caller_name="Max", topic="Drucker", path=store,
        )
        # different topic on a different (non-conflicting) slot
        b = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 10, 30),
            caller_name="Max", topic="Netzwerk", path=store,
        )
        assert a.ok and b.ok

    def test_different_time_not_duplicate(self, store):
        a = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 10, 0),
            caller_name="Max", topic="Drucker", path=store,
        )
        b = create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 10, 30),
            caller_name="Max", topic="Drucker", path=store,
        )
        assert a.ok and b.ok


class TestListAppointments:
    def _seed(self, store):
        create_simulated_appointment(
            appointment_type="callback", slot_start=datetime(2026, 7, 6, 8, 0),
            caller_name="A", call_id="c1", path=store,
        )
        create_simulated_appointment(
            appointment_type="sales_consultation", slot_start=datetime(2026, 7, 6, 8, 0),
            caller_name="B", call_id="c2", path=store,
        )
        create_simulated_appointment(
            appointment_type="on_site_visit_request", slot_start=datetime(2026, 7, 6, 9, 0),
            caller_name="C", call_id="c1", path=store,
        )

    def test_all(self, store):
        self._seed(store)
        assert len(list_appointments(path=store)) == 3

    def test_filter_by_type(self, store):
        self._seed(store)
        rows = list_appointments(appointment_type="callback", path=store)
        assert len(rows) == 1 and rows[0]["appointment_type"] == "callback"

    def test_filter_by_resource(self, store):
        self._seed(store)
        rows = list_appointments(resource="technician_sim_1", path=store)
        assert len(rows) == 1 and rows[0]["assigned_resource"] == "technician_sim_1"

    def test_filter_by_call_id(self, store):
        self._seed(store)
        rows = list_appointments(call_id="c1", path=store)
        assert {r["call_id"] for r in rows} == {"c1"}
        assert len(rows) == 2
