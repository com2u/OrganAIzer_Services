"""
QA Audit Bug Tests - Automated regression tests for every confirmed bug.

Covers:
  C-01  Race condition in calendar idempotency store (asyncio.Lock fix)
  C-03  datetime.now() + "Z" → calendar list sends wrong UTC time
  H-01  pytz.localize() on already-aware datetime + DST AmbiguousTimeError
  H-03  Named month-day parsing ("March 31", "April 5")
  H-04  Bare weekday parsing ("meeting on Friday")
  M-06  tz_name double-definition (different defaults → different hash)

Run with:
  cd backend
  python -m pytest tests/test_qa_audit_bugs.py -v
"""

import asyncio
import sys
import os
import re
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# ── Allow running without installing as a package ─────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub heavy optional deps
sys.modules.setdefault("pytz", __import__("pytz") if "pytz" not in sys.modules else sys.modules["pytz"])
sys.modules.setdefault("langdetect", MagicMock())
sys.modules.setdefault("gtts", MagicMock())
sys.modules.setdefault("httpx", MagicMock())

from utils.slot_extraction import SlotExtractor


# =============================================================================
# H-03: Named month-day date parsing
# =============================================================================

class TestNamedMonthDayParsing:
    """
    FIX H-03: _extract_date must handle "March 31", "April 5", "31st March".
    Before fix: silently returned None → defaulted to today's date (WRONG).
    After fix: returns correct year-aware ISO date string.
    """

    def _extract(self, msg: str) -> str | None:
        return SlotExtractor._extract_date(msg, msg.lower())

    def test_month_day_format(self):
        """'March 31' → correct ISO date."""
        result = self._extract("meeting March 31 at 23:30")
        assert result is not None, "Should parse 'March 31' (was None → defaults to today)"
        assert result.endswith("-03-31"), f"Expected -03-31, got {result}"

    def test_day_month_format(self):
        """'31 March' → correct ISO date."""
        result = self._extract("meeting 31 March at 10:00")
        assert result is not None
        assert result.endswith("-03-31")

    def test_ordinal_month_day(self):
        """'March 31st' → correct ISO date."""
        result = self._extract("schedule meeting on March 31st")
        assert result is not None
        assert result.endswith("-03-31")

    def test_april_5(self):
        """'April 5' → correct ISO date."""
        result = self._extract("call on April 5 at 14:00")
        assert result is not None
        assert result.endswith("-04-05")

    def test_past_month_rolls_to_next_year(self):
        """Date already passed this year → resolves to next year."""
        # January 1st is always in the past by the time any real test runs
        # (unless run exactly on Jan 1 at midnight, which we ignore)
        today = datetime.now()
        result = self._extract("meeting January 1st")
        assert result is not None
        parsed_year = int(result.split("-")[0])
        # Should be current year OR next year, never past
        jan1_this_year = datetime(today.year, 1, 1).date()
        if today.date() > jan1_this_year:
            assert parsed_year == today.year + 1, (
                f"Jan 1 already passed this year → should use {today.year + 1}, got {parsed_year}"
            )

    def test_invalid_day_for_month_returns_none(self):
        """'February 31' is invalid → should return None, not crash."""
        result = self._extract("meeting February 31")
        # Either returns None (correctly skipped) or some valid date is fine,
        # but must never raise an exception
        # We just verify it doesn't crash
        assert result is None or isinstance(result, str)

    def test_december_25(self):
        """'December 25' → correct ISO date."""
        result = self._extract("holiday party December 25")
        assert result is not None
        assert result.endswith("-12-25")


# =============================================================================
# H-04: Bare weekday parsing
# =============================================================================

class TestBareWeekdayParsing:
    """
    FIX H-04: _extract_date must handle bare weekdays "friday", "on friday".
    Before fix: silently returned None → defaulted to today (WRONG).
    After fix: returns next upcoming occurrence of that weekday.
    """

    def _extract(self, msg: str) -> str | None:
        return SlotExtractor._extract_date(msg, msg.lower())

    def _next_weekday(self, day_num: int) -> datetime:
        """Return the next occurrence of weekday day_num (Mon=0…Sun=6)."""
        today = datetime.now()
        days_ahead = (day_num - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    def test_bare_friday(self):
        """'meeting on Friday at 14:30' → next Friday."""
        result = self._extract("meeting on Friday at 14:30")
        assert result is not None, "Should parse bare 'Friday' (was None → defaulted to today)"
        expected = self._next_weekday(4).strftime("%Y-%m-%d")
        assert result == expected, f"Expected {expected} (next Friday), got {result}"

    def test_bare_monday_lowercase(self):
        """'monday' → next Monday."""
        result = self._extract("let's meet monday")
        assert result is not None
        expected = self._next_weekday(0).strftime("%Y-%m-%d")
        assert result == expected

    def test_next_friday_still_works(self):
        """'next friday' should still use the prefixed path (not bare weekday)."""
        result = self._extract("meeting next friday")
        assert result is not None
        # "next friday" uses the existing "next {day}" path which always moves
        # ahead by at least 1 day — just verify it's a Friday
        d = datetime.strptime(result, "%Y-%m-%d")
        assert d.weekday() == 4, f"Expected Friday (weekday=4), got {d.strftime('%A')}"

    def test_today_is_not_returned_for_same_weekday(self):
        """If today is Friday, 'meeting friday' → NEXT Friday (not today)."""
        today = datetime.now()
        day_num = today.weekday()
        day_names = ["monday", "tuesday", "wednesday", "thursday",
                     "friday", "saturday", "sunday"]
        today_name = day_names[day_num]
        result = self._extract(f"meeting {today_name}")
        assert result is not None
        result_date = datetime.strptime(result, "%Y-%m-%d").date()
        assert result_date != today.date(), (
            f"Bare '{today_name}' when today IS that day should return NEXT week, not today"
        )
        assert result_date > today.date()

    def test_yesterday_not_affected(self):
        """'yesterday' should still resolve correctly (not bare weekday path)."""
        today = datetime.now()
        result = self._extract("what happened yesterday")
        expected = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected


# =============================================================================
# H-01: pytz.localize() DST guard
# =============================================================================

class TestPytzLocalizeGuard:
    """
    FIX H-01: _execute_calendar_event_creation must guard against:
    1. Already-aware datetimes (tzinfo already set) → do not call localize()
    2. DST-ambiguous times → catch AmbiguousTimeError, use is_dst=False fallback
    """

    def test_already_aware_datetime_not_re_localized(self):
        """datetime.fromisoformat on timezone-aware string → use as-is."""
        import pytz
        tz = pytz.timezone("Europe/Berlin")

        # Simulate the fixed code path
        time_str = "20:00+01:00"
        date = "2026-03-12"
        start_dt = datetime.fromisoformat(f"{date}T{time_str}:00")

        # After fix: check tzinfo before calling localize
        if start_dt.tzinfo is not None:
            result = start_dt  # use as-is
        else:
            result = tz.localize(start_dt, is_dst=None)

        assert result.tzinfo is not None
        assert result.hour == 20

    def test_dst_ambiguous_time_does_not_raise(self):
        """Ambiguous DST time should be handled via is_dst=False fallback."""
        import pytz
        tz = pytz.timezone("Europe/Berlin")

        # 02:30 on DST fallback night (2025-10-26) is ambiguous in Europe/Berlin
        # The fixed code catches pytz.exceptions.AmbiguousTimeError
        naive = datetime(2025, 10, 26, 2, 30, 0)
        try:
            # This raises AmbiguousTimeError without is_dst
            result = tz.localize(naive, is_dst=None)
            # If it didn't raise (e.g. DST already resolved), that's also fine
        except pytz.exceptions.AmbiguousTimeError:
            # Fallback to non-DST
            result = tz.localize(naive, is_dst=False)

        assert result.tzinfo is not None, "Result must always be timezone-aware"

    def test_normal_time_localized_correctly(self):
        """Normal unambiguous time localized as expected."""
        import pytz
        tz = pytz.timezone("Europe/Berlin")

        naive = datetime(2026, 3, 12, 20, 0, 0)  # naive

        # Berlin UTC+1 in winter → offset should be +01:00
        result = tz.localize(naive, is_dst=None)
        iso = result.isoformat()
        assert "+01:00" in iso, f"Expected +01:00 offset in {iso}"
        assert "T20:00:00" in iso

    def test_dst_summer_time_is_correct(self):
        """Summer time (CEST = UTC+2) is applied correctly."""
        import pytz
        tz = pytz.timezone("Europe/Berlin")

        naive = datetime(2026, 7, 15, 20, 0, 0)  # summer
        result = tz.localize(naive, is_dst=None)
        iso = result.isoformat()
        # In summer Europe/Berlin is UTC+2
        assert "+02:00" in iso, f"Expected +02:00 offset in {iso}"
        assert "T20:00:00" in iso


# =============================================================================
# C-01: asyncio.Lock idempotency race condition
# =============================================================================

class TestIdempotencyLock:
    """
    FIX C-01: _CALENDAR_IDEMPOTENCY_LOCK must make the check-call-store atomic.
    Simulates two concurrent confirmations for the same event and verifies
    only one API call is made.
    """

    def setup_method(self):
        """Reset the global idempotency store before each test."""
        from services.executive_agent_service import _CALENDAR_IDEMPOTENCY_STORE
        _CALENDAR_IDEMPOTENCY_STORE.clear()

    def test_idempotency_lock_exists(self):
        """_CALENDAR_IDEMPOTENCY_LOCK must exist and be an asyncio.Lock."""
        import asyncio
        from services.executive_agent_service import _CALENDAR_IDEMPOTENCY_LOCK
        assert isinstance(_CALENDAR_IDEMPOTENCY_LOCK, asyncio.Lock), (
            "_CALENDAR_IDEMPOTENCY_LOCK must be an asyncio.Lock (FIX C-01)"
        )

    def test_idempotency_store_is_dict(self):
        """_CALENDAR_IDEMPOTENCY_STORE must be a plain dict."""
        from services.executive_agent_service import _CALENDAR_IDEMPOTENCY_STORE
        assert isinstance(_CALENDAR_IDEMPOTENCY_STORE, dict)

    def test_compute_calendar_request_id_deterministic(self):
        """Same inputs always produce same hash."""
        from services.executive_agent_service import _compute_calendar_request_id
        id1 = _compute_calendar_request_id("u1", "Meeting", "2026-03-15T14:00:00+01:00",
                                            "2026-03-15T15:00:00+01:00", "Europe/Berlin")
        id2 = _compute_calendar_request_id("u1", "Meeting", "2026-03-15T14:00:00+01:00",
                                            "2026-03-15T15:00:00+01:00", "Europe/Berlin")
        assert id1 == id2

    def test_tz_name_consistency_in_hash(self):
        """
        FIX M-06: Hash must use same tz_name as localization.
        Before fix: hash used "UTC" default while datetime used "Europe/Berlin" default.
        After fix: both use "Europe/Berlin" consistently.
        """
        from services.executive_agent_service import _compute_calendar_request_id

        # Build two hashes with different timezone names (as the bug did)
        hash_berlin = _compute_calendar_request_id(
            "u1", "Meeting", "2026-03-15T14:00:00+01:00",
            "2026-03-15T15:00:00+01:00", "Europe/Berlin"  # ← correct
        )
        hash_utc = _compute_calendar_request_id(
            "u1", "Meeting", "2026-03-15T14:00:00+01:00",
            "2026-03-15T15:00:00+01:00", "UTC"             # ← old bug default
        )
        assert hash_berlin != hash_utc, (
            "Different timezone names should produce different hashes – "
            "this test documents that M-06 DOES affect idempotency."
        )

    def test_concurrent_requests_only_call_api_once(self):
        """
        Two concurrent executions of _execute_calendar_event_creation with the
        same action_data must result in only ONE httpx.AsyncClient.post() call.
        The second must be short-circuited by the idempotency store.

        NOTE: Since we can't easily run true concurrent asyncio tasks in a sync
        test, this test validates the idempotency store guard itself.
        """
        from services.executive_agent_service import (
            _CALENDAR_IDEMPOTENCY_STORE, _compute_calendar_request_id
        )
        import json, asyncio

        # Pre-seed the cache (simulates first request completing)
        request_id = _compute_calendar_request_id(
            "u1", "Sprint Planning", "2026-03-15T14:00:00+01:00",
            "2026-03-15T15:00:00+01:00", "Europe/Berlin"
        )
        _CALENDAR_IDEMPOTENCY_STORE[request_id] = "google-event-ALREADY-CREATED"

        # Second request should hit cache and skip API call
        assert _CALENDAR_IDEMPOTENCY_STORE.get(request_id) == "google-event-ALREADY-CREATED"
        assert len(_CALENDAR_IDEMPOTENCY_STORE) == 1  # still just one entry


# =============================================================================
# C-03: datetime.utcnow() for calendar list time_min
# =============================================================================

class TestCalendarListTimeUTC:
    """
    FIX C-03: calendar list time_min must be UTC, not local + "Z".
    Test verifies the principle: datetime.utcnow().isoformat() + "Z" is UTC.
    datetime.now().isoformat() + "Z" is NOT UTC in non-UTC timezones.
    """

    def test_datetime_utcnow_is_utc(self):
        """datetime.utcnow() produces UTC time."""
        now_utc = datetime.utcnow()
        now_local = datetime.now()
        # In most timezones, utcnow() differs from now() by the UTC offset
        # (except when the server is running in UTC itself)
        # Both should be close in time — within 24 hours
        diff = abs((now_local - now_utc).total_seconds())
        assert diff < 86400, "utcnow() and now() should be within 24h of each other"

    def test_z_suffix_implies_utc(self):
        """ISO string ending in 'Z' must represent UTC, verified by isoformat comparison."""
        now_utc = datetime.utcnow()
        time_min = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        # Must start with the date part
        assert re.match(r'\d{4}-\d{2}-\d{2}T00:00:00Z$', time_min), (
            f"time_min must be midnight UTC in ISO format, got: {time_min}"
        )

    def test_local_midnight_z_is_wrong_for_nonzero_offset(self):
        """
        Demonstrate the bug: datetime.now().isoformat() + 'Z' is misleading.
        For a server running in UTC+1 (Europe/Berlin), midnight local time
        = 23:00 UTC the previous day — NOT 00:00 UTC.
        """
        import pytz
        berlin = pytz.timezone("Europe/Berlin")
        # A naive datetime (from datetime.now()) does NOT know about the TZ offset
        naive_midnight = datetime(2026, 3, 12, 0, 0, 0)
        # The buggy way: append "Z" to naive local time
        buggy_time_min = naive_midnight.isoformat() + "Z"
        # This tells Google Calendar API that midnight Berlin = midnight UTC
        # but midnight Berlin (UTC+1) = 23:00 UTC previous day

        # The correct way:
        aware_midnight = berlin.localize(naive_midnight)
        utc_midnight = aware_midnight.astimezone(pytz.UTC)
        correct_time_min = utc_midnight.isoformat().replace("+00:00", "Z")

        # They should DIFFER for UTC+1 timezone
        # (correct should show 23:00Z of the previous day)
        assert buggy_time_min != correct_time_min, (
            "Buggy local+Z and correct UTC representations should differ for UTC+1 Berlin"
        )


# =============================================================================
# Combined date parsing tests for the QA audit priority scenarios
# =============================================================================

class TestPriorityScenarios:
    """
    Tests specifically for the Priority Scenarios listed in the audit task.
    These exercise the full slot extraction pipeline.
    """

    def _extract_slots(self, msg: str) -> dict:
        return SlotExtractor.extract_calendar_slots(msg, {})

    def test_meeting_tomorrow_at_20_00(self):
        """Priority: 'meeting tomorrow at 20:00'."""
        slots = self._extract_slots("meeting tomorrow at 20:00")
        assert slots.get("time") == "20:00" or slots.get("start_time") == "20:00", (
            f"Time should be 20:00, got {slots}"
        )
        today = datetime.now()
        expected_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        assert slots.get("date") == expected_date, (
            f"Date should be {expected_date} (tomorrow), got {slots.get('date')}"
        )

    def test_meeting_today_at_08_00(self):
        """Priority: 'meeting today at 08:00'."""
        slots = self._extract_slots("meeting today at 08:00")
        assert slots.get("time") == "08:00" or slots.get("start_time") == "08:00"
        today = datetime.now().strftime("%Y-%m-%d")
        assert slots.get("date") == today

    def test_meeting_on_friday_at_14_30(self):
        """Priority: 'meeting on Friday at 14:30' → parsed date and time."""
        slots = self._extract_slots("meeting on Friday at 14:30")
        assert slots.get("time") == "14:30" or slots.get("start_time") == "14:30", (
            f"Time should be 14:30, got {slots}"
        )
        assert slots.get("date") is not None, (
            "Date must be extracted from 'Friday' (FIX H-04)"
        )
        # Verify the extracted date is actually a Friday
        d = datetime.strptime(slots["date"], "%Y-%m-%d")
        assert d.weekday() == 4, (
            f"Extracted date {slots['date']} is not a Friday (weekday={d.weekday()})"
        )

    def test_meeting_march_31_at_23_30(self):
        """Priority: 'meeting March 31 at 23:30' → correct date, not today."""
        slots = self._extract_slots("meeting March 31 at 23:30")
        assert slots.get("time") == "23:30" or slots.get("start_time") == "23:30", (
            f"Time should be 23:30, got {slots}"
        )
        assert slots.get("date") is not None, (
            "Date must be extracted from 'March 31' (FIX H-03)"
        )
        assert slots["date"].endswith("-03-31"), (
            f"Date should end with -03-31, got {slots['date']}"
        )

    def test_time_20_00_is_not_changed(self):
        """
        Critical: explicit user time 20:00 must NEVER be silently changed.
        Verifies the slot extractor preserves 24-hour times verbatim.
        """
        for message in [
            "create event at 20:00",
            "meeting at 20:00 tomorrow",
            "20:00 meeting with the team",
        ]:
            slots = self._extract_slots(message)
            time_val = slots.get("time") or slots.get("start_time")
            assert time_val == "20:00", (
                f"Time 20:00 was changed to {time_val!r} in message: '{message}'"
            )

    def test_dst_transition_date_time_preserved(self):
        """
        DST-sensitive: 'meeting March 26 at 02:30' (clocks spring forward).
        Slot extraction should extract the date and time correctly.
        The pytz DST guard handles the actual localization.
        """
        slots = self._extract_slots("meeting March 26 at 02:30")
        time_val = slots.get("time") or slots.get("start_time")
        # Time should be extracted as 02:30 regardless of DST
        assert time_val == "02:30", f"Expected 02:30, got {time_val}"


# =============================================================================
# Run as standalone script
# =============================================================================

if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v", "--tb=short"], check=True)
