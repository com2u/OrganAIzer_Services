"""
models.py — the simulated customer/location/contact record shape.

Distinguishes the three concepts named in the business requirement:
  1. the person calling         -> a ``known_contacts[]`` entry (or nobody, if
                                    the caller isn't on file at all)
  2. the customer/company       -> a top-level customer record
  3. the affected line/location -> a ``locations[]`` entry, each with its own
                                    landline number(s)

Phase 1 is READ-ONLY simulation data: this module defines the shape and a
validator used by the seed script only. Nothing in the ``customers`` package
writes to the store at call time — see store.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import SCHEMA_VERSION

__all__ = [
    "PhoneNumber",
    "Location",
    "KnownContact",
    "Customer",
    "RECORD_FIELDS",
    "validate_customer_record",
]

_VALID_NUMBER_TYPES = ("landline", "mobile")
_VALID_CUSTOMER_TYPES = ("business", "private")
_VALID_STATUSES = ("active", "inactive")


@dataclass(frozen=True)
class PhoneNumber:
    """A single phone number entry. ``type`` drives landline-vs-mobile matching."""

    number: str
    type: str  # "landline" | "mobile"
    role: Optional[str] = None
    verified: bool = True


@dataclass(frozen=True)
class Location:
    """One physical site or line grouping for a customer."""

    location_id: str
    label: str
    numbers: list  # list[PhoneNumber], kept plain for JSONL round-trip
    address: Optional[str] = None


@dataclass(frozen=True)
class KnownContact:
    """A person on file for a customer (the caller, if they match one)."""

    contact_id: str
    name: str
    mobile_numbers: list  # list[PhoneNumber]
    role: Optional[str] = None


@dataclass(frozen=True)
class Customer:
    """The customer/company entity itself."""

    customer_id: str
    name: str
    customer_type: str  # "business" | "private"
    locations: list       # list[Location]
    known_contacts: list  # list[KnownContact]
    status: str = "active"
    schema_version: str = SCHEMA_VERSION


# Canonical top-level field set for a stored record.
RECORD_FIELDS: tuple = (
    "customer_id",
    "schema_version",
    "name",
    "customer_type",
    "status",
    "locations",
    "known_contacts",
)


def validate_customer_record(record: dict) -> None:
    """
    Validate a customer record's shape. Raises ``ValueError`` on any problem.

    Used by the seed script before writing. There is no call-time writer in
    this package, so this validator is never on the hot path of a live call.
    """
    missing = [f for f in RECORD_FIELDS if f not in record]
    if missing:
        raise ValueError(f"Customer record missing fields: {', '.join(missing)}")

    if record["customer_type"] not in _VALID_CUSTOMER_TYPES:
        raise ValueError(f"Unknown customer_type {record['customer_type']!r}")

    if record["status"] not in _VALID_STATUSES:
        raise ValueError(f"Unknown status {record['status']!r}")

    for loc in record["locations"]:
        if "location_id" not in loc or "label" not in loc or "numbers" not in loc:
            raise ValueError(f"Location record missing required fields: {loc!r}")
        for num in loc["numbers"]:
            if num.get("type") not in _VALID_NUMBER_TYPES:
                raise ValueError(
                    f"Unknown number type in location {loc.get('location_id')!r}: {num!r}"
                )

    for contact in record["known_contacts"]:
        if "contact_id" not in contact or "name" not in contact:
            raise ValueError(f"Known-contact record missing required fields: {contact!r}")
        for num in contact.get("mobile_numbers", []):
            if num.get("type") != "mobile":
                raise ValueError(
                    f"known_contacts mobile_numbers entry is not type=mobile: {num!r}"
                )
