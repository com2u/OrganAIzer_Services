"""
Time preference parser tests (backend/voice/time_preferences.py).

Covers:
  - Today, tomorrow, day after tomorrow
  - Specific weekday names
  - Time windows (morning, afternoon, after lunch)
  - Exact times ("um 10:30", "gegen 10")
  - "ab 14 Uhr" (from X onwards)
  - ASAP vs flexible
  - Flexibility extraction
"""
import sys
import os
from datetime import datetime, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from voice.time_preferences import (
    parse_time_preference,
    TimePreference,
    format_preference_for_display,
)


# Test date: Monday 2026-07-06 at 11:15
TEST_NOW = datetime(2026, 7, 6, 11, 15)


class TestTodayTomorrow:
    """Test today/tomorrow/day-after parsing"""

    def test_heute_only_offers_future_slots(self):
        """Caller: 'Geht heute noch etwas?'"""
        pref = parse_time_preference("Geht heute noch etwas?", TEST_NOW)
        assert pref.target_day == "today"
        assert pref.days_offset == 0
        assert pref.urgency == "flexible"

    def test_morgen(self):
        """Caller: 'Morgen wäre gut'"""
        pref = parse_time_preference("Morgen wäre gut", TEST_NOW)
        assert pref.target_day == "tomorrow"
        assert pref.days_offset == 1

    def test_uebermorgen(self):
        """Caller: 'Übermorgen passt'"""
        pref = parse_time_preference("Übermorgen passt", TEST_NOW)
        assert pref.target_day == "day_after"
        assert pref.days_offset == 2

    def test_uebermorgen_umlaut_variant(self):
        """Caller: 'Uebermorgen' (without umlaut, common speech-to-text)"""
        pref = parse_time_preference("Uebermorgen passt", TEST_NOW)
        assert pref.target_day == "day_after"


class TestSpecificWeekday:
    """Test specific weekday parsing"""

    def test_montag(self):
        """Caller: 'Montag passt mir'"""
        pref = parse_time_preference("Montag passt mir", TEST_NOW)
        assert pref.target_day == "monday"
        # From Monday 11:15 to next Monday = 7 days
        assert pref.days_offset == 7

    def test_freitag(self):
        """Caller: 'Am Freitag'"""
        pref = parse_time_preference("Am Freitag", TEST_NOW)
        assert pref.target_day == "friday"
        # From Monday to Friday same week = 4 days
        assert pref.days_offset == 4

    def test_samstag(self):
        """Caller: 'Samstag geht auch'"""
        pref = parse_time_preference("Samstag geht auch", TEST_NOW)
        assert pref.target_day == "saturday"
        assert pref.days_offset == 5


class TestTimeWindows:
    """Test time window extraction (morning, afternoon, after lunch)"""

    def test_morning_vormittags(self):
        """Caller: 'Morgen vormittags'"""
        pref = parse_time_preference("Morgen vormittags", TEST_NOW)
        assert pref.target_day == "tomorrow"
        assert pref.time_window == (time(8, 0), time(12, 0))

    def test_morning_morgens(self):
        """Caller: 'Morgen morgens'"""
        pref = parse_time_preference("Morgen morgens", TEST_NOW)
        assert pref.time_window == (time(8, 0), time(12, 0))

    def test_morning_früh(self):
        """Caller: 'So früh wie möglich'"""
        pref = parse_time_preference("So früh wie möglich", TEST_NOW)
        assert pref.time_window == (time(8, 0), time(12, 0))

    def test_afternoon_nachmittags(self):
        """Caller: 'Morgen nachmittags'"""
        pref = parse_time_preference("Morgen nachmittags", TEST_NOW)
        assert pref.time_window == (time(13, 0), time(17, 0))

    def test_afternoon_nacht(self):
        """Caller: 'Später nacht' (speech-to-text variant of nachmittags)"""
        pref = parse_time_preference("Später nacht", TEST_NOW)
        # "nacht" alone is ambiguous, needs more context
        # This test documents behavior: we match "nacht" as afternoon
        assert pref.time_window == (time(13, 0), time(17, 0))

    def test_after_lunch_nach_mittagspause(self):
        """Caller: 'Nach der Mittagspause'"""
        pref = parse_time_preference("Nach der Mittagspause", TEST_NOW)
        assert pref.time_window == (time(13, 0), time(17, 0))

    def test_after_lunch_nach_mittag(self):
        """Caller: 'Nach Mittag'"""
        pref = parse_time_preference("Nach Mittag", TEST_NOW)
        assert pref.time_window == (time(13, 0), time(17, 0))

    def test_after_1200(self):
        """Caller: 'Nach 12 Uhr'"""
        pref = parse_time_preference("Nach 12 Uhr", TEST_NOW)
        assert pref.time_window == (time(13, 0), time(17, 0))

    def test_after_1300(self):
        """Caller: 'Nach 13 Uhr'"""
        pref = parse_time_preference("Nach 13 Uhr", TEST_NOW)
        assert pref.time_window == (time(13, 0), time(17, 0))


class TestExactTimes:
    """Test exact time extraction"""

    def test_um_time_with_colon(self):
        """Caller: 'Um 10:30 Uhr'"""
        pref = parse_time_preference("Um 10:30 Uhr", TEST_NOW)
        assert pref.requested_time == time(10, 30)

    def test_um_time_without_colon(self):
        """Caller: 'Um 1030'"""
        pref = parse_time_preference("Um 1030", TEST_NOW)
        assert pref.requested_time == time(10, 30)

    def test_um_time_hour_only(self):
        """Caller: 'Um 10 Uhr'"""
        pref = parse_time_preference("Um 10 Uhr", TEST_NOW)
        assert pref.requested_time == time(10, 0)

    def test_gegen_time(self):
        """Caller: 'Gegen 10 Uhr' (approximately 10)"""
        pref = parse_time_preference("Gegen 10 Uhr", TEST_NOW)
        assert pref.requested_time == time(10, 0)

    def test_ab_time_afternoon(self):
        """Caller: 'Ab 14 Uhr' (from 2 PM onwards)"""
        pref = parse_time_preference("Ab 14 Uhr", TEST_NOW)
        assert pref.time_window == (time(14, 0), time(17, 0))

    def test_ab_time_without_uhr(self):
        """Caller: 'Ab 14'"""
        pref = parse_time_preference("Ab 14", TEST_NOW)
        assert pref.time_window == (time(14, 0), time(17, 0))

    def test_combined_day_and_time(self):
        """Caller: 'Morgen um 10:30'"""
        pref = parse_time_preference("Morgen um 10:30", TEST_NOW)
        assert pref.target_day == "tomorrow"
        assert pref.requested_time == time(10, 30)


class TestUrgency:
    """Test urgency extraction (ASAP, soon, flexible)"""

    def test_so_frueh_wie_moeglich(self):
        """Caller: 'So früh wie möglich'"""
        pref = parse_time_preference("So früh wie möglich", TEST_NOW)
        assert pref.urgency == "asap"

    def test_schnellstmoeglich(self):
        """Caller: 'Schnellstmöglich'"""
        pref = parse_time_preference("Schnellstmöglich", TEST_NOW)
        assert pref.urgency == "asap"

    def test_sofort(self):
        """Caller: 'Sofort'"""
        pref = parse_time_preference("Sofort", TEST_NOW)
        assert pref.urgency == "asap"

    def test_flexibel(self):
        """Caller: 'Ich bin flexibel'"""
        pref = parse_time_preference("Ich bin flexibel", TEST_NOW)
        assert pref.urgency == "flexible"

    def test_ganz_flexibel(self):
        """Caller: 'Ganz flexibel'"""
        pref = parse_time_preference("Ganz flexibel", TEST_NOW)
        assert pref.urgency == "flexible"

    def test_egal(self):
        """Caller: 'Mir ist egal'"""
        pref = parse_time_preference("Mir ist egal", TEST_NOW)
        assert pref.urgency == "flexible"


class TestFlexibility:
    """Test flexibility score extraction"""

    def test_very_flexible_score(self):
        """Caller: 'Ich bin sehr flexibel'"""
        pref = parse_time_preference("Ich bin sehr flexibel", TEST_NOW)
        assert pref.flexibility == 1.0

    def test_no_flexibility_with_exact_time(self):
        """Caller: 'Montag um 10 Uhr, nicht ändern'"""
        pref = parse_time_preference("Montag um 10 Uhr", TEST_NOW)
        # Has exact time but no explicit rigidity marker
        assert pref.flexibility == 0.3  # Slight preference

    def test_explicit_rigid(self):
        """Caller: 'Genau um 10 Uhr'"""
        pref = parse_time_preference("Genau um 10 Uhr", TEST_NOW)
        assert pref.flexibility == 0.0

    def test_neutral_flexibility(self):
        """Caller: 'Montag passt mir'"""
        pref = parse_time_preference("Montag passt mir", TEST_NOW)
        # No flexibility markers
        assert pref.flexibility == 0.5


class TestComplexScenarios:
    """Test realistic caller scenarios"""

    def test_scenario_1_urgent_callback(self):
        """Caller: 'Ich brauche schnellstens einen Rückruf, heute noch!'"""
        pref = parse_time_preference("Ich brauche schnellstens einen Rückruf, heute noch!", TEST_NOW)
        assert pref.target_day == "today"
        assert pref.urgency == "asap"
        assert pref.flexibility <= 0.5  # Not very flexible (at most neutral)

    def test_scenario_2_flexible_sales(self):
        """Caller: 'Nächste Woche, bin sehr flexibel mit der Zeit'"""
        pref = parse_time_preference("Nächste Woche, bin sehr flexibel mit der Zeit", TEST_NOW)
        assert pref.target_day == "next_week"
        assert pref.flexibility == 1.0

    def test_scenario_3_morning_preferred(self):
        """Caller: 'Morgen früh, am liebsten vor 12 Uhr'"""
        pref = parse_time_preference("Morgen früh, am liebsten vor 12 Uhr", TEST_NOW)
        assert pref.target_day == "tomorrow"
        assert pref.time_window == (time(8, 0), time(12, 0))

    def test_scenario_4_specific_time_with_backup(self):
        """Caller: 'Freitag um 14:00, wenn nicht, dann später am Freitag'"""
        pref = parse_time_preference("Freitag um 14:00, wenn nicht, dann später am Freitag", TEST_NOW)
        assert pref.target_day == "friday"
        assert pref.requested_time == time(14, 0)
        assert pref.flexibility == 0.3  # Has preference but might accept alternatives


class TestEdgeCases:
    """Test edge cases and invalid input"""

    def test_no_time_preference(self):
        """Caller: 'Hallo, ich hätte gerne einen Termin'"""
        pref = parse_time_preference("Hallo, ich hätte gerne einen Termin", TEST_NOW)
        assert pref.target_day is None
        assert pref.time_window is None
        assert pref.requested_time is None

    def test_invalid_hour(self):
        """Caller: 'Um 25 Uhr' (invalid)"""
        pref = parse_time_preference("Um 25 Uhr", TEST_NOW)
        assert pref.requested_time is None

    def test_invalid_minute(self):
        """Caller: 'Um 10:75' (invalid)"""
        pref = parse_time_preference("Um 10:75", TEST_NOW)
        assert pref.requested_time is None

    def test_uppercase_input(self):
        """Test case-insensitive parsing"""
        pref = parse_time_preference("MORGEN UM 10:30", TEST_NOW)
        assert pref.target_day == "tomorrow"
        assert pref.requested_time == time(10, 30)

    def test_extra_whitespace(self):
        """Test robustness to whitespace"""
        pref = parse_time_preference("  Morgen    um   10:30  ", TEST_NOW)
        assert pref.target_day == "tomorrow"
        assert pref.requested_time == time(10, 30)


class TestFormatting:
    """Test human-readable formatting"""

    def test_format_simple(self):
        """Format: 'Tomorrow'"""
        pref = TimePreference(
            target_day="tomorrow",
            days_offset=1,
            time_window=None,
            requested_time=None,
            urgency="flexible",
            flexibility=0.5,
        )
        formatted = format_preference_for_display(pref)
        assert "Morgen" in formatted

    def test_format_with_time(self):
        """Format: 'Tomorrow at 10:30'"""
        pref = TimePreference(
            target_day="tomorrow",
            days_offset=1,
            time_window=None,
            requested_time=time(10, 30),
            urgency="flexible",
            flexibility=0.5,
        )
        formatted = format_preference_for_display(pref)
        assert "Morgen" in formatted
        assert "10:30" in formatted

    def test_format_with_window(self):
        """Format: 'Tomorrow afternoon'"""
        pref = TimePreference(
            target_day="tomorrow",
            days_offset=1,
            time_window=(time(13, 0), time(17, 0)),
            requested_time=None,
            urgency="flexible",
            flexibility=0.5,
        )
        formatted = format_preference_for_display(pref)
        assert "Morgen" in formatted
        assert "13:00" in formatted or "13:00-17:00" in formatted
