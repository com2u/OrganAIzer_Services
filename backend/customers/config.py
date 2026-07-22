"""
config.py — storage location and schema version for the customers domain.

Pure data, no I/O beyond resolving a path from the environment — mirrors
scheduler/config.py's shape.
"""
from __future__ import annotations

import os
from pathlib import Path

# Bump when the on-disk record shape changes.
SCHEMA_VERSION = "0.1"

# Default provenance stamped on seed records.
DEFAULT_SEED_SOURCE = "customer_demo_seed"

# Default JSONL store. backend/data/ is gitignored, so simulated customer data
# never enters git. Override with the CUSTOMERS_STORE_PATH env var (or the path
# argument on store/resolution functions, used by tests).
_DEFAULT_STORE = Path(__file__).parent.parent / "data" / "customers" / "customers.jsonl"


def default_store_path() -> Path:
    """Resolve the default JSONL store path (env var wins over the built-in default)."""
    env = os.environ.get("CUSTOMERS_STORE_PATH")
    return Path(env) if env else _DEFAULT_STORE
