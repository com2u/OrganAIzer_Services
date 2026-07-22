"""
customers — OrganAIzer phone-AI caller & customer resolution domain.

Phase 1 (current): READ-ONLY simulation. Owns the simulated customer/location/
contact master data (``backend/data/customers/customers.jsonl``, human/seed-
maintained) and the deterministic matching rules that resolve an inbound
caller to a customer record. Mirrors the ``scheduler`` package's shape: pure
data + pure functions, no voice/ESL dependency, no LLM calls.

No function in this package writes to customers.jsonl. Suffix-only number
matching is intentionally not implemented anywhere in this package — only
exact normalized matches may resolve a customer. See
voice/caller_resolution_dialogue.py for the per-call bridge that turns a
transcribed utterance into calls against :func:`resolve_caller`, and
voice/llm_bridge.build_identity_stage_instruction for the (Layer 1,
client-neutral) prompt text shown to the LLM for each identity stage.

Phase 2 (not implemented here) would add a separate, explicitly consent-gated
store for AI-learned callback numbers — never a write path into this package's
customers.jsonl.
"""
from __future__ import annotations

from .config import SCHEMA_VERSION, default_store_path
from .models import RECORD_FIELDS, validate_customer_record
from .resolution import (
    ResolutionResult,
    classify_number,
    lookup_by_landline,
    lookup_by_mobile,
    lookup_by_name,
    normalize_number,
    resolve_caller,
)
from .store import MalformedCustomerLine, all_customers, count, load

__all__ = [
    "SCHEMA_VERSION",
    "default_store_path",
    "RECORD_FIELDS",
    "validate_customer_record",
    "MalformedCustomerLine",
    "all_customers",
    "count",
    "load",
    "ResolutionResult",
    "classify_number",
    "lookup_by_landline",
    "lookup_by_mobile",
    "lookup_by_name",
    "normalize_number",
    "resolve_caller",
]
