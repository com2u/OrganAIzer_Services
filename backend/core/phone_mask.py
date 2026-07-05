"""
phone_mask.py — neutral phone-number masking utility.

A voice-agnostic home for :func:`mask_number` so any layer (voice, scheduler,
future services) can mask a raw number for safe display/storage without importing
the phone/voice stack. This module has no side effects and depends only on the
standard library, so it is safe to import anywhere.

The masking rule is the canonical one relied upon by the phone-safety and
logging-redaction specs — keep it byte-for-byte stable.
"""
from __future__ import annotations

import re


def mask_number(number: str) -> str:
    """
    Mask the middle of a phone number for safe display.

    Keeps a short prefix (country code / trunk prefix) and the last 4 digits;
    replaces everything in between with ******.

      "+491234567890"  -> "+49******7890"
      "06611234567"    -> "066******567"
      "+1 800 555-0100" -> "+1******0100"
    """
    if not number:
        return number
    digits_only = re.sub(r"\D", "", number)
    raw = number.strip()
    if raw.startswith("+"):
        prefix = raw[:4]
    elif raw.startswith("00"):
        prefix = raw[:5]
    elif raw.startswith("0"):
        prefix = raw[:3]
    else:
        prefix = raw[:2]
    suffix = digits_only[-4:] if len(digits_only) >= 4 else digits_only
    return f"{prefix}******{suffix}"
