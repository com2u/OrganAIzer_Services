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
"""
from __future__ import annotations

import contextlib
import importlib
import sys
from unittest.mock import MagicMock


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
