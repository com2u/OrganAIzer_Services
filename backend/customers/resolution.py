"""
resolution.py — deterministic caller -> customer matching.

Pure functions: no I/O beyond reading the customer store, no LLM calls, no
voice/ESL dependency (this package must not depend on the voice stack, same
rule scheduler/service.py follows for core.phone_mask). This is the ONLY place
that decides whether a caller has been identified and with what confidence —
the LLM only phrases questions using labels handed to it by the caller
(see voice/caller_resolution_dialogue.py and
voice/llm_bridge.build_identity_stage_instruction).

Matching rules (approved for Phase 1):
  - Exact normalized-number matches (landline or mobile) MAY resolve a
    customer automatically.
  - Suffix-only / partial-digit matching is intentionally NOT implemented
    anywhere in this module — it must never be able to auto-resolve a
    customer, unlike voice/contacts.py's suffix fallback for the unrelated
    outbound-contact-name feature.
  - Any signal that yields more than one match is "ambiguous" and is never
    auto-picked — the caller must be asked to disambiguate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import store as _store

__all__ = [
    "ResolutionResult",
    "normalize_number",
    "classify_number",
    "lookup_by_landline",
    "lookup_by_mobile",
    "lookup_by_name",
    "resolve_caller",
]

_MOBILE_PREFIX_RE = re.compile(r"^0(15|16|17)\d")


def normalize_number(raw: Optional[str]) -> str:
    """
    Normalize a German phone number to a digits-only national form
    (e.g. "01751234567"), regardless of whether it was given as +49, 0049, or 0.

    Duplicates (rather than imports) the equivalent logic in voice/contacts.py
    — the customers domain must not depend on the voice package. Returns ""
    for empty/unparseable input.
    """
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw).strip().lstrip("+"))
    if not digits:
        return ""
    if digits.startswith("0049"):
        digits = "0" + digits[4:]
    elif digits.startswith("49") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits


def classify_number(raw: Optional[str]) -> str:
    """Return "mobile", "landline", or "unknown" for a German number, any input format."""
    normalized = normalize_number(raw)
    if not normalized:
        return "unknown"
    if _MOBILE_PREFIX_RE.match(normalized):
        return "mobile"
    if normalized.startswith("0"):
        return "landline"
    return "unknown"


def _single_location(customer: dict) -> Optional[dict]:
    locs = customer.get("locations") or []
    return locs[0] if len(locs) == 1 else None


def lookup_by_landline(number: str, customers: Optional[list] = None) -> list:
    """
    Exact normalized match against every location's landline numbers.

    Returns a list of {"customer": ..., "location": ..., "contact": None}
    matches — empty if none, more than one only if the seed data itself has a
    duplicate (a data-integrity situation, still surfaced as ambiguous rather
    than silently picked).
    """
    needle = normalize_number(number)
    if not needle:
        return []
    pool = customers if customers is not None else _store.all_customers()
    matches = []
    for customer in pool:
        for loc in customer.get("locations", []):
            for num in loc.get("numbers", []):
                if num.get("type") != "landline":
                    continue
                if normalize_number(num.get("number")) == needle:
                    matches.append({"customer": customer, "location": loc, "contact": None})
    return matches


def lookup_by_mobile(number: str, customers: Optional[list] = None) -> list:
    """
    Exact normalized match against every known contact's mobile numbers.

    Returns a list of {"customer": ..., "location": ..., "contact": ...}
    matches. ``location`` is filled only when the matched customer has exactly
    one location on file (otherwise the caller must still be asked which
    location/line is affected).
    """
    needle = normalize_number(number)
    if not needle:
        return []
    pool = customers if customers is not None else _store.all_customers()
    matches = []
    for customer in pool:
        for contact in customer.get("known_contacts", []):
            for num in contact.get("mobile_numbers", []):
                if num.get("type") != "mobile":
                    continue
                if normalize_number(num.get("number")) == needle:
                    matches.append({
                        "customer": customer,
                        "location": _single_location(customer),
                        "contact": contact,
                    })
    return matches


def lookup_by_name(name: str, customers: Optional[list] = None) -> list:
    """
    Case-insensitive substring match against the customer name and every
    known contact's name. Returns at most one match per distinct customer
    (deduplicated), even if multiple contacts at that customer match.
    """
    needle = (name or "").strip().lower()
    if not needle:
        return []
    pool = customers if customers is not None else _store.all_customers()
    matches = []
    seen_ids = set()
    for customer in pool:
        cid = customer.get("customer_id")
        if cid in seen_ids:
            continue
        name_hit = needle in (customer.get("name") or "").lower()
        hit_contact = None
        if not name_hit:
            for contact in customer.get("known_contacts", []):
                if needle in (contact.get("name") or "").lower():
                    hit_contact = contact
                    break
        if name_hit or hit_contact:
            matches.append({
                "customer": customer,
                "location": _single_location(customer),
                "contact": hit_contact,
            })
            seen_ids.add(cid)
    return matches


@dataclass
class ResolutionResult:
    """Outcome of :func:`resolve_caller`. Never carries a raw phone number by itself."""

    confidence: str  # "none" | "low" | "high" | "ambiguous"
    method: str
    customer: Optional[dict] = None
    location: Optional[dict] = None
    candidates: list = field(default_factory=list)


def resolve_caller(
    *,
    caller_number: Optional[str] = None,
    affected_number: Optional[str] = None,
    stated_name: Optional[str] = None,
    customers: Optional[list] = None,
) -> ResolutionResult:
    """
    Pure deterministic resolution. Never mutates any store, never calls the LLM.

    Priority order: caller-ID number (landline/mobile) -> self-reported
    affected landline -> name-only. The first signal that yields exactly one
    match resolves the call: "high" confidence for any exact number match,
    "low" for a name-only match (always weak on its own — the caller must
    still be asked to confirm a landline). Any signal yielding more than one
    match returns "ambiguous" with the candidate list, never auto-picked.
    """
    pool = customers if customers is not None else _store.all_customers()

    if caller_number:
        kind = classify_number(caller_number)
        if kind == "landline":
            matches = lookup_by_landline(caller_number, pool)
            if len(matches) == 1:
                m = matches[0]
                return ResolutionResult("high", "landline_match", m["customer"], m["location"])
            if len(matches) > 1:
                return ResolutionResult("ambiguous", "landline_match_ambiguous", candidates=matches)
        elif kind == "mobile":
            matches = lookup_by_mobile(caller_number, pool)
            if len(matches) == 1:
                m = matches[0]
                return ResolutionResult("high", "mobile_match", m["customer"], m["location"])
            if len(matches) > 1:
                return ResolutionResult("ambiguous", "mobile_match_ambiguous", candidates=matches)

    if affected_number:
        matches = lookup_by_landline(affected_number, pool)
        if len(matches) == 1:
            m = matches[0]
            return ResolutionResult("high", "landline_match", m["customer"], m["location"])
        if len(matches) > 1:
            return ResolutionResult("ambiguous", "landline_match_ambiguous", candidates=matches)

    if stated_name:
        matches = lookup_by_name(stated_name, pool)
        if len(matches) == 1:
            m = matches[0]
            return ResolutionResult("low", "name_only", m["customer"], m["location"])
        if len(matches) > 1:
            return ResolutionResult("ambiguous", "name_only_ambiguous", candidates=matches)

    return ResolutionResult("none", "unresolved")
