"""
Phone ↔ Scheduler integration tests (v0.1).

Two layers:
  * engine — voice/scheduler_dialogue.handle_turn as a deterministic state machine
    (clock + store injected), covering the required behaviours.
  * wiring — driving voice/esl_call_handler._conversation_loop end-to-end with a
    scripted appointment conversation, proving the live hook books via the
    Scheduler and never calls the LLM to invent slots.

Hermetic: no FreeSWITCH, no ESL, no network. All storage goes to a tmp file.
"""
import os
import sys
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import scheduler_dialogue as sd  # noqa: E402
from scheduler import generate_slots, read_appointments  # noqa: E402

# Thursday 2026-07-02 09:00 → "Montag" resolves to 2026-07-06.
NOW = datetime(2026, 7, 2, 9, 0)
MONDAY = date(2026, 7, 6)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "appointments.jsonl"


def _turn(state, text, store, **kw):
    return sd.handle_turn(state, text, now=NOW, path=store, **kw)


# =============================================================================
# Engine — intent, offering, confirmation, safety
# =============================================================================
class TestIntentTriggersFlow:
    def test_non_appointment_defers_to_llm(self, store):
        assert _turn(sd.new_state(), "Wie sind Ihre Öffnungszeiten?", store) is None

    def test_appointment_intent_starts_flow(self, store):
        state = sd.new_state()
        res = _turn(state, "Ich hätte gerne einen Rückruf", store)
        assert res is not None
        assert state["stage"] == "collecting"
        assert state["appointment_type"] == "callback"
        # type already known → asks for the day, one question
        assert "Tag" in res.reply

    def test_unknown_type_is_asked_not_guessed(self, store):
        state = sd.new_state()
        res = _turn(state, "Ich möchte einen Termin vereinbaren", store)
        assert res is not None and state["appointment_type"] is None
        assert "Rückruf" in res.reply and "Wartung" in res.reply


class TestSlotsAreOfferedNotInvented:
    def test_offered_slots_come_from_scheduler(self, store):
        state = sd.new_state()
        _turn(state, "Ich hätte gerne einen Rückruf", store)      # → asks day
        res = _turn(state, "am Montag", store)                    # → offers slots
        assert state["stage"] == "offered"
        assert "folgende Zeiten" in res.reply
        # every offered slot must be a real Scheduler-generated slot for that day
        valid = {s.start for s in generate_slots(MONDAY, 30)}
        assert state["offered_slots"]
        assert all(slot.start in valid for slot in state["offered_slots"])
        assert len(state["offered_slots"]) <= 3

    def test_offer_mentions_it_is_vormerkung(self, store):
        state = sd.new_state()
        _turn(state, "Rückruf bitte", store)
        res = _turn(state, "Montag", store)
        assert "unverbindlich" in res.reply.lower()


class TestNoBookingBeforeConfirmation:
    def test_offering_does_not_create(self, store):
        state = sd.new_state()
        _turn(state, "Ich brauche eine Fernwartung", store)
        _turn(state, "Dienstag", store)
        assert state["stage"] == "offered"
        assert read_appointments(store) == []  # nothing booked yet

    def test_generic_yes_with_multiple_slots_asks_which(self, store):
        state = sd.new_state()
        _turn(state, "Rückruf", store)
        _turn(state, "Montag", store)
        assert len(state["offered_slots"]) > 1
        res = _turn(state, "ja", store)
        assert read_appointments(store) == []       # still not booked
        assert "erste" in res.reply.lower()


class TestBookingAfterConfirmation:
    def _book(self, store):
        state = sd.new_state()
        _turn(state, "Ich hätte gerne einen Rückruf", store)
        _turn(state, "am Montag", store)
        res = _turn(
            state, "die erste passt", store,
            phone="+491701234567", caller_name="Max Mustermann", call_id="call-1",
        )
        return state, res

    def test_explicit_confirmation_books(self, store):
        state, res = self._book(store)
        assert res.booked and state["stage"] == "booked"
        recs = read_appointments(store)
        assert len(recs) == 1
        assert recs[0]["appointment_type"] == "callback"
        assert recs[0]["call_id"] == "call-1"

    def test_time_based_confirmation_books(self, store):
        state = sd.new_state()
        _turn(state, "Rückruf", store)
        _turn(state, "Montag", store)
        first = state["offered_slots"][0]
        res = _turn(state, f"{first.start.hour} Uhr passt", store, phone="+491701234567")
        assert res.booked
        assert read_appointments(store)[0]["selected_slot_start"] == first.start_iso

    def test_raw_phone_never_stored(self, store):
        self._book(store)
        blob = store.read_text(encoding="utf-8")
        assert "+491701234567" not in blob
        assert "1701234567" not in blob
        rec = read_appointments(store)[0]
        assert rec["phone_masked"] and "*" in rec["phone_masked"]

    def test_status_always_simulated(self, store):
        self._book(store)
        assert all(r["status"] == "simulated" for r in read_appointments(store))

    def test_confirmation_wording_is_safe_vormerkung(self, store):
        _, res = self._book(store)
        assert "kein garantierter Termin" in res.reply
        for bad in sd.sched_phone.FORBIDDEN_PHRASES:
            assert bad.lower() not in res.reply.lower()

    def test_booked_stage_releases_to_llm(self, store):
        state, _ = self._book(store)
        # after booking, further unrelated turns defer to the LLM
        assert _turn(state, "Vielen Dank, das war alles", store) is None

    def test_invoice_callback_scenario_end_to_end(self, store):
        """Caller: "Ich brauche einen Rückruf wegen einer Rechnung." — the
        motive text must not confuse intent detection, and the topic must
        travel into the stored record."""
        state = sd.new_state()
        res = _turn(state, "Ich brauche einen Rückruf wegen einer Rechnung.", store)
        assert res is not None
        assert state["appointment_type"] == "callback"
        _turn(state, "am Montag", store)
        assert state["stage"] == "offered"
        res = _turn(
            state, "die erste passt", store,
            phone="+491701234567", caller_name="Max Mustermann", call_id="call-inv-1",
        )
        assert res.booked
        assert "kein garantierter Termin" in res.reply
        rec = read_appointments(store)[0]
        assert rec["status"] == "simulated"
        assert "Rechnung" in rec["topic"]
        assert "*" in rec["phone_masked"]
        assert "+491701234567" not in store.read_text(encoding="utf-8")


class TestRejectionAndReoffer:
    def test_negative_asks_for_another_day(self, store):
        state = sd.new_state()
        _turn(state, "Rückruf", store)
        _turn(state, "Montag", store)
        res = _turn(state, "nein, lieber einen anderen Tag", store)
        assert state["stage"] == "collecting"
        assert state["preferred_day"] is None
        assert read_appointments(store) == []
        assert "anderen Tag" in res.reply


class TestUnclearAndEmergencyDoNotBook:
    def test_emergency_escalates_without_booking(self, store):
        state = sd.new_state()
        res = _turn(state, "Notfall! Ich brauche sofort einen Techniker", store)
        assert res is not None and res.reply.upper().startswith("ESCALATE:")
        assert not res.booked
        assert read_appointments(store) == []
        assert state["stage"] == "idle"

    def test_emergency_midflow_escalates(self, store):
        state = sd.new_state()
        _turn(state, "Ich brauche einen Vor-Ort-Termin", store)
        res = _turn(state, "Es brennt, kommen Sie sofort!", store)
        assert res.reply.upper().startswith("ESCALATE:")
        assert read_appointments(store) == []

    def test_repeated_unclear_type_gives_up_without_booking(self, store):
        state = sd.new_state()
        _turn(state, "Ich möchte einen Termin", store)   # type unknown → ask
        _turn(state, "weiß nicht", store)                # attempt 1 → re-ask
        res = _turn(state, "keine ahnung", store)        # attempt 2 → give up
        assert read_appointments(store) == []
        assert state["stage"] == "idle"
        assert res is not None and "Mitarbeiter" in res.reply


class TestTypeMapping:
    @pytest.mark.parametrize("utterance,expected", [
        ("Ich möchte einen Rückruf", "callback"),
        ("Können Sie eine Fernwartung machen?", "remote_support"),
        ("Ich brauche einen Techniker vor Ort", "on_site_visit_request"),
        ("Wir bräuchten eine Wartung", "maintenance_request"),
        ("Ich hätte gern ein Angebot, Vertrieb bitte", "sales_consultation"),
        ("Ich brauche eine technische Beratung", "technical_consultation"),
    ])
    def test_intent_maps_to_type(self, store, utterance, expected):
        state = sd.new_state()
        _turn(state, utterance, store)
        assert state["appointment_type"] == expected


# =============================================================================
# Wiring — _conversation_loop routes appointment turns through the Scheduler
# =============================================================================
class TestConversationLoopWiring:
    def test_appointment_booked_via_loop_without_llm(self, tmp_path, monkeypatch):
        from pathlib import Path
        from voice.esl_call_handler import _conversation_loop
        from voice import scheduler_dialogue

        store = tmp_path / "appointments.jsonl"
        monkeypatch.setenv("SCHEDULER_STORE_PATH", str(store))

        # Hang up after the 3 scripted appointment turns are recorded.
        record_calls = [0]

        def _is_hung_up(self):
            return record_calls[0] >= 4

        mock_handler = MagicMock()
        type(mock_handler).is_hung_up = property(_is_hung_up)

        def _execute(*args, **kwargs):
            if args and args[0] == "record":
                record_calls[0] += 1
                Path(args[1].split()[0]).touch()  # so _process_turn reads the WAV
            return True

        mock_handler.execute.side_effect = _execute

        # Scripted caller: intent → day → pick first. Then silence.
        transcriptions = [
            ("Ich möchte einen Rückruf vereinbaren", "de"),
            ("am Montag", "de"),
            ("die erste passt", "de"),
            ("", "de"),
        ]
        t_idx = [0]

        def _fake_transcribe(path, lang=None):
            i = t_idx[0]
            t_idx[0] += 1
            return transcriptions[i] if i < len(transcriptions) else ("", "de")

        llm_called = [False]

        async def _fake_get_response(*a, **kw):
            llm_called[0] = True
            return "LLM SHOULD NOT DRIVE APPOINTMENTS"

        with patch("voice.esl_call_handler._audio_dir", return_value=Path(str(tmp_path))), \
             patch("voice.esl_call_handler._speak_and_play"), \
             patch("voice.esl_call_handler._get_filler_wav", return_value=""), \
             patch("voice.esl_call_handler.transcribe_file", side_effect=_fake_transcribe), \
             patch("voice.esl_call_handler.get_response", side_effect=_fake_get_response), \
             patch("voice.esl_call_handler.speak_to_file", return_value=""):
            _conversation_loop(
                handler=mock_handler,
                history=[],
                caller="+4930123456789",
                caller_name="Max Mustermann",
                started_at=datetime.now(timezone.utc),
                system_prompt="test",
                turn_count_ref=[0],
                uuid="uuid-appt-loop",
                initial_lang="de",
                dialogue_state=scheduler_dialogue.new_state(),
            )

        recs = read_appointments(str(store))
        assert len(recs) == 1, f"expected one simulated appointment, got {recs}"
        assert recs[0]["status"] == "simulated"
        assert recs[0]["appointment_type"] == "callback"
        assert recs[0]["call_id"] == "uuid-appt-loop"
        # raw caller number must not be stored
        assert "+4930123456789" not in store.read_text(encoding="utf-8")
        assert recs[0]["phone_masked"] and "*" in recs[0]["phone_masked"]
        # the LLM must never have been asked to handle the appointment turns
        assert llm_called[0] is False
