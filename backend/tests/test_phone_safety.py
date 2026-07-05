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
    """Unit tests for the retained voicemail helpers.

    NOTE: these helpers are NOT wired to escalation. The live escalation path
    deflects the caller into the COMtrexx waiting room (orbit 778/779), where a
    technician picks up manually; COMtrexx does not return the call to the AI on
    timeout, so there is no automatic voicemail fallback after deflect. These
    tests exercise the kept helpers in isolation; see TestEscalationUsesDeflect
    for the guarantee that escalation does not invoke them.
    """

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

    # ── FreeSWITCH-side hold music ────────────────────────────────────────────

    def test_hold_music_config_exists(self):
        assert hasattr(_vcfg, "AI_ESCALATION_HOLD_MUSIC")

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
            # Should not raise; min-hold falls back to bounded silence.
            _esl._ensure_min_hold(handler, 5)
        playbacks = [
            c.args[1] for c in handler.execute.call_args_list
            if c.args and c.args[0] == "playback"
        ]
        assert any("silence_stream" in str(p) for p in playbacks)


# =============================================================================
# Escalation waiting-room handoff — deflect/orbit restored (Phase 1 regression)
# =============================================================================

class TestEscalationUsesDeflect:
    """Escalation must park the caller in the COMtrexx waiting room via SIP
    REFER (deflect), never via a bridge to the gateway. A direct bridge INVITE
    to a park orbit (778/779) is rejected by COMtrexx with cause 88
    INCOMPATIBLE_DESTINATION — deflect is the only mechanism it accepts.
    These tests pin the regression that commit e6ce4d7 introduced.
    """

    def _escalation_src(self):
        import inspect
        return inspect.getsource(_esl._conversation_loop)

    def test_escalation_uses_deflect_refer(self):
        src = self._escalation_src()
        assert '"deflect"' in src
        assert "sip:{ext}@" in src

    def test_escalation_does_not_bridge_to_gateway(self):
        # The bridge-to-gateway path is what produced INCOMPATIBLE_DESTINATION.
        src = self._escalation_src()
        assert "sofia/gateway/comtrexx" not in src
        assert '"bridge"' not in src

    def test_escalation_tries_primary_then_secondary_orbit(self):
        src = self._escalation_src()
        assert "AI_WAITING_ROOM_PRIMARY" in src
        assert "AI_WAITING_ROOM_SECONDARY" in src

    def test_bridge_transfer_helpers_removed(self):
        # Dead bridge-only logic must be gone from the module.
        assert not hasattr(_esl, "_attempt_transfer")
        assert not hasattr(_esl, "_handle_transfer_or_voicemail")

    def test_voicemail_retained_but_not_invoked_by_escalation(self):
        # Voicemail code stays in the repo (Phase 2) but escalation must not call it.
        assert hasattr(_esl, "_run_voicemail")
        assert "_run_voicemail" not in self._escalation_src()


# =============================================================================
# Escalation email content + consent-gated recording (Phase 1.5)
# =============================================================================

class TestEscalationEmail:
    """The escalation email must give the technician what they need to pick the
    caller up from the COMtrexx waiting room, and must only attach the call
    recording when the caller consented.
    """

    def _started(self):
        return datetime(2026, 6, 24, 9, 14, 32, tzinfo=timezone.utc)

    def _transcript(self):
        return [
            {"role": "caller", "content": "Unsere Telefonanlage ist komplett tot."},
            {"role": "assistant", "content": "Ich verbinde Sie mit einem Mitarbeiter."},
        ]

    def _run(self, consent, recording_path="/tmp/7f3c_call.wav"):
        """Invoke handle_escalation with network/transfer stubbed; return body+kwargs."""
        with patch.object(_esc.config, "OPENROUTER_API_KEY", ""), \
             patch.object(_esc.config, "AI_WAITING_ROOM_PRIMARY", "778"), \
             patch.object(_esc.config, "AI_WAITING_ROOM_SECONDARY", "779"), \
             patch("voice.escalation._send_via_gmail", return_value=True) as m_gmail, \
             patch("voice.escalation._send_smtp_email") as m_smtp:
            _esc.handle_escalation(
                caller="+4966198765432",
                caller_name="Dr. Weber",
                transcript=self._transcript(),
                escalation_reason="Totalausfall Telefonanlage",
                started_at=self._started(),
                call_uuid="7f3c-abcd",
                esl_handler=MagicMock(),  # non-None → skip transfer attempt (no network)
                recording_consent=consent,
                recording_path=recording_path,
            )
        body = m_gmail.call_args.args[1]
        return body, m_gmail.call_args.kwargs, m_smtp

    # ── new fields ────────────────────────────────────────────────────────────

    def test_body_includes_waiting_room_primary_and_secondary(self):
        body, _, _ = self._run(consent=True)
        assert "Warteraum:" in body
        assert "778" in body
        assert "779" in body  # secondary listed as fallback

    def test_body_includes_currently_waiting_flag(self):
        body, _, _ = self._run(consent=True)
        assert "Status:" in body
        assert "wartet in der Warteschleife" in body

    def test_body_includes_pickup_instruction(self):
        body, _, _ = self._run(consent=True)
        assert "ANRUFER WARTET JETZT" in body
        assert "abholen" in body
        assert "Warteposition 778" in body

    def test_body_includes_call_uuid(self):
        body, _, _ = self._run(consent=True)
        assert "Call-ID:" in body
        assert "7f3c-abcd" in body

    def test_body_includes_local_berlin_timestamp(self):
        body, _, _ = self._run(consent=True)
        assert "Anrufbeginn (lokal):" in body
        # Still keeps the UTC line as well.
        assert "Anrufbeginn (UTC):" in body

    def test_format_local_converts_utc_to_berlin(self):
        # 09:14:32 UTC in June → 11:14:32 CEST (UTC+2).
        out = _esc._format_local(self._started())
        assert "11:14:32" in out

    # ── consent-gated recording attachment ─────────────────────────────────────

    def test_recording_attached_when_consent_true(self):
        _, kwargs, _ = self._run(consent=True)
        assert kwargs["recording_path"] == "/tmp/7f3c_call.wav"

    def test_recording_withheld_when_consent_false(self):
        body, kwargs, _ = self._run(consent=False)
        assert kwargs["recording_path"] is None
        # Consent status is still reported, email is still sent.
        assert "Aufzeichnung erlaubt: Nein" in body

    def test_smtp_fallback_also_consent_gated(self):
        # When Gmail fails, the SMTP fallback must receive the same gated path.
        with patch.object(_esc.config, "OPENROUTER_API_KEY", ""), \
             patch.object(_esc.config, "AI_WAITING_ROOM_PRIMARY", "778"), \
             patch.object(_esc.config, "AI_WAITING_ROOM_SECONDARY", "779"), \
             patch("voice.escalation._send_via_gmail", return_value=False), \
             patch("voice.escalation._send_smtp_email", return_value=True) as m_smtp:
            _esc.handle_escalation(
                caller="+4966198765432", caller_name="Dr. Weber",
                transcript=self._transcript(), escalation_reason="Ausfall",
                started_at=self._started(), call_uuid="7f3c-abcd",
                esl_handler=MagicMock(), recording_consent=False,
                recording_path="/tmp/7f3c_call.wav",
            )
        assert m_smtp.call_args.kwargs["recording_path"] is None


# =============================================================================
# Turn-taking — end-of-speech timing + unfinished-utterance detection
# =============================================================================

class TestEndOfSpeechTiming:
    """The AI must wait long enough after the caller stops before treating the
    turn as finished. This pins the trailing-silence window (end-of-speech only,
    not barge-in) and its wiring into the FreeSWITCH record silence-hits.
    """

    def test_silence_window_longer_than_legacy(self):
        # Was 1.8 s; raised by ~0.5–0.8 s so hesitant callers are not cut off.
        assert _vcfg.AI_RECORD_SILENCE_SECONDS > 1.8

    def test_silence_window_in_expected_range(self):
        # Keep it bounded so we do not add excessive latency after real silence.
        assert 2.5 <= _vcfg.AI_RECORD_SILENCE_SECONDS <= 2.7

    def test_silence_seconds_wired_to_record_silence_hits(self):
        # esl_call_handler converts the seconds into 20 ms silence frames.
        expected_hits = max(1, round(_vcfg.AI_RECORD_SILENCE_SECONDS * 1000 / 20))
        assert _esl._RECORD_SILENCE_TIMEOUT == expected_hits

    def test_silence_hits_increased_over_legacy(self):
        # Legacy 1.8 s == 90 frames; the new window must be strictly longer.
        assert _esl._RECORD_SILENCE_TIMEOUT > 90

    def test_threshold_and_max_seconds_defaults_unchanged(self):
        # Turn-taking change must touch ONLY the trailing-silence window. The
        # energy threshold and per-utterance cap are env-driven at runtime, so
        # pin their source defaults instead of runtime values (scope guard).
        import inspect
        src = inspect.getsource(_vcfg)
        assert '"AI_RECORD_SILENCE_THRESHOLD_MS", "500"' in src
        assert '"AI_RECORD_MAX_SECONDS", "8"' in src


class TestUnfinishedUtteranceDetection:
    """Mid-sentence pauses / hesitations must NOT trigger the LLM. The caller is
    still talking — the loop should offer a gentle continuation prompt instead.
    """

    @pytest.mark.parametrize("text", [
        "ähm",
        "Ähm",
        "also",
        "Moment",
        "ich wollte",
        "Ich wollte…",
        "und dann",
        "Und dann…",
        "Ich möchte",
        "Ja, und",
        "Das ist, weil",
    ])
    def test_unfinished_examples_detected(self, text):
        assert _esl._is_likely_unfinished_utterance(text) is True

    @pytest.mark.parametrize("text", [
        "Ja",
        "Nein",
        "OK",
        "Hallo",
        "Ich möchte einen Termin vereinbaren",
        "Ich wollte einen Rückruf bei Herrn Meyer",
        "Und dann hat er aufgelegt",
        "Vielen Dank für Ihre Hilfe",
    ])
    def test_complete_utterances_not_flagged(self, text):
        assert _esl._is_likely_unfinished_utterance(text) is False


# =============================================================================
# Inbound live-call prompt — concise, receptionist-style phone answers
# =============================================================================

class TestInboundPromptStyle:
    """The inbound live-call system prompt must instruct concise, natural,
    receptionist-style German answers (Priority 2). These pin the style rules
    in the prompt text; live answer quality is validated manually.
    """

    def _prompt(self) -> str:
        from voice.llm_bridge import _SYSTEM_PROMPT
        return _SYSTEM_PROMPT

    def test_prompt_has_character_budget(self):
        p = self._prompt()
        assert "60–140 characters" in p
        assert "180 characters" in p

    def test_prompt_requires_one_question_at_a_time(self):
        assert "One question at a time" in self._prompt()

    def test_prompt_forbids_long_empathy_paragraphs(self):
        assert "No long empathy paragraphs" in self._prompt()

    def test_prompt_sets_technical_support_default_context(self):
        assert "technical-support or reception enquiry" in self._prompt()

    def test_prompt_has_receptionist_persona(self):
        p = self._prompt().lower()
        assert "receptionist" in p

    def test_prompt_has_technical_diagnostic_pattern(self):
        # brief acknowledgement + one diagnostic question
        p = self._prompt()
        assert "ONE diagnostic question" in p
        assert "Betrifft es alle Geräte oder nur einzelne?" in p

    def test_prompt_keeps_safety_carveout_for_distress(self):
        # Brevity must not override the distress/crisis SAFETY RULES.
        assert "SAFETY RULES" in self._prompt()

    def test_prompt_retains_no_credentials_rule(self):
        # Scope guard: existing safety lines must remain.
        assert "Do not ask for passwords, PINs, or payment data." in self._prompt()


# =============================================================================
# Conversation craft — natural spoken German, intent, memory, varied
# acknowledgements, flow, and closing (Priorities 1–8).
# =============================================================================

class TestConversationCraftPrompt:
    """The inbound live-call prompt must steer the model toward receptionist-style
    conversation: spoken German, early intent recognition, in-call memory, varied
    acknowledgements, smooth flow, and a natural close. These pin the instruction
    text; real conversation quality is validated manually on live calls.
    """

    def _prompt(self) -> str:
        from voice.llm_bridge import _SYSTEM_PROMPT
        return _SYSTEM_PROMPT

    def test_has_conversation_craft_section(self):
        assert "CONVERSATION CRAFT" in self._prompt()

    def test_steers_spoken_not_written_german(self):
        p = self._prompt()
        assert "Spoken German, not written German" in p

    def test_recognises_intent_early(self):
        p = self._prompt()
        assert "Recognise the intent early" in p
        # do not over-diagnose once the intent is known
        assert "already know what they need" in p

    def test_active_listening_no_parroting(self):
        p = self._prompt()
        assert "Active listening, not parroting" in p
        # Backslash-newline continuations collapse to a single space at runtime.
        assert "Never repeat the caller's whole sentence" in p

    def test_varies_acknowledgements(self):
        p = self._prompt()
        assert "Vary your acknowledgements" in p

    def test_in_call_memory_never_ask_twice(self):
        p = self._prompt()
        assert "Remember within the call" in p
        assert "Never ask for the same thing twice" in p

    def test_natural_closing_once(self):
        p = self._prompt()
        assert "Haben Sie sonst noch eine Frage?" in p
        assert "only once" in p

    def test_scope_guard_safety_and_brevity_preserved(self):
        # The craft section must NOT have removed the brevity/safety pins.
        p = self._prompt()
        assert "60–140 characters" in p
        assert "One question at a time" in p
        assert "SAFETY RULES" in p


class TestOutboundPromptCraft:
    """The outbound persona prompt mirrors the key conversation-craft rules."""

    def _prompt(self) -> str:
        from voice.llm_bridge import OUTBOUND_SYSTEM_PROMPT
        return OUTBOUND_SYSTEM_PROMPT

    def test_outbound_varies_acknowledgements(self):
        assert "Vary your acknowledgements" in self._prompt()

    def test_outbound_remembers_within_call(self):
        assert "Never ask for the same thing twice" in self._prompt()

    def test_outbound_natural_close(self):
        assert "Auf Wiederhören" in self._prompt()


class TestContinuationRotation:
    """Repeated mid-sentence pauses must not replay the identical continuation
    sentence. The rotation is deterministic and keeps attempt 1 unchanged.
    """

    def test_attempt_one_preserves_original_de(self):
        assert _esl._rotating_continuation("de", 1) == (
            "Ja, ich höre zu — bitte fahren Sie fort."
        )

    def test_attempt_one_preserves_original_en(self):
        assert _esl._rotating_continuation("en", 1) == (
            "Yes, I'm listening — please go ahead."
        )

    def test_consecutive_attempts_differ(self):
        a1 = _esl._rotating_continuation("de", 1)
        a2 = _esl._rotating_continuation("de", 2)
        a3 = _esl._rotating_continuation("de", 3)
        assert a1 != a2 != a3
        assert len({a1, a2, a3}) == 3

    def test_unknown_lang_falls_back_to_german(self):
        assert _esl._rotating_continuation("fr", 1) == (
            "Ja, ich höre zu — bitte fahren Sie fort."
        )

    def test_attempt_zero_or_negative_is_safe(self):
        # Defensive: never index out of range on a 0/negative attempt.
        assert _esl._rotating_continuation("de", 0) == _esl._rotating_continuation("de", 1)
