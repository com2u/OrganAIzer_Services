"""
Scheduler v0.1 — model + record-validation tests (backend/scheduler/models.py,
config.py). Hermetic: no I/O, no network.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scheduler import (  # noqa: E402
    APPOINTMENT_TYPES,
    RESOURCES,
    SCHEMA_VERSION,
    STATUS_SIMULATED,
    Appointment,
    Slot,
    validate_appointment_type,
    validate_record,
)
from scheduler.models import RECORD_FIELDS  # noqa: E402


def _good_record() -> dict:
    return Appointment(
        id="abc",
        created_at="2026-07-06T08:00:00Z",
        source="phone_ai_simulation",
        caller_name="Max Mustermann",
        company="Muster GmbH",
        phone_masked="+49******7890",
        topic="Drucker",
        appointment_type="callback",
        selected_slot_start="2026-07-06T08:00:00",
        selected_slot_end="2026-07-06T08:30:00",
        assigned_resource="remote_support_queue",
        call_id="call-1",
    ).to_record()


class TestCatalogue:
    def test_type_catalogue_matches_spec(self):
        assert APPOINTMENT_TYPES["callback"].duration_minutes == 30
        assert APPOINTMENT_TYPES["callback"].resource == "remote_support_queue"
        assert APPOINTMENT_TYPES["remote_support"].resource == "remote_support_queue"
        assert APPOINTMENT_TYPES["technical_consultation"].resource == "technician_sim_1"
        assert APPOINTMENT_TYPES["on_site_visit_request"].duration_minutes == 60
        assert APPOINTMENT_TYPES["on_site_visit_request"].resource == "technician_sim_1"
        assert APPOINTMENT_TYPES["sales_consultation"].resource == "sales_queue"
        assert APPOINTMENT_TYPES["maintenance_request"].duration_minutes == 60
        assert APPOINTMENT_TYPES["maintenance_request"].resource == "technician_sim_1"

    def test_resources(self):
        assert set(RESOURCES) == {"technician_sim_1", "remote_support_queue", "sales_queue"}

    def test_every_type_resource_is_known(self):
        for spec in APPOINTMENT_TYPES.values():
            assert spec.resource in RESOURCES

    def test_validate_appointment_type(self):
        assert validate_appointment_type("callback").duration_minutes == 30
        with pytest.raises(ValueError):
            validate_appointment_type("haircut")


class TestSlot:
    def test_iso_helpers(self):
        s = Slot(datetime(2026, 7, 6, 8, 0), datetime(2026, 7, 6, 8, 30))
        assert s.start_iso == "2026-07-06T08:00:00"
        assert s.end_iso == "2026-07-06T08:30:00"


class TestRecordValidation:
    def test_valid_record_passes(self):
        validate_record(_good_record())  # must not raise

    def test_record_has_exactly_required_fields(self):
        rec = _good_record()
        assert set(rec.keys()) == set(RECORD_FIELDS)
        assert rec["schema_version"] == SCHEMA_VERSION
        assert rec["status"] == STATUS_SIMULATED

    def test_missing_field_rejected(self):
        rec = _good_record()
        del rec["appointment_type"]
        with pytest.raises(ValueError):
            validate_record(rec)

    def test_wrong_status_rejected(self):
        rec = _good_record()
        rec["status"] = "confirmed"
        with pytest.raises(ValueError):
            validate_record(rec)

    def test_unknown_type_rejected(self):
        rec = _good_record()
        rec["appointment_type"] = "haircut"
        with pytest.raises(ValueError):
            validate_record(rec)

    def test_resource_mismatch_rejected(self):
        rec = _good_record()
        rec["assigned_resource"] = "sales_queue"  # wrong for callback
        with pytest.raises(ValueError):
            validate_record(rec)

    def test_unmasked_phone_rejected(self):
        rec = _good_record()
        rec["phone_masked"] = "+491234567890"  # no mask char
        with pytest.raises(ValueError):
            validate_record(rec)

    def test_null_phone_allowed(self):
        rec = _good_record()
        rec["phone_masked"] = None
        validate_record(rec)  # must not raise
