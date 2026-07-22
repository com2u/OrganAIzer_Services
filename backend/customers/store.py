"""
store.py — read-only JSONL access to the simulated customer master data.

Mirrors scheduler/store_jsonl.py's read pattern (no module-level cache — the
file is small and read-only, so reading fresh avoids any stale-cache risk
across calls/tests). There is intentionally NO write/append function here:
Phase 1 customer data is human/seed-maintained and is never modified during
a call. Any future writer belongs to a separate module so this one stays
trivially auditable as read-only.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

from .config import default_store_path

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


class MalformedCustomerLine(ValueError):
    """Raised when the JSONL store contains a line that is not valid JSON."""


def _store_path(path: Optional[PathLike] = None) -> Path:
    return Path(path) if path is not None else default_store_path()


def load(path: Optional[PathLike] = None) -> list:
    """
    Read all customer records from the JSONL store.

    Returns an empty list if the store does not exist yet. Blank/whitespace-
    only lines are skipped. A line that is not valid JSON raises
    :class:`MalformedCustomerLine` with the file and line number.
    """
    target = _store_path(path)
    if not target.exists():
        logger.warning("Customers file not found: %s", target)
        return []

    records: list = []
    with open(target, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise MalformedCustomerLine(
                    f"Malformed JSON in {target} at line {lineno}: {exc.msg}"
                ) from exc
    return records


def all_customers(path: Optional[PathLike] = None) -> list:
    """Return the full customer list. Alias of :func:`load` for readability at call sites."""
    return load(path)


def count(path: Optional[PathLike] = None) -> int:
    return len(load(path))
