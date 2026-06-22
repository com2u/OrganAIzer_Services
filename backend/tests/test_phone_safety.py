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
        # No purpose → canonical Teleprofi outbound default greeting (no OrganAIzer)
        assert "Teleprofi Fulda" in line
        assert "OrganAIzer" not in line

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
        # A fallback intro for when history is empty must still exist (Teleprofi identity)
        assert "Teleprofi Fulda" in OUTBOUND_SYSTEM_PROMPT
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


# =============================================================================
# Missed-call voicemail fallback
# =============================================================================

from datetime import datetime, timezone
from voice import config as _vcfg
import voice.esl_call_handler as _esl
import voice.escalation as _esc


class TestVoicemailFallback:
    """Voicemail triggers only on no-answer; answered calls never enter it."""

    def _started(self):
        return datetime.now(timezone.utc)

    def _vm_handler(self, tmp, uuid):
        """Mock ESL handler that 'creates' the voicemail WAV when record runs."""
        handler = MagicMock()
        handler.is_hung_up = False

        def _exec(app, arg=None, **kw):
            if app == "record":
                (tmp / f"{uuid}_voicemail.wav").write_bytes(b"\x00" * 200)
            return True

        handler.execute.side_effect = _exec
        return handler

    # ── trigger logic ─────────────────────────────────────────────────────────

    def test_timeout_triggers_voicemail_flow(self):
        handler = MagicMock()
        handler.is_hung_up = False
        sentinel = {"voicemail_received": True}
        with patch("voice.esl_call_handler._attempt_transfer", return_value=False), \
             patch("voice.esl_call_handler._run_voicemail", return_value=sentinel) as m_vm:
            result = _esl._handle_transfer_or_voicemail(
                handler, "+496611234", None, "u1", self._started(), "de"
            )
        m_vm.assert_called_once()
        assert result is sentinel

    def test_answered_call_never_enters_voicemail(self):
        handler = MagicMock()
        handler.is_hung_up = False
        with patch("voice.esl_call_handler._attempt_transfer", return_value=True), \
             patch("voice.esl_call_handler._run_voicemail") as m_vm:
            result = _esl._handle_transfer_or_voicemail(
                handler, "+496611234", None, "u1", self._started(), "de"
            )
        m_vm.assert_not_called()
        assert result is None

    def test_no_voicemail_if_caller_already_hung_up(self):
        handler = MagicMock()
        handler.is_hung_up = True
        with patch("voice.escalation.send_voicemail_notification") as m_send, \
             patch("voice.esl_call_handler._speak_and_play"):
            info = _esl._run_voicemail(handler, "+49", None, "u", self._started(), "de")
        assert info["voicemail_received"] is False
        m_send.assert_not_called()

    # ── recording → email → summary ───────────────────────────────────────────

    def test_voicemail_summary_fields_populated(self, tmp_path):
        handler = self._vm_handler(tmp_path, "uuidA")
        with patch("voice.esl_call_handler._audio_dir", return_value=tmp_path), \
             patch("voice.esl_call_handler._speak_and_play"), \
             patch("voice.esl_call_handler.transcribe_file", return_value=("hallo test", "de")), \
             patch("voice.esl_call_handler._wav_duration_seconds", return_value=6), \
             patch("voice.escalation.send_voicemail_notification"):
            info = _esl._run_voicemail(
                handler, "+4966112345", "Hans", "uuidA", self._started(), "de"
            )
        assert info["caller_number"] == "+4966112345"
        assert info["voicemail_received"] is True
        assert info["voicemail_duration"] == 6
        assert info["voicemail_file"].endswith("uuidA_voicemail.wav")

    def test_voicemail_email_generated(self, tmp_path):
        handler = self._vm_handler(tmp_path, "uuidB")
        with patch("voice.esl_call_handler._audio_dir", return_value=tmp_path), \
             patch("voice.esl_call_handler._speak_and_play"), \
             patch("voice.esl_call_handler.transcribe_file", return_value=("hi", "de")), \
             patch("voice.esl_call_handler._wav_duration_seconds", return_value=9), \
             patch("voice.escalation.send_voicemail_notification") as m_send:
            _esl._run_voicemail(handler, "+4966199", None, "uuidB", self._started(), "de")
        m_send.assert_called_once()
        kw = m_send.call_args.kwargs
        assert kw["caller"] == "+4966199"
        assert kw["call_uuid"] == "uuidB"
        assert kw["duration_seconds"] == 9
        assert kw["recording_path"].endswith("uuidB_voicemail.wav")

    def test_voicemail_attachment_included(self):
        with patch("voice.escalation._send_via_gmail", return_value=False) as m_gmail, \
             patch("voice.escalation._send_smtp_email", return_value=True) as m_smtp:
            sent = _esc.send_voicemail_notification(
                caller="+4966199",
                caller_name=None,
                call_uuid="cid",
                started_at=self._started(),
                duration_seconds=12,
                recording_path="/tmp/cid_voicemail.wav",
                transcript="hallo",
            )
        assert sent is True
        # Subject is the required German missed-call line; recording is attached.
        assert "Verpasster Anruf" in m_gmail.call_args.args[0]
        assert m_gmail.call_args.kwargs["recording_path"] == "/tmp/cid_voicemail.wav"
        assert m_smtp.call_args.kwargs["recording_path"] == "/tmp/cid_voicemail.wav"

    # ── configurability ───────────────────────────────────────────────────────

    def test_transfer_timeout_defaults_to_35(self):
        assert _vcfg.AI_ESCALATION_TRANSFER_TIMEOUT_SECONDS == 35
        assert isinstance(_vcfg.AI_ESCALATION_TRANSFER_TIMEOUT_SECONDS, int)
        assert isinstance(_vcfg.AI_VOICEMAIL_MAX_SECONDS, int)

    def test_handle_passes_configured_timeout(self):
        handler = MagicMock()
        handler.is_hung_up = False
        with patch("voice.esl_call_handler._attempt_transfer", return_value=True) as m_t:
            _esl._handle_transfer_or_voicemail(
                handler, "+496611234", None, "u1", self._started(), "de"
            )
        m_t.assert_called_once()
        assert m_t.call_args.args[1] == _vcfg.AI_ESCALATION_TRANSFER_TIMEOUT_SECONDS

    # ── call stays alive through the ring window ──────────────────────────────

    def test_transfer_keeps_caller_alive_on_no_answer(self):
        # A failed/unanswered bridge must NOT hang up the caller — continue_on_fail
        # is set and the function returns False (→ voicemail), caller still on line.
        handler = MagicMock()
        handler.is_hung_up = False
        result = _esl._attempt_transfer(handler, 35)
        set_vars = [
            c.args[1] for c in handler.execute.call_args_list if c.args and c.args[0] == "set"
        ]
        assert any("continue_on_fail=true" == v for v in set_vars)
        assert any(v.startswith("call_timeout=35") for v in set_vars)
        handler.hangup.assert_not_called()
        # With at least one waiting-room target unset by default, returns False.
        assert result in (False, True)  # structural: never raises, returns a bool

    def test_run_voicemail_does_not_hang_up_call(self, tmp_path):
        handler = self._vm_handler(tmp_path, "uuidH")
        with patch("voice.esl_call_handler._audio_dir", return_value=tmp_path), \
             patch("voice.esl_call_handler._speak_and_play"), \
             patch("voice.esl_call_handler.transcribe_file", return_value=("x", "de")), \
             patch("voice.esl_call_handler._wav_duration_seconds", return_value=5), \
             patch("voice.escalation.send_voicemail_notification"):
            _esl._run_voicemail(handler, "+49661", None, "uuidH", self._started(), "de")
        handler.hangup.assert_not_called()

    # ── prompt + recording + email content ────────────────────────────────────

    def test_voicemail_prompt_text_is_used(self, tmp_path):
        handler = self._vm_handler(tmp_path, "uuidP")
        spoken = []
        with patch("voice.esl_call_handler._audio_dir", return_value=tmp_path), \
             patch("voice.esl_call_handler._speak_and_play",
                   side_effect=lambda h, t, lang=None: spoken.append(t)), \
             patch("voice.esl_call_handler.transcribe_file", return_value=("x", "de")), \
             patch("voice.esl_call_handler._wav_duration_seconds", return_value=5), \
             patch("voice.escalation.send_voicemail_notification"):
            _esl._run_voicemail(handler, "+49661", None, "uuidP", self._started(), "de")
        assert any(
            "hinterlassen Sie nach dem Signalton" in s
            and "schnellstmöglich bei Ihnen zurück" in s
            for s in spoken
        ), f"voicemail prompt not spoken; got {spoken}"

    def test_voicemail_recording_is_attempted(self, tmp_path):
        handler = self._vm_handler(tmp_path, "uuidR")
        with patch("voice.esl_call_handler._audio_dir", return_value=tmp_path), \
             patch("voice.esl_call_handler._speak_and_play"), \
             patch("voice.esl_call_handler.transcribe_file", return_value=("x", "de")), \
             patch("voice.esl_call_handler._wav_duration_seconds", return_value=5), \
             patch("voice.escalation.send_voicemail_notification"):
            _esl._run_voicemail(handler, "+49661", None, "uuidR", self._started(), "de")
        apps = [c.args[0] for c in handler.execute.call_args_list if c.args]
        assert "record" in apps

    def test_voicemail_email_contains_reason_and_received_flag(self):
        with patch("voice.escalation._send_via_gmail", return_value=True) as m_gmail, \
             patch("voice.escalation._send_smtp_email") as m_smtp:
            _esc.send_voicemail_notification(
                caller="+4966199",
                caller_name=None,
                call_uuid="cid",
                started_at=self._started(),
                duration_seconds=14,
                recording_path="/tmp/cid_voicemail.wav",
                transcript=None,
                escalation_reason="Totalausfall Telefonanlage",
            )
        body = m_gmail.call_args.args[1]
        assert "Totalausfall Telefonanlage" in body
        assert "voicemail_received=true" in body
        assert "/tmp/cid_voicemail.wav" in body
        m_smtp.assert_not_called()  # gmail succeeded → no SMTP fallback

    def test_run_voicemail_forwards_escalation_reason_to_email(self, tmp_path):
        handler = self._vm_handler(tmp_path, "uuidE")
        with patch("voice.esl_call_handler._audio_dir", return_value=tmp_path), \
             patch("voice.esl_call_handler._speak_and_play"), \
             patch("voice.esl_call_handler.transcribe_file", return_value=("x", "de")), \
             patch("voice.esl_call_handler._wav_duration_seconds", return_value=8), \
             patch("voice.escalation.send_voicemail_notification") as m_send:
            _esl._run_voicemail(
                handler, "+49661", None, "uuidE", self._started(), "de",
                escalation_reason="Praxis nicht erreichbar",
            )
        assert m_send.call_args.kwargs["escalation_reason"] == "Praxis nicht erreichbar"

    # ── minimum hold before voicemail ─────────────────────────────────────────

    def test_default_min_hold_is_10_seconds(self):
        assert _vcfg.AI_ESCALATION_MIN_HOLD_SECONDS == 10

    def test_voicemail_waits_for_min_hold_before_starting(self):
        handler = MagicMock()
        handler.is_hung_up = False
        calls = []
        with patch("voice.esl_call_handler._attempt_transfer", return_value=False), \
             patch("voice.esl_call_handler._ensure_min_hold",
                   side_effect=lambda h, r: calls.append("hold")), \
             patch("voice.esl_call_handler._run_voicemail",
                   side_effect=lambda *a, **k: calls.append("vm") or {"voicemail_received": True}):
            _esl._handle_transfer_or_voicemail(
                handler, "+496611234", None, "u1", self._started(), "de"
            )
        # Min-hold must run before voicemail.
        assert calls == ["hold", "vm"]

    def test_early_failed_bridge_waits_until_min_hold(self):
        handler = MagicMock()
        handler.is_hung_up = False
        captured = {}
        # _attempt_transfer (mocked) returns instantly → elapsed ~0 → remaining ~10.
        with patch("voice.esl_call_handler._attempt_transfer", return_value=False), \
             patch("voice.esl_call_handler._ensure_min_hold",
                   side_effect=lambda h, r: captured.__setitem__("remaining", r)), \
             patch("voice.esl_call_handler._run_voicemail", return_value={}):
            _esl._handle_transfer_or_voicemail(
                handler, "+496611234", None, "u1", self._started(), "de"
            )
        assert captured["remaining"] >= _vcfg.AI_ESCALATION_MIN_HOLD_SECONDS - 1

    def test_answered_transfer_skips_min_hold_and_voicemail(self):
        handler = MagicMock()
        handler.is_hung_up = False
        with patch("voice.esl_call_handler._attempt_transfer", return_value=True), \
             patch("voice.esl_call_handler._ensure_min_hold") as m_hold, \
             patch("voice.esl_call_handler._run_voicemail") as m_vm:
            result = _esl._handle_transfer_or_voicemail(
                handler, "+496611234", None, "u1", self._started(), "de"
            )
        assert result is None
        m_hold.assert_not_called()
        m_vm.assert_not_called()

    def test_min_hold_plays_waiting_audio(self):
        handler = MagicMock()
        handler.is_hung_up = False
        _esl._ensure_min_hold(handler, 8)
        playbacks = [
            c.args[1] for c in handler.execute.call_args_list
            if c.args and c.args[0] == "playback"
        ]
        # Bounded waiting audio is played, and it is NOT an artificial ring tone.
        assert playbacks, "expected bounded waiting audio playback"
        assert any("silence_stream" in str(p) for p in playbacks)

    def test_min_hold_does_not_use_artificial_ringback_tone(self):
        handler = MagicMock()
        handler.is_hung_up = False
        _esl._ensure_min_hold(handler, 8)
        playbacks = " ".join(
            str(c.args[1]) for c in handler.execute.call_args_list
            if c.args and c.args[0] == "playback"
        )
        assert "tone_stream" not in playbacks
        assert "440,480" not in playbacks  # the old ring cadence is gone

    def test_min_hold_noop_when_already_satisfied(self):
        handler = MagicMock()
        handler.is_hung_up = False
        _esl._ensure_min_hold(handler, 0)
        handler.execute.assert_not_called()

    def test_min_hold_noop_when_caller_hung_up(self):
        handler = MagicMock()
        handler.is_hung_up = True
        _esl._ensure_min_hold(handler, 8)
        handler.execute.assert_not_called()

    # ── COMtrexx early-media bridge (no artificial ringback) ──────────────────

    def _transfer_set_vars(self, handler):
        return [
            c.args[1] for c in handler.execute.call_args_list
            if c.args and c.args[0] == "set"
        ]

    def test_attempt_transfer_no_artificial_ringback_by_default(self):
        handler = MagicMock()
        handler.is_hung_up = False
        _esl._attempt_transfer(handler, 35)
        set_vars = " ".join(self._transfer_set_vars(handler))
        assert "instant_ringback" not in set_vars
        assert "ringback=%(" not in set_vars

    def test_attempt_transfer_enables_early_media(self):
        handler = MagicMock()
        handler.is_hung_up = False
        _esl._attempt_transfer(handler, 35)
        set_vars = self._transfer_set_vars(handler)
        assert any(v == "bridge_early_media=true" for v in set_vars)

    def test_attempt_transfer_sets_continue_on_fail(self):
        handler = MagicMock()
        handler.is_hung_up = False
        _esl._attempt_transfer(handler, 35)
        assert any(v == "continue_on_fail=true" for v in self._transfer_set_vars(handler))

    def test_attempt_transfer_call_timeout_is_35(self):
        handler = MagicMock()
        handler.is_hung_up = False
        _esl._attempt_transfer(handler, 35)
        set_vars = self._transfer_set_vars(handler)
        assert any(v == "call_timeout=35" for v in set_vars)
        assert any(v == "originate_timeout=35" for v in set_vars)

    def test_attempt_transfer_ringback_fallback_when_early_media_disabled(self):
        handler = MagicMock()
        handler.is_hung_up = False
        with patch.object(_vcfg, "AI_ESCALATION_USE_COMTREXX_EARLY_MEDIA", False), \
             patch.object(_vcfg, "AI_ESCALATION_HOLD_MUSIC", ""):
            _esl._attempt_transfer(handler, 35)
        set_vars = " ".join(self._transfer_set_vars(handler))
        # With early media disabled and no hold music, a synthetic ringback is ok.
        assert "instant_ringback=true" in set_vars
        assert "bridge_early_media=true" not in set_vars

    # ── FreeSWITCH-side hold music ────────────────────────────────────────────

    def test_hold_music_config_exists(self):
        assert hasattr(_vcfg, "AI_ESCALATION_HOLD_MUSIC")

    def test_attempt_transfer_uses_hold_music_when_configured(self):
        handler = MagicMock()
        handler.is_hung_up = False
        with patch.object(_vcfg, "AI_ESCALATION_HOLD_MUSIC", "/snd/teleprofi_hold.wav"):
            _esl._attempt_transfer(handler, 35)
        set_vars = self._transfer_set_vars(handler)
        assert "ringback=/snd/teleprofi_hold.wav" in set_vars
        assert "instant_ringback=true" in set_vars
        # The company WAV is used — never an artificial ring tone.
        assert all("ringback=%(" not in v for v in set_vars)

    def test_hold_music_takes_precedence_over_early_media(self):
        handler = MagicMock()
        handler.is_hung_up = False
        with patch.object(_vcfg, "AI_ESCALATION_HOLD_MUSIC", "/snd/teleprofi_hold.wav"), \
             patch.object(_vcfg, "AI_ESCALATION_USE_COMTREXX_EARLY_MEDIA", True):
            _esl._attempt_transfer(handler, 35)
        set_vars = self._transfer_set_vars(handler)
        assert "ringback=/snd/teleprofi_hold.wav" in set_vars
        assert "bridge_early_media=true" not in set_vars

    def test_min_hold_uses_hold_music_when_configured(self):
        handler = MagicMock()
        handler.is_hung_up = False
        with patch.object(_vcfg, "AI_ESCALATION_HOLD_MUSIC", "/snd/teleprofi_hold.wav"):
            _esl._ensure_min_hold(handler, 8)
        playbacks = [
            c.args[1] for c in handler.execute.call_args_list
            if c.args and c.args[0] == "playback"
        ]
        assert playbacks == ["/snd/teleprofi_hold.wav"]
        assert all("tone_stream" not in str(p) for p in playbacks)

    def test_missing_hold_music_does_not_crash(self):
        handler = MagicMock()
        handler.is_hung_up = False
        with patch.object(_vcfg, "AI_ESCALATION_HOLD_MUSIC", ""):
            # Neither call should raise; min-hold falls back to silence.
            _esl._attempt_transfer(handler, 35)
            _esl._ensure_min_hold(handler, 5)
        playbacks = [
            c.args[1] for c in handler.execute.call_args_list
            if c.args and c.args[0] == "playback"
        ]
        assert any("silence_stream" in str(p) for p in playbacks)
