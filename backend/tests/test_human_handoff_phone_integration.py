"""
Phone <-> human-handoff integration tests.

Two layers, mirroring test_customer_resolution_privacy.py / test_scheduler_
phone_integration.py:

  * wiring — driving voice/esl_call_handler._conversation_loop end-to-end with
    a mocked ESL handler, proving the deterministic ESCALATE_NOW short-circuit
    fires without depending on the LLM, that Stage 2 (recording consent, then
    the final-note question, then transfer) happens in the right order exactly
    once, and that a silent/refused final note never blocks the transfer.

  * boundary — calling voice/escalation.handle_escalation() directly (with the
    LLM summary call and the email transport both patched) to prove a raw
    callback number never reaches the LLM summary prompt, and appears only in
    the deterministic email body / handoff metadata.

Hermetic: no FreeSWITCH, no ESL, no network.
"""
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import human_handoff_dialogue as hh  # noqa: E402
from voice import config as voice_config  # noqa: E402


# =============================================================================
# Wiring — _conversation_loop drives the deterministic handoff end-to-end
# =============================================================================
class _CallDriver:
    """Shared scaffolding for driving _conversation_loop with a mocked handler."""

    def _drive(
        self, tmp_path, monkeypatch, transcriptions,
        handoff_state=None, get_response_replies=None, hangup_after_records=None,
    ):
        from voice.esl_call_handler import _conversation_loop

        monkeypatch.setattr(voice_config, "AI_WAITING_ROOM_PRIMARY", "778")
        monkeypatch.setattr(voice_config, "AI_WAITING_ROOM_SECONDARY", "")

        t_idx = [0]

        def _fake_transcribe(path, lang=None):
            i = t_idx[0]
            t_idx[0] += 1
            return transcriptions[i] if i < len(transcriptions) else ("", "de")

        record_calls = [0]

        def _is_hung_up(self):
            if hangup_after_records is None:
                return False  # the escalation branch always returns before another loop iteration
            return record_calls[0] >= hangup_after_records

        mock_handler = MagicMock()
        type(mock_handler).is_hung_up = property(_is_hung_up)

        execute_calls = []

        def _execute(*args, **kwargs):
            execute_calls.append(args)
            if args and args[0] == "record":
                record_calls[0] += 1
                Path(args[1].split()[0]).touch()
            return True

        mock_handler.execute.side_effect = _execute

        speak_calls = []

        def _fake_speak_and_play(handler, text, lang="de"):
            speak_calls.append(text)

        llm_called = [False]

        async def _fake_get_response(history, user_text, caller_name=None, system_extra=None, system_prompt=None):
            llm_called[0] = True
            reply = (get_response_replies or ["Alles klar."]).pop(0) if get_response_replies else "Alles klar."
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": reply})
            return reply

        escalation_calls = []

        def _fake_handle_escalation(*args, **kwargs):
            escalation_calls.append(kwargs)
            return {"summary": "test", "email_sent": True, "transfer_target": "778", "transfer_ok": True}

        history: list = []

        with patch("voice.esl_call_handler._audio_dir", return_value=Path(str(tmp_path))), \
             patch("voice.esl_call_handler._speak_and_play", side_effect=_fake_speak_and_play), \
             patch("voice.esl_call_handler._get_filler_wav", return_value=""), \
             patch("voice.esl_call_handler.transcribe_file", side_effect=_fake_transcribe), \
             patch("voice.esl_call_handler.get_response", side_effect=_fake_get_response), \
             patch("voice.esl_call_handler.speak_to_file", return_value=""), \
             patch("voice.escalation.handle_escalation", side_effect=_fake_handle_escalation):
            result = _conversation_loop(
                handler=mock_handler,
                history=history,
                caller="+4915199988877",
                caller_name=None,
                started_at=datetime.now(timezone.utc),
                system_prompt="test",
                turn_count_ref=[0],
                uuid="uuid-handoff-1",
                initial_lang="de",
                dialogue_state=None,
                identity_state=None,
                handoff_state=handoff_state,
            )

        return {
            "result": result,
            "history": history,
            "speak_calls": speak_calls,
            "execute_calls": execute_calls,
            "llm_called": llm_called[0],
            "escalation_calls": escalation_calls,
        }


class TestDeterministicEscalationWithoutLLM(_CallDriver):
    def test_escalates_even_when_llm_would_never_emit_escalate(self, tmp_path, monkeypatch):
        # The scripted LLM reply NEVER contains "ESCALATE:" — proves the
        # handoff engine does not depend on (or wait for) the LLM's own
        # judgement once the caller has insisted.
        transcriptions = [
            ("Ich möchte einen Mitarbeiter sprechen, es geht um meine Rechnung.", "de"),  # turn 1: OFFER_HELP
            ("Nein, ich möchte trotzdem mit jemandem sprechen.", "de"),                   # turn 2: insist -> ESCALATE_NOW
            ("ja", "de"),   # consent
            ("", "de"),     # final note (silence)
        ]
        out = self._drive(
            tmp_path, monkeypatch, transcriptions,
            handoff_state=hh.new_state(),
            get_response_replies=["Ich kann das gerne selbst prüfen."],
        )
        assert out["result"] is True  # escalation path returns True
        # Turn 1 went through the LLM (OFFER_HELP is phrased by the LLM).
        assert out["llm_called"] is True
        # Turn 2 must have short-circuited BEFORE reaching the LLM.
        assert any(
            m["content"].upper().startswith("ESCALATE:")
            for m in out["history"] if m["role"] == "assistant"
        )
        assert out["escalation_calls"], "handle_escalation was never called"


class TestPrematureLLMEscalationIsOverridden(_CallDriver):
    """
    Reproduces a real bug found via manual testing: system_extra told the LLM
    to offer help, but it replied with ESCALATE anyway (its own independent
    judgement, e.g. an "annoyed caller" read) — silently skipping the
    mandatory one-time offer. The call handler must override that reply with
    the deterministic fallback and must NOT transfer or call handle_escalation
    for it.
    """

    def test_offer_help_turn_does_not_escalate_when_llm_misbehaves(self, tmp_path, monkeypatch):
        transcriptions = [
            ("Ich möchte einen Mitarbeiter sprechen, es geht um meine Rechnung.", "de"),  # -> OFFER_HELP
            ("", "de"),  # next turn: silence, then hang up
        ]
        state = hh.new_state()
        out = self._drive(
            tmp_path, monkeypatch, transcriptions,
            handoff_state=state,
            get_response_replies=["ESCALATE: caller sounds annoyed"],  # LLM misbehaves
            hangup_after_records=2,
        )

        assert state["action"] == "OFFER_HELP"
        # No escalation/transfer happened for the misbehaving turn.
        assert not out["escalation_calls"]
        assert not [c for c in out["execute_calls"] if c and c[0] == "deflect"]
        # The archived reply is the deterministic fallback, never the raw
        # ESCALATE line the LLM actually returned.
        assistant_msgs = [m["content"] for m in out["history"] if m["role"] == "assistant"]
        assert any("Das kann ich eventuell auch direkt für Sie klären" in m for m in assistant_msgs)
        for m in out["history"]:
            assert not m["content"].upper().startswith("ESCALATE:")


class TestConsentBeforeFinalNoteAndTransferOnce(_CallDriver):
    def test_order_consent_then_final_note_then_transfer_exactly_once(self, tmp_path, monkeypatch):
        transcriptions = [
            # Single utterance: TIME_CRITICAL + explicit person request ->
            # deterministic ESCALATE_NOW on turn 1, no LLM call at all.
            ("Es ist sehr dringend, verbinden Sie mich bitte mit jemandem.", "de"),
            ("ja", "de"),         # recording consent
            ("", "de"),           # final-note answer: silence
        ]
        state = hh.new_state()
        out = self._drive(tmp_path, monkeypatch, transcriptions, handoff_state=state)

        assert out["result"] is True
        assert out["llm_called"] is False  # never reached the LLM

        # Stage 2 ordering: consent question spoken before the final-note question.
        consent_idx = next(i for i, s in enumerate(out["speak_calls"]) if "aufgezeichnet" in s)
        note_idx = next(i for i, s in enumerate(out["speak_calls"]) if s == hh.final_note_question())
        assert consent_idx < note_idx

        # Transfer (deflect) happens exactly once.
        deflects = [c for c in out["execute_calls"] if c and c[0] == "deflect"]
        assert len(deflects) == 1

        # Silence at the final note must not have blocked the transfer.
        assert state["final_note_already_collected"] is True
        assert state["final_note_text"] is None

        # Structured handoff context reached handle_escalation as ONE dict kwarg.
        assert len(out["escalation_calls"]) == 1
        ctx = out["escalation_calls"][0]["handoff_context"]
        assert ctx["category"] == "TIME_CRITICAL"
        assert ctx["human_requested"] is True
        assert ctx["handoff_confirmed"] is True

    def test_refusal_at_final_note_does_not_block_transfer(self, tmp_path, monkeypatch):
        transcriptions = [
            ("Es ist sehr dringend, verbinden Sie mich bitte mit jemandem.", "de"),
            ("ja", "de"),                 # consent
            ("Nein danke, das war's.", "de"),  # explicit refusal at final note
        ]
        state = hh.new_state()
        out = self._drive(tmp_path, monkeypatch, transcriptions, handoff_state=state)

        assert out["result"] is True
        deflects = [c for c in out["execute_calls"] if c and c[0] == "deflect"]
        assert len(deflects) == 1
        assert state["final_note_already_collected"] is True
        assert state["final_note_text"] is None


class TestFinalNoteAskedAtMostOnceWiring(_CallDriver):
    def test_final_note_question_spoken_only_once(self, tmp_path, monkeypatch):
        transcriptions = [
            ("Es ist sehr dringend, verbinden Sie mich bitte mit jemandem.", "de"),
            ("ja", "de"),
            ("Bitte dringend zurückrufen.", "de"),
        ]
        state = hh.new_state()
        out = self._drive(tmp_path, monkeypatch, transcriptions, handoff_state=state)
        note_asks = [s for s in out["speak_calls"] if s == hh.final_note_question()]
        assert len(note_asks) == 1
        assert state["final_note_asked"] is True


class TestRawNumbersNeverEnterHistory(_CallDriver):
    def test_callback_number_stated_during_handoff_never_enters_history(self, tmp_path, monkeypatch):
        transcriptions = [
            (
                "Ich möchte mit jemandem sprechen, meine Rückrufnummer ist "
                "0661 555000, es geht um meine Rechnung.",
                "de",
            ),
            ("Nein, ich bestehe trotzdem darauf, mit jemandem zu sprechen.", "de"),
            ("ja", "de"),
            ("", "de"),
        ]
        state = hh.new_state()
        out = self._drive(
            tmp_path, monkeypatch, transcriptions,
            handoff_state=state,
            get_response_replies=["Ich schaue mir das gerne selbst an."],
        )
        for msg in out["history"]:
            content = msg.get("content", "")
            assert "0661 555000" not in content
            assert "0661555000" not in content
            assert "555000" not in content
        # The raw number is recoverable only from deterministic state.
        assert state["callback_number_current_call"] is not None
        assert "555000" in state["callback_number_current_call"]


def _run_in_thread(fn):
    """
    Run fn() on a dedicated worker thread and return its result.

    handle_escalation() calls asyncio.run() internally (for the LLM summary).
    In production this always happens on the per-call thread spawned by
    ESLOutboundServer, never on the process's main thread — asyncio.run()
    closes and clears the event loop of whatever thread calls it, which would
    otherwise poison later tests in this same pytest process that rely on
    asyncio.get_event_loop()'s legacy auto-create behaviour on the MAIN
    thread (see tests/test_phone_safety.py::TestActiveCallBlocking). Running
    it on a worker thread here mirrors production and keeps this test
    hermetic with respect to the rest of the suite.
    """
    result = {}
    error = {}

    def _target():
        try:
            result["value"] = fn()
        except BaseException as exc:  # re-raise on the calling thread below
            error["exc"] = exc

    t = threading.Thread(target=_target)
    t.start()
    t.join(timeout=30)
    if "exc" in error:
        raise error["exc"]
    return result["value"]


# =============================================================================
# Boundary — handle_escalation(): sanitized transcript to the LLM summary,
# raw callback number ONLY in the deterministic email body / metadata.
# =============================================================================
class TestHandoffContextNeverReachesLLMSummary:
    def test_raw_callback_number_absent_from_llm_summary_request(self, monkeypatch, tmp_path):
        from voice import escalation as esc

        captured_summary_args = {}

        async def _fake_llm_summary(transcript, caller, caller_name, escalation_reason):
            captured_summary_args["transcript"] = transcript
            captured_summary_args["caller"] = caller
            captured_summary_args["caller_name"] = caller_name
            captured_summary_args["escalation_reason"] = escalation_reason
            return "Kurze Zusammenfassung."

        captured_email = {}

        def _fake_send_smtp(subject, body, recording_path=None):
            captured_email["subject"] = subject
            captured_email["body"] = body
            return True

        # Deliberately DIFFERENT from the caller-ID number below — the caller
        # number is legitimately passed to _llm_summary already (pre-existing
        # behaviour); this test isolates the handoff-collected callback number.
        raw_callback = "+4915155566677"
        handoff_context = {
            "human_requested": True,
            "category": "STANDARD_HUMAN_REQUEST",
            "reason_known": True,
            "reason_text": "Frage zur Rechnung",
            "ai_help_offered": True,
            "caller_insisted": True,
            "handoff_confirmed": True,
            "final_note_asked": True,
            "final_note_text": "Bitte dringend zurückrufen.",
            "callback_number_current_call": raw_callback,
        }

        # History (the transcript) already only ever contains sanitized text
        # by construction (esl_call_handler always appends sanitized_t) — the
        # fixture below models that invariant explicitly.
        transcript = [
            {"role": "user", "content": "Ich möchte mit jemandem sprechen."},
            {"role": "assistant", "content": "Worum geht es denn?"},
            {"role": "user", "content": "Es geht um meine Rechnung."},
        ]

        with patch("voice.escalation._llm_summary", side_effect=_fake_llm_summary), \
             patch("voice.escalation._send_via_gmail", return_value=False), \
             patch("voice.escalation._send_smtp_email", side_effect=_fake_send_smtp), \
             patch("voice.escalation.transfer_to_extension", return_value=True):
            result = _run_in_thread(lambda: esc.handle_escalation(
                caller="+4915199988877",
                caller_name=None,
                transcript=transcript,
                escalation_reason="STANDARD_HUMAN_REQUEST — Frage zur Rechnung",
                started_at=datetime.now(timezone.utc),
                call_uuid="uuid-boundary-1",
                esl_handler=MagicMock(),
                recording_consent=False,
                recording_path=None,
                handoff_context=handoff_context,
            ))

        # The raw callback number must never appear in ANY argument passed to
        # the LLM summary function — by construction it isn't even a
        # parameter of _llm_summary, this proves it structurally.
        for value in captured_summary_args.values():
            assert raw_callback not in repr(value)

        # ...but it MUST appear in the deterministic email body / metadata.
        assert raw_callback in captured_email["body"]
        assert result["summary"] == "Kurze Zusammenfassung."

    def test_raw_callback_number_present_only_in_structured_metadata(self, monkeypatch):
        from voice import escalation as esc

        captured_email = {}

        def _fake_send_smtp(subject, body, recording_path=None):
            captured_email["subject"] = subject
            captured_email["body"] = body
            return True

        raw_callback = "+4915155566677"
        handoff_context = {
            "category": "COMPLAINT",
            "reason_text": "Beschwerde über Rückruf",
            "final_note_text": None,
            "callback_number_current_call": raw_callback,
        }

        with patch("voice.escalation._llm_summary", new=AsyncMock(return_value="Zusammenfassung.")), \
             patch("voice.escalation._send_via_gmail", return_value=False), \
             patch("voice.escalation._send_smtp_email", side_effect=_fake_send_smtp), \
             patch("voice.escalation.transfer_to_extension", return_value=True):
            _run_in_thread(lambda: esc.handle_escalation(
                caller="+4915155566677",
                caller_name="Frau Weber",
                transcript=[{"role": "user", "content": "Ich bin sehr verärgert."}],
                escalation_reason="COMPLAINT — Beschwerde",
                started_at=datetime.now(timezone.utc),
                call_uuid="uuid-boundary-2",
                esl_handler=MagicMock(),
                handoff_context=handoff_context,
            ))

        # Raw number must never leak into the email SUBJECT (existing privacy
        # invariant — see escalation-email-privacy-guardian).
        assert raw_callback not in captured_email["subject"]
        # It must be present, and only, in the structured body field.
        assert "Rückrufnummer (nur dieser Anruf)" in captured_email["body"]
        assert raw_callback in captured_email["body"]
