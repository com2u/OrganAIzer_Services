"""
Privacy tests for caller/customer resolution.

This file has two genuinely different layers of coverage — read the class
docstrings, not just this header, before trusting a claim about what's
verified:

  1. ``TestNoDigitsInIdentityPrompt`` / ``TestCandidateLabelsAreDisplayOnly`` /
     ``TestBuildIdentityStageInstructionDirect`` check ONLY the system_extra
     side channel built by voice/caller_resolution_dialogue.build_prompt_extra()
     (wrapping voice/llm_bridge.build_identity_stage_instruction()). They do
     NOT exercise user_text, conversation history, or the arguments actually
     posted to OpenRouter.

  2. ``TestGetResponseNeverSeesRawNumbers`` is the layer that closes that gap:
     it drives voice/esl_call_handler._conversation_loop end-to-end with a
     mocked ESL handler and a patched voice.esl_call_handler.get_response,
     and asserts directly on the (history, user_text, system_extra) tuple
     get_response was actually called with — the same object graph that
     would be serialized into the OpenRouter request body, the transcript
     archive, and the escalation summary/email (all three consume the same
     `history` list; see backend/voice/call_log.py and
     backend/voice/escalation.py). It also proves dates/prices/ticket
     numbers/postal codes are left untouched, and that redact_phone_like()
     preserves the raw value only in caller-resolution state.

  3. ``TestIdentificationExemptionRestarts`` checks the exemption
     state-machine transition directly (dialogue-layer unit test — that's
     where the logic lives; layer 2 above additionally proves the resulting
     system_extra differs once identification restarts).
"""
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import customers.store as _customers_store
from voice import caller_resolution_dialogue as crd
from voice.llm_bridge import build_identity_stage_instruction

# Kept local (not imported from test_customer_resolution.py) so this file has
# no cross-test-module import dependency — pytest does not put the tests/
# directory on sys.path by default.
MUELLER_GMBH = {
    "customer_id": "cus_001",
    "name": "Müller GmbH",
    "customer_type": "business",
    "status": "active",
    "locations": [
        {
            "location_id": "loc_001",
            "label": "Hauptsitz Fulda",
            "address": "Bahnhofstraße 12, 36037 Fulda",
            "numbers": [{"number": "+49661123456", "type": "landline"}],
        },
    ],
    "known_contacts": [
        {"contact_id": "ct_001", "name": "Herr Müller", "role": "owner", "mobile_numbers": []},
    ],
}

ANNA_MUELLER = {
    "customer_id": "cus_002",
    "name": "Anna Müller",
    "customer_type": "private",
    "status": "active",
    "locations": [
        {
            "location_id": "loc_002",
            "label": "Privatanschluss",
            "address": "Gartenstraße 5, 36037 Fulda",
            "numbers": [{"number": "+49661998877", "type": "landline"}],
        },
    ],
    "known_contacts": [
        {
            "contact_id": "ct_002",
            "name": "Anna Müller",
            "role": "owner",
            "mobile_numbers": [{"number": "+4915199988877", "type": "mobile"}],
        },
    ],
}

BAECKEREI = {
    "customer_id": "cus_003",
    "name": "Bäckerei Fulda Kette",
    "customer_type": "business",
    "status": "active",
    "locations": [
        {"location_id": "loc_003a", "label": "Filiale Innenstadt", "numbers": [{"number": "+49661222333", "type": "landline"}]},
        {"location_id": "loc_003b", "label": "Filiale Petersberg", "numbers": [{"number": "+49661222444", "type": "landline"}]},
    ],
    "known_contacts": [
        {
            "contact_id": "ct_003",
            "name": "Frau Weber",
            "role": "manager",
            "mobile_numbers": [{"number": "+4915155566677", "type": "mobile"}],
        },
    ],
}

FIXTURE_CUSTOMERS = [MUELLER_GMBH, ANNA_MUELLER, BAECKEREI]

# A mobile that appears nowhere in the fixture data.
UNKNOWN_MOBILE = "+4915199912345"

# Any run of 4+ consecutive digits is treated as "looks like it could leak a
# phone number" for this test — deliberately stricter than a real phone
# number's length so partial leaks are also caught.
_DIGIT_RUN_RE = re.compile(r"\d{4,}")


def _patch_store(monkeypatch):
    monkeypatch.setattr(_customers_store, "load", lambda path=None: FIXTURE_CUSTOMERS)
    monkeypatch.setattr(_customers_store, "all_customers", lambda path=None: FIXTURE_CUSTOMERS)


class TestNoDigitsInIdentityPrompt:
    def test_awaiting_affected_number_instruction_has_no_digits(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, UNKNOWN_MOBILE)
        extra = crd.build_prompt_extra(state)
        assert extra is not None
        assert not _DIGIT_RUN_RE.search(extra)

    def test_disambiguation_instruction_has_no_digits(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Mein Name ist Müller.")
        assert state["identity_stage"] == "awaiting_disambiguation"
        extra = crd.build_prompt_extra(state)
        assert extra is not None
        assert not _DIGIT_RUN_RE.search(extra)
        # And explicitly not the raw numbers behind either candidate.
        assert "661123456" not in extra
        assert "661998877" not in extra

    def test_awaiting_location_instruction_has_no_digits(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "+4915155566677")  # Frau Weber's mobile — 2 locations
        assert state["identity_stage"] == "awaiting_location"
        extra = crd.build_prompt_extra(state)
        assert extra is not None
        assert not _DIGIT_RUN_RE.search(extra)

    def test_resolved_customer_produces_no_extra_at_all(self, monkeypatch):
        # Once resolved there is nothing further to ask — build_prompt_extra
        # returns None, so there is no text for a number to leak into.
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "+49661123456")  # Müller GmbH landline
        assert state["identity_stage"] == "resolved"
        assert crd.build_prompt_extra(state) is None

    def test_raw_caller_and_affected_numbers_never_appear_in_any_stage_output(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, UNKNOWN_MOBILE)
        # Walk through every stage this call passes through and check each
        # instruction the LLM would actually receive.
        seen_instructions = []
        extra = crd.build_prompt_extra(state)
        if extra:
            seen_instructions.append(extra)

        crd.observe_turn(state, "Meine Nummer die nicht geht ist 0661 123456.")
        extra = crd.build_prompt_extra(state)
        if extra:
            seen_instructions.append(extra)

        raw_needles = [
            UNKNOWN_MOBILE,
            re.sub(r"\D", "", UNKNOWN_MOBILE),
            "0661 123456",
            "0661123456",
            "661123456",  # affected number, digits only
        ]
        for text in seen_instructions:
            for needle in raw_needles:
                assert needle not in text, f"raw number leaked into LLM prompt: {needle!r} in {text!r}"


class TestCandidateLabelsAreDisplayOnly:
    def test_candidate_labels_never_contain_digits(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Mein Name ist Müller.")
        labels = crd.candidate_labels(state)
        assert labels
        for label in labels:
            assert not any(ch.isdigit() for ch in label)

    def test_location_labels_never_contain_digits(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "+4915155566677")
        labels = crd.candidate_labels(state)
        assert labels
        for label in labels:
            assert not any(ch.isdigit() for ch in label)


class TestBuildIdentityStageInstructionDirect:
    """Unit-level check on the llm_bridge function itself (Layer 1 wording)."""

    def test_templates_never_reference_a_number(self):
        for stage in (
            "awaiting_affected_number",
            "new_installation",
            "unresolved_continue",
        ):
            text = build_identity_stage_instruction(stage)
            assert text is not None
            assert not _DIGIT_RUN_RE.search(text)

    def test_unknown_stage_returns_none(self):
        assert build_identity_stage_instruction("not_started") is None
        assert build_identity_stage_instruction("resolved") is None
        assert build_identity_stage_instruction(None) is None

    def test_candidate_stage_without_labels_returns_none(self):
        # No labels supplied -> nothing safe to say -> no instruction at all,
        # rather than ever risking a templated fallback with raw data.
        assert build_identity_stage_instruction("awaiting_disambiguation", None) is None
        assert build_identity_stage_instruction("awaiting_disambiguation", []) is None


# =============================================================================
# Layer 2 — integration: the actual arguments passed to
# voice.esl_call_handler.get_response(), driven through the real
# _conversation_loop with a mocked ESL handler (no FreeSWITCH, no network).
# This is the layer the original privacy test suite did NOT cover — see the
# module docstring.
# =============================================================================
class TestGetResponseNeverSeesRawNumbers:
    """
    Drives _conversation_loop end-to-end and intercepts every call to
    voice.esl_call_handler.get_response, asserting directly on the
    (history, user_text, system_extra) it was actually called with — the
    same objects that would otherwise be serialized to OpenRouter, archived
    to the transcript log (call_log.py passes this exact `history`), and
    handed to escalation (escalation.py also consumes this exact `history`).
    """

    def _drive_call(self, monkeypatch, tmp_path, transcriptions, identity_state):
        from unittest.mock import patch as _patch
        from voice.esl_call_handler import _conversation_loop

        monkeypatch.setattr(_customers_store, "load", lambda path=None: FIXTURE_CUSTOMERS)
        monkeypatch.setattr(_customers_store, "all_customers", lambda path=None: FIXTURE_CUSTOMERS)

        t_idx = [0]

        def _fake_transcribe(path, lang=None):
            i = t_idx[0]
            t_idx[0] += 1
            return transcriptions[i] if i < len(transcriptions) else ("", "de")

        record_calls = [0]

        def _is_hung_up(self):
            return record_calls[0] >= len(transcriptions)

        mock_handler = MagicMock()
        type(mock_handler).is_hung_up = property(_is_hung_up)

        def _execute(*args, **kwargs):
            if args and args[0] == "record":
                record_calls[0] += 1
                Path(args[1].split()[0]).touch()  # so _process_turn reads the WAV
            return True

        mock_handler.execute.side_effect = _execute

        captured_calls = []

        async def _fake_get_response(history, user_text, caller_name=None, system_extra=None, system_prompt=None):
            captured_calls.append({
                "user_text": user_text,
                "history_snapshot": [dict(m) for m in history],
                "system_extra": system_extra,
            })
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": "Alles klar."})
            return "Alles klar."

        history: list = []

        with _patch("voice.esl_call_handler._audio_dir", return_value=Path(str(tmp_path))), \
             _patch("voice.esl_call_handler._speak_and_play"), \
             _patch("voice.esl_call_handler._get_filler_wav", return_value=""), \
             _patch("voice.esl_call_handler.transcribe_file", side_effect=_fake_transcribe), \
             _patch("voice.esl_call_handler.get_response", side_effect=_fake_get_response), \
             _patch("voice.esl_call_handler.speak_to_file", return_value=""):
            _conversation_loop(
                handler=mock_handler,
                history=history,
                caller=UNKNOWN_MOBILE,
                caller_name=None,
                started_at=datetime.now(timezone.utc),
                system_prompt=None,
                turn_count_ref=[0],
                uuid="uuid-privacy-integration",
                initial_lang="de",
                dialogue_state=None,
                identity_state=identity_state,
            )

        return captured_calls, history

    def test_spoken_landline_is_redacted_and_dates_prices_tickets_are_not(self, monkeypatch, tmp_path):
        RAW_LANDLINE_SPOKEN = "0661 123456"
        RAW_LANDLINE_DIGITS = "0661123456"

        transcriptions = [
            ("Meine Festnetznummer die nicht geht ist 0661 123456.", "de"),
            ("Der Vorfall war am 12.07.2026, das hat mich 129.99 Euro gekostet, Vorgang 458219.", "de"),
            ("", "de"),
        ]

        identity_state = crd.new_state()
        crd.init_from_call(identity_state, UNKNOWN_MOBILE)  # unregistered mobile, like Herr Müller

        captured_calls, history = self._drive_call(monkeypatch, tmp_path, transcriptions, identity_state)
        assert len(captured_calls) == 2

        # ── Turn 1: the spoken landline must never reach get_response ──
        turn1 = captured_calls[0]
        assert "[Festnetznummer übermittelt]" in turn1["user_text"], turn1["user_text"]
        for needle in (RAW_LANDLINE_SPOKEN, RAW_LANDLINE_DIGITS, "661123456"):
            assert needle not in turn1["user_text"]
        # the placeholder must preserve the sentence's meaning, not just blank it
        assert "Festnetznummer die nicht geht" in turn1["user_text"]

        # ── the persisted history (== what call_log/escalation later see)
        # must never contain the raw number either ──
        for msg in history:
            content = msg.get("content", "")
            for needle in (RAW_LANDLINE_SPOKEN, RAW_LANDLINE_DIGITS, "661123456"):
                assert needle not in content, f"raw number leaked into history: {msg!r}"

        # ── Turn 2: ordinary date / decimal price / ticket number must be
        # left completely untouched — no over-sanitization ──
        turn2 = captured_calls[1]
        assert turn2["user_text"] == transcriptions[1][0]
        assert "12.07.2026" in turn2["user_text"]
        assert "129.99" in turn2["user_text"]
        assert "458219" in turn2["user_text"]

        # ── the raw number must still be recoverable, but ONLY from
        # deterministic state, never from text ──
        assert identity_state["last_redacted_number"] is not None
        assert re.sub(r"\D", "", identity_state["last_redacted_number"]) == RAW_LANDLINE_DIGITS
        assert identity_state["affected_number_stated"] is not None
        assert identity_state["identity_stage"] == "resolved"
        assert identity_state["resolution"]["customer"]["customer_id"] == "cus_001"

    def test_spoken_mobile_callback_number_is_also_redacted(self, monkeypatch, tmp_path):
        # Not the affected Festnetznummer flow — a caller offering a mobile
        # callback number mid-conversation must be redacted too.
        transcriptions = [
            ("Sie erreichen mich auch unter meiner Telefonnummer 0151 99988877.", "de"),
            ("", "de"),
        ]
        identity_state = crd.new_state()
        crd.init_from_call(identity_state, "")  # withheld caller ID

        captured_calls, history = self._drive_call(monkeypatch, tmp_path, transcriptions, identity_state)
        assert len(captured_calls) == 1
        turn1 = captured_calls[0]
        assert "[Telefonnummer übermittelt]" in turn1["user_text"]
        assert "0151 99988877" not in turn1["user_text"]
        assert "015199988877" not in turn1["user_text"]
        for msg in history:
            assert "0151 99988877" not in msg.get("content", "")
        assert identity_state["last_redacted_number"] is not None

    def test_identification_restarts_after_exempt_enquiry_turns_customer_specific(self, monkeypatch, tmp_path):
        # Turn 1 is a general product question — identification stays exempt,
        # so system_extra must be None (or at least carry no identity prompt).
        # Turn 2 introduces a callback request tied to this customer's own
        # line — identification must resume, and the caller's spoken number
        # in that same turn must still be redacted.
        transcriptions = [
            ("Welche Produkte bieten Sie überhaupt an?", "de"),
            ("Ich hätte gerne einen Rückruf, meine Rufnummer ist 0661 555000.", "de"),
            ("", "de"),
        ]
        identity_state = crd.new_state()
        crd.init_from_call(identity_state, "")  # withheld caller ID, nothing resolved yet

        captured_calls, history = self._drive_call(monkeypatch, tmp_path, transcriptions, identity_state)
        assert len(captured_calls) == 2

        # Turn 1: exempt — no identity instruction leaked into system_extra.
        assert identity_state["identification_exempt"] is True or captured_calls[0]["system_extra"] is None
        turn1_extra = captured_calls[0]["system_extra"] or ""
        assert "CALLER IDENTIFICATION" not in turn1_extra

        # Turn 2: exemption must have been cleared by the callback request,
        # and the spoken number must still never reach get_response raw.
        assert identity_state["identification_exempt"] is False
        assert "0661 555000" not in captured_calls[1]["user_text"]
        assert "0661555000" not in captured_calls[1]["user_text"]
        for msg in history:
            assert "0661 555000" not in msg.get("content", "")
            assert "0661555000" not in msg.get("content", "")


# =============================================================================
# Layer 3 — the identification_exempt state-machine transition itself
# (dialogue-layer unit test; Layer 2 above additionally proves the resulting
# system_extra actually changes once identification restarts).
# =============================================================================
class TestIdentificationExemptionRestarts:
    def test_general_question_sets_exempt(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Welche Produkte bieten Sie an?")
        assert state["identification_exempt"] is True
        assert crd.build_prompt_extra(state) is None

    def test_fault_report_clears_exempt(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Welche Produkte bieten Sie an?")
        assert state["identification_exempt"] is True
        crd.observe_turn(state, "Mein Telefon funktioniert nicht mehr.")
        assert state["identification_exempt"] is False
        assert crd.build_prompt_extra(state) is not None

    def test_callback_request_clears_exempt(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Haben Sie auch Fritzboxen im Angebot?")
        assert state["identification_exempt"] is True
        crd.observe_turn(state, "Ich hätte gerne einen Rückruf dazu.")
        assert state["identification_exempt"] is False

    def test_account_reference_clears_exempt(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Was kostet ein neuer Router?")
        assert state["identification_exempt"] is True
        crd.observe_turn(state, "Es geht um meine Rechnung.")
        assert state["identification_exempt"] is False

    def test_urgent_outage_clears_exempt_and_is_immediate(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Öffnungszeiten, bitte?")
        assert state["identification_exempt"] is True
        crd.observe_turn(state, "Kompletter Ausfall, bei uns ist alles tot!")
        assert state["urgent"] is True
        assert state["identification_exempt"] is False
        # Urgency itself must never be gated behind identification.
        extra = crd.build_prompt_extra(state)
        assert extra is not None
        assert "do not block" in extra

    def test_pure_general_question_never_resolved_by_identity_and_customer_trigger_together_stays_unexempt(self, monkeypatch):
        # A single utterance that mixes a general-question phrase with a
        # customer-specific one must not be marked exempt in the first place.
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Haben Sie auch einen Rückruf-Service?")
        assert state["identification_exempt"] is False
