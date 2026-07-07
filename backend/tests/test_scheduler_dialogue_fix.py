"""
Tests for the repeated-question fix in scheduler_dialogue.py.

Verifies:
- AI never asks the same appointment reason question twice
- No internal appointment-type menu is exposed to caller
- Time and reason can be given in any order
- Within-call memory prevents re-asking for the same info
- Safe escalation after unclear attempts
"""
import pytest
from datetime import datetime, date, timedelta
from scheduler import generate_slots, read_appointments
from voice import scheduler_dialogue

# Thursday 2026-07-02 09:00 → "Montag" resolves to 2026-07-06 (like the
# integration tests). Used by the hermetic booking-flow tests below.
NOW = datetime(2026, 7, 2, 9, 0)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "appointments.jsonl"


class TestNoRepeatedQuestions:
    """Verify the AI never repeats the same question."""

    def test_appointment_reason_question_not_repeated(self):
        """The AI asks 'Worum geht es denn?' once, not twice."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Turn 1: Caller says they need an appointment
        result1 = scheduler_dialogue.handle_turn(
            state, "Ich brauche einen Termin.", now=now
        )
        assert result1 is not None
        assert "Worum geht es denn" in result1.reply
        assert "Rückruf, Fernwartung" not in result1.reply  # No menu!

        # Turn 2: Caller gives unclear answer (not matching keywords)
        result2 = scheduler_dialogue.handle_turn(
            state, "Also, ähm, ja.", now=now
        )
        assert result2 is not None
        # Second attempt should rephrase, NOT repeat the exact same question
        assert "Was möchten Sie klären" in result2.reply or "Fernwartung" in result2.reply
        # But NOT the same exact "Worum geht es denn?" sentence
        assert result2.reply != result1.reply


    def test_no_appointment_type_menu_exposed(self):
        """The appointment-type menu ('Rückruf, Fernwartung, ...') is never spoken."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Turn 1: Appointment intent
        result1 = scheduler_dialogue.handle_turn(
            state, "Ich brauch nen Termin.", now=now
        )
        assert result1 is not None
        # Should not expose the menu
        assert "Rückruf, Fernwartung, Vor-Ort" not in result1.reply
        assert "Rückruf, Fernwartung" not in result1.reply
        assert "Beratung oder Wartung" not in result1.reply

        # Turn 2: Unclear answer
        result2 = scheduler_dialogue.handle_turn(
            state, "Ich weiß nicht.", now=now
        )
        assert result2 is not None
        # Still no menu exposed
        assert "Rückruf, Fernwartung" not in result2.reply
        assert "Vor-Ort-Termin" not in result2.reply


    def test_clarification_question_differs_on_second_attempt(self):
        """On second unclear attempt, AI asks a different clarification question."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Turn 1: Appointment intent
        result1 = scheduler_dialogue.handle_turn(
            state, "Ich brauch einen Termin.", now=now
        )
        question1 = result1.reply

        # Turn 2: Unclear answer (first rephrase)
        result2 = scheduler_dialogue.handle_turn(
            state, "Ähm, ja, also...", now=now
        )
        question2 = result2.reply

        # Verify they differ
        assert question1 != question2


class TestNaturalInference:
    """Verify the AI infers appointment type from caller language."""

    def test_infers_remote_support_from_technical_problem(self):
        """When caller says 'technical problem', infer remote_support, don't ask menu."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Turn 1: Generic appointment request
        result1 = scheduler_dialogue.handle_turn(
            state, "Ich brauch einen Termin.", now=now
        )
        assert result1 is not None
        assert state["appointment_type"] is None  # Not inferred yet

        # Turn 2: Caller explains technical problem
        result2 = scheduler_dialogue.handle_turn(
            state, "Mein Internet funktioniert nicht.", now=now
        )
        assert result2 is not None
        # Should infer remote_support (or ask for day next)
        assert state["appointment_type"] == "remote_support"
        # Should not ask for type again; should ask for day
        assert "welchem Tag" in result2.reply or "wann" in result2.reply.lower()


    def test_infers_sales_consultation_from_new_system(self):
        """When caller says 'new phone system', infer sales_consultation if appointment intent present."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Caller explicitly asks for an appointment about a new system
        result = scheduler_dialogue.handle_turn(
            state, "Ich brauche einen Termin für eine neue Telefonanlage.", now=now
        )
        assert result is not None
        assert state["appointment_type"] == "sales_consultation"


    def test_infers_callback_from_explicit_ruckruf(self):
        """When caller explicitly says Rückruf, infer callback."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        result = scheduler_dialogue.handle_turn(
            state, "Können Sie mich morgen anrufen? Ich brauche einen Rückruf.", now=now
        )
        assert result is not None
        # Explicit callback request should infer callback type
        assert state.get("appointment_type") == "callback"


class TestTimeBeforeReason:
    """Verify the AI remembers time even if given before reason."""

    def test_caller_gives_time_before_reason(self):
        """Caller says 'tomorrow' before saying what kind of appointment."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)  # Tuesday

        # Turn 1: Caller gives time without reason
        result1 = scheduler_dialogue.handle_turn(
            state, "Morgen brauche ich einen Termin.", now=now
        )
        assert result1 is not None
        # Should remember the time
        assert state["have_time_preference"] is True
        expected_day = now.date() + timedelta(days=1)
        assert state["preferred_day"] == expected_day
        # Should ask for reason (not repeat the day request)
        assert "Worum geht es denn" in result1.reply

        # Turn 2: Caller explains what kind
        result2 = scheduler_dialogue.handle_turn(
            state, "Mein Internet geht nicht.", now=now
        )
        assert result2 is not None
        # Should infer type
        assert state["appointment_type"] == "remote_support"
        # Should NOT ask for day again; should offer slots or confirm
        assert "welchem Tag" not in result2.reply.lower()


    def test_caller_gives_reason_then_time(self):
        """Caller explains reason first, then mentions preferred day."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Turn 1: Generic appointment
        result1 = scheduler_dialogue.handle_turn(
            state, "Ich brauch einen Termin.", now=now
        )
        assert result1 is not None

        # Turn 2: Caller explains reason
        result2 = scheduler_dialogue.handle_turn(
            state, "Mein Router funktioniert nicht.", now=now
        )
        assert result2 is not None
        assert state["appointment_type"] == "remote_support"
        # Should ask for time
        assert "welchem Tag" in result2.reply or "wann" in result2.reply.lower()

        # Turn 3: Caller gives time
        result3 = scheduler_dialogue.handle_turn(
            state, "Morgen, wenn möglich.", now=now
        )
        assert result3 is not None
        # Should NOT ask for reason again
        assert "Worum geht es denn" not in result3.reply


class TestMemoryWithinCall:
    """Verify the AI remembers information within a call."""

    def test_remembers_stated_day(self):
        """AI doesn't re-ask for day if caller already said it."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Turn 1: Appointment + day
        result1 = scheduler_dialogue.handle_turn(
            state, "Ich brauch morgen einen Termin.", now=now
        )
        day_asked_in_1 = result1 and ("welchem Tag" in result1.reply or "wann" in result1.reply.lower())

        # Turn 2: Clarify reason
        result2 = scheduler_dialogue.handle_turn(
            state, "Mein Telefon funktioniert nicht.", now=now
        )
        day_asked_in_2 = result2 and ("welchem Tag" in result2.reply or "wann" in result2.reply.lower())

        # Day should only be asked once (or not at all if inferred in Turn 1)
        assert not (day_asked_in_1 and day_asked_in_2), \
            "AI asked for day in both Turn 1 and Turn 2"


    def test_no_reasking_for_same_detail(self):
        """AI never re-asks for a detail the caller already provided."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Multi-turn conversation
        turns = [
            "Ich brauch einen Termin.",  # intent
            "Wegen meinem Internet.",     # reason
            "Morgen bitte.",              # time
        ]

        prev_reply = ""
        for i, utterance in enumerate(turns):
            result = scheduler_dialogue.handle_turn(state, utterance, now=now)
            if result:
                # Should not repeat the exact same reply
                if i > 0:
                    assert result.reply != prev_reply, \
                        f"Turn {i} repeated the previous reply"
                prev_reply = result.reply


class TestEscalationAfterUnclarity:
    """Verify the AI stays helpful (callback offer) after unclear attempts."""

    def test_rephrases_once_then_offers_callback(self, store):
        """After one rephrase, the AI continues with a callback offer —
        it never restarts the flow or leaves a dangling question to the LLM."""
        state = scheduler_dialogue.new_state()

        # Turn 1: Appointment intent
        result1 = scheduler_dialogue.handle_turn(
            state, "Ich brauch einen Termin.", now=NOW, path=store
        )
        assert result1 is not None

        # Turn 2: First unclear attempt (should rephrase)
        result2 = scheduler_dialogue.handle_turn(state, "Ähm...", now=NOW, path=store)
        assert result2 is not None
        # Should rephrase, not repeat
        assert result2.reply != result1.reply

        # Turn 3: Still unclear → continue as a callback offer, nothing booked
        result3 = scheduler_dialogue.handle_turn(state, "Also...", now=NOW, path=store)
        assert result3 is not None
        assert "Mitarbeiter" in result3.reply
        assert state["appointment_type"] == "callback"
        assert read_appointments(store) == []

    def test_callback_fallback_flow_continues_to_booking(self, store):
        """The callback fallback keeps the deterministic flow alive: caller can
        still name a day, pick a slot, and only then is anything vorgemerkt."""
        state = scheduler_dialogue.new_state()
        scheduler_dialogue.handle_turn(state, "Ich möchte einen Termin vereinbaren.", now=NOW, path=store)
        scheduler_dialogue.handle_turn(state, "Ähm, ja, also...", now=NOW, path=store)
        res = scheduler_dialogue.handle_turn(state, "Ich weiß es echt nicht.", now=NOW, path=store)
        assert state["appointment_type"] == "callback"
        assert read_appointments(store) == []

        res = scheduler_dialogue.handle_turn(state, "am Montag", now=NOW, path=store)
        assert state["stage"] == "offered"
        assert read_appointments(store) == []  # offering still books nothing

        res = scheduler_dialogue.handle_turn(
            state, "die erste passt", now=NOW, path=store, phone="+491701234567"
        )
        assert res.booked
        assert "vorgemerkt" in res.reply
        assert len(read_appointments(store)) == 1


class TestDayQuestionNotRepeated:
    """An unparseable day answer must not re-ask an already-answered question."""

    def test_unparseable_day_answer_offers_earliest_slots(self, store):
        state = scheduler_dialogue.new_state()
        res1 = scheduler_dialogue.handle_turn(
            state, "Ich hätte gerne einen Rückruf.", now=NOW, path=store
        )
        assert "Tag" in res1.reply  # asks for the day once

        # Caller can't name a day → engine offers concrete times instead of
        # repeating the day question or falling back to "Worum geht es denn?"
        res2 = scheduler_dialogue.handle_turn(
            state, "Hm, da bin ich mir noch unsicher.", now=NOW, path=store
        )
        assert res2 is not None
        assert "Worum geht es denn" not in res2.reply
        assert "anbieten" in res2.reply
        assert state["stage"] == "offered"
        assert read_appointments(store) == []

    def test_naechste_woche_resolves_to_next_week(self, store):
        """'Nächste Woche' is a usable day answer (next Monday), not 'unclear'."""
        state = scheduler_dialogue.new_state()
        scheduler_dialogue.handle_turn(state, "Ich hätte gerne einen Rückruf.", now=NOW, path=store)
        scheduler_dialogue.handle_turn(state, "Am besten nächste Woche.", now=NOW, path=store)
        assert state["offer_day"] is not None
        assert state["offer_day"] >= date(2026, 7, 6)  # next Monday or later


class TestOfferAndConfirmationWording:
    """Spoken wording: one sentence offers, count-aware re-asks, vorgemerkt."""

    def _to_offered(self, store):
        state = scheduler_dialogue.new_state()
        scheduler_dialogue.handle_turn(state, "Ich hätte gerne einen Rückruf.", now=NOW, path=store)
        res = scheduler_dialogue.handle_turn(state, "am Montag", now=NOW, path=store)
        return state, res

    def test_offer_is_one_sentence_not_a_list(self, store):
        _, res = self._to_offered(store)
        assert "\n" not in res.reply       # never a bullet list read by TTS
        assert "anbieten" in res.reply
        assert "unverbindlich" in res.reply

    def test_reask_matches_number_of_offered_slots(self, store):
        """With two offered slots, the re-ask must not mention a third."""
        state = scheduler_dialogue.new_state()
        state["stage"] = "offered"
        state["appointment_type"] = "callback"
        state["offered_slots"] = generate_slots(date(2026, 7, 6), 30)[:2]
        res = scheduler_dialogue.handle_turn(state, "hmm, schwierig", now=NOW, path=store)
        assert "zweite" in res.reply
        assert "dritte" not in res.reply

    def test_confirmation_uses_vorgemerkt_not_gebucht(self, store):
        state, _ = self._to_offered(store)
        res = scheduler_dialogue.handle_turn(
            state, "die erste passt", now=NOW, path=store, phone="+491701234567"
        )
        assert res.booked
        assert "vorgemerkt" in res.reply
        assert "gebucht" not in res.reply.lower()
        assert "garantiert" not in res.reply.lower()

    def test_anything_else_asked_exactly_once_after_booking(self, store):
        state, _ = self._to_offered(store)
        res = scheduler_dialogue.handle_turn(
            state, "die erste passt", now=NOW, path=store, phone="+491701234567"
        )
        assert res.reply.count("Kann ich sonst noch etwas für Sie tun?") == 1
        # After booking, the engine releases the turn — no second "anything else?"
        assert scheduler_dialogue.handle_turn(
            state, "Nein, danke.", now=NOW, path=store
        ) is None


class TestBookingConfirmation:
    """Verify no booking without explicit confirmation."""

    def test_no_booking_without_confirmation(self):
        """AI should not book an appointment without caller's explicit yes."""
        state = scheduler_dialogue.new_state()
        now = datetime(2026, 7, 7, 10, 0, 0)

        # Set up a state as if we're about to offer slots
        state["stage"] = "offered"
        state["appointment_type"] = "remote_support"
        state["offered_slots"] = []  # Would be populated by _offer_slots

        # Caller's non-committal response
        result = scheduler_dialogue.handle_turn(
            state, "Ich weiß nicht.", now=now
        )
        if result:
            # Should not be booked
            assert result.booked is False

        # Caller explicitly rejects
        result = scheduler_dialogue.handle_turn(
            state, "Das passt nicht.", now=now
        )
        if result:
            assert result.booked is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
