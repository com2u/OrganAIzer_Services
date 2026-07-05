"""
Scheduler v0.1 — deterministic availability tests
(backend/scheduler/availability.py). Hermetic: no I/O, no network, clock injected
via `now`.
"""
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scheduler import (  # noqa: E402
    Appointment,
    available_slots,
    business_hours_for,
    generate_slots,
    is_open,
    slots_overlap,
)

MONDAY = date(2026, 7, 6)
FRIDAY = date(2026, 7, 10)
SATURDAY = date(2026, 7, 11)
SUNDAY = date(2026, 7, 12)


def test_reference_dates():
    assert MONDAY.weekday() == 0
    assert FRIDAY.weekday() == 4
    assert SATURDAY.weekday() == 5
    assert SUNDAY.weekday() == 6


class TestBusinessHours:
    def test_weekday_hours(self):
        for day in (date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8), date(2026, 7, 9)):
            hours = business_hours_for(day)
            assert hours is not None
            assert (hours[0].hour, hours[0].minute) == (8, 0)
            assert (hours[1].hour, hours[1].minute) == (16, 0)
            assert is_open(day)

    def test_friday_ends_at_13(self):
        hours = business_hours_for(FRIDAY)
        assert hours is not None
        assert (hours[0].hour, hours[1].hour, hours[1].minute) == (8, 13, 0)

    def test_weekend_closed(self):
        assert business_hours_for(SATURDAY) is None
        assert business_hours_for(SUNDAY) is None
        assert not is_open(SATURDAY)
        assert not is_open(SUNDAY)


class TestSlotGeneration:
    def test_no_weekend_slots(self):
        assert generate_slots(SATURDAY, 30) == []
        assert generate_slots(SUNDAY, 60) == []
        assert available_slots(SATURDAY, "callback") == []

    def test_monday_30min_grid(self):
        slots = generate_slots(MONDAY, 30)
        assert slots[0].start.strftime("%H:%M") == "08:00"
        assert slots[-1].start.strftime("%H:%M") == "15:30"
        assert slots[-1].end.strftime("%H:%M") == "16:00"
        assert len(slots) == 16  # 08:00–16:00 on a 30-min grid

    def test_friday_30_and_60(self):
        s30 = generate_slots(FRIDAY, 30)
        assert s30[-1].start.strftime("%H:%M") == "12:30"
        assert s30[-1].end.strftime("%H:%M") == "13:00"
        assert all(slot.end.hour <= 13 for slot in s30)
        s60 = generate_slots(FRIDAY, 60)
        assert s60[-1].start.strftime("%H:%M") == "12:00"
        assert s60[-1].end.strftime("%H:%M") == "13:00"

    def test_deterministic(self):
        assert generate_slots(MONDAY, 30) == generate_slots(MONDAY, 30)
        assert available_slots(MONDAY, "callback") == available_slots(MONDAY, "callback")

    def test_no_randomness_across_repeated_calls(self):
        runs = [tuple((s.start_iso, s.end_iso) for s in generate_slots(MONDAY, 60)) for _ in range(5)]
        assert len(set(runs)) == 1


class TestNowInjection:
    def test_now_excludes_past_slots_same_day(self):
        now = datetime(2026, 7, 6, 10, 0)  # Monday 10:00
        slots = generate_slots(MONDAY, 30, now=now)
        assert slots[0].start == datetime(2026, 7, 6, 10, 0)
        assert all(slot.start >= now for slot in slots)

    def test_now_in_future_day_keeps_all(self):
        now = datetime(2026, 7, 3, 10, 0)  # before Monday
        assert generate_slots(MONDAY, 30, now=now) == generate_slots(MONDAY, 30)

    def test_now_after_close_yields_none(self):
        now = datetime(2026, 7, 6, 17, 0)  # after Monday close
        assert generate_slots(MONDAY, 30, now=now) == []


class TestConflictExclusion:
    def test_overlap_helper(self):
        a0 = datetime(2026, 7, 6, 9, 0)
        a1 = datetime(2026, 7, 6, 9, 30)
        assert slots_overlap(a0, a1, datetime(2026, 7, 6, 9, 15), datetime(2026, 7, 6, 9, 45))
        assert not slots_overlap(a0, a1, datetime(2026, 7, 6, 9, 30), datetime(2026, 7, 6, 10, 0))

    def test_busy_slot_excluded(self):
        busy = Appointment(
            id="x", created_at="2026-07-06T00:00:00Z", source="s",
            caller_name=None, company=None, phone_masked=None, topic=None,
            appointment_type="callback",
            selected_slot_start="2026-07-06T09:00:00",
            selected_slot_end="2026-07-06T09:30:00",
            assigned_resource="remote_support_queue",
        ).to_record()
        free = available_slots(MONDAY, "callback", [busy])
        assert all(slot.start.strftime("%H:%M") != "09:00" for slot in free)

    def test_other_resource_not_excluded(self):
        busy = Appointment(
            id="x", created_at="2026-07-06T00:00:00Z", source="s",
            caller_name=None, company=None, phone_masked=None, topic=None,
            appointment_type="sales_consultation",
            selected_slot_start="2026-07-06T09:00:00",
            selected_slot_end="2026-07-06T09:30:00",
            assigned_resource="sales_queue",
        ).to_record()
        # callback lives on remote_support_queue, so the sales_queue booking is irrelevant
        free = available_slots(MONDAY, "callback", [busy])
        assert any(slot.start.strftime("%H:%M") == "09:00" for slot in free)
