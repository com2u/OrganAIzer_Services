"""
Unit tests for voice/concern_tracking.py — the small per-call tracker for
multiple caller concerns mentioned in one call.

No FreeSWITCH, no ESL, no LLM. Pure function-level tests, mirroring the
style of test_human_handoff_dialogue.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import concern_tracking as ct  # noqa: E402


# =============================================================================
# Explicit multi-intent marker detection — conservative, no semantic parsing
# =============================================================================

class TestMultiIntentDetection:
    def test_ordinary_und_without_explicit_marker_is_not_split(self):
        # "Mein Telefon klingelt nicht und unser WLAN ist auch schlecht." —
        # a real two-concern utterance, but with plain "und", not an explicit
        # marker ("und außerdem", "zusätzlich", ...). Conservative-by-design:
        # must NOT split (see test_explicit_marker_* below for the positive
        # "two concerns in one utterance" case that DOES split).
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Mein Telefon klingelt nicht und unser WLAN ist auch schlecht.",
        )
        assert record is None
        assert ct.open_concerns(state) == []

    def test_two_concerns_in_one_utterance_with_explicit_marker(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Ich brauche Hilfe mit Outlook und außerdem möchte ich einen Termin.",
        )
        assert record is not None
        assert "termin" in record["text"].lower()
        assert len(ct.open_concerns(state)) == 1

    def test_explicit_marker_zusaetzlich(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state,
            "Das Internet ist ausgefallen, zusätzlich wollte ich nach einer neuen Anlage fragen.",
        )
        assert record is not None
        assert "anlage" in record["text"].lower()

    def test_three_concerns_across_several_turns(self):
        state = ct.new_state()
        ct.observe_turn(state, "Das Telefon geht nicht und außerdem ist das WLAN langsam.")
        ct.observe_turn(state, "Zusätzlich habe ich noch eine Frage zur Rechnung.")
        ct.observe_turn(state, "Und dazu wollte ich noch einen Rückruf vereinbaren.")
        assert len(state) == 3
        assert all(c["status"] == "open" for c in state)

    def test_no_false_positive_from_ordinary_und_inside_one_sentence(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state, "Ich habe ein Problem mit meinem Telefon und mit meinem Router."
        )
        assert record is None
        assert ct.open_concerns(state) == []

    def test_english_marker_and_also(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state, "I need help with Outlook and also I'd like to book an appointment."
        )
        assert record is not None
        assert "appointment" in record["text"].lower()

    def test_english_ordinary_and_no_false_positive(self):
        state = ct.new_state()
        record = ct.observe_turn(
            state, "My phone and my WiFi are both not working."
        )
        assert record is None

    def test_empty_utterance_returns_none(self):
        assert ct.observe_turn(ct.new_state(), "") is None

    def test_marker_with_nothing_after_it_returns_none(self):
        state = ct.new_state()
        assert ct.observe_turn(state, "Und außerdem") is None
        assert ct.open_concerns(state) == []

    def test_repeated_identical_concern_not_added_twice(self):
        state = ct.new_state()
        ct.observe_turn(state, "Telefon kaputt und außerdem ist das WLAN langsam.")
        ct.observe_turn(state, "Wie gesagt, und außerdem ist das WLAN langsam.")
        assert len(state) == 1


# =============================================================================
# Priority — emergency > outage > operational > appointment > informational
# =============================================================================

class TestPriorityOrdering:
    def test_emergency_ranks_first(self):
        assert ct.classify_category("es ist ein notfall") == "emergency"
        assert ct._priority_rank("emergency") == 0

    def test_outage_ranks_second(self):
        assert ct.classify_category("kompletter ausfall der anlage") == "outage"
        assert ct._priority_rank("outage") == 1

    def test_appointment_ranks_fourth(self):
        assert ct.classify_category("ich hätte gern einen termin") == "appointment"
        assert ct._priority_rank("appointment") == 3

    def test_informational_ranks_last(self):
        assert ct.classify_category("wie viel kostet eine neue anlage") == "informational"
        assert ct._priority_rank("informational") == 4

    def test_urgent_concern_prioritized_first_among_open_concerns(self):
        state = ct.new_state()
        ct.observe_turn(state, "Ich habe eine Frage und außerdem hätte ich gern einen Termin.")
        ct.observe_turn(state, "Übrigens, zusätzlich ist es ein notfall, es brennt.")
        open_ = ct.open_concerns(state)
        highest = min(open_, key=lambda c: c["priority"])
        assert highest["category"] == "emergency"


# =============================================================================
# Status lifecycle — open / resolved / handed_off
# =============================================================================

class TestConcernStatusLifecycle:
    def test_resolved_concern_excluded_from_open_concerns(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B mit dem Router.")
        assert len(ct.open_concerns(state)) == 1
        text = state[0]["text"]
        assert ct.mark_resolved(state, text[:10]) is True
        # Resolved concern must not be repeated in a handoff — i.e. must not
        # appear in open_concerns(), which is the only source handoff/
        # escalation/call-log wiring reads from.
        assert ct.open_concerns(state) == []
        assert state[0]["status"] == "resolved"

    def test_mark_resolved_returns_false_when_nothing_matches(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B.")
        assert ct.mark_resolved(state, "völlig anderer text") is False
        assert len(ct.open_concerns(state)) == 1

    def test_mark_all_handed_off(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B mit dem Router.")
        ct.mark_all_handed_off(state)
        assert ct.open_concerns(state) == []
        assert state[0]["status"] == "handed_off"

    def test_handed_off_concern_not_marked_handed_off_twice_incorrectly(self):
        # mark_all_handed_off only touches OPEN concerns — a concern already
        # resolved must stay "resolved", not get silently overwritten.
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B.")
        ct.mark_resolved(state, state[0]["text"][:10])
        ct.mark_all_handed_off(state)
        assert state[0]["status"] == "resolved"


# =============================================================================
# Prompt extra + acknowledgement wording
# =============================================================================

class TestPromptExtraAndAcknowledgement:
    def test_no_open_concerns_returns_none(self):
        assert ct.build_prompt_extra(ct.new_state()) is None

    def test_single_open_concern_extra(self):
        state = ct.new_state()
        ct.observe_turn(state, "Problem A und außerdem Problem B mit dem Router.")
        extra = ct.build_prompt_extra(state)
        assert extra is not None
        assert "Problem B" in extra or "problem b" in extra.lower()

    def test_acknowledgement_does_not_quote_raw_caller_text(self):
        # Must not attempt to grammatically embed an arbitrary caller
        # fragment — see the function's own docstring reasoning.
        ack_de = ct.acknowledgement_for_new_concern(2, lang="de")
        ack_en = ct.acknowledgement_for_new_concern(2, lang="en")
        assert isinstance(ack_de, str) and ack_de
        assert isinstance(ack_en, str) and ack_en
        assert ack_de != ack_en

    def test_acknowledgement_singular_vs_plural_wording_differs(self):
        single = ct.acknowledgement_for_new_concern(1, lang="de")
        plural = ct.acknowledgement_for_new_concern(3, lang="de")
        assert single != plural
