#!/usr/bin/env python3
"""
seed_customers_demo.py — populate the customers JSONL store with realistic
simulated customer/location/contact records for testing and evaluation.

Mirrors seed_scheduler_demo_calendar.py: safe for repeated runs (skips
re-seeding unless --force is passed), writes only synthetic data, and the
resulting store is Phase-1 READ-ONLY at call time — nothing in the customers
package ever writes to this file during a live call. This script is a one-time
human/setup operation, not something the AI or any call-time code invokes.

Usage:
    cd backend
    python scripts/seed_customers_demo.py [--force] [--path <path>]

Options:
    --force           Ignore existing seed marker, re-seed from scratch
    --path <path>     Write to a custom store path instead of the default
    --dry-run         Print what would be seeded without writing
    --help            Show this message
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from customers import default_store_path, validate_customer_record
from customers.config import DEFAULT_SEED_SOURCE
from customers.store import load as read_customers

# ── Demo records ─────────────────────────────────────────────────────────────
# Covers: a known landline + a caller whose mobile is NOT on file (Herr Müller,
# the scenario named in the business requirement), a duplicate-name collision
# ("Müller" matches two unrelated customers), a business with multiple
# locations/lines, and a simple single-location/single-mobile customer.
_DEMO_CUSTOMERS: list[dict] = [
    {
        "customer_id": "cus_001",
        "schema_version": "0.1",
        "name": "Müller GmbH",
        "customer_type": "business",
        "status": "active",
        "locations": [
            {
                "location_id": "loc_001",
                "label": "Hauptsitz Fulda",
                "address": "Bahnhofstraße 12, 36037 Fulda",
                "numbers": [
                    {"number": "+49661123456", "type": "landline", "role": "main", "verified": True},
                ],
            },
        ],
        "known_contacts": [
            {
                "contact_id": "ct_001",
                "name": "Herr Müller",
                "role": "owner",
                # Intentionally empty: Herr Müller's private mobile is NOT on
                # file — this is the "unknown mobile for an existing customer"
                # scenario from the business requirement.
                "mobile_numbers": [],
            },
        ],
    },
    {
        "customer_id": "cus_002",
        "schema_version": "0.1",
        "name": "Anna Müller",
        "customer_type": "private",
        "status": "active",
        "locations": [
            {
                "location_id": "loc_002",
                "label": "Privatanschluss",
                "address": "Gartenstraße 5, 36037 Fulda",
                "numbers": [
                    {"number": "+49661998877", "type": "landline", "role": "main", "verified": True},
                ],
            },
        ],
        "known_contacts": [
            {
                "contact_id": "ct_002",
                "name": "Anna Müller",
                "role": "owner",
                "mobile_numbers": [
                    {"number": "+4915199988877", "type": "mobile", "role": "primary", "verified": True},
                ],
            },
        ],
    },
    {
        "customer_id": "cus_003",
        "schema_version": "0.1",
        "name": "Bäckerei Fulda Kette",
        "customer_type": "business",
        "status": "active",
        "locations": [
            {
                "location_id": "loc_003a",
                "label": "Filiale Innenstadt",
                "address": "Marktplatz 3, 36037 Fulda",
                "numbers": [
                    {"number": "+49661222333", "type": "landline", "role": "main", "verified": True},
                ],
            },
            {
                "location_id": "loc_003b",
                "label": "Filiale Petersberg",
                "address": "Petersberg 8, 36037 Fulda",
                "numbers": [
                    {"number": "+49661222444", "type": "landline", "role": "main", "verified": True},
                ],
            },
        ],
        "known_contacts": [
            {
                "contact_id": "ct_003",
                "name": "Frau Weber",
                "role": "manager",
                "mobile_numbers": [
                    {"number": "+4915155566677", "type": "mobile", "role": "primary", "verified": True},
                ],
            },
        ],
    },
    {
        "customer_id": "cus_004",
        "schema_version": "0.1",
        "name": "Kanzlei Schmidt & Partner",
        "customer_type": "business",
        "status": "active",
        "locations": [
            {
                "location_id": "loc_004",
                "label": "Büro Fulda",
                "address": "Rangstraße 20, 36037 Fulda",
                "numbers": [
                    {"number": "+49661555000", "type": "landline", "role": "main", "verified": True},
                ],
            },
        ],
        "known_contacts": [
            {
                "contact_id": "ct_004",
                "name": "Herr Schmidt",
                "role": "owner",
                "mobile_numbers": [
                    {"number": "+4917012345678", "type": "mobile", "role": "primary", "verified": True},
                ],
            },
        ],
    },
]


def _check_seed_marker(path: Path) -> bool:
    """Check whether this store already carries the demo-seed marker."""
    if not path.exists():
        return False
    records = read_customers(path)
    return any(r.get("_seed_source") == DEFAULT_SEED_SOURCE for r in records)


def seed_customers(path: Path, force: bool = False, dry_run: bool = False) -> int:
    """
    Seed the customers store with fake customer/location/contact records.

    Returns the number of records seeded (0 if skipped because already seeded).
    """
    if path.exists() and not force and _check_seed_marker(path):
        print("ℹ️  Customers store already seeded (found demo seed marker). Use --force to re-seed.")
        return 0

    records = []
    for customer in _DEMO_CUSTOMERS:
        validate_customer_record(customer)
        record = dict(customer)
        record["_seed_source"] = DEFAULT_SEED_SOURCE
        records.append(record)

    if dry_run:
        print(f"\n📋 DRY RUN: would seed {len(records)} customers to {path}\n")
        for r in records:
            loc_labels = ", ".join(loc["label"] for loc in r["locations"])
            print(f"  {r['customer_id']:10} {r['name']:28} [{loc_labels}]")
        print()
        return len(records)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✅ Seeded {len(records)} customers to {path}")
    print(f"📁 Store size: {path.stat().st_size} bytes")
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed the customers JSONL store with realistic simulated customer records."
    )
    parser.add_argument("--force", action="store_true", help="Re-seed even if demo seed marker exists")
    parser.add_argument("--path", type=Path, default=None, help="Custom store path (default: from config)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be seeded without writing")

    args = parser.parse_args()
    path = args.path or default_store_path()

    print("🌱 Seeding customers demo store")
    print(f"📍 Store: {path}")

    count = seed_customers(path=path, force=args.force, dry_run=args.dry_run)
    return 0 if count >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
