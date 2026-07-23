"""
Tests for calendar event creation intent detection, slot extraction,
provider locking, and the full confirmation flow.

Test coverage (task spec):
  1. "create event tomorrow 12-13 call it Lunch"
     → CALENDAR_CREATE + correct slots (title, date, start_time, end_time)
  2. "yes" after pending_action → CONFIRM_ACTION (confirms execution path)
  3. Provider locking: "on my outlook calendar" → provider=outlook, NOT google

Additional regression tests:
  4. Flexible phrasing: "create me an event" (no exact-phrase match in legacy list)
  5. "calender" (typo) + "outlook" → CALENDAR_CREATE + provider=outlook
  6. Google provider locking
  7. Empty pending_action path (confirmation without pending → GENERAL_MESSAGE)
  8. SlotExtractor._extract_provider expanded aliases (office365, o365, gcal)
  9. SlotExtractor._extract_timezone abbreviations and IANA strings
 10. Full slot extraction from the problem sentence

Run with:
  cd backend
  python -m pytest tests/test_calendar_intent.py -v
"""

import sys
import os
from datetime import datetime, timedelta

import pytest

# ── Allow importing backend modules without a package install ─────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# utils.intent_router and utils.slot_extraction import only re/logging/
# datetime/typing — no pytz/langdetect/gtts/httpx/msal dependency, so no
# stubbing is needed (or was ever needed) for this file's own imports. The
# previous module-level sys.modules.setdefault(...) stubs here were dead
# defensive scaffolding that had no purpose for this file but permanently
# polluted sys.modules for every test file collected afterward in the same
# run (see test_no_cross_file_pollution.py).
from utils.intent_router import IntentRouter, IntentType
from utils.slot_extraction import SlotExtractor


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1 – Intent detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalendarCreateIntentDetection:
    """_detect_calendar_intent and route_message must return CALENDAR_CREATE."""

    def _route(self, msg):
        """Helper: route a fresh message with no active task / pending action."""
        return IntentRouter.route_message(
            message=msg,
            active_task=None,
            pending_action=None,
            last_question_type=None,
        )

    # ── Core failing case from bug report ────────────────────────────────────
    def test_create_me_an_event_outlook_calender_detected(self):
        """
        'create me an event on my outlook calender for tomorrow at 12:00-13:00, call it Lunch'
        was previously routed as GENERAL_MESSAGE. Must now be CALENDAR_CREATE.
        """
        msg = "create me an event on my outlook calender for tomorrow at 12:00-13:00, call it Lunch"
        result = self._route(msg)
        assert result["intent_type"] == IntentType.CALENDAR_CREATE, (
            f"Expected CALENDAR_CREATE, got {result['intent_type']!r}\n"
            f"Reasoning: {result.get('reasoning')}"
        )

    # ── Provider locked in extracted_slots ───────────────────────────────────
    def test_outlook_provider_locked_in_extracted_slots(self):
        """
        When 'outlook' is in the message, extracted_slots['provider'] must be 'outlook'.
        """
        msg = "create me an event on my outlook calendar for tomorrow at 12:00-13:00"
        result = self._route(msg)
        assert result["intent_type"] == IntentType.CALENDAR_CREATE
        assert result["extracted_slots"].get("provider") == "outlook", (
            f"Expected provider='outlook' in extracted_slots, got: {result['extracted_slots']}"
        )

    def test_google_provider_locked_in_extracted_slots(self):
        """When 'google' is in the message, extracted_slots['provider'] must be 'google'."""
        msg = "add an event tomorrow at 10am on google calendar"
        result = self._route(msg)
        assert result["intent_type"] == IntentType.CALENDAR_CREATE
        assert result["extracted_slots"].get("provider") == "google"

    # ── Flexible phrasing (the regression patterns) ───────────────────────────
    def test_create_me_an_event_no_provider(self):
        """'create me an event tomorrow at 5pm' → CALENDAR_CREATE (regex match)."""
        result = self._route("create me an event tomorrow at 5pm")
        assert result["intent_type"] == IntentType.CALENDAR_CREATE

    def test_add_me_a_meeting(self):
        result = self._route("add me a meeting next friday at 9am")
        assert result["intent_type"] == IntentType.CALENDAR_CREATE

    def test_schedule_a_meeting(self):
        result = self._route("schedule a meeting with the team tomorrow")
        assert result["intent_type"] == IntentType.CALENDAR_CREATE

    def test_book_an_appointment(self):
        result = self._route("book an appointment for next monday at 14:00")
        assert result["intent_type"] == IntentType.CALENDAR_CREATE

    def test_make_an_event(self):
        result = self._route("make an event called Sprint Review on friday at 3pm")
        assert result["intent_type"] == IntentType.CALENDAR_CREATE

    # ── Typo: "calender" instead of "calendar" ────────────────────────────────
    def test_calender_typo_still_detected(self):
        """'outlook calender' (typo) must not break intent detection."""
        msg = "create me an event on my outlook calender for monday at 10:00"
        result = self._route(msg)
        assert result["intent_type"] == IntentType.CALENDAR_CREATE
        # Provider must still be detected because "outlook" keyword is present
        assert result["extracted_slots"].get("provider") == "outlook"

    # ── No provider → extracted_slots should have no provider key ─────────────
    def test_no_provider_in_message_means_no_lock(self):
        """If no provider keyword, extracted_slots should not contain provider."""
        msg = "schedule a meeting tomorrow at noon"
        result = self._route(msg)
        assert result["intent_type"] == IntentType.CALENDAR_CREATE
        # provider key should be absent (agent will ask or use default later)
        assert "provider" not in result["extracted_slots"]

    # ── Microsoft aliases ─────────────────────────────────────────────────────
    def test_microsoft_keyword_locks_outlook(self):
        msg = "create a meeting on microsoft calendar tomorrow at 2pm"
        result = self._route(msg)
        assert result["intent_type"] == IntentType.CALENDAR_CREATE
        assert result["extracted_slots"].get("provider") == "outlook"

    def test_office365_keyword_locks_outlook(self):
        msg = "add an event to office365 tomorrow at 10am"
        result = self._route(msg)
        assert result["intent_type"] == IntentType.CALENDAR_CREATE
        assert result["extracted_slots"].get("provider") == "outlook"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2 – Calendar slot extraction
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalendarSlotExtraction:
    """SlotExtractor.extract_calendar_slots must parse the problem sentence fully."""

    PROBLEM_SENTENCE = (
        "create me an event on my outlook calender "
        "for tomorrow at 12:00-13:00, call it Lunch"
    )

    def _slots(self, msg, existing=None):
        return SlotExtractor.extract_calendar_slots(msg, existing or {})

    # ── Full sentence ─────────────────────────────────────────────────────────
    def test_title_extracted_from_call_it_pattern(self):
        slots = self._slots(self.PROBLEM_SENTENCE)
        assert slots.get("title") == "Lunch", (
            f"Expected title='Lunch', got {slots.get('title')!r}"
        )

    def test_start_time_extracted(self):
        slots = self._slots(self.PROBLEM_SENTENCE)
        assert slots.get("start_time") == "12:00", (
            f"Expected start_time='12:00', got {slots.get('start_time')!r}"
        )

    def test_end_time_extracted(self):
        slots = self._slots(self.PROBLEM_SENTENCE)
        assert slots.get("end_time") == "13:00", (
            f"Expected end_time='13:00', got {slots.get('end_time')!r}"
        )
        # No duration should be set when explicit end_time is present
        assert "duration" not in slots, (
            "duration must NOT be set when explicit end_time is provided"
        )

    def test_date_is_tomorrow(self):
        slots = self._slots(self.PROBLEM_SENTENCE)
        expected_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert slots.get("date") == expected_date, (
            f"Expected date={expected_date!r}, got {slots.get('date')!r}"
        )

    def test_provider_is_outlook(self):
        slots = self._slots(self.PROBLEM_SENTENCE)
        assert slots.get("provider") == "outlook", (
            f"Expected provider='outlook', got {slots.get('provider')!r}"
        )

    # ── Slot locking (existing slots not overwritten) ─────────────────────────
    def test_existing_provider_not_overwritten(self):
        """If provider already locked to 'google', message with 'outlook' should not change it."""
        existing = {"provider": "google"}
        slots = self._slots(
            "create me an event on my outlook calendar tomorrow at 10am",
            existing=existing,
        )
        # extract_calendar_slots receives existing; it should NOT overwrite
        assert slots.get("provider") is None or slots.get("provider") == "google", (
            "Existing provider='google' must not be overwritten by 'outlook' in message"
        )

    def test_existing_date_not_overwritten(self):
        fixed_date = "2026-05-01"
        existing = {"date": fixed_date}
        slots = self._slots("change the time to 15:00", existing=existing)
        assert slots.get("date") is None  # not re-extracted when already present

    # ── Individual patterns ───────────────────────────────────────────────────
    def test_time_range_hhmm_dash_hhmm(self):
        slots = self._slots("meeting at 09:00-10:30")
        assert slots["start_time"] == "09:00"
        assert slots["end_time"] == "10:30"

    def test_time_range_from_to_format(self):
        slots = self._slots("from 14:00 to 15:30")
        assert slots["start_time"] == "14:00"
        assert slots["end_time"] == "15:30"

    def test_ampm_range(self):
        slots = self._slots("2pm to 4pm")
        assert slots["start_time"] == "14:00"
        assert slots["end_time"] == "16:00"

    def test_tomorrow_date(self):
        slots = self._slots("schedule event tomorrow")
        assert slots["date"] == (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    def test_today_date(self):
        slots = self._slots("add meeting today at 3pm")
        assert slots["date"] == datetime.now().strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3 – Provider extraction unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractProvider:
    """SlotExtractor._extract_provider must recognise all aliases."""

    def p(self, text):
        return SlotExtractor._extract_provider(text.lower())

    # Microsoft family
    def test_outlook(self):       assert self.p("outlook calendar") == "outlook"
    def test_microsoft(self):     assert self.p("microsoft calendar") == "outlook"
    def test_office365_space(self): assert self.p("office 365") == "outlook"
    def test_office365_no_space(self): assert self.p("office365") == "outlook"
    def test_o365(self):          assert self.p("o365") == "outlook"
    def test_ms_calendar(self):   assert self.p("ms calendar") == "outlook"

    # Google family
    def test_google(self):        assert self.p("google calendar") == "google"
    def test_gmail(self):         assert self.p("gmail") == "google"
    def test_gcal(self):          assert self.p("gcal") == "google"

    # Typo: "calender" alone doesn't imply a provider
    def test_calender_alone_returns_none(self):
        assert self.p("calender") is None

    # "outlook calender" (typo) → outlook detected from "outlook" keyword
    def test_outlook_calender_typo(self):
        assert self.p("outlook calender") == "outlook"

    # No provider → None
    def test_no_provider(self):   assert self.p("add event tomorrow") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4 – Timezone extraction unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractTimezone:
    """SlotExtractor._extract_timezone must recognise abbreviations and IANA."""

    def tz(self, text):
        return SlotExtractor._extract_timezone(text, text.lower())

    def test_utc(self):           assert self.tz("event at 10am UTC") == "UTC"
    def test_gmt(self):           assert self.tz("10:00 GMT") == "UTC"
    def test_cet(self):           assert self.tz("at 09:00 CET") == "Europe/Berlin"
    def test_est(self):           assert self.tz("3pm EST") == "America/New_York"
    def test_pst(self):           assert self.tz("9am PST") == "America/Los_Angeles"
    def test_iana_berlin(self):   assert self.tz("Europe/Berlin") == "Europe/Berlin"
    def test_iana_new_york(self): assert self.tz("America/New_York") == "America/New_York"
    def test_no_timezone(self):   assert self.tz("event tomorrow at noon") is None
    # "best" should NOT match "EST"
    def test_no_false_positive_best(self):
        result = self.tz("best time is 10am")
        assert result != "America/New_York", "'best' must not be parsed as EST"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5 – Confirmation flow (CONFIRM_ACTION routing)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfirmationFlow:
    """
    'yes' after a pending calendar event confirmation must route to CONFIRM_ACTION,
    not GENERAL_MESSAGE.
    """

    def _pending(self):
        return {
            "type": "create_calendar_event",
            "status": "awaiting_confirmation",
            "data": {
                "title": "Lunch",
                "date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                "time": "12:00",
                "end_time": "13:00",
                "provider": "outlook",
            },
        }

    def _active_task(self):
        return {
            "type": "calendar_event",
            "status": "awaiting_confirmation",
            "data": {"title": "Lunch"},
        }

    def test_yes_with_pending_action_routes_to_confirm(self):
        result = IntentRouter.route_message(
            message="yes",
            active_task=self._active_task(),
            pending_action=self._pending(),
            last_question_type=None,
        )
        assert result["intent_type"] == IntentType.CONFIRM_ACTION, (
            f"'yes' with pending_action must route to CONFIRM_ACTION, "
            f"got {result['intent_type']!r}"
        )

    def test_yes_without_pending_action_routes_to_general(self):
        """'yes' with NO pending action must NOT be treated as a confirmation."""
        result = IntentRouter.route_message(
            message="yes",
            active_task=None,
            pending_action=None,
            last_question_type=None,
        )
        assert result["intent_type"] == IntentType.GENERAL_MESSAGE, (
            f"'yes' without pending_action must route to GENERAL_MESSAGE, "
            f"got {result['intent_type']!r}"
        )

    def test_ok_with_pending_action_routes_to_confirm(self):
        result = IntentRouter.route_message(
            message="ok",
            active_task=self._active_task(),
            pending_action=self._pending(),
            last_question_type=None,
        )
        assert result["intent_type"] == IntentType.CONFIRM_ACTION

    def test_sure_with_pending_action_routes_to_confirm(self):
        result = IntentRouter.route_message(
            message="sure",
            active_task=self._active_task(),
            pending_action=self._pending(),
            last_question_type=None,
        )
        assert result["intent_type"] == IntentType.CONFIRM_ACTION


# ═══════════════════════════════════════════════════════════════════════════════
# Section 6 – Provider locking end-to-end: "on my outlook calendar" must NOT
#              fall back to google
# ═══════════════════════════════════════════════════════════════════════════════

class TestProviderLocking:
    """
    Task spec: "Provider locking: 'on my outlook calendar' must NOT fall back to google."
    """

    def test_outlook_never_falls_back_to_google(self):
        msg = "create me an event on my outlook calendar tomorrow at 2pm"
        result = IntentRouter.route_message(
            message=msg,
            active_task=None,
            pending_action=None,
        )
        assert result["intent_type"] == IntentType.CALENDAR_CREATE
        provider = result["extracted_slots"].get("provider")
        assert provider == "outlook", (
            f"Expected provider='outlook' — must NOT fall back to google. Got: {provider!r}"
        )
        assert provider != "google", "Outlook was incorrectly mapped to google!"

    def test_google_calendar_locks_to_google(self):
        msg = "add a meeting on google calendar next friday at 10am"
        result = IntentRouter.route_message(
            message=msg,
            active_task=None,
            pending_action=None,
        )
        assert result["intent_type"] == IntentType.CALENDAR_CREATE
        assert result["extracted_slots"].get("provider") == "google"

    def test_slot_extraction_with_outlook_provider_locked(self):
        """Slot extraction also must return provider=outlook, not google."""
        msg = "create me an event on my outlook calendar tomorrow at 12:00-13:00, call it Lunch"
        slots = SlotExtractor.extract_calendar_slots(msg, {})
        assert slots.get("provider") == "outlook", (
            f"SlotExtractor must lock provider='outlook'. Got: {slots.get('provider')!r}"
        )
        assert slots.get("provider") != "google"


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v"], check=True)
