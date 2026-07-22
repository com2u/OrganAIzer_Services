"""
Tests for the customers domain (backend/customers) and the per-call bridge
(voice/caller_resolution_dialogue.py) — Phase 1: read-only simulation.

Covers the twelve required scenarios plus the underlying resolve_caller()
matching rules. No FreeSWITCH, no ESL, no LLM calls — pure deterministic logic
against an in-memory fixture customer list (never the real seed file, so these
tests are independent of scripts/seed_customers_demo.py).

Privacy assertions (raw numbers never reach the LLM-bound prompt) live in
test_customer_resolution_privacy.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from customers.resolution import (
    ResolutionResult,
    classify_number,
    lookup_by_landline,
    lookup_by_mobile,
    lookup_by_name,
    normalize_number,
    resolve_caller,
)
from voice import caller_resolution_dialogue as crd

# ── fixture customers (mirrors scripts/seed_customers_demo.py, kept local so
# these tests never depend on the actual seeded file) ─────────────────────────

MUELLER_GMBH = {
    "customer_id": "cus_001",
    "name": "Müller GmbH",
    "customer_type": "business",
    "status": "active",
    "locations": [
        {
            "location_id": "loc_001",
            "label": "Hauptsitz Fulda",
            "address": "Bahnhofstraße 12, 36037 Fulda",
            "numbers": [{"number": "+49661123456", "type": "landline"}],
        },
    ],
    "known_contacts": [
        {"contact_id": "ct_001", "name": "Herr Müller", "role": "owner", "mobile_numbers": []},
    ],
}

ANNA_MUELLER = {
    "customer_id": "cus_002",
    "name": "Anna Müller",
    "customer_type": "private",
    "status": "active",
    "locations": [
        {
            "location_id": "loc_002",
            "label": "Privatanschluss",
            "address": "Gartenstraße 5, 36037 Fulda",
            "numbers": [{"number": "+49661998877", "type": "landline"}],
        },
    ],
    "known_contacts": [
        {
            "contact_id": "ct_002",
            "name": "Anna Müller",
            "role": "owner",
            "mobile_numbers": [{"number": "+4915199988877", "type": "mobile"}],
        },
    ],
}

BAECKEREI = {
    "customer_id": "cus_003",
    "name": "Bäckerei Fulda Kette",
    "customer_type": "business",
    "status": "active",
    "locations": [
        {"location_id": "loc_003a", "label": "Filiale Innenstadt", "numbers": [{"number": "+49661222333", "type": "landline"}]},
        {"location_id": "loc_003b", "label": "Filiale Petersberg", "numbers": [{"number": "+49661222444", "type": "landline"}]},
    ],
    "known_contacts": [
        {
            "contact_id": "ct_003",
            "name": "Frau Weber",
            "role": "manager",
            "mobile_numbers": [{"number": "+4915155566677", "type": "mobile"}],
        },
    ],
}

SCHMIDT = {
    "customer_id": "cus_004",
    "name": "Kanzlei Schmidt & Partner",
    "customer_type": "business",
    "status": "active",
    "locations": [
        {"location_id": "loc_004", "label": "Büro Fulda", "numbers": [{"number": "+49661555000", "type": "landline"}]},
    ],
    "known_contacts": [
        {
            "contact_id": "ct_004",
            "name": "Herr Schmidt",
            "role": "owner",
            "mobile_numbers": [{"number": "+4917012345678", "type": "mobile"}],
        },
    ],
}

FIXTURE_CUSTOMERS = [MUELLER_GMBH, ANNA_MUELLER, BAECKEREI, SCHMIDT]

# A mobile that appears nowhere in the fixture data — used for the "unknown
# mobile, existing customer" (Herr Müller) and "withheld caller ID" scenarios.
UNKNOWN_MOBILE = "+4915199912345"


# =============================================================================
# Normalization / classification
# =============================================================================

class TestNormalizeAndClassify:
    def test_plus49_landline_normalizes(self):
        assert normalize_number("+49661123456") == normalize_number("0661123456")

    def test_0049_prefix_normalizes(self):
        assert normalize_number("0049661123456") == normalize_number("0661123456")

    def test_national_zero_form_unchanged(self):
        assert normalize_number("0661123456") == "0661123456"

    def test_empty_input(self):
        assert normalize_number("") == ""
        assert normalize_number(None) == ""

    def test_classify_mobile(self):
        assert classify_number("+4917012345678") == "mobile"
        assert classify_number("+4915112345678") == "mobile"
        assert classify_number("+4916012345678") == "mobile"

    def test_classify_landline(self):
        assert classify_number("+49661123456") == "landline"
        assert classify_number("0661123456") == "landline"

    def test_classify_unknown_for_empty(self):
        assert classify_number("") == "unknown"


# =============================================================================
# Lookup primitives — exact match only, never suffix
# =============================================================================

class TestLookupPrimitives:
    def test_lookup_by_landline_exact_hit(self):
        matches = lookup_by_landline("+49661123456", FIXTURE_CUSTOMERS)
        assert len(matches) == 1
        assert matches[0]["customer"]["customer_id"] == "cus_001"
        assert matches[0]["location"]["location_id"] == "loc_001"

    def test_lookup_by_landline_no_suffix_fallback(self):
        # Shares the last 7 digits with +49661123456 but is not the same
        # number end-to-end — must NOT match (unlike voice/contacts.py's
        # suffix fallback, which this domain deliberately does not implement).
        matches = lookup_by_landline("+49991123456", FIXTURE_CUSTOMERS)
        assert matches == []

    def test_lookup_by_landline_miss(self):
        assert lookup_by_landline("+49661000000", FIXTURE_CUSTOMERS) == []

    def test_lookup_by_mobile_exact_hit(self):
        matches = lookup_by_mobile("+4917012345678", FIXTURE_CUSTOMERS)
        assert len(matches) == 1
        assert matches[0]["customer"]["customer_id"] == "cus_004"

    def test_lookup_by_mobile_miss(self):
        assert lookup_by_mobile(UNKNOWN_MOBILE, FIXTURE_CUSTOMERS) == []

    def test_lookup_by_name_duplicate(self):
        matches = lookup_by_name("Müller", FIXTURE_CUSTOMERS)
        ids = {m["customer"]["customer_id"] for m in matches}
        assert ids == {"cus_001", "cus_002"}

    def test_lookup_by_name_no_match(self):
        assert lookup_by_name("Nichtvorhanden", FIXTURE_CUSTOMERS) == []


# =============================================================================
# resolve_caller() — the pure deterministic orchestrator
# =============================================================================

class TestResolveCaller:
    def test_known_landline_resolves_high(self):
        result = resolve_caller(caller_number="+49661555000", customers=FIXTURE_CUSTOMERS)
        assert result.confidence == "high"
        assert result.method == "landline_match"
        assert result.customer["customer_id"] == "cus_004"
        assert result.location["location_id"] == "loc_004"

    def test_known_mobile_single_location_resolves_high_with_location(self):
        result = resolve_caller(caller_number="+4917012345678", customers=FIXTURE_CUSTOMERS)
        assert result.confidence == "high"
        assert result.method == "mobile_match"
        assert result.customer["customer_id"] == "cus_004"
        assert result.location["location_id"] == "loc_004"

    def test_known_mobile_multiple_locations_resolves_customer_without_location(self):
        result = resolve_caller(caller_number="+4915155566677", customers=FIXTURE_CUSTOMERS)
        assert result.confidence == "high"
        assert result.customer["customer_id"] == "cus_003"
        assert result.location is None  # must still ask which location/line

    def test_unknown_mobile_plus_affected_landline_resolves_high(self):
        # Herr Müller: calls from a private mobile that is NOT on file, but
        # gives the affected Festnetznummer for Müller GmbH.
        result = resolve_caller(
            caller_number=UNKNOWN_MOBILE,
            affected_number="+49661123456",
            customers=FIXTURE_CUSTOMERS,
        )
        assert result.confidence == "high"
        assert result.method == "landline_match"
        assert result.customer["customer_id"] == "cus_001"

    def test_withheld_caller_id_resolves_via_affected_number_alone(self):
        result = resolve_caller(
            caller_number=None,
            affected_number="+49661123456",
            customers=FIXTURE_CUSTOMERS,
        )
        assert result.confidence == "high"
        assert result.customer["customer_id"] == "cus_001"

    def test_withheld_caller_id_with_nothing_else_is_unresolved(self):
        result = resolve_caller(caller_number=None, customers=FIXTURE_CUSTOMERS)
        assert result.confidence == "none"
        assert result.method == "unresolved"

    def test_duplicate_name_is_ambiguous_not_autopicked(self):
        result = resolve_caller(stated_name="Müller", customers=FIXTURE_CUSTOMERS)
        assert result.confidence == "ambiguous"
        ids = {c["customer"]["customer_id"] for c in result.candidates}
        assert ids == {"cus_001", "cus_002"}

    def test_unknown_festnetznummer_falls_through_to_none(self):
        result = resolve_caller(affected_number="+49661000000", customers=FIXTURE_CUSTOMERS)
        assert result.confidence == "none"

    def test_name_only_is_low_confidence_not_authoritative(self):
        result = resolve_caller(stated_name="Schmidt", customers=FIXTURE_CUSTOMERS)
        assert result.confidence == "low"
        assert result.method == "name_only"
        assert result.customer["customer_id"] == "cus_004"

    def test_nothing_given_is_unresolved(self):
        result = resolve_caller(customers=FIXTURE_CUSTOMERS)
        assert result.confidence == "none"
        assert result.customer is None


# =============================================================================
# Per-call dialogue bridge — voice/caller_resolution_dialogue.py
# =============================================================================
# All tests here use the module-level default store, so they monkeypatch
# customers.resolution._store.all_customers via the `customers` kwarg is not
# available at the dialogue layer — instead we patch the store module.

import customers.store as _customers_store


def _patch_store(monkeypatch):
    monkeypatch.setattr(_customers_store, "load", lambda path=None: FIXTURE_CUSTOMERS)
    monkeypatch.setattr(_customers_store, "all_customers", lambda path=None: FIXTURE_CUSTOMERS)


class TestKnownLandlineDialogue:
    def test_resolved_immediately_at_call_start(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "+49661555000")
        assert state["identity_stage"] == "resolved"
        assert state["resolution"]["customer"]["customer_id"] == "cus_004"


class TestKnownMobileDialogue:
    def test_resolved_immediately_at_call_start(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "+4917012345678")
        assert state["identity_stage"] == "resolved"


class TestUnknownMobileKnownFestnetznummer:
    def test_mueller_scenario_resolves_after_landline_given(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, UNKNOWN_MOBILE)
        assert state["identity_stage"] == "awaiting_affected_number"

        crd.observe_turn(state, "Meine Nummer die nicht geht ist 0661 123456.")
        assert state["identity_stage"] == "resolved"
        assert state["resolution"]["customer"]["customer_id"] == "cus_001"


class TestWithheldCallerId:
    def test_resolves_via_self_reported_landline(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        assert state["caller_number_present"] is False
        assert state["identity_stage"] == "awaiting_affected_number"

        crd.observe_turn(state, "Die betroffene Nummer ist 0661 123456.")
        assert state["identity_stage"] == "resolved"
        assert state["resolution"]["customer"]["customer_id"] == "cus_001"


class TestDuplicateNamesDialogue:
    def test_ambiguous_then_disambiguated_by_location(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Mein Name ist Müller.")
        assert state["identity_stage"] == "awaiting_disambiguation"
        labels = crd.candidate_labels(state)
        assert any("Müller GmbH" in l for l in labels)
        assert any("Anna Müller" in l for l in labels)

        crd.observe_turn(state, "Ich meine die Firma in der Bahnhofstraße, Hauptsitz Fulda.")
        assert state["identity_stage"] == "resolved"
        assert state["resolution"]["customer"]["customer_id"] == "cus_001"


class TestMultipleLocationsDialogue:
    def test_awaiting_location_then_resolved(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "+4915155566677")
        assert state["identity_stage"] == "awaiting_location"

        crd.observe_turn(state, "Es geht um die Filiale Petersberg.")
        assert state["identity_stage"] == "resolved"
        assert state["resolution"]["location"]["location_id"] == "loc_003b"


class TestUnknownFestnetznummerDialogue:
    def test_stays_unresolved_and_keeps_asking(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Die Nummer ist 0661 000000.")
        assert state["identity_stage"] == "awaiting_affected_number"
        assert state["resolution"]["confidence"] == "none"


class TestNewInstallationDialogue:
    def test_skips_number_based_flow(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Wir hatten noch keinen Anschluss, es geht um einen Neuanschluss.")
        assert state["identity_stage"] == "new_installation"
        extra = crd.build_prompt_extra(state)
        assert extra is not None
        assert "NEW INSTALLATION" in extra


class TestExternalTechnicianDialogue:
    def test_role_set_and_resolution_still_proceeds(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Ich rufe im Auftrag von Müller GmbH an, ich bin Techniker vor Ort.")
        assert state["caller_role"] == "technician_on_behalf"

        crd.observe_turn(state, "Die Nummer ist 0661 123456.")
        assert state["identity_stage"] == "resolved"
        assert state["caller_role"] == "technician_on_behalf"
        assert state["resolution"]["customer"]["customer_id"] == "cus_001"


class TestUrgentOutageDialogue:
    def test_urgent_flag_set_without_blocking_identification(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Kompletter Ausfall, bei uns ist alles tot.")
        assert state["urgent"] is True
        assert state["identity_stage"] == "awaiting_affected_number"
        extra = crd.build_prompt_extra(state)
        assert extra is not None
        assert "do not block" in extra


class TestGeneralProductEnquiryDialogue:
    def test_identification_exempt_no_prompt(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Welche Produkte bieten Sie an?")
        assert state["identification_exempt"] is True
        assert crd.build_prompt_extra(state) is None


class TestCallerRefusesIdentificationDialogue:
    def test_two_refusals_degrade_to_unresolved_continue(self, monkeypatch):
        _patch_store(monkeypatch)
        state = crd.new_state()
        crd.init_from_call(state, "")
        crd.observe_turn(state, "Das sage ich Ihnen nicht.")
        assert state["identity_stage"] == "awaiting_affected_number"
        assert state["ask_attempts"] == 1

        crd.observe_turn(state, "Nein, das gebe ich nicht raus.")
        assert state["identity_stage"] == "unresolved_continue"
        extra = crd.build_prompt_extra(state)
        assert extra is not None
        assert "UNVERIFIED" in extra
