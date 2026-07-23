"""
Regression test: test_openclaw_safety.py and test_phone_safety.py's async
test helpers must not depend on asyncio.get_event_loop()'s legacy "current
loop for this thread" state.

That state is exactly what production code calling asyncio.run() clears
when it finishes (by design — see asyncio.run()'s own implementation and
tests/test_human_handoff_phone_integration.py::_run_in_thread, which
already documents this for voice/escalation.py's handle_escalation()).
Anything in the same pytest process that runs such code on the main thread
before test_openclaw_safety.py / test_phone_safety.py's async tests leaves
asyncio.set_event_loop(None) in effect, and the old
`asyncio.get_event_loop().run_until_complete(...)` helper pattern then
raises "There is no current event loop in thread 'MainThread'" — a
collection-order-dependent failure, not a real bug.

tests/conftest.py::run_isolated (used by both files' local `_run` helpers)
fixes this by using asyncio.run() itself, which creates its own loop
regardless of prior thread-local state. This test proves that directly by
forcing the exact poisoned state first.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from tests.conftest import run_isolated

_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent


class TestRunIsolatedSurvivesClearedEventLoop:
    def test_run_isolated_works_after_set_event_loop_none(self):
        asyncio.set_event_loop(None)

        async def _coro():
            return "ok"

        # Must not raise "There is no current event loop in thread 'MainThread'".
        assert run_isolated(_coro()) == "ok"

    def test_run_isolated_works_repeatedly_after_set_event_loop_none(self):
        """Not a one-shot fluke — must survive the poisoned state on every call."""
        for i in range(3):
            asyncio.set_event_loop(None)

            async def _coro(n=i):
                return n * 2

            assert run_isolated(_coro()) == i * 2

    def test_run_isolated_propagates_exceptions(self):
        """The isolated runner must not swallow errors raised inside the coroutine."""
        asyncio.set_event_loop(None)

        async def _boom():
            raise ValueError("expected failure")

        try:
            run_isolated(_boom())
        except ValueError as exc:
            assert str(exc) == "expected failure"
        else:
            raise AssertionError("expected ValueError to propagate")


class TestAffectedFilesSurviveClearedEventLoop:
    """End-to-end proof, via subprocess, that the actual test files (not
    just the shared helper in isolation) pass regardless of collection
    order relative to whatever cleared the main thread's event loop.
    """

    def _run_pytest(self, *relative_paths: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "pytest", *relative_paths, "-q"],
            cwd=str(_BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=180,
        )

    def test_openclaw_safety_and_phone_safety_together(self):
        result = self._run_pytest(
            "tests/test_openclaw_safety.py",
            "tests/test_phone_safety.py",
        )
        assert "There is no current event loop" not in result.stdout, result.stdout
        assert "never awaited" not in result.stdout, result.stdout
        assert result.returncode == 0, (
            f"Expected a clean pass, got returncode={result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_known_poisoner_then_affected_files(self):
        """test_phone_safety.py's own TestEscalationEmail calls
        voice.escalation.handle_escalation() directly on the main thread,
        which internally calls asyncio.run() — exactly the kind of call
        that used to poison later tests. Run it explicitly ahead of the
        two affected files to reproduce the original ordering hazard.
        """
        result = self._run_pytest(
            "tests/test_phone_safety.py::TestEscalationEmail",
            "tests/test_openclaw_safety.py",
            "tests/test_phone_safety.py::TestActiveCallBlocking",
        )
        assert "There is no current event loop" not in result.stdout, result.stdout
        assert result.returncode == 0, (
            f"Expected a clean pass, got returncode={result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
