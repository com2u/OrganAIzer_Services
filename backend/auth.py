"""
API key authentication for OrganAIzer backend.

Keys are loaded at startup from the API_KEYS environment variable
(comma-separated list). No file-system dependency.

Example .env entry:
    API_KEYS=key-abc123,key-def456
"""

import os
import logging
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load API keys from environment at module import time.
# Fail fast so the problem is caught on startup, not on first request.
#
# Supports two env var forms for backward compatibility:
#   API_KEYS=key1,key2,key3   (comma-separated list, recommended)
#   API_KEY=single-key        (single key, legacy — used as fallback)
# ---------------------------------------------------------------------------
_raw = os.getenv("API_KEYS", "").strip() or os.getenv("API_KEY", "").strip()
if not _raw:
    raise RuntimeError(
        "No API keys configured. Set either:\n"
        "  API_KEYS=key1,key2   (comma-separated, for multiple keys)\n"
        "  API_KEY=key1         (single key, backward-compatible)\n"
        "in your backend/.env file before starting the server."
    )

API_KEYS: set[str] = {k.strip() for k in _raw.split(",") if k.strip()}

if not API_KEYS:
    raise RuntimeError(
        "API_KEYS / API_KEY environment variable was set but contained no usable keys "
        "(check for stray commas or whitespace-only values)."
    )

logger.info(f"API key auth initialised with {len(API_KEYS)} key(s).")

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key")


async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    FastAPI dependency that validates the X-API-Key request header.

    Returns the key on success; raises HTTP 401 on failure.
    """
    if api_key in API_KEYS:
        logger.info("API key validation successful.")
        return api_key

    logger.warning("API key validation failed: invalid or unknown key.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key",
    )
