"""
store_jsonl.py — JSONL persistence for simulated appointments.

An append-only JSONL file (one JSON object per line). No database. Default
location resolves via :func:`config.default_store_path`
(``backend/data/scheduler/appointments.jsonl``, which is gitignored). The path
can be overridden with the ``SCHEDULER_STORE_PATH`` env var or the ``path``
argument (tests point this at a temp file).

This module performs pure local file I/O only — no network, no external API.

Storage is deliberately behind this small interface (append/read) so it can be
swapped for SQLite or a real calendar backend later without changing the service
layer. See docs/scheduler-architecture.md ("Migration path").
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

from .config import default_store_path
from .models import validate_record

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


class MalformedAppointmentLine(ValueError):
    """Raised when the JSONL store contains a line that is not valid JSON."""


def store_path(path: Optional[PathLike] = None) -> Path:
    """Resolve the JSONL store path (explicit *path* wins over the config default)."""
    if path is not None:
        return Path(path)
    return default_store_path()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_appointment(record: dict, path: Optional[PathLike] = None) -> Path:
    """
    Validate and append one appointment *record* as a single JSONL line.

    Returns the store path written to. Raises ``ValueError`` if the record fails
    validation (e.g. wrong status, unknown type, unmasked phone number).
    """
    validate_record(record)
    target = store_path(path)
    _ensure_parent(target)
    line = json.dumps(record, ensure_ascii=False)
    with open(target, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    logger.debug("Appended simulated appointment %s to %s", record.get("id"), target.name)
    return target


def read_appointments(path: Optional[PathLike] = None) -> list[dict]:
    """
    Read all appointment records from the JSONL store.

    Returns an empty list if the store does not exist yet. Blank/whitespace-only
    lines are skipped. A line that is not valid JSON raises
    :class:`MalformedAppointmentLine` with the file and line number — we fail
    loudly rather than silently dropping data.
    """
    target = store_path(path)
    if not target.exists():
        return []

    records: list[dict] = []
    with open(target, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise MalformedAppointmentLine(
                    f"Malformed JSON in {target} at line {lineno}: {exc.msg}"
                ) from exc
    return records
