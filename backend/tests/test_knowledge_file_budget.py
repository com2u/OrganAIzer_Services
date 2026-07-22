"""
Unit test for backend/voice/knowledge/teleprofi_fulda.md — guards the
character budget enforced at runtime by voice/llm_bridge.py.

The live knowledge file is loaded in FULL into every call's system prompt
(_load_knowledge_file / _MAX_KNOWLEDGE_CHARS in voice/llm_bridge.py). Past
that cap the loader truncates silently (only a log line, no error), which
would cut the file off mid-section on a live call. This test fails loudly
before that can happen.

Hermetic: reads the file directly via the production loader function, no
FreeSWITCH, no ESL, no LLM.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice.llm_bridge import (  # noqa: E402
    _DEFAULT_KNOWLEDGE_PATH,
    _MAX_KNOWLEDGE_CHARS,
    _load_knowledge_file,
)


class TestKnowledgeFileCharacterBudget:
    def _raw_text(self) -> str:
        return _DEFAULT_KNOWLEDGE_PATH.read_text(encoding="utf-8")

    def test_file_is_under_max_knowledge_chars(self):
        raw = self._raw_text()
        assert len(raw) < _MAX_KNOWLEDGE_CHARS, (
            f"teleprofi_fulda.md is {len(raw)} chars, at or over the "
            f"_MAX_KNOWLEDGE_CHARS cap of {_MAX_KNOWLEDGE_CHARS}. The live "
            "prompt loader truncates silently past this size — trim the "
            "file before content gets cut off mid-call."
        )

    def test_loader_does_not_silently_truncate_the_live_file(self):
        # Cross-check against the actual production loader so this test
        # tracks real runtime behavior even if the cap or loader logic
        # changes later.
        raw = self._raw_text()
        loaded = _load_knowledge_file(_DEFAULT_KNOWLEDGE_PATH)
        assert loaded == raw, (
            "voice.llm_bridge._load_knowledge_file() returned fewer "
            "characters than the file on disk — the live knowledge file "
            "is being truncated at call time."
        )
