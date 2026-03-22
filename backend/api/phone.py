"""
Phone API — status, contacts, and dial endpoints for the AI voice-call module.

Endpoints:
  GET  /api/phone/status    — SIP registration state + active call info
  GET  /api/phone/contacts  — contact list loaded from AI_Phone_Contacts.xlsx
  POST /api/phone/dial      — initiate an outbound call (503 until Phase 3)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from voice import contacts as _contacts

logger = logging.getLogger(__name__)

router = APIRouter(tags=["phone"])

# ── shared state ──────────────────────────────────────────────────────────────
# sip_client.py (Phase 3) will import and mutate this dict when registration
# state or an active call changes.  All values here are safe offline defaults.
phone_state: dict = {
    "registered":   False,
    "extension":    "",
    "server":       "",
    "active_call":  None,   # None or {"caller": str, "started_at": str}
}


# ── models ────────────────────────────────────────────────────────────────────

class ActiveCall(BaseModel):
    caller: str
    caller_name: Optional[str] = None
    started_at: str            # ISO-8601


class PhoneStatus(BaseModel):
    registered: bool
    extension: str
    server: str
    active_call: Optional[ActiveCall] = None


class ContactEntry(BaseModel):
    name: str
    number: str
    status: str


class DialRequest(BaseModel):
    number: str
    display_name: Optional[str] = None


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=PhoneStatus)
async def get_status() -> PhoneStatus:
    """
    Return the current SIP registration state and active call information.
    Returns registered=False with empty fields until SIP is configured (Phase 3).
    """
    raw_call = phone_state.get("active_call")
    active: Optional[ActiveCall] = None
    if raw_call:
        active = ActiveCall(
            caller=raw_call.get("caller", ""),
            caller_name=raw_call.get("caller_name"),
            started_at=raw_call.get("started_at", ""),
        )

    return PhoneStatus(
        registered=phone_state.get("registered", False),
        extension=phone_state.get("extension", ""),
        server=phone_state.get("server", ""),
        active_call=active,
    )


@router.get("/contacts", response_model=list[ContactEntry])
async def get_contacts() -> list[ContactEntry]:
    """
    Return all contacts loaded from AI_Phone_Contacts.xlsx.
    Returns an empty list if the file has not been placed yet.
    """
    try:
        entries = _contacts.all_contacts()
    except Exception as exc:
        logger.error("Error loading contacts: %s", exc)
        return []

    return [
        ContactEntry(name=c["name"], number=c["number"], status=c["status"])
        for c in entries
    ]


@router.post("/dial")
async def dial(request: DialRequest):
    """
    Initiate an outbound call.
    Returns 503 until the SIP client is wired up in Phase 3.
    """
    logger.info("Dial request for %s (%s) — SIP not yet connected",
                request.number, request.display_name or "")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "SIP_NOT_CONNECTED",
            "message": (
                "SIP client is not registered yet. "
                "Set COMTREXX_SIP_USER, COMTREXX_SIP_PASS, and COMTREXX_EXTENSION "
                "in backend/.env and restart the server."
            ),
        },
    )
