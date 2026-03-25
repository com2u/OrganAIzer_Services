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
import socket as _socket
import threading
import time
from typing import Optional

import pyVoIP
from pyVoIP.VoIP import VoIPPhone, VoIPCall, CallState
from pyVoIP.VoIP import PhoneStatus

from voice import config
from voice.call_handler import handle_call

logger = logging.getLogger(__name__)

# Route pyVoIP's internal debug() calls to our logger so we can see
# the actual SIP messages exchanged with the PBX.
def _pyvoip_debug_to_logger(msg, exc=None):
    if exc is not None:
        logger.debug("pyVoIP: %s", exc)
    else:
        logger.debug("pyVoIP: %s", msg)

import pyVoIP as _pyvoip_module
import pyVoIP.SIP as _pv_sip
import pyVoIP.VoIP as _pv_voip
import hashlib as _hashlib
import uuid as _uuid

# Route pyVoIP debug output to our logger.
# IMPORTANT: SIP.py and VoIP.py do `debug = pyVoIP.debug` at *import time*, so
# replacing pyVoIP.debug afterward has no effect on their local binding.
# We must also patch the module-level names in SIP and VoIP directly.
_pyvoip_module.debug = _pyvoip_debug_to_logger
_pyvoip_module.DEBUG = True  # enable so internal guards don't short-circuit
_pv_sip.debug = _pyvoip_debug_to_logger
_pv_voip.debug = _pyvoip_debug_to_logger

# ── COMtrexx SIP auth compatibility patch ─────────────────────────────────────
# pyVoIP 1.6.4 hardcodes ";transport=UDP" in two places for REGISTER:
#   1. The HA2 digest computation  →  MD5("REGISTER:sip:<server>;transport=UDP")
#   2. The Authorization header    →  uri="sip:<server>;transport=UDP"
#
# COMtrexx (and many strict PBXes) expect the plain URI without the transport
# parameter, causing a second 401 that pyVoIP surfaces as "Invalid Username or
# Password" — even when credentials are correct.
#
# Fix: patch gen_authorization so HA2 uses bare sip:<server>, and wrap
# gen_register to strip ";transport=UDP" from the Authorization uri= field.
# Both must match for the digest to verify correctly.

def _patched_gen_authorization(self, request):
    realm = request.authentication["realm"]
    nonce = request.authentication["nonce"]
    method = request.headers["CSeq"]["method"]
    uri = f"sip:{self.server}"  # no ;transport=UDP

    HA1 = _hashlib.md5(
        f"{self.username}:{realm}:{self.password}".encode("utf8")
    ).hexdigest()
    HA2 = _hashlib.md5(
        f"{method}:{uri}".encode("utf8")
    ).hexdigest()

    qop_raw = request.authentication.get("qop", "")
    if "auth" in qop_raw:
        # RFC 2617 qop=auth: response = MD5(HA1:nonce:nc:cnonce:qop:HA2)
        cnonce = _uuid.uuid4().hex[:16]
        nc = "00000001"
        self._digest_cnonce = cnonce
        self._digest_nc = nc
        self._digest_qop = "auth"
        return _hashlib.md5(
            f"{HA1}:{nonce}:{nc}:{cnonce}:auth:{HA2}".encode("utf8")
        ).hexdigest().encode("utf8")
    else:
        # RFC 2069 fallback (no qop in challenge)
        self._digest_cnonce = None
        self._digest_nc = None
        self._digest_qop = None
        return _hashlib.md5(
            f"{HA1}:{nonce}:{HA2}".encode("utf8")
        ).hexdigest().encode("utf8")

_orig_gen_register = _pv_sip.SIPClient.gen_register

def _patched_gen_register(self, request, deregister=False):
    result = _orig_gen_register(self, request, deregister)
    # Strip ;transport=UDP from the Authorization uri= field (HA2 also uses bare URI)
    result = result.replace(
        f'uri="sip:{self.server};transport=UDP"',
        f'uri="sip:{self.server}"',
    )
    # Inject qop/nc/cnonce/opaque when RFC 2617 qop=auth was used
    if getattr(self, "_digest_qop", None) == "auth":
        cnonce = self._digest_cnonce
        nc = self._digest_nc
        opaque = request.authentication.get("opaque", "")
        extra = f',qop=auth,nc={nc},cnonce="{cnonce}"'
        if opaque:
            extra += f',opaque="{opaque}"'
        result = result.replace(",algorithm=MD5\r\n", f"{extra},algorithm=MD5\r\n")
        logger.debug(
            "SIP Authorization (RFC 2617 qop=auth): username=%s registrar=%s "
            "realm=%s uri=sip:%s qop=auth nc=%s cnonce=%s opaque=%s algorithm=MD5",
            self.username, self.server,
            request.authentication.get("realm", ""),
            self.server, nc, cnonce, opaque or "(none)",
        )
    else:
        logger.debug(
            "SIP Authorization (RFC 2069, no qop): username=%s registrar=%s "
            "realm=%s uri=sip:%s algorithm=MD5",
            self.username, self.server,
            request.authentication.get("realm", ""),
            self.server,
        )
    return result

def _patched_handle_bad_request(self):
    # pyVoIP's default silently does nothing, then falls through to raise
    # InvalidAccountInfoError("Invalid Username or Password") — completely wrong
    # for a transport error.  Raise a clear exception immediately instead.
    # The full PBX response (including reason phrase) is visible at DEBUG level
    # in the lines logged just before this is called.
    raise RuntimeError(
        "PBX rejected REGISTER with 400 Bad Request. "
        "COMtrexx sends this with reason 'Use SIP/TLS' when the device/softphone "
        "account is configured to require TLS. "
        "To test over UDP: in COMtrexx open the device settings for this softphone "
        "and disable the 'Secure SIP (TLS)' / 'SIPS' option. "
        "Note: pyVoIP 1.6.4 is UDP-only — TLS is not supported by this library."
    )

_pv_sip.SIPClient.gen_authorization = _patched_gen_authorization
_pv_sip.SIPClient.genAuthorization = _patched_gen_authorization  # deprecated alias
_pv_sip.SIPClient.gen_register = _patched_gen_register
_pv_sip.SIPClient._handle_bad_request = _patched_handle_bad_request
# genRegister delegates to self.gen_register → patching gen_register is enough

# Imported lazily to avoid a circular import at module level
_phone_state: Optional[dict] = None

# pyVoIP schedules its own re-registration at (default_expires - 5) = 115s.
# We check at 90s so we only reconnect if pyVoIP's own re-register failed.
_WATCHDOG_INTERVAL  = 90
# pyVoIP leaves the SIP socket non-blocking after __register().
# Its recv_loop (started with Timer(1, ...)) resets it to blocking after ~1s.
# We wait this long after phone.start() before allowing dial().
_POST_REGISTER_WAIT = 2.0   # seconds
# Timeout applied to the SIP socket so invite()'s recv() never hangs forever.
_SIP_RECV_TIMEOUT   = 30.0  # seconds
_WSAENOTSOCK        = 10038
_WSAEWOULDBLOCK     = 10035


def _resolve_registrar_host() -> str:
    """Return the SIP registrar host used by pyVoIP REGISTER/INVITE requests."""
    return (config.COMTREXX_SIP_DOMAIN or config.COMTREXX_IP).strip()


def _resolve_host_ip(host: str) -> str:
    """Resolve *host* to an IPv4 address for logging/debugging."""
    try:
        return _socket.gethostbyname(host)
    except Exception:
        return host


def _detect_local_ip(remote: str) -> str:
    """Return the local IP that would be used to reach *remote*."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect((remote, 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


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
      - watchdog thread detects silent socket death and reconnects
    """

    def __init__(self) -> None:
        self._phone: Optional[VoIPPhone] = None
        self._lock        = threading.Lock()
        self._stop_event  = threading.Event()

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

        self._stop_event.clear()
        self._register()

        # Watchdog: detects silent socket death and reconnects
        t = threading.Thread(
            target=self._watchdog_loop,
            name="sip-watchdog",
            daemon=True,
        )
        t.start()

    def _register(self) -> bool:
        """Create and start a VoIPPhone instance. Returns True on success."""
        try:
            registrar_host = _resolve_registrar_host()
            registrar_ip = _resolve_host_ip(registrar_host)
            local_ip = config.COMTREXX_LOCAL_IP or _detect_local_ip(registrar_host)
            if local_ip == "0.0.0.0":
                logger.warning(
                    "Could not determine a specific local SIP bind IP for registrar %s; "
                    "pyVoIP will bind to %s.",
                    registrar_host,
                    local_ip,
                )
            logger.info(
                "Registering SIP over UDP: username=%s, auth_username=%s, registrar=%s, "
                "resolved_server=%s, port=%d, extension=%s, local_bind=%s:%d",
                config.COMTREXX_SIP_USER,
                config.COMTREXX_SIP_USER,
                registrar_host,
                registrar_ip,
                config.COMTREXX_SIP_PORT,
                config.COMTREXX_EXTENSION,
                local_ip,
                config.COMTREXX_LOCAL_SIP_PORT,
            )
            phone = VoIPPhone(
                server=registrar_host,
                port=config.COMTREXX_SIP_PORT,
                username=config.COMTREXX_SIP_USER,
                password=config.COMTREXX_SIP_PASS,
                myIP=local_ip,
                callCallback=self._on_call,
                sipPort=config.COMTREXX_LOCAL_SIP_PORT,
                rtpPortLow=10000,
                rtpPortHigh=20000,
            )
            phone.start()
            # pyVoIP's recv_loop starts after a 1-second Timer and resets the
            # SIP socket from non-blocking back to blocking.  Wait for it so
            # the socket is ready for an immediate dial() call.
            time.sleep(_POST_REGISTER_WAIT)
            # Apply a recv timeout so invite() never blocks indefinitely if the
            # PBX stops responding (e.g. 0.0.0.0 contact issue is now fixed,
            # but belt-and-suspenders guard against any future network hiccup).
            try:
                phone.sip.s.settimeout(_SIP_RECV_TIMEOUT)
            except Exception:
                pass
            with self._lock:
                self._phone = phone

            # Poll until COMtrexx confirms registration (200 OK to REGISTER).
            # pyVoIP is async — phone.start() fires the REGISTER but the PBX
            # 401-challenge / re-auth roundtrip may take several seconds.
            # We wait up to 10 s; if still only REGISTERING at that point the
            # PBX has not accepted us and we treat it as a failure.
            confirmed = self._wait_for_confirmed_registration(max_wait=10.0)

            state = _get_phone_state()
            if not confirmed:
                logger.error(
                    "SIP registration not confirmed by PBX after 10 s — "
                    "check credentials, domain, and network reachability."
                )
                try:
                    phone.stop()
                except Exception:
                    pass
                with self._lock:
                    self._phone = None
                state["registered"] = False
                return False

            state["registered"] = True
            state["extension"]  = config.COMTREXX_EXTENSION
            state["server"]     = f"{registrar_host}:{config.COMTREXX_SIP_PORT}"

            logger.info(
                "SIP registered — extension %s on %s",
                config.COMTREXX_EXTENSION,
                registrar_host,
            )
            return True

        except Exception as exc:
            logger.error(
                "SIP registration failed: registrar=%s resolved_server=%s port=%d "
                "username=%s local_ip=%s extension=%s error=%s",
                _resolve_registrar_host(),
                _resolve_host_ip(_resolve_registrar_host()),
                config.COMTREXX_SIP_PORT,
                config.COMTREXX_SIP_USER,
                config.COMTREXX_LOCAL_IP or "auto",
                config.COMTREXX_EXTENSION,
                exc,
                exc_info=True,
            )
            with self._lock:
                self._phone = None
            _get_phone_state()["registered"] = False
            return False

    def _reconnect(self) -> bool:
        """Tear down the current phone instance and re-register."""
        logger.warning("SIP reconnect triggered — tearing down old socket…")
        with self._lock:
            if self._phone is not None:
                try:
                    self._phone.stop()
                except Exception:
                    pass
                self._phone = None
        return self._register()

    def _watchdog_loop(self) -> None:
        """Periodically verify the SIP socket is alive; reconnect if not."""
        while not self._stop_event.wait(timeout=_WATCHDOG_INTERVAL):
            if not self.is_registered():
                logger.warning("SIP watchdog: socket appears dead — reconnecting…")
                self._reconnect()

    def stop(self) -> None:
        """Deregister and stop the SIP client."""
        self._stop_event.set()
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
        state["bridge_call"] = None

    def is_registered(self) -> bool:
        """Return True only when COMtrexx has confirmed registration (REGISTERED state)."""
        if self._phone is None:
            return False
        try:
            status = self._phone.get_status()
            if status == PhoneStatus.REGISTERED:
                return True
            logger.debug("SIP status: %s", status)
            return False
        except Exception:
            return False

    def _wait_for_confirmed_registration(self, max_wait: float = 10.0) -> bool:
        """
        Poll pyVoIP status until the PBX confirms registration (REGISTERED),
        or until max_wait seconds elapse.  Returns True on success.
        Bails out immediately if pyVoIP transitions to FAILED or INACTIVE
        (which means it has given up after hitting REGISTER_FAILURE_THRESHOLD).
        """
        _terminal = {PhoneStatus.FAILED, PhoneStatus.INACTIVE}
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            with self._lock:
                ph = self._phone
            if ph is not None:
                try:
                    s = ph.get_status()
                    if s == PhoneStatus.REGISTERED:
                        return True
                    if s in _terminal:
                        logger.error(
                            "SIP registration failed — pyVoIP status is %s "
                            "(check credentials and enable DEBUG logging for "
                            "the full SIP exchange).",
                            s.value,
                        )
                        return False
                    logger.debug("Waiting for SIP registration — current status: %s", s)
                except Exception:
                    pass
            time.sleep(0.2)
        return False

    # ── outbound ──────────────────────────────────────────────────────────────

    @staticmethod
    def _sip_socket_valid(phone: VoIPPhone) -> bool:
        """Return True if phone's SIP socket is open and usable."""
        try:
            return phone.sip.s is not None and phone.sip.s.fileno() != -1
        except Exception:
            return False

    def _wait_for_sip_socket(self, max_wait: float = 3.0) -> bool:
        """Poll until the SIP socket reports a valid fileno, or timeout."""
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            with self._lock:
                ph = self._phone
            if ph is not None and self._sip_socket_valid(ph):
                return True
            time.sleep(0.1)
        logger.warning("SIP socket did not become ready within %.1fs", max_wait)
        return False

    def dial(self, number: str) -> Optional[VoIPCall]:
        """
        Initiate an outbound call.  Returns the VoIPCall object or None on error.
        Automatically reconnects once if the SIP socket has silently died
        (WinError 10038 / WSAENOTSOCK).
        """
        for attempt in range(2):
            with self._lock:
                phone = self._phone
            if phone is None:
                logger.error("dial() called but SIP client is not started.")
                return None
            try:
                logger.info("Dialing %s (attempt %d)", number, attempt + 1)
                return phone.call(number)
            except OSError as exc:
                if exc.winerror in (_WSAENOTSOCK, _WSAEWOULDBLOCK) and attempt == 0:
                    if exc.winerror == _WSAENOTSOCK:
                        logger.warning(
                            "Dial failed — dead socket (WinError 10038). Reconnecting…"
                        )
                        if not self._reconnect():
                            logger.error("Reconnect failed; cannot dial %s.", number)
                            return None
                    else:
                        logger.warning(
                            "Dial failed — socket not ready (WinError 10035). "
                            "Waiting %gs…", _POST_REGISTER_WAIT
                        )
                        time.sleep(_POST_REGISTER_WAIT)
                    # Poll until pyVoIP's socket is truly ready before retrying.
                    # _register() already sleeps _POST_REGISTER_WAIT, but the
                    # recv_loop thread may still be resetting sip.s at that point.
                    if not self._wait_for_sip_socket():
                        logger.error(
                            "SIP socket never became ready; cannot dial %s.", number
                        )
                        return None
                else:
                    logger.error("Failed to dial %s: %s", number, exc)
                    return None
            except TimeoutError:
                logger.error(
                    "Dial %s timed out after %gs — PBX did not respond to INVITE.",
                    number, _SIP_RECV_TIMEOUT,
                )
                return None
            except Exception as exc:
                logger.error("Failed to dial %s: %s", number, exc)
                return None
        return None

    # ── inbound callback ──────────────────────────────────────────────────────

    def _on_call(self, call: VoIPCall) -> None:
        """
        pyVoIP calls this in a Timer thread when an inbound call arrives.
        Must return quickly — spawn a thread for the actual handling.
        """
        logger.info("Inbound call received — state: %s", call.state)
        state = _get_phone_state()

        # Reject if a call is already in progress or a decision is pending
        if state.get("active_call") is not None or state.get("ringing_call") is not None:
            logger.info("Already busy — rejecting new inbound call.")
            try:
                call.deny()
            except Exception:
                pass
            return

        t = threading.Thread(
            target=self._screen_and_handle,
            args=(call, state),
            name="ai-call-screen",
            daemon=True,
        )
        t.start()

    def _screen_and_handle(self, call: VoIPCall, state: dict) -> None:
        """
        Wait for the operator to decide whether the AI or the human answers.
        Runs in a daemon thread so _on_call() returns immediately.
        """
        from datetime import datetime, timezone
        from api.phone import wait_for_ring_decision
        from voice import config as _cfg

        # ── identify caller ───────────────────────────────────────────────────
        caller = ""
        try:
            caller = call.request.headers.get("From", "")
            if "<sip:" in caller:
                caller = caller.split("<sip:")[1].split("@")[0].split(">")[0]
            elif "sip:" in caller:
                caller = caller.split("sip:")[1].split("@")[0]
        except Exception:
            caller = "unknown"

        from voice import contacts as _contacts
        contact = _contacts.lookup_by_number(caller)
        caller_name = contact["name"] if contact else None
        display = caller_name or caller

        logger.info(
            "Inbound from %s (%s) — waiting %ds for operator decision…",
            caller, caller_name or "unknown", _cfg.AI_RING_TIMEOUT_SECONDS,
        )

        # ── advertise ringing state for the frontend ──────────────────────────
        state["ringing_call"] = {
            "caller":        caller,
            "caller_name":   caller_name,
            "ringing_since": datetime.now(timezone.utc).isoformat(),
            "direction":     "inbound",
        }

        # ── wait for operator or timeout ──────────────────────────────────────
        decision = wait_for_ring_decision(timeout=float(_cfg.AI_RING_TIMEOUT_SECONDS))
        state["ringing_call"] = None

        if decision == "human":
            logger.info("Operator takes the call from %s — answering and bridging audio.", display)
            import time
            from datetime import datetime, timezone
            from voice import call_log as _call_log

            started_at = datetime.now(timezone.utc)
            try:
                call.answer()
            except Exception as exc:
                logger.error("Could not answer call for bridge: %s", exc)
                return

            state["active_call"] = {
                "caller":      caller,
                "caller_name": caller_name,
                "started_at":  started_at.isoformat(),
                "mode":        "human",
            }
            state["bridge_call"] = call

            # Keep thread alive until call ends; WebSocket bridge reads/writes audio
            while call.state != CallState.ENDED:
                time.sleep(0.5)

            state["bridge_call"]  = None
            state["active_call"]  = None
            ended_at = datetime.now(timezone.utc)
            _call_log.record(
                caller=caller,
                caller_name=caller_name,
                direction="inbound",
                started_at=started_at,
                ended_at=ended_at,
                turn_count=0,
            )
            logger.info(
                "Bridged inbound call ended: %s  duration=%ds",
                display,
                int((ended_at - started_at).total_seconds()),
            )
            return

        # decision == "ai" (or timed out) → AI handles it
        logger.info("AI answering call from %s", display)
        handle_call(call, state)
