"""
Conversation-language tracking regression tests for voice/esl_call_handler.py.

Root cause pinned here: the loop used to re-detect the conversation language
from the AI's OWN generated reply (`_detect_lang(r)`). A short LLM
acknowledgement like "Okay." has no German markers, was classified as English,
and flipped the TTS voice mid-call — the caller heard two different
receptionists.

The fix makes the conversation language belong to the CALLER:
  * it starts from the call context (greeting language),
  * it is updated only by `_caller_language(caller_text, current)`, which
    requires strong evidence (>= 4 words with unambiguous markers) to switch,
  * AI replies are never used for language detection.

Hermetic: no FreeSWITCH, no ESL, no Whisper, no network, no LLM.

Run with (WSL debian12 + .venv-wsl):
    cd backend && ../.venv-wsl/bin/python -m pytest tests/test_language_tracking.py -q
"""
import inspect
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import voice.esl_call_handler as _esl  # noqa: E402
from voice.esl_call_handler import _caller_language, _conversation_loop  # noqa: E402


# =============================================================================
# Unit — _caller_language (the only mechanism allowed to change the language)
# =============================================================================
class TestCallerLanguageHelper:
    @pytest.mark.parametrize("short_text", [
        "Okay.", "Gut.", "Verstanden.", "Alles klar.", "Ja.", "Nein danke.",
        "Okay thanks.", "Yes.", "Hm.",
    ])
    def test_short_utterances_never_switch(self, short_text):
        """Anything under the word threshold keeps the current language."""
        assert _caller_language(short_text, "de") == "de"
        assert _caller_language(short_text, "en") == "en"

    def test_long_german_stays_german(self):
        t = "Ich habe eine Frage zu meiner letzten Rechnung"
        assert _caller_language(t, "de") == "de"

    def test_long_english_switches_from_german(self):
        t = "Hello, I would like to make an appointment please"
        assert _caller_language(t, "de") == "en"

    def test_german_switches_back_from_english(self):
        t = "Ich möchte bitte einen Techniker sprechen"
        assert _caller_language(t, "en") == "de"

    def test_mixed_language_prefers_german(self):
        """German markers are high-precision — they win over English words."""
        t = "Hello, ich möchte bitte einen Techniker"
        assert _caller_language(t, "en") == "de"

    def test_ambiguous_text_keeps_current(self):
        """No markers of either language → no switch, in both directions."""
        t = "Alpha beta gamma delta epsilon"
        assert _caller_language(t, "de") == "de"
        assert _caller_language(t, "en") == "en"

    def test_single_english_marker_is_not_enough(self):
        """One weak English hit in a longer utterance must not flip the voice."""
        t = "Yes Alpha Beta Gamma Delta"
        assert _caller_language(t, "de") == "de"


# =============================================================================
# Pin — AI replies are never fed into language detection
# =============================================================================
class TestNoReplyBasedDetection:
    def test_loop_does_not_detect_language_from_llm_reply(self):
        """The conversation loop must not call _detect_lang on AI output.
        Language updates go exclusively through _caller_language(caller_text)."""
        src = inspect.getsource(_esl._conversation_loop)
        assert "_detect_lang" not in src, (
            "_conversation_loop must not re-detect the conversation language "
            "from generated text — that is the two-receptionists bug."
        )
        assert "_caller_language" in src

    def test_detect_lang_helper_retained_as_speak_fallback(self):
        """_detect_lang stays as the lang=None safety net of _speak_and_play."""
        assert "_detect_lang" in inspect.getsource(_esl._speak_and_play)


# =============================================================================
# Wiring — drive _conversation_loop with scripted calls
# =============================================================================
def _run_scripted_call(
    tmp_path,
    transcriptions,
    replies,
    *,
    initial_lang="de",
    dialogue_state=None,
    max_records=None,
    deflect_ok=True,
):
    """Run _conversation_loop hermetically with a scripted conversation.

    transcriptions: caller utterances in order ("" = silent turn); extra
                    recordings past the script transcribe to "".
    replies:        LLM replies consumed in order.

    Returns a dict with everything the AI "spoke":
      speak_file — (text, lang) of every speak_to_file call (LLM/scheduler replies)
      spoken     — (text, lang) of every _speak_and_play call (check-ins,
                   farewells, consent, hold, continuation prompts)
      fillers    — language of every filler fetched
      stt_hints  — language hint passed to transcribe_file each turn
      escalated  — return value of the loop
      llm_calls  — how many times the LLM was invoked
    """
    if max_records is None:
        max_records = len(transcriptions) + 1

    speak_file_calls: list = []
    spoken: list = []
    filler_langs: list = []
    stt_hints: list = []
    record_calls = [0]
    t_idx = [0]
    llm_calls = [0]

    def _is_hung_up(self):
        return record_calls[0] >= max_records

    handler = MagicMock()
    type(handler).is_hung_up = property(_is_hung_up)

    def _execute(*args, **kwargs):
        if args and args[0] == "record":
            record_calls[0] += 1
            Path(args[1].split()[0]).touch()
        if args and args[0] == "deflect":
            return deflect_ok
        return True

    handler.execute.side_effect = _execute

    def _fake_transcribe(path, lang=None):
        stt_hints.append(lang)
        i = t_idx[0]
        t_idx[0] += 1
        text = transcriptions[i] if i < len(transcriptions) else ""
        return text, (lang or "de")

    async def _fake_get_response(*a, **kw):
        i = llm_calls[0]
        llm_calls[0] += 1
        return replies[i] if i < len(replies) else "Okay."

    def _fake_speak_to_file(text, lang="de", **kw):
        speak_file_calls.append((text, lang))
        return ""

    def _fake_speak_and_play(handler, text, lang=None):
        spoken.append((text, lang))

    def _fake_filler(lang):
        filler_langs.append(lang)
        return ""

    with patch("voice.esl_call_handler._audio_dir", return_value=Path(str(tmp_path))), \
         patch("voice.esl_call_handler._speak_and_play", side_effect=_fake_speak_and_play), \
         patch("voice.esl_call_handler._get_filler_wav", side_effect=_fake_filler), \
         patch("voice.esl_call_handler.transcribe_file", side_effect=_fake_transcribe), \
         patch("voice.esl_call_handler.get_response", side_effect=_fake_get_response), \
         patch("voice.esl_call_handler.speak_to_file", side_effect=_fake_speak_to_file), \
         patch("voice.escalation.handle_escalation",
               return_value={"summary": "", "email_sent": False}):
        escalated = _conversation_loop(
            handler=handler,
            history=[],
            caller="+4966112345678",
            caller_name="Max Mustermann",
            started_at=datetime.now(timezone.utc),
            system_prompt="test",
            turn_count_ref=[0],
            uuid="uuid-lang-test",
            initial_lang=initial_lang,
            dialogue_state=dialogue_state,
        )

    return {
        "escalated": escalated,
        "speak_file": speak_file_calls,
        "spoken": spoken,
        "fillers": filler_langs,
        "stt_hints": stt_hints,
        "llm_calls": llm_calls[0],
    }


class TestGermanCallStaysGerman:
    """The core regression: short AI acknowledgements must never flip the voice."""

    def test_short_ai_acknowledgements_keep_german_voice(self, tmp_path):
        res = _run_scripted_call(
            tmp_path,
            transcriptions=[
                "Ich habe eine Frage zu meiner Telefonanlage.",
                "Können Sie mir mit der Rechnung helfen?",
                "Der Techniker soll sich bitte melden.",
                "Dann warte ich auf den Anruf, vielen Dank.",
            ],
            replies=["Okay.", "Gut.", "Verstanden.", "Alles klar."],
        )
        # Every AI reply — including the marker-free "Okay." — spoken in German.
        assert len(res["speak_file"]) == 4
        assert all(lang == "de" for _, lang in res["speak_file"]), res["speak_file"]
        # Every filler phrase stays German (the old bug made turn-2 filler English).
        assert res["fillers"] and all(l == "de" for l in res["fillers"]), res["fillers"]
        # Whisper keeps receiving the German hint every turn.
        assert all(h == "de" for h in res["stt_hints"]), res["stt_hints"]
        assert res["escalated"] is False

    def test_checkin_prompt_stays_german_after_short_ack(self, tmp_path):
        """Silence check-in after an 'Okay.' reply must still be German."""
        res = _run_scripted_call(
            tmp_path,
            transcriptions=[
                "Ich habe eine Frage zu meiner Telefonanlage.",
                "",  # silent turn 1
                "",  # silent turn 2 → check-in prompt
            ],
            replies=["Okay."],
        )
        checkins = [(t, l) for t, l in res["spoken"] if "noch da" in t or "still there" in t]
        assert checkins == [("Sind Sie noch da?", "de")], res["spoken"]

    def test_scheduler_deterministic_replies_stay_german(self, tmp_path, monkeypatch):
        """Appointment turns (deterministic Scheduler replies) stay German even
        though the flow interleaves with the language tracking."""
        from voice import scheduler_dialogue

        monkeypatch.setenv("SCHEDULER_STORE_PATH", str(tmp_path / "appointments.jsonl"))
        res = _run_scripted_call(
            tmp_path,
            transcriptions=[
                "Ich möchte einen Rückruf vereinbaren",
                "am Montag",
                "die erste passt",
                "",
            ],
            replies=[],
            dialogue_state=scheduler_dialogue.new_state(),
        )
        assert res["llm_calls"] == 0, "Scheduler turns must never reach the LLM"
        assert res["speak_file"], "expected spoken scheduler replies"
        assert all(lang == "de" for _, lang in res["speak_file"]), res["speak_file"]
        assert all(l == "de" for l in res["fillers"]), res["fillers"]

    def test_escalation_stays_german_after_short_ack(self, tmp_path):
        """Escalation right after an 'Okay.' reply: consent, hold message and
        the failed-transfer farewell must all be German. Under the old
        reply-based detection conv_lang would already be 'en' here."""
        res = _run_scripted_call(
            tmp_path,
            transcriptions=[
                "Ich habe ein Problem mit der Telefonanlage.",
                "Ich möchte bitte mit einem Mitarbeiter sprechen.",
                "ja",  # consent answer
            ],
            replies=["Okay.", "ESCALATE: Kunde möchte einen Mitarbeiter sprechen"],
            max_records=10,
            deflect_ok=False,  # both orbits fail → farewell branch is exercised
        )
        assert res["escalated"] is True
        # Consent + hold are hard-coded German (existing invariant).
        assert any("Bevor ich Sie weiterleite" in t and l == "de"
                   for t, l in res["spoken"]), res["spoken"]
        assert any(
            t == "Einen Moment bitte, ich leite Sie an einen Mitarbeiter weiter."
            and l == "de"
            for t, l in res["spoken"]
        ), res["spoken"]
        # The farewell after a failed transfer follows conv_lang — must be German.
        farewell = [(t, l) for t, l in res["spoken"]
                    if "zurückrufen" in t or "call you back" in t]
        assert farewell, res["spoken"]
        assert all(l == "de" and "Mitarbeiter" in t for t, l in farewell), farewell


class TestGenuineEnglishCallStillWorks:
    def test_english_caller_switches_and_stays_english(self, tmp_path):
        """Strong caller-side evidence still switches the call to English, and
        short English AI replies keep it there."""
        res = _run_scripted_call(
            tmp_path,
            transcriptions=[
                "Hello, I would like to speak with someone about my phone system please.",
                "Yes, my name is John Smith, thank you.",
            ],
            replies=[
                "Of course, may I have your name?",
                "Thank you, John. Goodbye!",  # farewell ends the call
            ],
        )
        # Both replies spoken with the English voice after the caller-side switch.
        assert [l for _, l in res["speak_file"]] == ["en", "en"], res["speak_file"]
        # Turn 1 filler plays before the switch is known (inherent one-turn lag);
        # from turn 2 the filler is English.
        assert res["fillers"][0] == "de"
        assert all(l == "en" for l in res["fillers"][1:]), res["fillers"]
        # The STT hint follows the caller's language on the next turn.
        assert res["stt_hints"] == ["de", "en"], res["stt_hints"]
