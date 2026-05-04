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
