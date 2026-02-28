"""
Outlook / Microsoft Graph integration.

Uses MSAL (msal) for device-code-flow authentication and
the Microsoft Graph REST API directly via `requests`.

Replaces the previous msgraph-sdk implementation which could not be installed
on Windows without Long Path support enabled (260-char path limit exceeded
by the generated SDK file tree).

Dependencies: msal, requests  — both already in requirements.txt.
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

import requests
from msal import PublicClientApplication, SerializableTokenCache

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SCOPES = [
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Calendars.Read",
]

# ---------------------------------------------------------------------------
# Token cache (persistent)
# ---------------------------------------------------------------------------
_cache: Optional[SerializableTokenCache] = None
_msal_app: Optional[PublicClientApplication] = None
_device_code_info: Optional[dict] = None
_cached_token: Optional[str] = None


def _get_cache_file() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "token_cache.json")


def _load_cache() -> SerializableTokenCache:
    global _cache
    if _cache is not None:
        return _cache

    cache = SerializableTokenCache()
    cache_file = _get_cache_file()
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cache.deserialize(json.load(f))
            logger.info(f"Token cache loaded from {cache_file}")
        except Exception as e:
            logger.warning(f"Failed to load token cache: {e}")
    else:
        logger.info("No existing token cache found")

    _cache = cache
    return _cache


def _save_cache() -> None:
    if _cache is None or not _cache.has_state_changed:
        return
    cache_file = _get_cache_file()
    try:
        with open(cache_file, "w") as f:
            json.dump(_cache.serialize(), f)
        logger.info(f"Token cache saved to {cache_file}")
    except Exception as e:
        logger.error(f"Failed to save token cache: {e}")


def _get_msal_app() -> PublicClientApplication:
    global _msal_app
    if _msal_app is not None:
        return _msal_app

    client_id = os.getenv("AZURE_CLIENT_ID")
    tenant_id = os.getenv("AZURE_TENANT_ID", "common")
    if not client_id:
        raise RuntimeError(
            "AZURE_CLIENT_ID environment variable must be set for Outlook integration"
        )

    cache = _load_cache()
    _msal_app = PublicClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )
    return _msal_app


def _acquire_token() -> str:
    """
    Acquire an access token via MSAL.

    Tries silent auth first (uses cached refresh token).
    Falls back to device-code flow if no valid cached token exists.
    """
    global _device_code_info, _cached_token

    app = _get_msal_app()

    # Try silent acquisition first (cached token / refresh token)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache()
            return result["access_token"]

    # Initiate device code flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Failed to initiate device flow: {flow.get('error_description')}")

    _device_code_info = flow
    logger.info(
        f"Device code flow initiated. "
        f"User code: {flow['user_code']}  "
        f"URL: {flow['verification_uri']}"
    )

    # Wait for user to authenticate (blocking; runs in a thread in practice)
    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(
            f"Device code authentication failed: {result.get('error_description')}"
        )

    _save_cache()
    logger.info("Device code authentication successful")
    return result["access_token"]


def _graph_get(path: str) -> dict:
    """Send authenticated GET to Microsoft Graph."""
    token = _acquire_token()
    response = requests.get(
        f"{GRAPH_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _graph_post(path: str, body: dict) -> Optional[dict]:
    """Send authenticated POST to Microsoft Graph."""
    token = _acquire_token()
    response = requests.post(
        f"{GRAPH_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    response.raise_for_status()
    # 202 Accepted (sendMail) returns no body
    if response.status_code == 202 or not response.content:
        return None
    return response.json()


# ---------------------------------------------------------------------------
# Public API — same signatures as before
# ---------------------------------------------------------------------------

def get_graph_client():
    """
    Compatibility shim.  Previously returned a GraphServiceClient.
    Now just warms up the MSAL app and returns None; callers should
    use the read_emails / send_email / read_calendar_events helpers directly.
    """
    _get_msal_app()
    return None


async def read_emails(max_results: int = 10) -> List[Dict[str, Any]]:
    """Read the latest emails from the connected Outlook account."""
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _graph_get(f"/me/messages?$top={max_results}&$orderby=receivedDateTime desc")
        )
        emails = []
        for msg in data.get("value", []):
            from_addr = msg.get("from", {}).get("emailAddress", {})
            emails.append({
                "id": msg.get("id"),
                "subject": msg.get("subject"),
                "from": from_addr.get("address"),
                "to": [r["emailAddress"]["address"] for r in msg.get("toRecipients", [])],
                "received_date_time": msg.get("receivedDateTime"),
                "body_preview": msg.get("bodyPreview"),
                "is_read": msg.get("isRead"),
            })
        logger.info(f"Retrieved {len(emails)} emails")
        _save_cache()
        return emails
    except Exception as e:
        logger.error(f"Failed to read emails: {e}")
        raise RuntimeError(f"Failed to read emails: {e}") from e


async def send_email(to: str, subject: str, body: str) -> Dict[str, Any]:
    """Send an email via the connected Outlook account."""
    try:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        }
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: _graph_post("/me/sendMail", payload)
        )
        logger.info("Email sent successfully")
        _save_cache()
        return {"message": "Email sent successfully"}
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise RuntimeError(f"Failed to send email: {e}") from e


async def read_calendar_events(max_results: int = 10) -> List[Dict[str, Any]]:
    """Read upcoming calendar events from the connected Outlook account."""
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _graph_get(f"/me/events?$top={max_results}&$orderby=start/dateTime")
        )
        events = []
        for ev in data.get("value", []):
            events.append({
                "id": ev.get("id"),
                "subject": ev.get("subject"),
                "start": ev.get("start", {}).get("dateTime"),
                "end": ev.get("end", {}).get("dateTime"),
                "location": ev.get("location", {}).get("displayName"),
                "body_preview": ev.get("bodyPreview"),
            })
        logger.info(f"Retrieved {len(events)} calendar events")
        _save_cache()
        return events
    except Exception as e:
        logger.error(f"Failed to read calendar events: {e}")
        raise RuntimeError(f"Failed to read calendar events: {e}") from e


def get_device_code_info() -> Optional[dict]:
    """Return the current device code authentication info (if active)."""
    return _device_code_info
