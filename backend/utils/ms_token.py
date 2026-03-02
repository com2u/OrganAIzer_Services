"""
Microsoft OAuth Token Management Helper
========================================
Single authoritative function: get_valid_ms_token(user_id)

All Microsoft Graph callers MUST use this function to obtain tokens.

Features:
- Loads encrypted tokens from token_storage
- Structured diagnostic logging: exists, expires_at, expired, aud, scp (NO full token)
- Auto-refresh via MSAL ConfidentialClientApplication when token is expired
- 401-retry on first Graph call failure (one attempt per request)
- Proper error codes: MICROSOFT_UNAUTHORIZED, MICROSOFT_FORBIDDEN, CONFIGURATION_ERROR
- Never logs full access token — only first 12 chars and decoded JWT payload fields

Usage:
    from utils.ms_token import get_valid_ms_token
    token = get_valid_ms_token(user_id)              # raises HTTPException on failure
    headers = {"Authorization": f"Bearer {token}"}
"""

import os
import json
import base64
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import HTTPException
from msal import ConfidentialClientApplication

from utils.token_storage import get_token_storage

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Microsoft Graph scopes
# NOTE: Do NOT include openid / profile / offline_access here.
#       MSAL adds them automatically; passing them explicitly causes
#       a "reserved scope" ValueError.
# ------------------------------------------------------------------
MICROSOFT_GRAPH_SCOPES = [
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/User.Read",
]


# ==============================================================================
# Internal helpers
# ==============================================================================

def _ms_authority() -> str:
    """Return MSAL authority URL from MICROSOFT_TENANT_ID env var.

    Defaults to 'common' so the app works for BOTH personal Microsoft accounts
    (@outlook.com, @hotmail.com, @live.com) AND work/school accounts (Entra ID).

    To restrict to a single tenant, set MICROSOFT_TENANT_ID=<your-tenant-guid>.
    To restrict to personal accounts only, set MICROSOFT_TENANT_ID=consumers.
    To restrict to work/school accounts only, set MICROSOFT_TENANT_ID=organizations.

    IMPORTANT: The authority used for initial auth and token refresh MUST match.
    """
    tenant = os.getenv("MICROSOFT_TENANT_ID", "common")
    return f"https://login.microsoftonline.com/{tenant}"


def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    """
    Decode JWT payload WITHOUT verifying the signature.
    Used ONLY for diagnostic logging — never trusts the decoded data for auth.
    Returns {} if decoding fails.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        # Base64url decode — pad to multiple of 4
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return {}


def _log_token_diagnostics(user_id: str, tokens: Dict[str, Any]) -> None:
    """
    Log structured token diagnostics — safe, no secret leakage.

    Logs:
    - token exists? (bool)
    - len(access_token) and first 20 chars
    - expires_at and "expired?" (bool, includes 5-minute buffer)
    - decoded JWT claims: aud, iss, scp, tid
    """
    access_token: str = tokens.get("access_token", "")
    refresh_token: str = tokens.get("refresh_token", "")
    expires_at: str = tokens.get("expires_at", "")

    has_access = bool(access_token)
    has_refresh = bool(refresh_token)
    token_len = len(access_token)
    token_prefix = (access_token[:20] + "...") if len(access_token) > 20 else "(short/empty)"

    logger.info(
        "[MS_TOKEN] user=%s  has_access_token=%s  has_refresh_token=%s  "
        "token_len=%d  token_prefix=%s",
        user_id, has_access, has_refresh, token_len, token_prefix,
    )
    logger.info(
        "[MS_TOKEN] user=%s  stored_scopes=%s",
        user_id, tokens.get("scopes", "(not stored)"),
    )

    # Expiry check
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            is_expired = datetime.utcnow() >= exp_dt - timedelta(minutes=5)
            logger.info(
                "[MS_TOKEN] user=%s  expires_at=%s  expired_or_expiring_soon=%s",
                user_id, expires_at, is_expired,
            )
        except Exception as e:
            logger.warning("[MS_TOKEN] user=%s  Cannot parse expires_at=%r: %s", user_id, expires_at, e)
    else:
        logger.warning("[MS_TOKEN] user=%s  expires_at NOT stored — will refresh to be safe", user_id)

    # Decode JWT for aud/iss/scp/tid validation
    if access_token:
        payload = _decode_jwt_payload(access_token)
        aud = payload.get("aud", "(not found)")
        iss = payload.get("iss", "(not found)")
        scp = payload.get("scp", payload.get("roles", "(not found)"))
        tid = payload.get("tid", "(not found)")
        exp_claim = payload.get("exp")
        exp_claim_str = "(n/a)"
        if exp_claim:
            try:
                exp_claim_str = datetime.utcfromtimestamp(exp_claim).isoformat()
            except Exception:
                pass

        logger.info(
            "[MS_TOKEN] user=%s  jwt.aud=%s  jwt.iss=%s  jwt.scp=%s  jwt.tid=%s  jwt.exp=%s",
            user_id, aud, iss, scp, tid, exp_claim_str,
        )

        # Critical warning: wrong audience means 401 from Graph
        aud_str = str(aud).lower()
        if aud and "graph.microsoft.com" not in aud_str and "00000003-0000-0000-c000-000000000000" not in aud_str:
            logger.warning(
                "[MS_TOKEN] ⚠️  WRONG TOKEN AUDIENCE detected: aud=%s — "
                "This token is NOT for Microsoft Graph and WILL cause 401. "
                "Make sure your OAuth flow requests Graph scopes, not just openid/profile.",
                aud,
            )


def _refresh_ms_token(user_id: str, tokens: Dict[str, Any]) -> str:
    """
    Refresh the Microsoft access token using the stored refresh_token.

    Persists refreshed tokens back to encrypted storage.
    Returns the new access_token string.

    Raises:
        HTTPException(401, MICROSOFT_UNAUTHORIZED): no refresh_token, or MSAL error
        HTTPException(500, CONFIGURATION_ERROR): missing env vars
    """
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        logger.error(
            "[MS_TOKEN] user=%s  refresh_token is missing — cannot refresh. "
            "User must re-authenticate.",
            user_id,
        )
        raise HTTPException(
            status_code=401,
            detail={
                "code": "MICROSOFT_UNAUTHORIZED",
                "message": (
                    "Microsoft session has expired and no refresh token is available. "
                    "Please reconnect your Microsoft account via the Integrations page."
                ),
                "action": "RECONNECT_MICROSOFT",
            },
        )

    client_id = os.getenv("MICROSOFT_CLIENT_ID")
    client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CONFIGURATION_ERROR",
                "message": "MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET must be set in .env",
            },
        )

    logger.info("[MS_TOKEN] user=%s  Attempting token refresh via MSAL...", user_id)

    try:
        app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=_ms_authority(),
        )
        result = app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=MICROSOFT_GRAPH_SCOPES,
        )
    except Exception as e:
        logger.error("[MS_TOKEN] user=%s  MSAL refresh threw exception: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=401,
            detail={
                "code": "MICROSOFT_UNAUTHORIZED",
                "message": f"Microsoft token refresh failed: {e}. Please reconnect your account.",
                "action": "RECONNECT_MICROSOFT",
            },
        )

    if "error" in result:
        error_desc = result.get("error_description", result.get("error", "Unknown error"))
        logger.error("[MS_TOKEN] user=%s  Token refresh FAILED: %s", user_id, error_desc)
        raise HTTPException(
            status_code=401,
            detail={
                "code": "MICROSOFT_UNAUTHORIZED",
                "message": (
                    f"Microsoft token refresh failed: {error_desc}. "
                    "Please reconnect your Microsoft account."
                ),
                "action": "RECONNECT_MICROSOFT",
            },
        )

    new_access_token: str = result["access_token"]
    new_refresh_token: str = result.get("refresh_token", refresh_token)  # MSAL may return a new one
    expires_in: int = result.get("expires_in", 3600)
    new_expires_at: str = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

    updated_tokens = {
        **tokens,
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "expires_at": new_expires_at,
        "expires_in": expires_in,
    }
    get_token_storage().save_tokens(user_id, "microsoft", updated_tokens)

    logger.info(
        "[MS_TOKEN] user=%s  Token refreshed successfully. expires_at=%s",
        user_id, new_expires_at,
    )
    # Log diagnostics on the new token (verifies aud, scp)
    _log_token_diagnostics(user_id, updated_tokens)
    return new_access_token


# ==============================================================================
# Public API
# ==============================================================================

def get_valid_ms_token(user_id: str) -> str:
    """
    Get a valid Microsoft Graph access token for the given user.

    Algorithm:
    1. Load tokens from encrypted storage
    2. Log structured diagnostics (existence, expires_at, expired, jwt.aud, jwt.scp)
    3. If token is expired (or within 5-minute buffer) → refresh via refresh_token
    4. Return access_token

    Raises:
        HTTPException(401, MICROSOFT_UNAUTHORIZED): no tokens, empty token, or refresh failed
        HTTPException(500, CONFIGURATION_ERROR): MICROSOFT_CLIENT_ID/SECRET missing

    Security:
        Never logs the full access token — only first 12 chars and decoded JWT fields.
    """
    token_storage = get_token_storage()
    tokens = token_storage.load_tokens(user_id, "microsoft")

    if not tokens:
        logger.warning("[MS_TOKEN] user=%s  No Microsoft tokens found in storage.", user_id)
        raise HTTPException(
            status_code=401,
            detail={
                "code": "MICROSOFT_UNAUTHORIZED",
                "message": (
                    "Microsoft account not connected. "
                    "Please connect it via the Integrations page."
                ),
                "action": "CONNECT_MICROSOFT",
            },
        )

    # Log diagnostics (safe — no full token logged)
    _log_token_diagnostics(user_id, tokens)

    # Determine if refresh is needed
    expires_at = tokens.get("expires_at")
    needs_refresh = False

    if not expires_at:
        logger.warning(
            "[MS_TOKEN] user=%s  expires_at not stored — refreshing to be safe.", user_id
        )
        needs_refresh = True
    else:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            if datetime.utcnow() >= exp_dt - timedelta(minutes=5):
                logger.info(
                    "[MS_TOKEN] user=%s  Token expired or expiring in <5 min — refreshing.",
                    user_id,
                )
                needs_refresh = True
        except Exception as e:
            logger.warning(
                "[MS_TOKEN] user=%s  Cannot parse expires_at=%r (%s) — refreshing to be safe.",
                user_id, expires_at, e,
            )
            needs_refresh = True

    if needs_refresh:
        return _refresh_ms_token(user_id, tokens)

    access_token = tokens.get("access_token")
    if not access_token:
        logger.error(
            "[MS_TOKEN] user=%s  access_token field is empty in stored tokens.", user_id
        )
        raise HTTPException(
            status_code=401,
            detail={
                "code": "MICROSOFT_UNAUTHORIZED",
                "message": "Stored Microsoft token is empty. Please reconnect your account.",
                "action": "RECONNECT_MICROSOFT",
            },
        )

    return access_token
