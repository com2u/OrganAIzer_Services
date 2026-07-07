"""
Natural call ending after a spoken goodbye.

When the AI's reply is a farewell ("… Auf Wiederhören."), _conversation_loop
must end the call instead of recording on and asking "Sind Sie noch da?"
after having said goodbye.

Hermetic: no FreeSWITCH, no ESL, no network, no real audio.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice.esl_call_handler import _conversation_loop, _is_farewell_reply  # noqa: E402


class TestFarewellDetection:
    @pytest.mark.parametrize("reply", [
        "Dann wünsche ich Ihnen einen schönen Tag. Auf Wiederhören.",
        "Vielen Dank für Ihren Anruf bei Teleprofi Fulda. Auf Wiederhören.",
        "Thank you for calling. Goodbye!",
    ])
    def test_farewell_replies_detected(self, reply):
        assert _is_farewell_reply(reply) is True

    @pytest.mark.parametrize("reply", [
        "",
        "Guten Tag, wie kann ich Ihnen helfen?",
        "Ich höre Ihnen zu — bitte fahren Sie fort.",
        "Am Montag, den 6. Juli könnte ich Ihnen 9 Uhr anbieten.",
        "Kann ich sonst noch etwas für Sie tun?",
    ])
    def test_normal_replies_not_detected(self, reply):
        assert _is_farewell_reply(reply) is False


class TestLoopEndsAfterFarewell:
    def test_loop_ends_naturally_after_ai_goodbye(self, tmp_path):
        """After the AI speaks its farewell the loop exits on its own —
        no further record turns, no 'Sind Sie noch da?' after the goodbye."""
        mock_handler = MagicMock()
        record_calls = [0]

        # Safety net only — the farewell break must fire long before this.
        def _is_hung_up(self):
            return record_calls[0] >= 10

        type(mock_handler).is_hung_up = property(_is_hung_up)

        def _execute(*args, **kwargs):
            if args and args[0] == "record":
                record_calls[0] += 1
                Path(args[1].split()[0]).touch()
            return True

        mock_handler.execute.side_effect = _execute

        def _fake_transcribe(path, lang=None):
            return ("Vielen Dank, das war alles.", "de")

        llm_calls = [0]

        async def _fake_get_response(*a, **kw):
            llm_calls[0] += 1
            return "Dann wünsche ich Ihnen einen schönen Tag. Auf Wiederhören."

        spoken: list[str] = []

        with patch("voice.esl_call_handler._audio_dir", return_value=Path(str(tmp_path))), \
             patch("voice.esl_call_handler._speak_and_play",
                   side_effect=lambda h, t, lang=None: spoken.append(t)), \
             patch("voice.esl_call_handler._get_filler_wav", return_value=""), \
             patch("voice.esl_call_handler.transcribe_file", side_effect=_fake_transcribe), \
             patch("voice.esl_call_handler.get_response", side_effect=_fake_get_response), \
             patch("voice.esl_call_handler.speak_to_file", return_value=""):
            escalated = _conversation_loop(
                handler=mock_handler,
                history=[],
                caller="+4930123456789",
                caller_name=None,
                started_at=datetime.now(timezone.utc),
                system_prompt="test",
                turn_count_ref=[0],
                uuid="uuid-farewell-loop",
                initial_lang="de",
            )

        assert escalated is False
        assert record_calls[0] == 1, (
            f"Loop kept recording after the AI said goodbye ({record_calls[0]} records)"
        )
        assert llm_calls[0] == 1
        # No silence check-in after the goodbye
        assert not any("noch da" in s for s in spoken)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
