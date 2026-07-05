"""
call_trigger.py - natural-language call-initiation layer.

Detects call intent in a user message, resolves the target (number or
contact name), asks for confirmation, and fires originate_call() on approval.

State machine per session_id (in-memory only, never persisted):

  No pending + call intent detected
      -> resolve contact
          0 matches -> action: "error"
          1 match   -> save _pending -> action: "confirm_prompt"
          2+ matches -> action: "clarification_needed"  (no auto-pick)
  Pending + affirmative -> originate_call() -> action: "calling"
  Pending + negative    -> clear pending    -> action: "cancelled"
  Pending + unrecognised -> re-ask          -> action: "confirm_prompt"
  No pending + no intent -> action: "none"

Phone numbers are masked in every outward-facing value.
Real numbers are held only in _pending (process memory, never logged).
"""
from __future__ import annotations

import logging
import re
import threading

# Number masking lives in the neutral core utility so non-voice layers (e.g. the
# scheduler) can mask without importing the voice stack. Re-exported here so
# existing `from voice.call_trigger import mask_number` call sites keep working.
from core.phone_mask import mask_number

logger = logging.getLogger(__name__)

# -- phone number masking -----------------------------------------------------
# mask_number is provided by core.phone_mask (imported above).


_GERMAN_RE = re.compile(r"^(\+49|0049|(?!00)0)\d")


def is_german_number(number: str) -> bool:
    """
    Return True only for German phone numbers.

    Allowed: +49..., 0049..., or a single leading 0 (national/local).
    Blocked: +1, +44, +33, 0033, 0044, and all other international prefixes.
    """
    clean = re.sub(r"[\s\(\)\-]", "", number)
    return bool(_GERMAN_RE.match(clean))


# -- intent detection ---------------------------------------------------------

_INTENT_RE = re.compile(
    r"\b(call|dial|phone|ruf|rufe|anruf|anrufen|ring|richte)\b",
    re.IGNORECASE,
)


def detect_call_intent(text: str) -> bool:
    """Return True if *text* contains a call-trigger keyword."""
    return bool(_INTENT_RE.search(text))


# -- target extraction --------------------------------------------------------

_PHONE_RE = re.compile(r"(\+?\d[\d\s\(\)\-]{5,}\d)")

_STRIP_WORDS = re.compile(
    r"\b(call|dial|phone|ruf|rufe|anruf|anrufen|ring|an|bitte|mal|kurz)\b",
    re.IGNORECASE,
)

_PURPOSE_SEPARATOR_RE = re.compile(
    r"\b(?:and\s+)?tell(?:\s+(?:him|her|them))?(?:\s+that)?\s+|"
    r"\b(?:und\s+)?(?:sag|sage)(?:\s+(?:ihm|ihr|denen))?(?:\s+dass)?\s+",
    re.IGNORECASE,
)
_RICHTE_AUS_RE = re.compile(
    r"^\s*(?:bitte\s+)?richte\s+(?P<target>.+?)\s+aus"
    r"(?:,?\s*(?:dass|das|that))?\s+(?P<purpose>.+)$",
    re.IGNORECASE,
)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")
_PURPOSE_QUOTES = "\"'`"


def _sanitize_purpose(value: str | None) -> str | None:
    """Normalize a call purpose/message for confirmation and opening_line only."""
    if not value:
        return None
    purpose = _CONTROL_CHARS_RE.sub(" ", value)
    purpose = re.sub(r"\s+", " ", purpose).strip()
    purpose = purpose.strip(_PURPOSE_QUOTES).strip()
    if not purpose:
        return None
    return purpose[:300].rstrip()


def extract_call_target(text: str) -> dict:
    """
    Return {"number": str|None, "name": str|None}.

    If a phone number pattern is found it is returned as *number*.
    Otherwise the remaining text after stripping trigger words is used as *name*.
    """
    m = _PHONE_RE.search(text)
    if m:
        raw = m.group(1)
        number = re.sub(r"[\s\(\)\-]", "", raw)
        return {"number": number, "name": None}

    name = _STRIP_WORDS.sub("", text).strip().strip(".,!?")
    return {"number": None, "name": name if name else None}


def extract_call_request(text: str) -> dict:
    """
    Return {"number": str|None, "name": str|None, "purpose": str|None}.

    Purpose is intentionally parsed separately from the call target so it can
    be used only in the confirmation copy and outbound opening_line.
    """
    target_text = text
    purpose = None

    richte = _RICHTE_AUS_RE.match(text)
    if richte:
        target_text = richte.group("target")
        purpose = _sanitize_purpose(richte.group("purpose"))
    else:
        separator = _PURPOSE_SEPARATOR_RE.search(text)
        if separator and separator.start() > 0:
            target_text = text[:separator.start()]
            purpose = _sanitize_purpose(text[separator.end():])

    target = extract_call_target(target_text)
    target["purpose"] = purpose
    return target


# -- contact resolution -------------------------------------------------------

def resolve_contact(target: dict) -> dict:
    """
    Resolve a call target to a contact record.

    Returns one of:
      {"status": "ok",        "number": str, "display_name": str|None}
      {"status": "error",     "message": str}
      {"status": "ambiguous", "options": [{"display_name": str, "masked_number": str}, ...]}
    """
    if target.get("number"):
        if not is_german_number(target["number"]):
            return {"status": "error", "message": "Ich kann aktuell nur deutsche Telefonnummern anrufen."}
        return {"status": "ok", "number": target["number"], "display_name": None}

    name = (target.get("name") or "").strip()
    if not name:
        return {"status": "error", "message": "Kein Name oder Nummer angegeben."}

    from voice import contacts as _contacts

    matches = _contacts.lookup_by_name(name)

    if len(matches) == 0:
        return {"status": "error", "message": f"Kein Kontakt für '{name}' gefunden."}

    if len(matches) == 1:
        c = matches[0]
        if not is_german_number(c["number"]):
            return {"status": "error", "message": "Ich kann aktuell nur deutsche Telefonnummern anrufen."}
        return {"status": "ok", "number": c["number"], "display_name": c["name"] or None}

    # Multiple matches - filter to German numbers only before offering options.
    german = [c for c in matches if is_german_number(c["number"])]
    if len(german) == 0:
        return {"status": "error", "message": "Ich kann aktuell nur deutsche Telefonnummern anrufen."}
    if len(german) == 1:
        c = german[0]
        return {"status": "ok", "number": c["number"], "display_name": c["name"] or None}
    options = [
        {"display_name": c["name"], "masked_number": mask_number(c["number"])}
        for c in german
    ]
    return {"status": "ambiguous", "options": options}


# -- session state ------------------------------------------------------------

_pending: dict[str, dict] = {}  # session_id -> {number, display_name, purpose}
_pending_lock = threading.Lock()

_AFFIRMATIVE = re.compile(
    r"^(yes|ja|ok|okay|yep|yeah|sure|yup|"
    r"klar|genau|stimmt|gerne|bitte|los|weiter|mach es|ruf an|anrufen)$",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"^(no|nein|cancel|abbruch|abbrechen|stop|nicht|vergiss)$",
    re.IGNORECASE,
)


def _format_purpose_confirm_message(label: str, masked: str, purpose: str, retry: bool = False) -> str:
    """Build confirmation copy for calls that include a user-provided purpose."""
    if label == masked:
        target_label = masked
    else:
        target_label = f"{label} ({masked})"
    suffix = " Bitte mit ja oder nein antworten." if retry else " [ja/nein]"
    return f"Soll ich {target_label} anrufen und mitteilen: \"{purpose}\"?{suffix}"


def _build_confirm_response(resolved: dict, session_id: str, purpose: str | None = None) -> dict:
    """Save resolved contact to _pending and return a confirm_prompt response."""
    with _pending_lock:
        _pending[session_id] = {
            "number": resolved["number"],
            "display_name": resolved.get("display_name"),
            "purpose": purpose,
        }
    masked = mask_number(resolved["number"])
    label = resolved.get("display_name") or masked
    response = {
        "action": "confirm_prompt",
        "message": f"Soll ich {label} ({masked}) anrufen? [ja/nein]",
        "display_name": resolved.get("display_name"),
        "masked_number": masked,
    }
    if purpose:
        response["message"] = _format_purpose_confirm_message(label, masked, purpose)
        response["purpose"] = purpose
    return response


# -- main entry point ---------------------------------------------------------

def handle_message(text: str, session_id: str) -> dict:
    """
    Process one user message for call-trigger logic.

    Returns a dict with at minimum {"action": str, "message": str}.
    Additional keys depend on action:
      confirm_prompt       - display_name, masked_number
      calling              - display_name, masked_number, uuid
      clarification_needed - options: [{display_name, masked_number}]
      cancelled / error    - message
      none                 - message (empty string)
    """
    normalized = text.strip()

    with _pending_lock:
        pending = _pending.get(session_id)

    # -- branch: pending confirmation -----------------------------------------
    if pending:
        # originate_call() is only reachable below, after the user explicitly
        # confirmed via a prior confirm_prompt and a separate affirmative reply.
        if _AFFIRMATIVE.match(normalized):
            with _pending_lock:
                ctx = _pending.pop(session_id, None)
            if ctx is None:
                return {"action": "error", "message": "Kein ausstehender Anruf gefunden."}

            from voice.outbound import originate_call
            from voice.llm_bridge import OUTBOUND_SYSTEM_PROMPT

            from voice import config as _vc

            number = ctx["number"]
            display_name = ctx.get("display_name")
            purpose = ctx.get("purpose")
            masked = mask_number(number)
            label = display_name or masked
            opening_line = _vc.AI_OUTBOUND_GREETING
            if purpose:
                opening_line = _vc.AI_OUTBOUND_GREETING_PURPOSE.format(purpose=purpose)

            outbound_note = (
                "\n\n[Context: You placed this outbound call. Your opening line has "
                "already been delivered and is your first message in the conversation "
                "history. Do not re-introduce yourself. Continue naturally from there.]"
            )
            success, result = originate_call(
                number=number,
                opening_line=opening_line,
                system_prompt=OUTBOUND_SYSTEM_PROMPT + outbound_note,
                lang="de",
            )
            if not success:
                logger.warning("originate_call failed for masked=%s: %s", masked, result)
                return {
                    "action": "error",
                    "message": f"Anruf konnte nicht eingeleitet werden: {result}",
                }

            logger.info("Outbound call initiated: display_name=%s masked=%s uuid=%s",
                        display_name, masked, result)
            return {
                "action": "calling",
                "message": f"Ruf zu {label} wird eingeleitet …",
                "display_name": display_name,
                "masked_number": masked,
                "uuid": result,
            }

        if _NEGATIVE.match(normalized):
            with _pending_lock:
                _pending.pop(session_id, None)
            return {"action": "cancelled", "message": "Abgebrochen."}

        # Unrecognised input - check if user is selecting a contact by name/number
        target = extract_call_request(normalized)
        if target["number"] or target["name"]:
            resolved = resolve_contact(target)
            if resolved["status"] == "ok":
                return _build_confirm_response(resolved, session_id, target.get("purpose"))
            if resolved["status"] == "ambiguous":
                return {
                    "action": "clarification_needed",
                    "message": "Mehrere Kontakte gefunden. Wen genau?",
                    "options": resolved["options"],
                }
            # status == "error": fall through to re-prompt with original pending

        # Re-prompt using the already-read pending context (no second lock needed)
        masked = mask_number(pending.get("number", ""))
        label = pending.get("display_name") or masked
        purpose = pending.get("purpose")
        if purpose:
            return {
                "action": "confirm_prompt",
                "message": _format_purpose_confirm_message(label, masked, purpose, retry=True),
                "display_name": pending.get("display_name"),
                "masked_number": masked,
                "purpose": purpose,
            }
        return {
            "action": "confirm_prompt",
            "message": f"Soll ich {label} ({masked}) anrufen? Bitte mit ja oder nein antworten.",
            "display_name": pending.get("display_name"),
            "masked_number": masked,
        }

    # -- branch: no pending ---------------------------------------------------
    if not detect_call_intent(normalized):
        return {"action": "none", "message": ""}

    target = extract_call_request(normalized)
    resolved = resolve_contact(target)

    if resolved["status"] == "error":
        return {"action": "error", "message": resolved["message"]}

    if resolved["status"] == "ambiguous":
        return {
            "action": "clarification_needed",
            "message": "Mehrere Kontakte gefunden. Wen genau?",
            "options": resolved["options"],
        }

    return _build_confirm_response(resolved, session_id, target.get("purpose"))
