"""
call_log.py — appends a structured record for every completed call
to logs/call_log.jsonl (one JSON object per line).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_DIR  = Path(__file__).parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "call_log.jsonl"


def _ensure_log_dir() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def record(
    caller: str,
    caller_name: str | None,
    direction: str,           # "inbound" | "outbound"
    started_at: datetime,
    ended_at: datetime,
    turn_count: int,
    transcript_summary: str = "",
) -> None:
    """
    Append one call record to logs/call_log.jsonl.
    Never raises — logging errors are swallowed so a log failure
    cannot crash an active call.
    """
    try:
        _ensure_log_dir()
        duration_s = int((ended_at - started_at).total_seconds())
        entry = {
            "ts":               ended_at.astimezone(timezone.utc).isoformat(),
            "direction":        direction,
            "caller":           caller,
            "caller_name":      caller_name or "",
            "started_at":       started_at.astimezone(timezone.utc).isoformat(),
            "duration_seconds": duration_s,
            "turn_count":       turn_count,
            "summary":          transcript_summary,
        }
        with open(_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(
            "Call logged: %s %s  %ds  %d turns",
            direction, caller_name or caller, duration_s, turn_count,
        )
    except Exception as exc:
        logger.error("Failed to write call log: %s", exc)
