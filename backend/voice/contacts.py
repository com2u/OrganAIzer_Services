"""
contacts.py — loads AI_Phone_Contacts.xlsx and provides name/number lookups.

Column names are discovered at load time from the real file headers.
No sample data, no fallbacks, no hardcoded entries.

Expected column patterns (case-insensitive substring match):
  Name columns : anything containing "first", "last", "name", "vorname", "nachname"
  Phone columns: anything containing "phone", "tel", "number", "nummer", "mobil", "fax"
  Status column: anything containing "status"

Override with env vars if your headers differ:
  CONTACTS_COL_FIRSTNAME, CONTACTS_COL_LASTNAME,
  CONTACTS_COL_PHONE, CONTACTS_COL_STATUS
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

import openpyxl

from voice.config import CONTACTS_FILE

logger = logging.getLogger(__name__)

# ── optional env-var overrides for column names ───────────────────────────────
_ENV_FIRST  = os.environ.get("CONTACTS_COL_FIRSTNAME", "")
_ENV_LAST   = os.environ.get("CONTACTS_COL_LASTNAME", "")
_ENV_PHONE  = os.environ.get("CONTACTS_COL_PHONE", "")
_ENV_STATUS = os.environ.get("CONTACTS_COL_STATUS", "")

# ── internal store ────────────────────────────────────────────────────────────
# Each entry: {"name": str, "number": str, "status": str, "raw": dict}
_contacts: list[dict] = []
_loaded: bool = False


# ── helpers ───────────────────────────────────────────────────────────────────

def _norm_number(raw: str) -> str:
    """Strip all non-digit characters except leading +."""
    if not raw:
        return ""
    raw = str(raw).strip()
    # preserve leading +
    if raw.startswith("+"):
        return "+" + re.sub(r"\D", "", raw[1:])
    return re.sub(r"\D", "", raw)


def _find_col(headers: list[str], patterns: list[str], override: str = "") -> Optional[str]:
    """Return the first header whose lower-case form contains any pattern."""
    if override and override in headers:
        return override
    for h in headers:
        hl = h.lower() if h else ""
        if any(p in hl for p in patterns):
            return h
    return None


def _resolve_columns(headers: list[str]) -> dict[str, Optional[str]]:
    return {
        "first":  _find_col(headers, ["first", "vorname", "given"],   _ENV_FIRST),
        "last":   _find_col(headers, ["last",  "nachname", "family"],  _ENV_LAST),
        "name":   _find_col(headers, ["name"],                          ""),
        "phone":  _find_col(headers, ["phone", "tel", "number", "nummer", "mobil", "handy"], _ENV_PHONE),
        "status": _find_col(headers, ["status"],                        _ENV_STATUS),
    }


# ── public API ────────────────────────────────────────────────────────────────

def load(force: bool = False) -> int:
    """
    Load contacts from the xlsx file.
    Returns the number of contacts loaded, or 0 if the file is missing.
    Safe to call multiple times — reloads only when force=True.
    """
    global _contacts, _loaded
    if _loaded and not force:
        return len(_contacts)

    _contacts = []
    _loaded = True

    # Resolve file path relative to this file's parent (backend/)
    base = Path(__file__).parent.parent
    path = base / CONTACTS_FILE
    if not path.exists():
        logger.warning("Contacts file not found: %s", path)
        return 0

    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    except Exception as exc:
        logger.error("Failed to open contacts file %s: %s", path, exc)
        return 0

    if not rows:
        logger.warning("Contacts file is empty: %s", path)
        return 0

    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    cols = _resolve_columns(headers)

    if not cols["phone"]:
        logger.error(
            "Could not detect a phone column in %s. Headers found: %s",
            path, headers,
        )
        return 0

    for row in rows[1:]:
        record = dict(zip(headers, row))
        raw_phone = record.get(cols["phone"], "")
        if not raw_phone:
            continue  # skip rows with no phone number

        # Build display name
        parts = []
        if cols["first"] and record.get(cols["first"]):
            parts.append(str(record[cols["first"]]).strip())
        if cols["last"] and record.get(cols["last"]):
            parts.append(str(record[cols["last"]]).strip())
        if not parts and cols["name"] and record.get(cols["name"]):
            parts.append(str(record[cols["name"]]).strip())
        display_name = " ".join(parts).strip()

        status = ""
        if cols["status"] and record.get(cols["status"]):
            status = str(record[cols["status"]]).strip()

        _contacts.append({
            "name":   display_name,
            "number": _norm_number(str(raw_phone)),
            "status": status,
            "raw":    record,
        })

    logger.info("Loaded %d contacts from %s", len(_contacts), path)
    return len(_contacts)


def lookup_by_number(number: str) -> Optional[dict]:
    """
    Return the first contact whose normalised number matches,
    or None if not found.
    """
    load()
    needle = _norm_number(number)
    if not needle:
        return None
    for c in _contacts:
        # match if stored number ends with the last 7+ digits of the caller
        if c["number"] and (
            c["number"] == needle
            or c["number"].endswith(needle[-7:])
            or needle.endswith(c["number"][-7:])
        ):
            return c
    return None


def lookup_by_name(name: str) -> list[dict]:
    """
    Return all contacts whose display name contains `name` (case-insensitive).
    """
    load()
    needle = name.strip().lower()
    if not needle:
        return []
    return [c for c in _contacts if needle in c["name"].lower()]


def all_contacts() -> list[dict]:
    """Return a copy of the full contact list (no raw field)."""
    load()
    return [{"name": c["name"], "number": c["number"], "status": c["status"]}
            for c in _contacts]


def count() -> int:
    load()
    return len(_contacts)
