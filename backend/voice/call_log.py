"""
call_log.py — appends a structured record for every completed call
to logs/call_log.jsonl (one JSON object per line).
Full conversation transcripts are archived under logs/transcripts/.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_LOG_DIR        = Path(__file__).parent.parent / "logs"
_LOG_FILE       = _LOG_DIR / "call_log.jsonl"
_TRANSCRIPT_DIR = _LOG_DIR / "transcripts"


def _ensure_log_dir() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)


def _write_transcript(
    caller: str,
    started_at: datetime,
    transcript: list[dict],
) -> None:
    """
    Write the full conversation transcript to logs/transcripts/<date>_<caller>.jsonl.
    One JSON object per line, each object being one conversation turn.
    """
    date_str    = started_at.strftime("%Y%m%d_%H%M%S")
    safe_caller = re.sub(r"[^\w+]", "_", caller)[:20]
    fname       = _TRANSCRIPT_DIR / f"{date_str}_{safe_caller}.jsonl"
    with open(fname, "w", encoding="utf-8") as fh:
        for turn in transcript:
            fh.write(json.dumps(turn, ensure_ascii=False) + "\n")
    logger.debug("Transcript saved: %s (%d turns)", fname.name, len(transcript))


def record(
    caller: str,
    caller_name: str | None,
    direction: str,                         # "inbound" | "outbound"
    started_at: datetime,
    ended_at: datetime,
    turn_count: int,
    transcript_summary: str = "",
    transcript: Optional[list[dict]] = None,
) -> None:
    """
    Append one call record to logs/call_log.jsonl.
    If *transcript* is provided, also archive the full conversation to
    logs/transcripts/<date>_<caller>.jsonl.

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

        if transcript:
            _write_transcript(caller, started_at, transcript)

    except Exception as exc:
        logger.error("Failed to write call log: %s", exc)
