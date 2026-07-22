"""
Unit tests for voice/human_handoff_dialogue.py — the deterministic
"caller wants a person" state machine (Stage 1: request understanding,
Stage 2: transfer preparation).

Hermetic: no FreeSWITCH, no ESL, no network, no LLM. Drives the module
directly as a state machine, exactly like test_scheduler_phone_integration.py
does for voice/scheduler_dialogue.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import human_handoff_dialogue as hh  # noqa: E402


# =============================================================================
# Stage 1 — human-request understanding
# =============================================================================
class TestReasonUnderstanding:
    def test_unknown_reason_is_asked(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte mit jemandem sprechen.")
        assert state["human_requested"] is True
        assert state["reason_known"] is False
        assert state["action"] == "ASK_REASON"
        extra = hh.build_prompt_extra(state)
        assert extra is not None and "REASON UNKNOWN" in extra

    def test_known_reason_is_not_asked_again(self):
        # Reason is stated on an EARLIER turn, before the person request.
        state = hh.new_state()
        hh.observe_turn(state, "Mein Internet funktioniert nicht mehr.")
        assert state["reason_known"] is True
        hh.observe_turn(state, "Verbinden Sie mich bitte mit jemandem.")
        assert state["action"] != "ASK_REASON"
        assert state["action"] == "OFFER_HELP"

    def test_reason_given_in_the_same_utterance_is_captured(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte einen Mitarbeiter sprechen, es geht um meine Rechnung.")
        assert state["reason_known"] is True
        assert "Rechnung" in state["reason_text"]
        assert state["action"] == "OFFER_HELP"

    def test_reason_asked_once_then_next_turn_is_captured_verbatim(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich will mit jemandem sprechen.")
        assert state["action"] == "ASK_REASON"
        hh.observe_turn(state, "Meine Fritzbox blinkt komisch.")  # no known keyword
        assert state["reason_known"] is True
        assert state["reason_text"] == "Meine Fritzbox blinkt komisch."
        assert state["action"] == "OFFER_HELP"


class TestHelpOfferedAtMostOnce:
    def test_help_offered_exactly_once(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte einen Mitarbeiter sprechen, es geht um meine Rechnung.")
        assert state["action"] == "OFFER_HELP"
        assert state["ai_help_offered"] is True

        # Caller doesn't insist and doesn't refuse — AI keeps helping normally,
        # offer is not repeated. CONTINUE_HELPING (not None) is returned so the
        # LLM keeps getting told not to re-escalate for the earlier request
        # still sitting in conversation history — see build_prompt_extra.
        hh.observe_turn(state, "Ah gut, können Sie mir das erklären?")
        assert state["action"] == "CONTINUE_HELPING"
        assert state["ai_help_offered"] is True
        extra = hh.build_prompt_extra(state)
        assert extra is not None and "DO NOT RE-ESCALATE" in extra

        # Even later, the offer itself is never issued a second time.
        hh.observe_turn(state, "Alles klar, danke.")
        assert state["action"] != "OFFER_HELP"


class TestRepeatedRequestRespected:
    def test_repeated_human_request_stops_offering_and_escalates(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte einen Mitarbeiter sprechen, es geht um meine Rechnung.")
        assert state["action"] == "OFFER_HELP"
        hh.observe_turn(state, "Nein, ich möchte trotzdem mit jemandem sprechen.")
        assert state["caller_insisted"] is True
        assert state["action"] == "ESCALATE_NOW"
        assert hh.should_escalate_now(state) is True
        # ESCALATE_NOW is never phrased by the LLM.
        assert hh.build_prompt_extra(state) is None

    def test_negative_human_request_phrasing_is_detected(self):
        # The caller frames the request as a refusal of the AI, not a
        # positive "connect me" ask — must still register as a request.
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte nicht mit einem Bot sprechen.")
        assert state["human_requested"] is True
        assert state["category"] == "STANDARD_HUMAN_REQUEST"


class TestEmergencyBypassesDialogue:
    def test_emergency_skips_ask_and_offer(self):
        state = hh.new_state()
        hh.observe_turn(state, "Es brennt, verbinden Sie mich sofort mit jemandem!")
        assert state["category"] == "EMERGENCY"
        assert state["action"] == "ESCALATE_NOW"
        # Never asked for a reason, never offered help.
        assert state["reason_asked"] is False
        assert state["ai_help_offered"] is False

    def test_time_critical_also_bypasses_stage_1(self):
        state = hh.new_state()
        hh.observe_turn(state, "Kompletter Ausfall, verbinden Sie mich bitte mit jemandem.")
        assert state["category"] == "TIME_CRITICAL"
        assert state["action"] == "ESCALATE_NOW"


class TestCategoryUpgrading:
    def test_category_upgrades_across_turns_and_never_downgrades(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte mit jemandem sprechen.")
        assert state["category"] == "STANDARD_HUMAN_REQUEST"

        hh.observe_turn(state, "Das ist eine Frechheit, ich warte schon seit Tagen.")
        assert state["category"] == "COMPLAINT"

        hh.observe_turn(state, "Kompletter Ausfall, nichts funktioniert mehr.")
        assert state["category"] == "TIME_CRITICAL"

        # A later, lower-urgency utterance must never downgrade the category.
        hh.observe_turn(state, "Ach so, das ist eigentlich nicht so wichtig.")
        assert state["category"] == "TIME_CRITICAL"

        hh.observe_turn(state, "Es brennt!")
        assert state["category"] == "EMERGENCY"


class TestComplaintBypassesSelfService:
    def test_complaint_never_gets_the_help_offer(self):
        state = hh.new_state()
        hh.observe_turn(
            state,
            "Das ist eine Frechheit, ich warte schon seit einer Woche auf einen "
            "Rückruf wegen meiner Rechnung, verbinden Sie mich mit jemandem.",
        )
        assert state["category"] == "COMPLAINT"
        assert state["reason_known"] is True
        assert state["action"] == "ESCALATE_NOW"
        assert state["ai_help_offered"] is False

    def test_complaint_with_unknown_reason_asks_once_then_escalates(self):
        state = hh.new_state()
        hh.observe_turn(state, "Das ist eine Frechheit, ich bin genervt, verbinden Sie mich!")
        # Complaint keyword present but no reason captured yet from this text.
        assert state["category"] == "COMPLAINT"
        if not state["reason_known"]:
            assert state["action"] == "ASK_REASON"
            hh.observe_turn(state, "Es geht um meine Fritzbox.")
        assert state["ai_help_offered"] is False
        assert state["action"] == "ESCALATE_NOW"


class TestExplicitNoMoreQuestions:
    def test_no_more_questions_bypasses_offer_and_escalates(self):
        state = hh.new_state()
        hh.observe_turn(
            state,
            "Ich hätte gerne einen Mitarbeiter wegen meiner Rechnung. "
            "Verbinden Sie mich bitte einfach, keine weiteren Fragen.",
        )
        assert state["no_more_questions"] is True
        assert state["action"] == "ESCALATE_NOW"
        assert state["ai_help_offered"] is False

    def test_no_more_questions_also_skips_final_note(self):
        state = hh.new_state()
        hh.observe_turn(state, "Verbinden Sie mich bitte einfach, keine weiteren Fragen.")
        hh.mark_handoff_confirmed(state)
        assert hh.should_ask_final_note(state) is False


class TestDeterministicEscalationSignal:
    def test_should_escalate_now_true_only_for_escalate_now_action(self):
        state = hh.new_state()
        assert hh.should_escalate_now(state) is False
        hh.observe_turn(state, "Es brennt, verbinden Sie mich!")
        assert hh.should_escalate_now(state) is True

    def test_mark_handoff_confirmed_is_idempotent_and_clears_action(self):
        state = hh.new_state()
        hh.observe_turn(state, "Es brennt, verbinden Sie mich!")
        hh.mark_handoff_confirmed(state)
        assert state["handoff_confirmed"] is True
        assert state["action"] is None
        hh.mark_handoff_confirmed(state)  # idempotent, no error
        assert state["handoff_confirmed"] is True


# =============================================================================
# Stage 2 — transfer preparation
# =============================================================================
class TestFinalNoteAskedAtMostOnce:
    def test_final_note_asked_once_then_not_again(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte mit jemandem sprechen, es geht um meine Rechnung.")
        hh.mark_handoff_confirmed(state)
        assert hh.should_ask_final_note(state) is True
        hh.mark_final_note_asked(state)
        assert hh.should_ask_final_note(state) is False


class TestFinalNoteIndependentOfReasonKnown:
    def test_final_note_asked_even_when_reason_was_never_known(self):
        # Simulates the LLM-triggered ESCALATE: path for a trigger unrelated
        # to a person-request (e.g. "credentials needed") — human_requested/
        # reason_known were never touched by stage 1 at all.
        state = hh.new_state()
        assert state["reason_known"] is False
        hh.mark_handoff_confirmed(state)
        assert hh.should_ask_final_note(state) is True

    def test_final_note_skipped_reasons_do_not_include_reason_known(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte mit jemandem sprechen, es geht um meine Rechnung.")
        assert state["reason_known"] is True
        hh.mark_handoff_confirmed(state)
        # Reason IS known, but that alone must not skip the final note.
        assert hh.should_ask_final_note(state) is True


class TestFinalNoteSkipConditions:
    def test_emergency_skips_final_note(self):
        state = hh.new_state()
        hh.observe_turn(state, "Es brennt, verbinden Sie mich!")
        hh.mark_handoff_confirmed(state)
        assert hh.should_ask_final_note(state) is False

    def test_already_collected_skips_final_note(self):
        state = hh.new_state()
        hh.mark_handoff_confirmed(state)
        hh.record_final_note_response(state, "Alles gesagt.")
        assert hh.should_ask_final_note(state) is False


class TestFinalNoteNeverBlocksTransfer:
    def test_silence_never_raises_and_marks_collected(self):
        state = hh.new_state()
        hh.record_final_note_response(state, None)
        assert state["final_note_already_collected"] is True
        assert state["final_note_text"] is None

    def test_empty_transcription_never_raises_and_marks_collected(self):
        state = hh.new_state()
        hh.record_final_note_response(state, "")
        assert state["final_note_already_collected"] is True
        assert state["final_note_text"] is None

    def test_refusal_marks_collected_without_a_note(self):
        state = hh.new_state()
        hh.record_final_note_response(state, "Nein danke, das war's.")
        assert state["final_note_already_collected"] is True
        assert state["final_note_text"] is None


# =============================================================================
# Callback-number / raw-number privacy boundary
# =============================================================================
class TestCallbackNumberPrivacyBoundary:
    def test_reason_text_never_contains_a_raw_number_even_if_spoken_alongside(self):
        state = hh.new_state()
        hh.observe_turn(
            state,
            "Es geht um meine Rufnummer 0661 123456, die tot ist, "
            "verbinden Sie mich bitte mit jemandem.",
        )
        assert "0661" not in (state["reason_text"] or "")
        assert "123456" not in (state["reason_text"] or "")
        assert state["callback_number_current_call"] is not None
        assert "123456" in state["callback_number_current_call"]

    def test_final_note_text_never_contains_a_raw_number(self):
        state = hh.new_state()
        hh.record_final_note_response(
            state, "Rufen Sie mich zurück unter 0151 9998887."
        )
        assert "9998887" not in (state["final_note_text"] or "")
        assert state["callback_number_current_call"] is not None
        assert "9998887" in state["callback_number_current_call"]

    def test_callback_number_never_appears_in_prompt_extra(self):
        state = hh.new_state()
        hh.observe_turn(
            state, "Meine Nummer ist 0661 555000, ich möchte mit jemandem sprechen."
        )
        extra = hh.build_prompt_extra(state)
        if extra:
            assert "555000" not in extra


# =============================================================================
# Structured handoff context reaches escalation
# =============================================================================
class TestFallbackWhenLLMEscalatesPrematurely:
    """
    Reproduces a real bug found via manual testing: system_extra told the LLM
    to ask the reason / offer help, but nothing stopped it from replying with
    ESCALATE anyway (e.g. via its own independent "annoyed caller" judgement)
    — silently skipping a mandatory stage-1 step. This is the deterministic
    backstop for when prompt-following alone isn't enough.
    """

    def test_overrides_premature_escalate_during_ask_reason(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte mit jemandem sprechen.")
        assert state["action"] == "ASK_REASON"
        fallback = hh.fallback_reply_if_llm_escalated_prematurely(
            state, "ESCALATE: STANDARD_HUMAN_REQUEST — caller sounds impatient"
        )
        assert fallback is not None
        assert "ESCALATE" not in fallback.upper()

    def test_overrides_premature_escalate_during_offer_help(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte einen Mitarbeiter sprechen, es geht um meine Rechnung.")
        assert state["action"] == "OFFER_HELP"
        fallback = hh.fallback_reply_if_llm_escalated_prematurely(state, "ESCALATE: annoyed caller")
        assert fallback is not None
        assert "ESCALATE" not in fallback.upper()

    def test_no_override_when_llm_complies(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte mit jemandem sprechen.")
        assert hh.fallback_reply_if_llm_escalated_prematurely(state, "Worum geht es denn?") is None

    def test_no_override_for_actions_other_than_ask_reason_or_offer_help(self):
        state = hh.new_state()
        hh.observe_turn(state, "Es brennt, verbinden Sie mich!")
        assert state["action"] == "ESCALATE_NOW"
        # ESCALATE_NOW is the deterministic path itself — nothing to override.
        assert hh.fallback_reply_if_llm_escalated_prematurely(state, "ESCALATE: fire") is None


class TestBuildHandoffContext:
    def test_context_is_a_single_flat_dict_with_expected_fields(self):
        state = hh.new_state()
        hh.observe_turn(state, "Ich möchte mit jemandem sprechen, es geht um meine Rechnung.")
        hh.mark_handoff_confirmed(state)
        hh.record_final_note_response(state, "Bitte dringend zurückrufen.")
        ctx = hh.build_handoff_context(state)
        assert ctx["human_requested"] is True
        assert ctx["reason_known"] is True
        assert ctx["reason_text"] and "Rechnung" in ctx["reason_text"]
        assert ctx["handoff_confirmed"] is True
        assert ctx["final_note_text"] == "Bitte dringend zurückrufen."
        assert set(ctx.keys()) == {
            "human_requested", "category", "reason_known", "reason_text",
            "ai_help_offered", "caller_insisted", "handoff_confirmed",
            "final_note_asked", "final_note_text", "callback_number_current_call",
        }
