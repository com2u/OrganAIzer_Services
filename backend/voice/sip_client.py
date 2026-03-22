"""
sip_client.py — registers the AI as a SIP extension on COMtrexx
and dispatches inbound calls to call_handler.

Usage (from main.py lifespan):
    from voice.sip_client import SIPClient
    client = SIPClient()
    client.start()   # non-blocking — runs pyVoIP in daemon threads
    ...
    client.stop()

Outbound calls (Phase 4+):
    call = client.dial("+49xxxxxxxxx")
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from pyVoIP.VoIP import VoIPPhone, VoIPCall, CallState
from pyVoIP.VoIP.status import PhoneStatus

from voice import config
from voice.call_handler import handle_call

logger = logging.getLogger(__name__)

# Imported lazily to avoid a circular import at module level
_phone_state: Optional[dict] = None


def _get_phone_state() -> dict:
    """Lazy import of the shared state dict from api/phone.py."""
    global _phone_state
    if _phone_state is None:
        from api.phone import phone_state
        _phone_state = phone_state
    return _phone_state


class SIPClient:
    """
    Thin wrapper around pyVoIP.VoIPPhone that:
      - validates credentials before attempting registration
      - keeps phone_state in sync with registration status
      - dispatches each inbound call to call_handler in its own thread
      - provides a dial() method for outbound calls
    """

    def __init__(self) -> None:
        self._phone: Optional[VoIPPhone] = None
        self._lock  = threading.Lock()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Start SIP registration.  Safe to call even when credentials are not
        yet configured — logs a warning and returns without raising.
        """
        missing = config.validate()
        if missing:
            logger.warning(
                "SIP client not started — missing env vars: %s. "
                "Fill them in backend/.env and restart.",
                ", ".join(missing),
            )
            return

        try:
            logger.info(
                "Registering SIP: %s@%s:%d (extension %s)",
                config.COMTREXX_SIP_USER,
                config.COMTREXX_SIP_DOMAIN,
                config.COMTREXX_SIP_PORT,
                config.COMTREXX_EXTENSION,
            )
            self._phone = VoIPPhone(
                server=config.COMTREXX_IP,
                port=config.COMTREXX_SIP_PORT,
                username=config.COMTREXX_SIP_USER,
                password=config.COMTREXX_SIP_PASS,
                callCallback=self._on_call,
                sipPort=5060,
                rtpPortLow=10000,
                rtpPortHigh=20000,
            )
            self._phone.start()

            # Update shared state for the /api/phone/status endpoint
            state = _get_phone_state()
            state["registered"] = True
            state["extension"]  = config.COMTREXX_EXTENSION
            state["server"]     = f"{config.COMTREXX_IP}:{config.COMTREXX_SIP_PORT}"

            logger.info(
                "SIP registered — extension %s on %s",
                config.COMTREXX_EXTENSION,
                config.COMTREXX_IP,
            )

        except Exception as exc:
            logger.error("SIP registration failed: %s", exc, exc_info=True)
            self._phone = None
            state = _get_phone_state()
            state["registered"] = False

    def stop(self) -> None:
        """Deregister and stop the SIP client."""
        with self._lock:
            if self._phone is not None:
                try:
                    self._phone.stop()
                    logger.info("SIP client stopped.")
                except Exception as exc:
                    logger.error("Error stopping SIP client: %s", exc)
                finally:
                    self._phone = None

        state = _get_phone_state()
        state["registered"]  = False
        state["active_call"] = None

    def is_registered(self) -> bool:
        if self._phone is None:
            return False
        try:
            return self._phone.get_status() == PhoneStatus.REGISTERED
        except Exception:
            return False

    # ── outbound ──────────────────────────────────────────────────────────────

    def dial(self, number: str) -> Optional[VoIPCall]:
        """
        Initiate an outbound call.  Returns the VoIPCall object or None on error.
        The call starts in DIALING state; call_handler.handle_call() should be
        invoked in a separate thread to run the conversation loop.
        """
        if self._phone is None:
            logger.error("dial() called but SIP client is not started.")
            return None
        try:
            logger.info("Dialing %s", number)
            call = self._phone.call(number)
            return call
        except Exception as exc:
            logger.error("Failed to dial %s: %s", number, exc)
            return None

    # ── inbound callback ──────────────────────────────────────────────────────

    def _on_call(self, call: VoIPCall) -> None:
        """
        pyVoIP calls this in a Timer thread when an inbound call arrives.
        Must return quickly — spawn a thread for the actual handling.
        """
        logger.info("Inbound call received — state: %s", call.state)
        state = _get_phone_state()

        # Reject if a call is already in progress
        if state.get("active_call") is not None:
            logger.info("Already in a call — rejecting new inbound call.")
            try:
                call.deny()
            except Exception:
                pass
            return

        t = threading.Thread(
            target=handle_call,
            args=(call, state),
            name="ai-call-handler",
            daemon=True,
        )
        t.start()
