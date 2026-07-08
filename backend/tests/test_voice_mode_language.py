"""
Browser voice-mode language-tracking regression tests (api/voice_mode.py).

Same root cause as the phone path (see tests/test_language_tracking.py): the
TTS language used to be re-detected from the AI's OWN reply via langdetect
(`detect_language(normalized)`), so a short acknowledgement like "Okay." could
be classified as English and flip the TTS voice mid-session.

The fix mirrors the phone path:
  * each session carries a user-owned conversation language (default "de"),
  * it is updated ONLY from the accepted user transcript, BEFORE the AI reply
    exists, via the shared tracker utils/lang_tracking.py,
  * the AI reply is never language-detected.

Hermetic: no WebSocket, no Whisper, no LLM, no network.

Run with (WSL debian12 + .venv-wsl):
    cd backend && ../.venv-wsl/bin/python -m pytest tests/test_voice_mode_language.py -q
"""
import os
import re
import sys
import uuid as _uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import api.voice_mode as vm  # noqa: E402
from utils.lang_tracking import update_conversation_language  # noqa: E402


def _fresh_session() -> str:
    return f"lang-test-{_uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _clean_registry():
    """Remove any session entries a test created so tests never leak state."""
    before = set(vm._session_registry)
    yield
    for sid in set(vm._session_registry) - before:
        vm._session_registry.pop(sid, None)


def _voice_mode_source() -> str:
    return open(vm.__file__, encoding="utf-8").read()


# =============================================================================
# Session language lifecycle — user-owned, exactly like the phone path
# =============================================================================
class TestSessionLanguageLifecycle:
    def test_session_defaults_to_german(self):
        assert vm._get_session_lang(_fresh_session()) == "de"
        assert vm.DEFAULT_SESSION_LANG == "de"

    @pytest.mark.parametrize("ack", ["Okay.", "Gut.", "Verstanden.", "Alles klar."])
    def test_german_session_stays_german_after_short_ai_ack(self, ack):
        """Simulate the exact per-turn flow of voice_stream: the language is
        updated from the user transcript, then the AI reply (the short ack) is
        spoken — the TTS language must still be German."""
        sid = _fresh_session()
        # Turn: user speaks German → session language is fixed before the AI runs
        tts_lang = vm._update_session_lang(sid, "Ich habe eine Frage zu meinem Kalender.")
        assert tts_lang == "de"
        # The AI replies with a short acknowledgement. Nothing in the flow may
        # feed it back into the language state — prove the state is untouched.
        reply = ack  # noqa: F841 — the reply plays no role in language tracking
        assert vm._get_session_lang(sid) == "de"
        # Next turn's user input (short German) keeps the language stable too.
        assert vm._update_session_lang(sid, "Ja bitte.") == "de"

    def test_short_user_utterances_never_switch(self):
        sid = _fresh_session()
        vm._update_session_lang(sid, "Ich möchte bitte meine Termine sehen.")
        for short in ["Okay.", "Ja.", "Yes.", "Hm.", "Alles klar."]:
            assert vm._update_session_lang(sid, short) == "de"

    def test_genuine_english_user_input_switches(self):
        sid = _fresh_session()
        lang = vm._update_session_lang(
            sid, "Hello, I would like to check my calendar please."
        )
        assert lang == "en"
        # Short acknowledgements keep it English afterwards.
        assert vm._update_session_lang(sid, "Okay.") == "en"

    def test_german_user_input_switches_back(self):
        sid = _fresh_session()
        vm._update_session_lang(sid, "Hello, I would like to check my calendar please.")
        lang = vm._update_session_lang(sid, "Ich möchte bitte auf Deutsch weitermachen.")
        assert lang == "de"

    def test_ambiguous_user_input_keeps_current(self):
        sid = _fresh_session()
        vm._update_session_lang(sid, "Ich möchte bitte meine Termine sehen.")
        assert vm._update_session_lang(sid, "Alpha beta gamma delta epsilon") == "de"

    def test_connect_seeds_language_like_voice_stream(self):
        """voice_stream seeds the registry entry with the default language."""
        src = _voice_mode_source()
        assert '"lang": DEFAULT_SESSION_LANG' in src


# =============================================================================
# Pin — the AI reply is never used to mutate the session language
# =============================================================================
class TestNoReplyBasedDetection:
    def test_tts_no_longer_detects_language_from_reply(self):
        """The old bug line was `lang = detect_language(normalized)` on the
        normalized AI reply. It must be gone, and tts_service.detect_language
        must not be imported/used by voice_mode at all."""
        src = _voice_mode_source()
        assert "detect_language(normalized" not in src
        # Strip comments so mentions in explanatory comments don't count.
        code_only = re.sub(r"#[^\n]*", "", src)
        assert "detect_language" not in code_only, (
            "voice_mode.py must not language-detect AI output — the session "
            "language is owned by the user (utils.lang_tracking)."
        )

    def test_language_is_updated_from_transcript_only(self):
        """Every _update_session_lang call site passes the user transcript."""
        src = _voice_mode_source()
        calls = re.findall(r"_update_session_lang\(([^)]*)\)", src)
        # at least the definition + one call site
        call_sites = [c for c in calls if "session_id" in c and "transcript" in c]
        assert call_sites, "voice_stream must update the language from the transcript"
        for c in calls:
            assert "reply" not in c, f"AI reply passed into language tracking: {c}"

    def test_tts_uses_session_language(self):
        """The TTS block speaks with the user-owned conversation language."""
        src = _voice_mode_source()
        assert re.search(r"lang\s*=\s*conv_lang", src), (
            "TTS must use the session conversation language, not a re-detection"
        )


# =============================================================================
# Pin — one shared tracker for phone and browser (no duplicated heuristics)
# =============================================================================
class TestSharedHelper:
    def test_phone_and_browser_use_the_same_tracker(self):
        """The phone path delegates to utils.lang_tracking; browser voice mode
        imports the same function — the heuristics can never drift apart."""
        from voice.esl_call_handler import _caller_language

        samples = [
            ("Okay.", "de"),
            ("Gut.", "en"),
            ("Ich habe eine Frage zu meiner Rechnung", "en"),
            ("Hello, I would like to make an appointment please", "de"),
            ("Alpha beta gamma delta epsilon", "de"),
        ]
        for text, current in samples:
            assert _caller_language(text, current) == \
                update_conversation_language(text, current)

    def test_esl_handler_has_no_local_marker_sets(self):
        """esl_call_handler must import the marker sets from the shared module
        rather than defining its own copies."""
        import voice.esl_call_handler as _esl

        src = open(_esl.__file__, encoding="utf-8").read()
        assert "from utils.lang_tracking import" in src
        assert "_EN_WORDS = frozenset" not in src
        assert "_DE_WORDS = frozenset" not in src
