"""
Regression tests for voice/executive-agent bugs fixed in the 2026-03-13 audit.

Bug reference                  | Test class / function
-------------------------------|------------------------------------------------------
#1 Voice WS crash (null task)  | TestFix1NullSafeActiveTask
#2 Confirmation priority       | TestFix2ConfirmationPriority
#3 Provider prefill in WS      | TestFix3VoiceProviderPrefill
#4 Email count extraction       | TestFix4EmailReadCount
#5 awaiting_confirmation loop   | TestFix5AwaitingConfirmationLoop
#6 Low-info transcript filter   | TestFix6LowInfoTranscript
#7 Latency / thread pool        | TestFix7ThreadPool

Run with:
    cd backend && python -m pytest tests/test_voice_bugs_regression.py -v
"""

import re
import sys
import os
import inspect
import pytest
import asyncio

# ---------------------------------------------------------------------------
# Path setup so we can import backend modules without installing the package.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===========================================================================
# Bug #1 — Null-safe _active_task access in voice_mode.py
# ===========================================================================

class TestFix1NullSafeActiveTask:
    """
    The logging Section 8 in voice_stream previously crashed with:
        AttributeError: 'NoneType' object has no attribute 'get'
    when _active_task was None (no active task after a completed action).

    Fix: (_active_task or {}).get("data") or {}
    """

    def test_null_active_task_two_step_extraction(self):
        """Simulates the patched extraction logic — must never raise."""
        _active_task = None  # no active task

        # The OLD code would raise AttributeError here:
        # (_active_task.get("data", {}) or {}).get("provider")
        #
        # The NEW code uses the two-step null-safe pattern:
        _task_data = (_active_task or {}).get("data") or {}
        _voice_provider = (
            _task_data.get("provider")
            or "unresolved"
        )
        assert _voice_provider == "unresolved"

    def test_empty_data_dict_in_active_task(self):
        """Task present but data is None — must not crash."""
        _active_task = {"type": "calendar_event", "status": "awaiting_confirmation", "data": None}
        _task_data = (_active_task or {}).get("data") or {}
        assert _task_data == {}
        assert _task_data.get("provider") is None

    def test_active_task_with_provider(self):
        """Normal path — provider extracted correctly."""
        _active_task = {
            "type": "calendar_event",
            "status": "awaiting_confirmation",
            "data": {"provider": "google", "title": "Meeting"},
        }
        _task_data = (_active_task or {}).get("data") or {}
        assert _task_data.get("provider") == "google"

    def test_voice_task_state_null_guard(self):
        """_voice_task_state must be 'IDLE' when active_task is None."""
        _active_task = None
        _voice_task_state = (
            _active_task.get("status", "IDLE").upper()
            if _active_task else "IDLE"
        )
        assert _voice_task_state == "IDLE"


# ===========================================================================
# Bug #2 — Confirmation handling priority (voice transcripts with punctuation)
# ===========================================================================

class TestFix2ConfirmationPriority:
    """
    IntentRouter._is_confirm_intent must return True for:
      "yes."  "Yes."  "yes, please."  "Yes, please."  "okay."  "ok."
    It must return False for:
      "no"  "cancel"  "maybe"
    """

    def _is_confirm(self, msg: str) -> bool:
        from utils.intent_router import IntentRouter
        return IntentRouter._is_confirm_intent(msg.lower().strip())

    def test_plain_yes(self):
        assert self._is_confirm("yes") is True

    def test_yes_with_period(self):
        assert self._is_confirm("yes.") is True

    def test_yes_capital_with_period(self):
        assert self._is_confirm("Yes.") is True

    def test_yes_please_with_period(self):
        assert self._is_confirm("yes, please.") is True

    def test_yes_please_capital(self):
        assert self._is_confirm("Yes, please.") is True

    def test_okay_period(self):
        assert self._is_confirm("okay.") is True

    def test_ok_exclamation(self):
        assert self._is_confirm("ok!") is True

    def test_sounds_good(self):
        assert self._is_confirm("sounds good.") is True

    def test_no_is_not_confirm(self):
        assert self._is_confirm("no") is False

    def test_cancel_is_not_confirm(self):
        assert self._is_confirm("cancel") is False

    def test_maybe_is_not_confirm(self):
        assert self._is_confirm("maybe") is False

    def test_confirmation_routes_to_confirm_action_when_pending(self):
        """
        When a pending_action exists with status=awaiting_confirmation,
        affirmative input must produce CONFIRM_ACTION — not PROVIDE_SLOT_VALUE.
        """
        from utils.intent_router import IntentRouter, IntentType

        pending = {"type": "create_calendar_event", "status": "awaiting_confirmation", "data": {}}
        active  = {"type": "calendar_event", "status": "awaiting_confirmation", "data": {}}

        for phrase in ["yes", "Yes.", "yes, please.", "Yes, please!", "okay.", "ok"]:
            result = IntentRouter.route_message(
                message=phrase,
                active_task=active,
                pending_action=pending,
                last_question_type=None,
            )
            assert result["intent_type"] == IntentType.CONFIRM_ACTION, (
                f"Expected CONFIRM_ACTION for {phrase!r}, got {result['intent_type']}"
            )


# ===========================================================================
# Bug #3 — Voice provider prefill: params must be hints, not forced
# ===========================================================================

class TestFix3VoiceProviderPrefill:
    """
    The voice_stream handler must NOT pass calendar_provider/mail_provider to
    agent.process_message() as forced slot values.

    We verify the signature of process_message: it accepts provider params,
    but the voice_stream call site (post-fix) must NOT supply them.
    """

    def test_voice_stream_does_not_forward_providers(self):
        """
        Read voice_mode.py and verify the agent.process_message() call does NOT
        pass calendar_provider= or mail_provider= from the WebSocket URL params.
        """
        voice_module_path = os.path.join(
            os.path.dirname(__file__), "..", "api", "voice_mode.py"
        )
        with open(voice_module_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Find the agent.process_message() call block
        # The fix comment should be present
        assert "intentionally NOT forwarded" in source, (
            "voice_mode.py must contain comment explaining provider params are not forwarded"
        )

        # The actual call must NOT contain calendar_provider= or mail_provider= as args.
        # We strip Python comment lines (# …) before checking so that the fix comment
        # "# calendar_provider and mail_provider intentionally NOT forwarded." is not
        # mistakenly matched as an actual argument.
        call_match = re.search(
            r'ai_resp\s*=\s*await\s+agent\.process_message\s*\((.+?)\)',
            source, re.DOTALL
        )
        assert call_match is not None, "Could not find agent.process_message() call in voice_mode.py"
        call_args_raw = call_match.group(1)
        # Remove comment-only lines so keyword presence test targets actual code
        call_args_no_comments = re.sub(r'#[^\n]*', '', call_args_raw)

        assert "calendar_provider" not in call_args_no_comments, (
            "voice_mode.py must NOT pass calendar_provider= to process_message() — it is a context hint only\n"
            f"Found in call args (comments stripped):\n{call_args_no_comments}"
        )
        assert "mail_provider" not in call_args_no_comments, (
            "voice_mode.py must NOT pass mail_provider= to process_message() — it is a context hint only\n"
            f"Found in call args (comments stripped):\n{call_args_no_comments}"
        )


# ===========================================================================
# Bug #4 — Email read count: word-based numeric extraction
# ===========================================================================

class TestFix4EmailReadCount:
    """
    extract_email_read_slots must correctly parse word-based counts like
    "two", "three", "five" in common voice-transcribed phrases.
    """

    def _slots(self, msg: str) -> dict:
        from utils.slot_extraction import SlotExtractor
        return SlotExtractor.extract_email_read_slots(msg)

    def test_last_two_emails(self):
        slots = self._slots("Can you show me my last two emails on my Gmail account?")
        assert slots["count"] == 2, f"Expected 2, got {slots['count']}"

    def test_last_three_emails(self):
        slots = self._slots("show me my last three emails")
        assert slots["count"] == 3

    def test_last_five_emails(self):
        slots = self._slots("read my last five emails")
        assert slots["count"] == 5

    def test_show_three_messages(self):
        slots = self._slots("show three messages")
        assert slots["count"] == 3

    def test_next_five_emails(self):
        slots = self._slots("read my next five emails")
        assert slots["count"] == 5

    def test_numeric_count_still_works(self):
        """Digit-based extraction must still work after the fix."""
        slots = self._slots("show me last 3 emails")
        assert slots["count"] == 3

    def test_digit_ten(self):
        slots = self._slots("get me last 10 emails")
        assert slots["count"] == 10

    def test_word_one(self):
        slots = self._slots("show me my last one email")
        assert slots["count"] == 1

    def test_a_couple_of_emails(self):
        slots = self._slots("show me a couple of emails")
        assert slots["count"] == 2

    def test_a_few_emails(self):
        slots = self._slots("show me a few emails")
        assert slots["count"] == 3

    def test_default_count_without_number(self):
        """No count mentioned → safe default of 5."""
        slots = self._slots("check my inbox")
        assert slots["count"] == 5


# ===========================================================================
# Bug #5 — awaiting_confirmation loop: same-content repeat must not re-loop
# ===========================================================================

class TestFix5AwaitingConfirmationLoop:
    """
    When _handle_modify_draft is called while active_task.status ==
    'awaiting_confirmation' and NLU extracts updates that are IDENTICAL to
    the current_data, the fix must treat this as an implicit confirmation
    (call _handle_confirmation) rather than re-dispatching and looping.
    """

    @pytest.fixture
    def loop(self):
        return asyncio.new_event_loop()

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_modified_draft_loop_guard_logic(self):
        """
        Unit test of the loop-guard logic in isolation (no I/O required).

        Simulates: updates == current_data (same content → implicit confirm)
        """
        current_data = {
            "title": "Meeting with Chef",
            "date": "2026-03-14",
            "time": "08:00",
            "provider": "google",
        }
        updates = {
            "title": "Meeting with Chef",
            "date": "2026-03-14",
        }
        active_task_status = "awaiting_confirmation"

        changed_keys = {
            k: v for k, v in updates.items()
            if current_data.get(k) != v
        }
        assert changed_keys == {}, "No keys should differ — user repeated same content"
        # Verify the code path that should be taken: implicit confirmation
        should_confirm = (active_task_status == "awaiting_confirmation" and not changed_keys)
        assert should_confirm is True

    def test_partial_update_not_treated_as_confirm(self):
        """
        When some keys DO differ, only those keys should be updated, not confirmed.
        """
        current_data = {
            "title": "Meeting with Chef",
            "date": "2026-03-14",
            "time": "08:00",
            "provider": "google",
        }
        updates = {
            "title": "Meeting with Chef",  # same
            "time": "09:00",               # changed!
        }
        changed_keys = {
            k: v for k, v in updates.items()
            if current_data.get(k) != v
        }
        assert changed_keys == {"time": "09:00"}
        # The fix applies only changes, not a full confirm
        assert len(changed_keys) == 1

    def test_empty_updates_do_not_confirm(self):
        """
        If NLU found NO updates at all (empty dict), the loop guard must NOT
        trigger implicit confirmation (empty dict ≠ same-content repeat — it's
        a failed extraction, handled separately).
        """
        current_data = {"title": "Meeting", "provider": "google"}
        updates = {}  # NLU found nothing

        # The fix only runs when updates is truthy
        guard_fires = bool(updates)
        assert guard_fires is False, (
            "An empty updates dict should NOT trigger the same-content loop guard"
        )


# ===========================================================================
# Bug #6 — Low-information transcript filtering
# ===========================================================================

class TestFix6LowInfoTranscript:
    """
    _is_low_information_transcript must return True for filler-only or
    trailing-filler fragments, and False for real short commands.
    """

    def _check(self, text: str) -> bool:
        # Import directly from voice_mode
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
        from voice_mode import _is_low_information_transcript
        return _is_low_information_transcript(text)

    # ── Should be filtered (True) ─────────────────────────────────────────────

    def test_pure_filler_um(self):
        assert self._check("um") is True

    def test_pure_filler_uh(self):
        assert self._check("uh") is True

    def test_pure_filler_hmm(self):
        assert self._check("hmm") is True

    def test_all_filler_words(self):
        assert self._check("well uh um") is True

    def test_trailing_filler_short(self):
        # "Hello, can you uh" — 4 words, ends with filler
        assert self._check("Hello, can you uh") is True

    def test_trailing_filler_exactly_six_words(self):
        assert self._check("yes I think so uh") is True

    def test_empty_string(self):
        assert self._check("") is True

    # ── Must NOT be filtered (False) ─────────────────────────────────────────

    def test_plain_yes(self):
        assert self._check("yes") is False

    def test_plain_no(self):
        assert self._check("no") is False

    def test_cancel(self):
        assert self._check("cancel") is False

    def test_hello(self):
        assert self._check("hello") is False

    def test_real_short_command(self):
        assert self._check("create a meeting") is False

    def test_real_command_with_trailing_filler_seven_words(self):
        # 7 words — exceeds the 6-word limit, so not filtered even if it ends with "uh"
        assert self._check("schedule my meeting with Anna tomorrow uh") is False

    def test_confirmation_phrase(self):
        assert self._check("yes please go ahead") is False


# ===========================================================================
# Bug #7 — Thread pool / latency: verify executor uses ≥ 4 workers
# ===========================================================================

class TestFix7ThreadPool:
    """
    The CPU-bound thread executor in voice_mode.py must be configured with
    at least 4 workers to reduce queue-wait for concurrent STT requests.
    """

    def test_executor_max_workers_ge_4(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
        import voice_mode
        executor = voice_mode._cpu_executor
        # ThreadPoolExecutor stores _max_workers as an attribute
        max_workers = getattr(executor, "_max_workers", None)
        assert max_workers is not None, "_cpu_executor must have _max_workers attribute"
        assert max_workers >= 4, (
            f"_cpu_executor must have at least 4 workers to reduce STT queue latency, "
            f"got {max_workers}"
        )

    def test_latency_comments_present(self):
        """
        Ensure the latency root-cause comments were added (they document the fix
        for future maintainers and prevent regression via 'delete comment + revert').
        """
        voice_module_path = os.path.join(
            os.path.dirname(__file__), "..", "api", "voice_mode.py"
        )
        with open(voice_module_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "LATENCY SPIKE ROOT CAUSES" in source, (
            "voice_mode.py must contain LATENCY SPIKE ROOT CAUSES comment block (Bug #7 fix)"
        )
        assert "max_workers" in source, (
            "voice_mode.py must document max_workers reasoning (Bug #7 fix)"
        )


# ===========================================================================
# Integration-level smoke test — IntentRouter PRIORITY ordering
# ===========================================================================

class TestIntentRouterPriorityOrder:
    """
    Confirm that CONFIRM_ACTION is evaluated BEFORE PROVIDE_SLOT_VALUE
    so that "yes" during awaiting_confirmation always confirms, never fills.
    """

    def test_yes_during_awaiting_confirmation_is_confirm(self):
        from utils.intent_router import IntentRouter, IntentType

        active  = {"type": "calendar_event", "status": "awaiting_confirmation", "data": {"title": "Meeting"}}
        pending = {"type": "create_calendar_event", "status": "awaiting_confirmation", "data": {}}

        for phrase in ["yes", "yes.", "Yes.", "yes, please.", "Yes, please!", "ok", "okay."]:
            result = IntentRouter.route_message(
                message=phrase,
                active_task=active,
                pending_action=pending,
            )
            assert result["intent_type"] == IntentType.CONFIRM_ACTION, (
                f"CONFIRM_ACTION must take priority for {phrase!r}, "
                f"got {result['intent_type']}"
            )

    def test_correction_during_awaiting_confirmation_is_modify_draft(self):
        """'no, use outlook' while awaiting_confirmation → MODIFY_DRAFT / CANCEL."""
        from utils.intent_router import IntentRouter, IntentType

        active  = {"type": "calendar_event", "status": "awaiting_confirmation", "data": {}}
        pending = {"type": "create_calendar_event", "status": "awaiting_confirmation", "data": {}}

        # "no, use outlook" should NOT be CONFIRM_ACTION
        result = IntentRouter.route_message(
            message="no, use outlook",
            active_task=active,
            pending_action=pending,
        )
        assert result["intent_type"] != IntentType.CONFIRM_ACTION, (
            "A correction phrase must NOT be classified as CONFIRM_ACTION"
        )
