"""
Scheduler v0.1 — JSONL store tests (backend/scheduler/store_jsonl.py).

All writes go to a pytest tmp file, so the real store
(backend/data/scheduler/appointments.jsonl) is never touched.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scheduler import (  # noqa: E402
    Appointment,
    MalformedAppointmentLine,
    append_appointment,
    read_appointments,
)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "appointments.jsonl"


def _record(start="2026-07-06T08:00:00", end="2026-07-06T08:30:00", rid="a"):
    return Appointment(
        id=rid, created_at="2026-07-06T00:00:00Z", source="s",
        caller_name="Max", company=None, phone_masked=None, topic="t",
        appointment_type="callback",
        selected_slot_start=start, selected_slot_end=end,
        assigned_resource="remote_support_queue",
    ).to_record()


def test_append_read_roundtrip(store):
    path = append_appointment(_record(), path=store)
    assert path == store
    records = read_appointments(store)
    assert len(records) == 1
    assert records[0]["appointment_type"] == "callback"
    # each line is standalone JSON
    lines = [ln for ln in store.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    json.loads(lines[0])


def test_one_object_per_line(store):
    append_appointment(_record(rid="a"), path=store)
    append_appointment(_record(start="2026-07-06T08:30:00", end="2026-07-06T09:00:00", rid="b"), path=store)
    lines = store.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(ln)["id"] for ln in lines] == ["a", "b"]


def test_missing_store_is_empty(tmp_path):
    assert read_appointments(tmp_path / "nope.jsonl") == []


def test_blank_lines_skipped(store):
    append_appointment(_record(rid="a"), path=store)
    with open(store, "a", encoding="utf-8") as fh:
        fh.write("\n   \n\n")
    append_appointment(_record(start="2026-07-06T08:30:00", end="2026-07-06T09:00:00", rid="b"), path=store)
    records = read_appointments(store)
    assert [r["id"] for r in records] == ["a", "b"]


def test_malformed_json_fails_clearly(store):
    append_appointment(_record(rid="a"), path=store)
    with open(store, "a", encoding="utf-8") as fh:
        fh.write("{not valid json]\n")
    with pytest.raises(MalformedAppointmentLine) as exc:
        read_appointments(store)
    assert "line 2" in str(exc.value)


def test_append_rejects_invalid_record(store):
    with pytest.raises(ValueError):
        append_appointment({"status": "simulated"}, path=store)
    # nothing should have been written
    assert read_appointments(store) == []


def test_append_rejects_unmasked_phone(store):
    rec = _record()
    rec["phone_masked"] = "+491234567890"  # unmasked
    with pytest.raises(ValueError):
        append_appointment(rec, path=store)
