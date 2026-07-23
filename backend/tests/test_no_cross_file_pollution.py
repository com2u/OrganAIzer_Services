"""
Regression test: one calendar test file must not be able to break another,
unrelated test file's collection or mocking when both run in the same
pytest process.

Two real bugs were found and fixed in this batch:

1. test_calendar_event_creation.py / test_calendar_intent.py /
   test_qa_audit_bugs.py used to stub sys.modules["httpx"] (and others) at
   MODULE level with no cleanup. Because a MagicMock stand-in for "httpx"
   was still present in sys.modules when test_email_foundation.py was later
   collected, `from fastapi.testclient import TestClient` (which imports
   starlette.testclient, which does `import httpx` internally and
   subclasses one of its types) raised:
       TypeError: metaclass conflict: the metaclass of a derived class
       must be a (non-strict) subclass of the metaclasses of all its bases
   — a collection ERROR that aborted the whole run, not just one file.

2. TestMicrosoftRouteExists._get_routes() in test_calendar_event_creation.py
   used to `del sys.modules["api.integrations"]` and reimport it under
   stubbed OAuth deps, permanently replacing the module object. Any other
   test file that had already captured a reference to the ORIGINAL
   api.integrations (e.g. test_email_foundation.py's `router` object, and
   its `patch("api.integrations.get_token_storage")` calls, which patch
   whatever object sys.modules currently holds) kept running against the
   real router while patches applied to the *different* re-imported module
   had no effect — mocked calls silently fell through to the real
   (failing) implementation.

Both are fixed by scoping stubs (tests/conftest.py::stub_missing_modules)
and by reusing an already-imported real module instead of deleting and
reimporting it. This test proves it by actually running the previously-
conflicting files together in a subprocess and asserting a clean pass —
the same way a real `pytest tests/` invocation would collect them.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent


def _run_pytest(*relative_paths: str, extra_args: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *relative_paths, *extra_args, "-q"],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )


class TestCalendarFilesDoNotPolluteOtherFiles:
    def test_calendar_event_creation_then_email_foundation_collect_cleanly(self):
        """Bug 1 reproduction: httpx stub leaking from a calendar file into
        test_email_foundation.py's collection.
        """
        result = _run_pytest(
            "tests/test_calendar_event_creation.py",
            "tests/test_email_foundation.py",
        )
        assert "ERROR collecting" not in result.stdout, result.stdout
        assert "metaclass conflict" not in result.stdout, result.stdout
        assert result.returncode == 0, (
            f"Expected a clean pass, got returncode={result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_calendar_intent_then_email_foundation_collect_cleanly(self):
        result = _run_pytest(
            "tests/test_calendar_intent.py",
            "tests/test_email_foundation.py",
        )
        assert "ERROR collecting" not in result.stdout, result.stdout
        assert result.returncode == 0, result.stdout

    def test_qa_audit_bugs_then_email_foundation_collect_cleanly(self):
        result = _run_pytest(
            "tests/test_qa_audit_bugs.py",
            "tests/test_email_foundation.py",
        )
        assert "ERROR collecting" not in result.stdout, result.stdout
        assert result.returncode == 0, result.stdout

    def test_microsoft_route_exists_does_not_break_email_foundation_mocking(self):
        """Bug 2 reproduction: TestMicrosoftRouteExists reimporting
        api.integrations under stubbed deps used to break
        test_email_foundation.py's patch("api.integrations.get_token_storage").
        Runs both files' tests (not just collection) since this bug only
        manifested once TestMicrosoftRouteExists's tests actually executed.
        """
        result = _run_pytest(
            "tests/test_calendar_event_creation.py",
            "tests/test_email_foundation.py",
        )
        assert "No tokens found for test_user" not in result.stdout, (
            "test_email_foundation.py's token_storage mock was bypassed — "
            "api.integrations was reimported under a different module "
            "identity by another test file.\n" + result.stdout
        )
        assert result.returncode == 0, result.stdout

    def test_order_independence_reversed(self):
        """Same files, reversed order — pollution bugs are collection-order
        dependent by nature, so this must pass regardless of which file
        pytest happens to discover first.
        """
        result = _run_pytest(
            "tests/test_email_foundation.py",
            "tests/test_calendar_event_creation.py",
            "tests/test_calendar_intent.py",
            "tests/test_qa_audit_bugs.py",
        )
        assert "ERROR collecting" not in result.stdout, result.stdout
        assert result.returncode == 0, result.stdout
