"""
Shared test helpers for backend/tests/.

`services.executive_agent_service` hard-imports `httpx` and `pytz` at module
level. A few test files need to import it without requiring those packages
to be installed in every environment that might collect these tests.
Previously this was done with module-level `sys.modules.setdefault(name,
MagicMock())` calls left in place for the rest of the pytest process — which
silently breaks any later-collected file that needs the *real* module (see
test_no_cross_file_pollution.py). `stub_missing_modules` tries a real import
first (so a genuinely-installed package is never shadowed by a fake — just
not yet-imported is not the same as absent), and only stubs + later removes
the stub for names that are truly unavailable, so it can never leak a fake
module into another test file regardless of collection order.

`run_isolated` runs a coroutine to completion without depending on
`asyncio.get_event_loop()`'s legacy "current loop for this thread" state —
see its own docstring for why that matters here.
"""
from __future__ import annotations

import asyncio
import contextlib
import importlib
import sys
from unittest.mock import MagicMock


def run_isolated(coro):
    """Run *coro* to completion on a brand-new event loop.

    Several tests (and production code paths they exercise, e.g.
    voice/escalation.py's handle_escalation calling asyncio.run() for its
    LLM summary) call asyncio.run() internally, which — by design — clears
    the calling thread's "current event loop" when it finishes. A helper
    that instead does `asyncio.get_event_loop().run_until_complete(...)`
    depends on that thread-local state already being set, so it breaks
    with "There is no current event loop in thread 'MainThread'" whenever
    it runs after something else in the same pytest process has cleared it
    — this is collection-order-dependent cross-test pollution, not a real
    bug (see test_no_cross_file_pollution.py for the sys.modules analogue).

    asyncio.run() already does exactly the sequence this needs — create a
    new loop, set it for the current thread, run the coroutine, cancel
    leftover tasks, shut down async generators and the default executor,
    then clear the thread's event loop and close it — so it is used
    directly rather than reimplementing that sequence by hand. No loop
    state is kept between calls; nothing here is module-level/global.
    """
    return asyncio.run(coro)


@contextlib.contextmanager
def stub_missing_modules(*names: str):
    """Ensure each name in *names* is importable during the wrapped block.

    Real packages already present (or successfully importable) are left
    exactly as-is — never shadowed. Only names that genuinely raise
    ImportError get a MagicMock stand-in, and only those are removed from
    sys.modules again on exit.
    """
    inserted = []
    for name in names:
        if name in sys.modules:
            continue
        try:
            importlib.import_module(name)
        except ImportError:
            sys.modules[name] = MagicMock()
            inserted.append(name)
    try:
        yield
    finally:
        for name in inserted:
            del sys.modules[name]
