"""
caller_resolution_dialogue.py — deterministic per-call caller/customer
identification bridge for the phone AI.

This is the narrow bridge between the live voice loop and the ``customers``
domain package (backend/customers), the same role voice/scheduler_dialogue.py
plays for backend/scheduler. Given the per-call ``state`` dict and the
caller's latest (already-transcribed) utterance, it deterministically:

  * redacts any phone-like number out of the utterance BEFORE it is allowed
    anywhere near the LLM (:func:`redact_phone_like` / :func:`process_utterance`) —
    this is the module's primary privacy boundary, not just an add-on,
  * classifies the utterance (general question, urgent outage, technician
    calling on behalf of a customer, new-installation, refusal),
  * extracts a self-reported affected number and/or stated name using plain
    regexes (no LLM),
  * calls :func:`customers.resolve_caller` to (re)compute a match, and
  * decides which identity-stage instruction (if any) the LLM should receive
    next turn via :func:`build_prompt_extra`.

Safety design (mirrors the rest of the voice stack):
  - The LLM never decides whether a customer match is good enough — this
    module and ``customers.resolve_caller`` do. The LLM only phrases the
    question the deterministic layer decided to ask.
  - Raw phone numbers are never placed in ``build_prompt_extra``'s output —
    only customer/location display labels the resolver already trusts.
  - Raw phone numbers spoken by the caller are never placed in the text
    returned by :func:`process_utterance`/:func:`redact_phone_like` either —
    they are replaced with a neutral placeholder and preserved ONLY in
    ``state["last_redacted_number"]`` / ``state["affected_number_stated"]``.
    Callers of this module (voice/esl_call_handler.py) MUST use the
    sanitized text for history/LLM/transcript, never the original.
  - Nothing here writes to customers.jsonl. Phase 1 is read-only.
  - Urgent-outage and general-question detection never block the identity
    flow from continuing in the background. General questions are exempt
    from identification only until a later turn introduces something
    customer-specific (a fault, a callback/appointment, an account
    reference, or an urgent outage) — see ``identification_exempt`` and
    :func:`_is_customer_specific_trigger`.

The engine holds no global state — everything lives in the ``state`` dict the
caller owns (created fresh per call via :func:`new_state`), so there is no
cross-call leakage.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Optional

from customers import ResolutionResult, resolve_caller
from voice.llm_bridge import build_identity_stage_instruction

# Give up asking and continue on a best-effort basis after this many refusals.
_MAX_ASK_ATTEMPTS = 2


def new_state() -> dict:
    """Create a fresh per-call caller-resolution state."""
    return {
        "identity_stage": "not_started",
        "caller_number_raw": None,
        "caller_number_present": False,
        "resolution": None,  # last ResolutionResult, as a dict
        "caller_role": "unknown",  # "unknown" | "customer" | "technician_on_behalf"
        "identification_exempt": False,
        "urgent": False,
        "ask_attempts": 0,
        "stated_name": None,
        "affected_number_stated": None,
        # Deterministic-only record of the last number redacted out of an
        # utterance, regardless of identity_stage — see redact_phone_like().
        # Never copy this into any LLM-bound text.
        "last_redacted_number": None,
    }


def init_from_call(state: dict, caller_number: Optional[str]) -> None:
    """
    Seed the state from the call's caller-ID number (may be empty/None if
    withheld). Attempts an immediate resolution — a known landline or a
    verified single-match mobile resolves the call before the caller says
    anything.
    """
    state["caller_number_raw"] = caller_number or None
    state["caller_number_present"] = bool(caller_number)
    result = resolve_caller(caller_number=caller_number)
    _apply_resolution(state, result)


def _apply_resolution(state: dict, result: ResolutionResult) -> None:
    state["resolution"] = asdict(result)
    if result.confidence == "high":
        customer = result.customer
        if customer is not None and result.location is None and len(customer.get("locations") or []) > 1:
            state["identity_stage"] = "awaiting_location"
        else:
            state["identity_stage"] = "resolved"
    elif result.confidence == "ambiguous":
        state["identity_stage"] = "awaiting_disambiguation"
    elif result.confidence == "low":
        state["identity_stage"] = "awaiting_affected_number"
    else:  # "none"
        if state["identity_stage"] not in ("new_installation", "unresolved_continue"):
            state["identity_stage"] = "awaiting_affected_number"


def process_utterance(state: dict, utterance: str) -> str:
    """
    The single entry point voice/esl_call_handler.py should call once per
    turn. Does everything :func:`observe_turn` does AND returns a version of
    the utterance that is safe to append to LLM conversation history / pass
    to llm_bridge.get_response() / archive in a transcript / hand to
    escalation — any phone-like number found is replaced with a neutral
    placeholder in the RETURNED text and preserved only in ``state``.

    Never calls the LLM; never touches customers.jsonl.
    """
    if not utterance:
        return utterance

    redacted, raw_number = redact_phone_like(utterance)
    if raw_number is not None:
        state["last_redacted_number"] = raw_number

    _apply_turn_state(state, utterance, raw_number)
    return redacted


def observe_turn(state: dict, utterance: str) -> None:
    """
    Back-compat convenience wrapper around :func:`process_utterance` for
    callers that only need the state-mutation side effect (e.g. tests that
    don't drive the LLM). Live call code should call
    :func:`process_utterance` directly and use its returned sanitized text —
    calling this instead would silently discard the sanitization.
    """
    process_utterance(state, utterance)


def _apply_turn_state(state: dict, utterance: str, raw_number: Optional[str]) -> None:
    """
    Deterministically update caller-identity state from one transcribed
    caller utterance, given the phone-like number (if any) already found by
    :func:`redact_phone_like` for this same utterance — this function never
    re-scans the raw text for a number itself, so the redacted text and the
    state always agree on exactly the same match.
    """
    text = utterance.strip().lower()

    # "Nothing asked yet" also covers the post-init_from_call default
    # ("awaiting_affected_number" with no attempts/answers yet) — the silent
    # caller-ID resolution at call start already sets that stage before the
    # caller has said a word, so "not_started" alone would never match here.
    _nothing_asked_yet = (
        state["identity_stage"] == "not_started"
        or (
            state["identity_stage"] == "awaiting_affected_number"
            and state["ask_attempts"] == 0
            and not state["affected_number_stated"]
            and not state["stated_name"]
        )
    )
    if (
        _nothing_asked_yet
        and _is_identification_exempt(text)
        and not _is_fault_report(text)
        and not _is_customer_specific_trigger(text)
    ):
        state["identification_exempt"] = True

    # Re-arm identification if a call that started as a general enquiry
    # turns out to be customer-specific after all (fault, appointment/
    # callback, account reference, or urgent outage) — the exemption must
    # never be permanent for the rest of the call.
    if state.get("identification_exempt") and (
        _is_fault_report(text) or _is_customer_specific_trigger(text) or _is_urgent_outage(text)
    ):
        state["identification_exempt"] = False

    if _is_urgent_outage(text):
        state["urgent"] = True

    if _is_technician_call(text):
        state["caller_role"] = "technician_on_behalf"

    if state["identity_stage"] == "resolved":
        return

    if _is_new_installation(text):
        state["identity_stage"] = "new_installation"
        return

    if state["identity_stage"] not in ("awaiting_affected_number", "awaiting_disambiguation", "awaiting_location"):
        return

    if state["identity_stage"] == "awaiting_disambiguation":
        picked = _pick_candidate(state, text)
        if picked is not None:
            state["resolution"] = asdict(ResolutionResult(
                confidence="high",
                method="disambiguation_selected",
                customer=picked.get("customer"),
                location=picked.get("location"),
            ))
            state["identity_stage"] = "resolved"
        return

    if state["identity_stage"] == "awaiting_location":
        customer = (state.get("resolution") or {}).get("customer")
        if customer:
            loc = _match_location(customer, text)
            if loc is not None:
                res = dict(state["resolution"])
                res["location"] = loc
                res["confidence"] = "high"
                state["resolution"] = res
                state["identity_stage"] = "resolved"
        return

    # awaiting_affected_number
    if _is_refusal(text):
        state["ask_attempts"] += 1
        if state["ask_attempts"] >= _MAX_ASK_ATTEMPTS:
            state["identity_stage"] = "unresolved_continue"
        return

    if raw_number:
        state["affected_number_stated"] = raw_number
    name = _maybe_extract_name(utterance)
    if name:
        state["stated_name"] = name

    if raw_number or name:
        result = resolve_caller(
            caller_number=state["caller_number_raw"],
            affected_number=state["affected_number_stated"],
            stated_name=state["stated_name"],
        )
        _apply_resolution(state, result)


def candidate_labels(state: dict) -> Optional[list]:
    """
    Return display-only labels (customer name + location label) for the
    current disambiguation/location-selection candidates. Never includes a
    phone number — this is the boundary that keeps raw numbers out of the
    LLM-bound prompt.
    """
    res = state.get("resolution") or {}
    stage = state.get("identity_stage")
    if stage == "awaiting_disambiguation":
        labels = []
        for cand in res.get("candidates") or []:
            customer = cand.get("customer") or {}
            location = cand.get("location")
            label = customer.get("name", "unbekannt")
            if location:
                label = f"{label} ({location.get('label')})"
            labels.append(label)
        return labels or None
    if stage == "awaiting_location":
        customer = res.get("customer") or {}
        labels = [loc.get("label") for loc in customer.get("locations", []) if loc.get("label")]
        return labels or None
    return None


def build_prompt_extra(state: dict) -> Optional[str]:
    """
    Return the system_extra fragment to feed the LLM for this call's current
    identity stage, or None when no extra instruction is needed (already
    resolved, not started, or identification-exempt). Delegates the actual
    instruction text to llm_bridge.build_identity_stage_instruction — this
    module only decides WHICH stage/labels apply, never the wording.
    """
    if state.get("identification_exempt"):
        return None
    return build_identity_stage_instruction(
        state.get("identity_stage"),
        candidate_labels(state),
    )


# ── candidate / location matching ─────────────────────────────────────────────

def _pick_candidate(state: dict, text: str) -> Optional[dict]:
    candidates = (state.get("resolution") or {}).get("candidates") or []
    for cand in candidates:
        customer = cand.get("customer") or {}
        location = cand.get("location")
        name = (customer.get("name") or "").lower()
        if name and name in text:
            return cand
        if location:
            label = (location.get("label") or "").lower()
            if label and label in text:
                return cand
    return None


def _match_location(customer: dict, text: str) -> Optional[dict]:
    for loc in customer.get("locations", []):
        label = (loc.get("label") or "").lower()
        if label and label in text:
            return loc
    return None


# ── keyword classification (German-first, mirrors scheduler_dialogue.py) ─────

def _contains(text: str, needles) -> bool:
    return any(n in text for n in needles)


_FAULT_KEYWORDS = (
    "geht nicht", "funktioniert nicht", "kaputt", "defekt", "ausfall",
    "störung", "stoerung", "kein ton", "keine verbindung", "tot", "gestört",
    "gestoert",
)

_GENERAL_QUESTION_KEYWORDS = (
    "was kostet", "wie viel kostet", "welche produkte", "öffnungszeiten",
    "oeffnungszeiten", "preisliste", "allgemeine frage", "haben sie",
    "bieten sie", "informieren",
)

_URGENT_OUTAGE_KEYWORDS = (
    "kompletter ausfall", "totalausfall", "alles tot", "komplett ausgefallen",
    "nichts funktioniert mehr", "gar nichts geht mehr", "alles ist tot",
)

_TECHNICIAN_KEYWORDS = (
    "ich bin techniker", "als techniker", "im auftrag von", "im auftrag des kunden",
    "externer techniker", "ich rufe im auftrag",
)

_NEW_INSTALLATION_KEYWORDS = (
    "neuanschluss", "neue leitung", "noch keine nummer", "neuinstallation",
    "neukunde ohne anschluss", "haben noch keinen anschluss", "wir sind neukunde",
)

_REFUSAL_KEYWORDS = (
    "möchte ich nicht", "moechte ich nicht", "sage ich nicht", "sage ich ihnen nicht",
    "gebe ich nicht", "gebe ich ihnen nicht", "das ist privat", "kann ich nicht sagen",
    "will ich nicht geben", "nein, das nicht", "nicht mitteilen", "nicht rausgeben",
)

# Turns a call that started "identification_exempt" (a general question) back
# into one that needs identification — an appointment/callback/account
# reference is inherently customer-specific, not a generic FAQ. Fault
# reports and urgent outages are handled by _is_fault_report/_is_urgent_outage
# and are also treated as customer-specific triggers (see _apply_turn_state).
_CUSTOMER_SPECIFIC_TRIGGER_KEYWORDS = (
    "rückruf", "rueckruf", "zurückrufen", "zurueckrufen", "termin",
    "vereinbaren", "meine kundennummer", "mein vertrag", "meine rechnung",
    "mein konto", "meine buchung", "meine bestellung", "mein anschluss",
    "meine leitung", "mein vorgang",
)


def _is_fault_report(text: str) -> bool:
    return _contains(text, _FAULT_KEYWORDS)


def _is_customer_specific_trigger(text: str) -> bool:
    return _contains(text, _CUSTOMER_SPECIFIC_TRIGGER_KEYWORDS)


def _is_identification_exempt(text: str) -> bool:
    return _contains(text, _GENERAL_QUESTION_KEYWORDS)


def _is_urgent_outage(text: str) -> bool:
    return _contains(text, _URGENT_OUTAGE_KEYWORDS)


def _is_technician_call(text: str) -> bool:
    return _contains(text, _TECHNICIAN_KEYWORDS)


def _is_new_installation(text: str) -> bool:
    return _contains(text, _NEW_INSTALLATION_KEYWORDS)


def _is_refusal(text: str) -> bool:
    return _contains(text, _REFUSAL_KEYWORDS)


# ── deterministic extraction & redaction from free text (no LLM) ─────────────
#
# _find_phone_like_match() is the single source of truth for "is this digit
# run a phone number" — both _extract_number_like() (state-only) and
# redact_phone_like() (the privacy boundary) delegate to it, so the text a
# caller sees redacted and the number recorded in state are always the exact
# same match. Never call the raw regex directly from anywhere else.

_NUMBER_LIKE_RE = re.compile(r"(\+?\d[\d\s\-/.]{4,}\d)")

# A caller invoking one of these near a digit run is telling us it's a phone
# number — trigger-phrase matches are preferred over untriggered candidates.
#
# Deliberately does NOT include bare "nummer ist" / "nummer lautet": German
# compounds like "Vorgangsnummer"/"Kundennummer"/"Rechnungsnummer" end in
# "...nummer", so a bare "nummer ist"/"nummer lautet" trigger would match as
# a substring of e.g. "Vorgangsnummer ist" and wrongly override the
# non-phone rejection below. "meine/die/unsere/betroffene nummer" are safe
# because they require a preceding word with a space, which never occurs
# inside a single compound noun.
_PHONE_TRIGGER_PHRASES = (
    "rufnummer", "telefonnummer", "festnetznummer", "anschlussnummer",
    "anschluss", "meine nummer", "die nummer", "unsere nummer",
    "betroffene nummer", "erreichbar unter",
)

# A caller invoking one of these near a digit run is telling us it's NOT a
# phone number — reject that candidate unless a phone trigger is closer.
# Includes both the compound ("vorgangsnummer") and bare ("vorgang 458219",
# said without the word "Nummer" at all — a very natural phrasing) forms.
_NON_PHONE_NUMBER_PHRASES = (
    "vorgangsnummer", "vorgang nummer", "vorgang",
    "ticketnummer", "ticket nummer", "ticket",
    "fallnummer", "fall nummer",
    "kundennummer", "kunden nummer",
    "rechnungsnummer", "rechnung nummer", "rechnung",
    "auftragsnummer", "auftrag nummer", "auftrag",
    "bestellnummer", "bestell nummer", "bestellung",
    "postleitzahl", "plz", "durchwahl",
)

# DD.MM.YYYY / DD/MM/YYYY (or 2-digit year) — rejected outright, never a phone number.
_DATE_SHAPE_RE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}$")

# NNN.NN — a dot-decimal price (e.g. "129.99") — rejected outright.
_DECIMAL_PRICE_RE = re.compile(r"^\d{1,6}\.\d{2}$")

# How much preceding text to inspect for a trigger/non-trigger phrase.
_CONTEXT_WINDOW_CHARS = 30


def _local_context(text: str, match_start: int) -> str:
    return text[max(0, match_start - _CONTEXT_WINDOW_CHARS):match_start].lower()


def _looks_like_date(candidate: str) -> bool:
    return bool(_DATE_SHAPE_RE.match(candidate.strip()))


def _looks_like_decimal_price(candidate: str) -> bool:
    return bool(_DECIMAL_PRICE_RE.match(candidate.strip()))


def _find_phone_like_match(text: str):
    """
    Return the ``re.Match`` for the best phone-like digit run in *text*, or
    ``None``. Rejects date-shaped and dot-decimal-price-shaped candidates
    outright, rejects any candidate whose closest nearby cue is a non-phone
    reference phrase (Vorgangsnummer, Kundennummer, Postleitzahl, Durchwahl,
    ...) unless a phone-trigger phrase (Rufnummer, Telefonnummer, ...) is
    at least as close, and prefers a phone-triggered candidate over an
    untriggered one when both are present in the same utterance.
    """
    fallback = None
    for m in _NUMBER_LIKE_RE.finditer(text):
        candidate = m.group(1).strip()
        digits = re.sub(r"\D", "", candidate.lstrip("+"))
        if len(digits) < 6:
            continue
        if _looks_like_date(candidate) or _looks_like_decimal_price(candidate):
            continue

        context = _local_context(text, m.start())
        has_phone_trigger = _contains(context, _PHONE_TRIGGER_PHRASES)
        has_non_phone_trigger = _contains(context, _NON_PHONE_NUMBER_PHRASES)

        if has_non_phone_trigger and not has_phone_trigger:
            continue  # explicitly described as a non-phone number

        if has_phone_trigger:
            return m  # strongest signal — take it immediately

        if fallback is None:
            fallback = m  # keep as a fallback in case nothing stronger turns up

    return fallback


def _extract_number_like(text: str) -> Optional[str]:
    """Find a digit run that looks like a phone number in free text (state-only)."""
    m = _find_phone_like_match(text)
    return m.group(1).strip() if m else None


def _placeholder_for(text: str, match_start: int) -> str:
    # Deliberately scans the WHOLE utterance (not the tight local-context
    # window used for trigger/reject decisions) — a caller can easily say
    # "Festnetznummer" more than _CONTEXT_WINDOW_CHARS before the digits
    # ("Meine Festnetznummer, die schon seit Tagen nicht geht, ist ...").
    # Wording choice only, never affects whether/what gets redacted.
    if _contains(text.lower(), ("festnetznummer", "festnetz", "anschlussnummer", "anschluss")):
        return "[Festnetznummer übermittelt]"
    return "[Telefonnummer übermittelt]"


def redact_phone_like(text: str) -> tuple:
    """
    Return ``(sanitized_text, raw_number_or_None)``.

    Pure and stateless — safe to call for both inbound and outbound turns.
    If a phone-like number is found, it is replaced in the returned text
    with a neutral placeholder ("[Festnetznummer übermittelt]" or
    "[Telefonnummer übermittelt]") that preserves the sentence's meaning so
    the LLM can continue naturally; the raw value is returned separately so
    the CALLER of this function can store it in deterministic state — never
    in text — and is never included in the returned string.

    Ordinary years, dates, prices, ticket/case numbers, extensions, and
    postal codes are left untouched — see :func:`_find_phone_like_match`.
    """
    if not text:
        return text, None
    m = _find_phone_like_match(text)
    if m is None:
        return text, None
    raw = m.group(1).strip()
    placeholder = _placeholder_for(text, m.start())
    sanitized = text[:m.start()] + placeholder + text[m.end():]
    return sanitized, raw


_NAME_PATTERNS = (
    re.compile(r"mein name ist ([A-Za-zÄÖÜäöüß\-\s]+)", re.IGNORECASE),
    re.compile(r"ich hei(?:ß|ss)e ([A-Za-zÄÖÜäöüß\-\s]+)", re.IGNORECASE),
    re.compile(r"hier (?:ist|spricht) ([A-Za-zÄÖÜäöüß\-\s]+)", re.IGNORECASE),
)


def _maybe_extract_name(utterance: str) -> Optional[str]:
    """Extract a stated name from a small set of explicit German phrasings only."""
    for pattern in _NAME_PATTERNS:
        m = pattern.search(utterance)
        if m:
            name = m.group(1).strip().rstrip(".,!?")
            words = name.split()
            if 1 <= len(words) <= 4:
                return " ".join(words)
    return None
