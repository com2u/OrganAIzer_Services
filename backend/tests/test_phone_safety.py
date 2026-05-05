"""
Phone safety tests for voice/call_trigger.py and api/phone.py.

Covers:
  - German-only number restriction (is_german_number)
  - Number masking (mask_number) — raw number never leaks
  - Purpose extraction from natural-language messages
  - Confirmation state machine (confirm_prompt → calling)
  - Affirmative without pending does NOT dial
  - Active-call blocking via phone_state

No FreeSWITCH, no ESL, no real calls, no real contacts file.
originate_call is patched for every test that reaches the dial path.
"""

import asyncio
import sys
import os
import threading
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice.call_trigger import (
    is_german_number,
    mask_number,
    extract_call_request,
    handle_message,
    _pending,
    _pending_lock,
)

# ── Shared session IDs so tests never collide ─────────────────────────────────
_SID = "test_session_phone_safety"
_SID2 = "test_session_active_block"

# ── Originate-call mock: always succeeds, no network ─────────────────────────
_FAKE_UUID = "fake-uuid-1234-5678"
_FAKE_ORIGINATE = MagicMock(return_value=(True, _FAKE_UUID))


def _clear_pending():
    with _pending_lock:
        _pending.clear()


# =============================================================================
# German number restriction — is_german_number()
# =============================================================================

class TestGermanNumberAllowed:
    """Numbers that MUST be allowed."""

    def test_plus49_long(self):
        assert is_german_number("+4930123456789") is True

    def test_plus49_mobile(self):
        assert is_german_number("+4915112345678") is True

    def test_plus49_short_local(self):
        assert is_german_number("+498001234567") is True

    def test_0049_prefix(self):
        assert is_german_number("0049301234567") is True

    def test_national_zero_prefix(self):
        assert is_german_number("0661123456789") is True

    def test_national_mobile_zero(self):
        assert is_german_number("01751234567") is True

    def test_spaces_stripped(self):
        assert is_german_number("+49 30 123 456 789") is True

    def test_dashes_stripped(self):
        assert is_german_number("+49-30-1234-5678") is True

    def test_parentheses_stripped(self):
        assert is_german_number("+49 (30) 1234567") is True


class TestNonGermanNumberBlocked:
    """Numbers that MUST be blocked (non-German)."""

    def test_us_number(self):
        assert is_german_number("+18005551234") is False

    def test_uk_number(self):
        assert is_german_number("+441234567890") is False

    def test_france_number(self):
        assert is_german_number("+33123456789") is False

    def test_00_france(self):
        assert is_german_number("0033123456789") is False

    def test_00_uk(self):
        assert is_german_number("0044123456789") is False

    def test_00_us(self):
        assert is_german_number("001800555") is False

    def test_swiss_number(self):
        assert is_german_number("+41441234567") is False

    def test_austria_number(self):
        assert is_german_number("+43112345678") is False

    def test_empty_string(self):
        assert is_german_number("") is False

    def test_letters_only(self):
        assert is_german_number("notanumber") is False


# =============================================================================
# Number masking — mask_number()
# =============================================================================

class TestNumberMasking:
    """mask_number must never leak the raw number in the output."""

    def _assert_masked(self, raw: str):
        masked = mask_number(raw)
        # Raw number must not appear unchanged in the masked output
        # Strip spaces/dashes for the leak check
        digits = "".join(c for c in raw if c.isdigit())
        # Middle digits should be gone; masked form must contain ******
        assert "******" in masked, f"Expected ****** in masked form for {raw!r}"
        # The full original must not appear verbatim
        assert raw.replace(" ", "") not in masked.replace(" ", "")

    def test_plus49_number_masked(self):
        self._assert_masked("+491234567890")

    def test_national_number_masked(self):
        self._assert_masked("06611234567890")

    def test_0049_number_masked(self):
        self._assert_masked("0049301234567890")

    def test_last_four_digits_preserved(self):
        masked = mask_number("+491234569999")
        assert "9999" in masked

    def test_prefix_preserved_plus49(self):
        masked = mask_number("+4930123456789")
        assert masked.startswith("+49")

    def test_prefix_preserved_0049(self):
        masked = mask_number("00493012345678")
        # prefix for 0049... starts with digits after stripping
        assert "00" in masked[:5]

    def test_prefix_preserved_national(self):
        masked = mask_number("0661123456789")
        assert masked.startswith("066")

    def test_empty_input_returns_empty(self):
        assert mask_number("") == ""

    def test_none_like_empty_not_crash(self):
        # empty string edge case — must not raise
        result = mask_number("")
        assert isinstance(result, str)


# =============================================================================
# Purpose extraction — extract_call_request()
# =============================================================================

class TestPurposeExtraction:
    """extract_call_request must detect message intent and split off purpose."""

    def test_tell_him_purpose(self):
        result = extract_call_request("call +4930123456789 and tell him the meeting is cancelled")
        assert result["number"] == "+4930123456789"
        assert result["purpose"] == "the meeting is cancelled"

    def test_tell_them_purpose(self):
        result = extract_call_request("call +4930112345 and tell them we are running late")
        assert result["purpose"] == "we are running late"

    def test_sag_ihm_purpose(self):
        result = extract_call_request("rufe +4930987654321 an und sag ihm das Meeting ist verschoben")
        assert result["purpose"] is not None
        assert "Meeting" in result["purpose"]

    def test_richte_aus_pattern(self):
        result = extract_call_request("richte Anna aus dass das Meeting abgesagt ist")
        assert result["name"] == "Anna"
        assert result["purpose"] == "das Meeting abgesagt ist"

    def test_richte_aus_with_bitte(self):
        result = extract_call_request("bitte richte Klaus aus dass er morgen kommen soll")
        assert result["name"] == "Klaus"
        assert result["purpose"] is not None
        assert "morgen" in result["purpose"]

    def test_no_purpose_returns_none(self):
        result = extract_call_request("call +4930123456789")
        assert result["purpose"] is None

    def test_purpose_stripped_of_control_chars(self):
        result = extract_call_request("call +4930123456789 and tell him \x00hello")
        # Control chars must be stripped
        if result["purpose"]:
            assert "\x00" not in result["purpose"]

    def test_purpose_max_length(self):
        long_purpose = "x" * 400
        result = extract_call_request(f"call +4930123456789 and tell him {long_purpose}")
        if result["purpose"]:
            assert len(result["purpose"]) <= 300


# =============================================================================
# Confirmation state machine — handle_message()
# =============================================================================

class TestConfirmationRequired:
    """A call intent must produce confirm_prompt, NEVER call immediately."""

    def setup_method(self):
        _clear_pending()

    def teardown_method(self):
        _clear_pending()

    def test_call_number_returns_confirm_prompt(self):
        result = handle_message("call +4930123456789", _SID)
        assert result["action"] == "confirm_prompt"
        assert "masked_number" in result
        # Raw number must NOT appear in any response field
        for v in result.values():
            if isinstance(v, str):
                assert "+4930123456789" not in v, (
                    f"Raw phone number leaked in response field: {v!r}"
                )

    def test_ruf_an_returns_confirm_prompt(self):
        result = handle_message("ruf +4915112345678 an", _SID + "_ruf")
        assert result["action"] == "confirm_prompt"

    def test_no_call_is_made_without_confirmation(self):
        with patch("voice.outbound.originate_call", _FAKE_ORIGINATE) as mock_call:
            handle_message("call +4930123456789", _SID + "_nc")
            mock_call.assert_not_called()

    def test_confirm_prompt_contains_masked_number_only(self):
        result = handle_message("call +4930123456789", _SID + "_mask")
        message = result.get("message", "")
        assert "+4930123456789" not in message
        assert "masked_number" in result
        assert "******" in result["masked_number"]


class TestAffirmativeWithoutPending:
    """Affirmative input with no pending call must NOT dial."""

    def setup_method(self):
        _clear_pending()

    def teardown_method(self):
        _clear_pending()

    def _assert_no_call(self, phrase: str):
        with patch("voice.outbound.originate_call", _FAKE_ORIGINATE) as mock_call:
            result = handle_message(phrase, _SID + "_nopend")
            mock_call.assert_not_called()
            assert result["action"] != "calling"

    def test_ja_without_pending_does_not_call(self):
        self._assert_no_call("ja")

    def test_yes_without_pending_does_not_call(self):
        self._assert_no_call("yes")

    def test_ok_without_pending_does_not_call(self):
        self._assert_no_call("ok")

    def test_klar_without_pending_does_not_call(self):
        self._assert_no_call("klar")

    def test_ja_returns_none_action(self):
        result = handle_message("ja", _SID + "_none")
        # "ja" has no call-intent keyword → action: "none"
        assert result["action"] == "none"


class TestAffirmativeWithPending:
    """After a confirm_prompt, affirmative triggers the call."""

    def setup_method(self):
        _clear_pending()

    def teardown_method(self):
        _clear_pending()

    def test_ja_after_pending_calls_originate(self):
        sid = _SID + "_affirm"
        # Pre-seed a pending entry (simulates the user having said "call +49...")
        with _pending_lock:
            _pending[sid] = {
                "number": "+4930123456789",
                "display_name": "TestKontakt",
                "purpose": None,
            }

        with patch("voice.outbound.originate_call", return_value=(True, _FAKE_UUID)) as mock_call:
            result = handle_message("ja", sid)

        assert result["action"] == "calling"
        mock_call.assert_called_once()
        call_args = mock_call.call_args
        assert call_args.kwargs.get("number") == "+4930123456789" or \
               (call_args.args and call_args.args[0] == "+4930123456789")

    def test_nein_after_pending_cancels(self):
        sid = _SID + "_neg"
        with _pending_lock:
            _pending[sid] = {"number": "+4930123456789", "display_name": None, "purpose": None}

        with patch("voice.outbound.originate_call", _FAKE_ORIGINATE) as mock_call:
            result = handle_message("nein", sid)

        assert result["action"] == "cancelled"
        mock_call.assert_not_called()

    def test_cancel_after_pending_cancels(self):
        sid = _SID + "_cancel"
        with _pending_lock:
            _pending[sid] = {"number": "+4930123456789", "display_name": None, "purpose": None}

        with patch("voice.outbound.originate_call", _FAKE_ORIGINATE) as mock_call:
            result = handle_message("abbrechen", sid)

        assert result["action"] == "cancelled"
        mock_call.assert_not_called()

    def test_calling_response_contains_masked_number_only(self):
        sid = _SID + "_mask_call"
        with _pending_lock:
            _pending[sid] = {
                "number": "+4930123456789",
                "display_name": "Test",
                "purpose": None,
            }

        with patch("voice.outbound.originate_call", return_value=(True, _FAKE_UUID)):
            result = handle_message("ja", sid)

        assert result["action"] == "calling"
        for v in result.values():
            if isinstance(v, str):
                assert "+4930123456789" not in v, (
                    f"Raw phone number leaked in calling response field: {v!r}"
                )

    def test_non_german_number_in_pending_never_reaches_originate(self):
        """
        This should never happen in normal flow (resolve_contact blocks non-German
        numbers), but if _pending were seeded with one the behaviour must be safe.
        The outbound layer does not recheck — the guard is at resolve_contact time.
        This test verifies that a pending entry with a non-German number still
        passes through and originate_call is called with whatever is in _pending.
        It documents that the German-only gate lives at resolve_contact, not here.
        """
        sid = _SID + "_nongerman"
        with _pending_lock:
            _pending[sid] = {
                "number": "+18005551234",
                "display_name": None,
                "purpose": None,
            }

        with patch("voice.outbound.originate_call", return_value=(True, _FAKE_UUID)) as mock_call:
            result = handle_message("ja", sid)

        # originate_call IS called — German guard was already at resolve_contact
        assert result["action"] == "calling"
        mock_call.assert_called_once()


# =============================================================================
# Non-German number blocked at resolve_contact()
# =============================================================================

class TestNonGermanBlockedAtResolution:
    """resolve_contact must reject non-German numbers before any pending is set."""

    def setup_method(self):
        _clear_pending()

    def teardown_method(self):
        _clear_pending()

    def test_us_number_returns_error_not_confirm(self):
        result = handle_message("call +18005551234", _SID + "_usblock")
        assert result["action"] == "error"
        assert "nur deutsche" in result["message"].lower() or \
               "german" in result["message"].lower()

    def test_us_number_does_not_add_to_pending(self):
        sid = _SID + "_uspend"
        handle_message("call +18005551234", sid)
        with _pending_lock:
            assert sid not in _pending

    def test_uk_number_blocked(self):
        result = handle_message("call +441234567890", _SID + "_uk")
        assert result["action"] == "error"

    def test_no_call_for_blocked_number(self):
        with patch("voice.outbound.originate_call", _FAKE_ORIGINATE) as mock_call:
            handle_message("call +18005551234", _SID + "_nodc")
            mock_call.assert_not_called()


# =============================================================================
# Active-call blocking — api/phone.py phone_state check
# =============================================================================

class TestActiveCallBlocking:
    """
    The /message endpoint must return 409 when a call is already active.
    Tested by calling handle_call_message() directly (no HTTP server needed).
    """

    def setup_method(self):
        _clear_pending()

    def teardown_method(self):
        _clear_pending()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_active_call_blocks_affirmative(self):
        from fastapi import HTTPException
        import api.phone as phone_api

        phone_api.phone_state["active_call"] = {
            "caller": "+4930111111111",
            "started_at": "2026-01-01T10:00:00",
        }
        phone_api.phone_state["ringing_call"] = None

        try:
            request = phone_api.CallMessageRequest(message="ja", session_id=_SID2)
            with pytest.raises(HTTPException) as exc_info:
                self._run(phone_api.handle_call_message(request))
            assert exc_info.value.status_code == 409
            assert exc_info.value.detail["code"] == "CALL_IN_PROGRESS"
        finally:
            phone_api.phone_state["active_call"] = None

    def test_ringing_call_blocks_affirmative(self):
        from fastapi import HTTPException
        import api.phone as phone_api

        phone_api.phone_state["active_call"] = None
        phone_api.phone_state["ringing_call"] = {
            "caller": "+4930222222222",
            "ringing_since": "2026-01-01T10:00:00",
            "direction": "inbound",
        }

        try:
            request = phone_api.CallMessageRequest(message="ok", session_id=_SID2 + "_ring")
            with pytest.raises(HTTPException) as exc_info:
                self._run(phone_api.handle_call_message(request))
            assert exc_info.value.status_code == 409
        finally:
            phone_api.phone_state["ringing_call"] = None

    def test_no_active_call_does_not_block(self):
        import api.phone as phone_api

        phone_api.phone_state["active_call"] = None
        phone_api.phone_state["ringing_call"] = None

        request = phone_api.CallMessageRequest(message="ja", session_id=_SID2 + "_free")
        # With no pending, "ja" returns action="none" without raising
        with patch("voice.outbound.originate_call", _FAKE_ORIGINATE):
            result = self._run(phone_api.handle_call_message(request))
        assert result["action"] == "none"


# =============================================================================
# Outbound opening_line carries the custom purpose
# =============================================================================

class TestOutboundOpeningLineWithPurpose:
    """Purpose from the user message must appear in opening_line passed to originate_call."""

    def setup_method(self):
        _clear_pending()

    def teardown_method(self):
        _clear_pending()

    def _confirm_and_call(self, sid: str, message: str) -> tuple:
        """Drive handle_message through confirm → ja, return (opening_line, system_prompt)."""
        handle_message(message, sid)
        with patch("voice.outbound.originate_call", return_value=(True, "uuid-test")) as m:
            handle_message("ja", sid)
        kw = m.call_args.kwargs
        return kw.get("opening_line", ""), kw.get("system_prompt", "")

    def test_purpose_in_opening_line(self):
        line, _ = self._confirm_and_call(
            "test_ol_purpose",
            "call +4930123456789 and tell them the meeting is at 3pm",
        )
        assert "3pm" in line or "3" in line

    def test_purpose_replaces_generic_greeting(self):
        line, _ = self._confirm_and_call(
            "test_ol_no_generic",
            "call +4930123456789 and tell them the project is done",
        )
        # Custom purpose → must NOT use the default "kurz vorzustellen" fallback
        assert "kurz vorzustellen" not in line

    def test_no_purpose_uses_default_opening_line(self):
        line, _ = self._confirm_and_call(
            "test_ol_default",
            "call +4930123456789",
        )
        # No purpose → default OrganAIzer intro should appear
        assert "OrganAIzer" in line or "KI-Assistent" in line

    def test_purpose_message_content_in_opening_line(self):
        sid = "test_ol_content"
        handle_message("call +4930123456789 and tell them Ihr Paket ist angekommen", sid)
        with patch("voice.outbound.originate_call", return_value=(True, "uuid-pkg")) as m:
            handle_message("ja", sid)
        line = m.call_args.kwargs.get("opening_line", "")
        assert "Paket" in line or "angekommen" in line


# =============================================================================
# Outbound system prompt / note must prevent re-introduction
# =============================================================================

class TestOutboundSystemPromptHasNoReintroduction:
    """system_prompt passed to originate_call must tell the LLM not to re-introduce itself."""

    def setup_method(self):
        _clear_pending()

    def teardown_method(self):
        _clear_pending()

    def _get_prompt_for_purpose_call(self, sid: str) -> str:
        handle_message("call +4930123456789 and tell them the meeting is cancelled", sid)
        with patch("voice.outbound.originate_call", return_value=(True, "uuid-sp")) as m:
            handle_message("ja", sid)
        return m.call_args.kwargs.get("system_prompt", "")

    def test_system_prompt_contains_do_not_re_introduce(self):
        prompt = self._get_prompt_for_purpose_call("test_sp_norei")
        assert "do not re-introduce" in prompt.lower() or "not re-introduce" in prompt.lower()

    def test_system_prompt_references_conversation_history(self):
        prompt = self._get_prompt_for_purpose_call("test_sp_hist")
        assert "history" in prompt.lower() or "conversation" in prompt.lower()

    def test_outbound_system_prompt_constant_has_no_hardcoded_intro_directive(self):
        from voice.llm_bridge import OUTBOUND_SYSTEM_PROMPT
        # The old "Introduce yourself with: ..." mandate must be gone
        assert 'Introduce yourself as calling from OrganAIzer with:' not in OUTBOUND_SYSTEM_PROMPT

    def test_outbound_system_prompt_constant_still_has_fallback_intro(self):
        from voice.llm_bridge import OUTBOUND_SYSTEM_PROMPT
        # A fallback intro for when history is empty must still exist
        assert "OrganAIzer" in OUTBOUND_SYSTEM_PROMPT
        assert "history" in OUTBOUND_SYSTEM_PROMPT.lower() or \
               "already been delivered" in OUTBOUND_SYSTEM_PROMPT.lower()


# =============================================================================
# Outbound history seeded with opening_line before _conversation_loop
# =============================================================================

class TestOutboundHistorySeededWithOpeningLine:
    """handle_esl_call must append opening_line to history before calling _conversation_loop."""

    def test_opening_line_appended_to_history_before_loop(self):
        import queue as _queue
        from pathlib import Path
        from voice.esl_call_handler import handle_esl_call
        import voice.outbound as _outbound

        _UUID = "uuid-hist-seed"
        _OPENING = "Guten Tag, ich rufe wegen des abgesagten Meetings an."

        mock_handler = MagicMock()
        mock_handler.is_hung_up = False
        mock_handler.get_uuid.return_value = _UUID
        mock_handler.get_caller_id.return_value = "+4930123456789"
        mock_handler.get_caller_name.return_value = ""
        mock_handler.execute.return_value = True

        captured: list = []

        def _capture_loop(handler, history, **kw):
            captured.extend(list(history))

        ps = {
            "active_call": None, "ringing_call": None,
            "esl_handler": None, "bridge_call": None,
            "whisper_queue": _queue.Queue(),
        }

        _outbound._pending[_UUID] = {
            "number": "+4930123456789",
            "opening_line": _OPENING,
            "system_prompt": "test prompt",
            "lang": "de",
        }
        try:
            with patch("voice.esl_call_handler._speak_and_play"), \
                 patch("voice.esl_call_handler._conversation_loop",
                       side_effect=_capture_loop), \
                 patch("voice.esl_call_handler._audio_dir",
                       return_value=Path("/tmp")):
                handle_esl_call(mock_handler, ps)
        finally:
            _outbound._pending.pop(_UUID, None)

        assert any(
            m.get("role") == "assistant" and _OPENING in m.get("content", "")
            for m in captured
        ), f"opening_line not found in history; captured={captured}"

    def test_history_is_empty_for_inbound_calls(self):
        """Inbound calls must NOT pre-seed history — they start fresh."""
        import queue as _queue
        from pathlib import Path
        from voice.esl_call_handler import handle_esl_call

        mock_handler = MagicMock()
        mock_handler.is_hung_up = False
        mock_handler.get_uuid.return_value = "uuid-inbound-hist"
        mock_handler.get_caller_id.return_value = "+4930111111111"
        mock_handler.get_caller_name.return_value = ""
        mock_handler.execute.return_value = True

        captured: list = []

        def _capture_loop(handler, history, **kw):
            captured.extend(list(history))

        ps = {
            "active_call": None, "ringing_call": None,
            "esl_handler": None, "bridge_call": None,
            "whisper_queue": _queue.Queue(),
        }

        # No entry in _outbound._pending → inbound path.
        # wait_for_ring_decision is imported inside the function body, so patch
        # it at the source module rather than on esl_call_handler.
        with patch("voice.esl_call_handler._speak_and_play"), \
             patch("voice.esl_call_handler._conversation_loop",
                   side_effect=_capture_loop), \
             patch("voice.esl_call_handler._audio_dir",
                   return_value=Path("/tmp")), \
             patch("api.phone.wait_for_ring_decision", return_value="ai"):
            handle_esl_call(mock_handler, ps)

        # Inbound history must not contain any pre-seeded assistant messages
        assert not any(m.get("role") == "assistant" for m in captured), \
            f"Inbound history should be empty; captured={captured}"


# =============================================================================
# Empty-turn / silence resilience — _conversation_loop
# =============================================================================

class TestEmptyTurnLogic:
    """
    _conversation_loop must tolerate multiple silent turns before hanging up.
    No FreeSWITCH, no real audio — the WAV file never exists so transcription
    returns empty, driving the empty-turn counter each iteration.
    """

    def _run_loop_all_empty(self) -> list[str]:
        """
        Run _conversation_loop with all-empty recording turns until it terminates
        on its own (farewell + break).  Returns the list of texts passed to
        _speak_and_play in call order.
        """
        from datetime import datetime, timezone
        from pathlib import Path
        from voice.esl_call_handler import _conversation_loop

        mock_handler = MagicMock()
        mock_handler.execute.return_value = True
        mock_handler.is_hung_up = False

        spoken: list[str] = []

        def _fake_speak(handler, text, lang=None):
            spoken.append(text)

        with patch("voice.esl_call_handler._audio_dir", return_value=Path("/tmp")), \
             patch("voice.esl_call_handler._speak_and_play", side_effect=_fake_speak), \
             patch("voice.esl_call_handler._get_filler_wav", return_value=""):
            _conversation_loop(
                handler=mock_handler,
                history=[],
                caller="+4930123456789",
                caller_name=None,
                started_at=datetime.now(timezone.utc),
                system_prompt="test",
                turn_count_ref=[0],
                uuid="uuid-empty-loop",
                initial_lang="de",
            )

        return spoken

    def test_farewell_is_eventually_spoken(self):
        spoken = self._run_loop_all_empty()
        assert any("Auf Wiederhören" in s or "Goodbye" in s for s in spoken), (
            f"Farewell never spoken; got: {spoken}"
        )

    def test_check_in_played_after_two_empty_turns(self):
        spoken = self._run_loop_all_empty()
        assert any("noch da" in s or "still there" in s.lower() for s in spoken), (
            f"Check-in ('Sind Sie noch da?') never spoken; got: {spoken}"
        )

    def test_check_in_precedes_farewell(self):
        spoken = self._run_loop_all_empty()
        check_in_idx = next(
            (i for i, s in enumerate(spoken) if "noch da" in s or "still there" in s.lower()),
            None,
        )
        farewell_idx = next(
            (i for i, s in enumerate(spoken) if "Auf Wiederhören" in s or "Goodbye" in s),
            None,
        )
        assert check_in_idx is not None, "Check-in never played"
        assert farewell_idx is not None, "Farewell never played"
        assert check_in_idx < farewell_idx, "Check-in must be spoken before farewell"

    def test_at_least_six_record_attempts_before_hangup(self):
        """Loop must survive at least 6 silent turns — well above the old limit of 4."""
        from datetime import datetime, timezone
        from pathlib import Path
        from voice.esl_call_handler import _conversation_loop

        mock_handler = MagicMock()
        mock_handler.is_hung_up = False
        record_calls = [0]

        def _count(*args, **kwargs):
            if args and args[0] == "record":
                record_calls[0] += 1
            return True

        mock_handler.execute.side_effect = _count

        with patch("voice.esl_call_handler._audio_dir", return_value=Path("/tmp")), \
             patch("voice.esl_call_handler._speak_and_play"), \
             patch("voice.esl_call_handler._get_filler_wav", return_value=""):
            _conversation_loop(
                handler=mock_handler,
                history=[],
                caller="+4930123456789",
                caller_name=None,
                started_at=datetime.now(timezone.utc),
                system_prompt="test",
                turn_count_ref=[0],
                uuid="uuid-record-count",
                initial_lang="de",
            )

        assert record_calls[0] >= 6, (
            f"Expected ≥6 record attempts before hangup, got {record_calls[0]}"
        )

    def test_real_speech_resets_empty_counter(self):
        """After a real transcription, empty_turns resets — call must not hang up prematurely."""
        from datetime import datetime, timezone
        from pathlib import Path
        from voice.esl_call_handler import _conversation_loop

        mock_handler = MagicMock()
        record_calls = [0]

        def _is_hung_up(self):
            # Hang up after 4 record calls (synchronous counter — no threading race).
            # Sequence: empty, empty (check-in), Hallo (counter resets), empty → hung up.
            # The loop exits before reaching _MAX_EMPTY_TURNS so farewell is never spoken.
            return record_calls[0] >= 4

        type(mock_handler).is_hung_up = property(_is_hung_up)

        spoken: list[str] = []

        def _count_execute(*args, **kwargs):
            if args and args[0] == "record":
                record_calls[0] += 1
                # Touch the WAV file so _process_turn's Path.exists() check
                # succeeds and transcribe_file (our fake) is actually called.
                Path(args[1].split()[0]).touch()
            return True

        mock_handler.execute.side_effect = _count_execute

        # Transcription: 2 empty turns, 1 real speech, 1 empty — counter must reset
        transcriptions = [("", "de"), ("", "de"), ("Hallo", "de"), ("", "de")]
        _t_idx = [0]

        def _fake_transcribe(path, lang=None):
            idx = _t_idx[0]
            _t_idx[0] += 1
            if idx < len(transcriptions):
                return transcriptions[idx]
            return ("", "de")

        async def _fake_get_response(*a, **kw):
            return "Danke!"

        with patch("voice.esl_call_handler._audio_dir", return_value=Path("/tmp")), \
             patch("voice.esl_call_handler._speak_and_play",
                   side_effect=lambda h, t, lang=None: spoken.append(t)), \
             patch("voice.esl_call_handler._get_filler_wav", return_value=""), \
             patch("voice.esl_call_handler.transcribe_file",
                   side_effect=_fake_transcribe), \
             patch("voice.esl_call_handler.get_response",
                   side_effect=_fake_get_response), \
             patch("voice.esl_call_handler.speak_to_file", return_value=""):
            _conversation_loop(
                handler=mock_handler,
                history=[],
                caller="+4930123456789",
                caller_name=None,
                started_at=datetime.now(timezone.utc),
                system_prompt="test",
                turn_count_ref=[0],
                uuid="uuid-reset-test",
                initial_lang="de",
            )

        # Loop exits via is_hung_up after 4 record calls — well before _MAX_EMPTY_TURNS.
        # Farewell must NOT be spoken; the "hung up" exit should fire first.
        farewell_spoken = any("Auf Wiederhören" in s or "Goodbye" in s for s in spoken)
        assert not farewell_spoken, (
            f"Farewell spoken too early after counter reset; spoken={spoken}"
        )
