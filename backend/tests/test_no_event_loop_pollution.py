"""
Regression test: backend test files must not depend on
asyncio.get_event_loop()'s legacy "current loop for this thread" state.

That state gets cleared by two different things in a pytest process:

  1. Production code calling asyncio.run() on the main thread (by design —
     see asyncio.run()'s own implementation and
     tests/test_human_handoff_phone_integration.py::_run_in_thread, which
     documents this for voice/escalation.py's handle_escalation()).
  2. pytest-asyncio tearing down an async test. backend/test_auth.py's
     @pytest.mark.asyncio tests do this on every run, so the hazard is no
     longer occasional — it is guaranteed for everything collected after
     them.

Either one leaves asyncio.set_event_loop(None) in effect, and the old
`asyncio.get_event_loop().run_until_complete(...)` helper pattern then
raises "There is no current event loop in thread 'MainThread'" — a
collection-order-dependent failure, not a real bug.

tests/conftest.py::run_isolated fixes this by using asyncio.run() itself,
which creates its own loop regardless of prior thread-local state. This
file proves that three ways:

  * directly, by forcing the poisoned state and calling run_isolated;
  * end-to-end, by running the affected files after a known poisoner;
  * at the source level, by scanning for reintroductions of the legacy
    pattern (see TestNoLegacyEventLoopRunnersInSource).

The source-level scan exists because the first version of this file only
asserted against test_openclaw_safety.py and test_phone_safety.py — the
two files that had been migrated at the time. Three other files kept the
legacy pattern and were not covered, so the guard passed while 62 tests
were one collection-order change away from failing. An enumerated list of
"affected files" is exactly the thing that goes stale; the scan does not.
"""
from __future__ import annotations

import ast
import asyncio
import subprocess
import sys
from pathlib import Path

from tests.conftest import run_isolated

_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent

# Files whose async call sites were migrated off the legacy pattern and must
# stay clean regardless of what runs before them. Kept in sync with the
# source scan below, which is what actually prevents new offenders.
_AFFECTED_FILES = (
    "tests/test_openclaw_safety.py",
    "tests/test_phone_safety.py",
    "tests/test_executive_agent_safety.py",
    "tests/test_microsoft_integration.py",
    "tests/test_calendar_event_creation.py",
)


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

    def _assert_clean(self, result: subprocess.CompletedProcess) -> None:
        assert "There is no current event loop" not in result.stdout, result.stdout
        assert "never awaited" not in result.stdout, result.stdout
        assert result.returncode == 0, (
            f"Expected a clean pass, got returncode={result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_all_affected_files_together(self):
        self._assert_clean(self._run_pytest(*_AFFECTED_FILES))

    def test_known_poisoner_then_affected_files(self):
        """test_phone_safety.py's own TestEscalationEmail calls
        voice.escalation.handle_escalation() directly on the main thread,
        which internally calls asyncio.run() — exactly the kind of call
        that used to poison later tests. Run it explicitly ahead of the
        affected files to reproduce the original ordering hazard.
        """
        self._assert_clean(self._run_pytest(
            "tests/test_phone_safety.py::TestEscalationEmail",
            "tests/test_openclaw_safety.py",
            "tests/test_phone_safety.py::TestActiveCallBlocking",
        ))

    def test_pytest_asyncio_teardown_then_affected_files(self):
        """backend/test_auth.py is the poisoner that actually bites today.

        It sits at the repo root, so pytest collects it before everything
        under tests/, and its @pytest.mark.asyncio tests leave
        asyncio.set_event_loop(None) in effect once pytest-asyncio tears
        them down. This is the exact ordering the full-suite run uses.
        """
        self._assert_clean(self._run_pytest("test_auth.py", *_AFFECTED_FILES))


# =============================================================================
# Source-level guard — catches reintroductions without running them
# =============================================================================

# Call sites that are genuinely allowed to use the legacy runner, as
# "<path relative to backend/>:<line>": "<why>". Deliberately empty — every
# known site has been migrated to tests/conftest.py::run_isolated. Adding an
# entry here is a decision to accept a collection-order-dependent test, so it
# needs a real justification in the value, not just a path.
_LEGACY_RUNNER_ALLOWLIST: dict[str, str] = {}


def _iter_test_sources():
    """Every backend test module, plus the shared tests/conftest.py."""
    yield from sorted(_BACKEND_DIR.glob("test_*.py"))
    yield from sorted(_TESTS_DIR.glob("test_*.py"))
    yield _TESTS_DIR / "conftest.py"


def _is_get_event_loop_call(node: ast.AST) -> bool:
    """True for `asyncio.get_event_loop()`."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_event_loop"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
    )


def _find_legacy_runners(path: Path) -> list[str]:
    """Return "<relpath>:<line>" for each legacy runner call in *path*.

    Uses the AST rather than a text search so that prose — this module's own
    docstrings, the explanatory comments in the migrated files — never counts
    as an offence. Two spellings are treated as the same hazard:

        asyncio.get_event_loop().run_until_complete(...)      # chained
        loop = asyncio.get_event_loop(); loop.run_until_complete(...)

    The two-step form was not what broke the suite, but it depends on the
    identical thread-local state. A scan that only caught the chained form
    would give exactly the false confidence that let this bug survive.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel = path.relative_to(_BACKEND_DIR).as_posix()

    # Names bound to asyncio.get_event_loop() anywhere in this module.
    loop_names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and _is_get_event_loop_call(node.value)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    offences = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "run_until_complete":
            continue
        receiver = node.func.value
        chained = _is_get_event_loop_call(receiver)
        two_step = isinstance(receiver, ast.Name) and receiver.id in loop_names
        if chained or two_step:
            offences.append(f"{rel}:{node.lineno}")
    return offences


class TestNoLegacyEventLoopRunnersInSource:
    """Fail on reintroduction, rather than waiting for a collection-order
    change to turn it into 62 mystery failures somewhere else.
    """

    def test_no_unallowlisted_legacy_runners(self):
        found = [
            site
            for path in _iter_test_sources()
            for site in _find_legacy_runners(path)
            if site not in _LEGACY_RUNNER_ALLOWLIST
        ]
        assert not found, (
            "asyncio.get_event_loop().run_until_complete(...) depends on the "
            "main thread's legacy current-loop state, which pytest-asyncio "
            "teardown and production asyncio.run() calls both clear.\n"
            "Use tests/conftest.py::run_isolated instead.\n"
            "Offending call sites:\n  " + "\n  ".join(found)
        )

    def test_allowlist_entries_are_real_and_justified(self):
        """An allowlist that outlives its call sites silently stops guarding."""
        live = {
            site
            for path in _iter_test_sources()
            for site in _find_legacy_runners(path)
        }
        stale = sorted(set(_LEGACY_RUNNER_ALLOWLIST) - live)
        assert not stale, f"Allowlist entries no longer match any call site: {stale}"

        unjustified = sorted(
            site for site, why in _LEGACY_RUNNER_ALLOWLIST.items() if not why.strip()
        )
        assert not unjustified, f"Allowlist entries need a reason: {unjustified}"

    def test_scanner_detects_both_spellings(self):
        """The scanner must actually fire — otherwise it passes vacuously.

        Guards against the detector silently breaking (e.g. an AST shape
        change) and reporting a clean suite forever after.
        """
        sample = _TESTS_DIR / "_scanner_probe_tmp.py"
        sample.write_text(
            "import asyncio\n"
            "def chained(c):\n"
            "    return asyncio.get_event_loop().run_until_complete(c)\n"
            "def two_step(c):\n"
            "    loop = asyncio.get_event_loop()\n"
            "    return loop.run_until_complete(c)\n",
            encoding="utf-8",
        )
        try:
            found = _find_legacy_runners(sample)
        finally:
            sample.unlink()
        assert len(found) == 2, f"Scanner missed a spelling, found only: {found}"
