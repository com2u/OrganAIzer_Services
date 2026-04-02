"""
esl_client.py — FreeSWITCH Event Socket Layer (ESL) integration.

Provides two capabilities:

1. send_api_command(cmd)  — one-shot inbound ESL command (used by escalation.py).
   Opens a fresh TCP connection to FS, authenticates, sends one `api` command,
   returns the response body.  Never raises.

2. ESLOutboundServer / ESLOutboundHandler — inbound TCP server that accepts
   FreeSWITCH outbound socket connections (one per call) and provides per-call
   ESL control.

   Dialplan side (FS conf/dialplan/...):
       <action application="socket" data="127.0.0.1:8085 async full"/>

   Outbound ESL protocol (FS connects to Python):
     FS → CHANNEL_DATA event (call info)
     Py → connect\n\n
     FS → +OK
     Py → linger\n\n          (keep socket open after hangup for cleanup)
     FS → +OK
     Py → myevents\n\n        (subscribe to events for this channel)
     FS → +OK
     Py → sendmsg commands …
     FS → CHANNEL_EXECUTE_COMPLETE, CHANNEL_HANGUP*, …
"""
from __future__ import annotations

import logging
import os
import socket
import threading
from typing import Callable, Optional

from voice import config

logger = logging.getLogger(__name__)

_TIMEOUT_S = 10
_BUF       = 4096
_ENC       = "utf-8"

# ── persistent inbound ESL connection pool (for send_api_command) ─────────────
# One persistent connection is kept alive and reused across calls.
# If it drops, it is automatically re-established on the next use.
_pool_sock: Optional[socket.socket] = None
_pool_lock: threading.Lock = threading.Lock()


# ── shared packet parser ───────────────────────────────────────────────────────

def _recv_packet(sock: socket.socket, buf: Optional[bytearray] = None) -> tuple[dict[str, str], str]:
    """
    Read one ESL packet from *sock*.

    An ESL packet is:  <headers>\n\n[<body of Content-Length bytes>]

    Returns (headers_dict, body_str).
    Raises ConnectionError if the socket closes mid-read.

    *buf* is an optional bytearray carry-over buffer.  Pass the same object
    on consecutive calls for the same socket so that data over-read from a
    previous call (e.g. the start of the next packet arriving in the same
    TCP segment) is not silently discarded.
    """
    raw = bytes(buf) if buf is not None else b""
    if buf is not None:
        buf.clear()

    while b"\n\n" not in raw:
        chunk = sock.recv(_BUF)
        if not chunk:
            raise ConnectionError("ESL socket closed during read")
        raw += chunk

    head_bytes, _, remainder = raw.partition(b"\n\n")
    headers: dict[str, str] = {}
    for line in head_bytes.decode(_ENC).splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            headers[k.strip()] = v.strip()

    body = ""
    length = int(headers.get("Content-Length", 0))
    if length:
        while len(remainder) < length:
            more = sock.recv(_BUF)
            if not more:
                raise ConnectionError("ESL socket closed while reading body")
            remainder += more
        body = remainder[:length].decode(_ENC, errors="replace")
        if buf is not None:
            buf.extend(remainder[length:])
    else:
        if buf is not None:
            buf.extend(remainder)

    return headers, body


def _parse_event_body(body: str) -> dict[str, str]:
    """Parse a text/event-plain body (key: value lines) into a dict."""
    result: dict[str, str] = {}
    for line in body.splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            result[k.strip()] = v.strip()
    return result


# ── one-shot inbound ESL command ───────────────────────────────────────────────

def _open_esl_connection(host: str, port: int, password: str) -> socket.socket:
    """
    Open and authenticate a new ESL inbound connection.
    Raises on any error (caller handles).
    """
    sock = socket.create_connection((host, port), timeout=_TIMEOUT_S)
    sock.settimeout(_TIMEOUT_S)

    headers, _ = _recv_packet(sock)
    if headers.get("Content-Type") != "auth/request":
        sock.close()
        raise ValueError(f"Unexpected ESL greeting: {headers}")

    sock.sendall(f"auth {password}\n\n".encode(_ENC))
    headers, _ = _recv_packet(sock)
    reply = headers.get("Reply-Text", "")
    if not reply.startswith("+OK"):
        sock.close()
        raise PermissionError(f"ESL auth rejected: {reply!r}")

    return sock


def send_api_command(command: str) -> str:
    """
    Send one API command to FreeSWITCH via a persistent pooled ESL connection.
    The connection is kept alive and reused across calls; if it drops it is
    automatically re-established (one retry).

    Returns "" on any error.  Never raises.

    Examples:
        send_api_command("status")
        send_api_command("uuid_transfer <uuid> 778 XML default")
    """
    global _pool_sock

    host     = config.FREESWITCH_ESL_HOST
    port     = config.FREESWITCH_ESL_PORT
    password = config.FREESWITCH_ESL_PASSWORD

    with _pool_lock:
        for attempt in range(2):
            try:
                if _pool_sock is None:
                    _pool_sock = _open_esl_connection(host, port, password)
                    logger.debug("ESL pool: new connection to %s:%d", host, port)

                _pool_sock.sendall(f"api {command}\n\n".encode(_ENC))
                _, body = _recv_packet(_pool_sock)
                logger.debug("ESL %r → %r", command, body[:200])
                return body

            except Exception as exc:
                logger.warning(
                    "ESL pool command failed (attempt %d/2): %s", attempt + 1, exc
                )
                # Close and discard the broken connection
                if _pool_sock is not None:
                    try:
                        _pool_sock.close()
                    except OSError:
                        pass
                    _pool_sock = None
                # Second attempt falls through to reconnect; after that give up
                if attempt == 1:
                    logger.error("ESL send_api_command(%r) failed: %s", command, exc)
                    return ""

    return ""  # unreachable, satisfies type checkers


# ── ESL outbound handler (one per call) ───────────────────────────────────────

class ESLOutboundHandler:
    """
    Manages one FreeSWITCH outbound socket connection (one call).

    FreeSWITCH connects to our server; we receive the CHANNEL_DATA event,
    complete the ESL handshake, then expose execute() for call control.

    Thread model:
      - The caller thread (call_callback) calls execute() which blocks until
        FreeSWITCH sends CHANNEL_EXECUTE_COMPLETE.
      - A separate _event_reader daemon thread reads all incoming packets and
        dispatches them: sets threading.Events for pending executes, sets
        _hung_up on hangup.
    """

    def __init__(self, sock: socket.socket, addr: tuple) -> None:
        self._sock                  = sock
        self._addr                  = addr
        self._channel_data: dict[str, str] = {}
        self._hung_up               = threading.Event()
        # Serialise sendmsg writes — one command in flight at a time
        self._send_lock             = threading.Lock()
        # app_name → Event that fires on CHANNEL_EXECUTE_COMPLETE
        self._pending_lock          = threading.Lock()
        self._pending: dict[str, threading.Event] = {}
        self._reader: Optional[threading.Thread] = None
        self._recv_buf: bytearray = bytearray()  # carry-over buffer for _recv_packet

    # ── public API ────────────────────────────────────────────────────────────

    def execute(
        self,
        app: str,
        arg: str = "",
        timeout: float = 10.0,
    ) -> bool:
        """
        Tell FreeSWITCH to execute *app* with *arg* on this channel.
        Blocks until CHANNEL_EXECUTE_COMPLETE arrives or *timeout* / hangup.

        Returns True on successful completion, False on timeout or hangup.
        """
        if self._hung_up.is_set():
            return False

        evt = threading.Event()
        with self._pending_lock:
            self._pending[app] = evt

        msg = (
            f"sendmsg\n"
            f"call-command: execute\n"
            f"execute-app-name: {app}\n"
            f"execute-app-arg: {arg}\n"
            f"event-lock: true\n"
            f"\n"
        )
        try:
            with self._send_lock:
                self._sock.sendall(msg.encode(_ENC))
        except OSError as exc:
            logger.warning("execute(%s): send failed: %s", app, exc)
            with self._pending_lock:
                self._pending.pop(app, None)
            return False

        # Wait for completion or hangup
        done = False
        deadline = timeout
        step   = 0.1
        while deadline > 0:
            if evt.wait(timeout=min(step, deadline)):
                done = True
                break
            if self._hung_up.is_set():
                break
            deadline -= step

        with self._pending_lock:
            self._pending.pop(app, None)

        if not done and not self._hung_up.is_set():
            logger.warning("execute(%s): timed out after %.1fs", app, timeout)
        return done

    def hangup(self, cause: str = "NORMAL_CLEARING") -> None:
        """Send hangup to FreeSWITCH. Safe to call multiple times."""
        if self._hung_up.is_set():
            return
        msg = (
            f"sendmsg\n"
            f"call-command: execute\n"
            f"execute-app-name: hangup\n"
            f"execute-app-arg: {cause}\n"
            f"\n"
        )
        try:
            with self._send_lock:
                self._sock.sendall(msg.encode(_ENC))
        except OSError:
            pass

    def get_uuid(self) -> str:
        """Return the channel UUID from CHANNEL_DATA."""
        return (
            self._channel_data.get("Caller-Unique-ID")
            or self._channel_data.get("Unique-ID")
            or ""
        )

    def get_caller_id(self) -> str:
        """Return caller number from CHANNEL_DATA."""
        return (
            self._channel_data.get("Caller-Caller-ID-Number")
            or self._channel_data.get("Caller-ANI")
            or ""
        )

    def get_caller_name(self) -> str:
        """Return caller display name from CHANNEL_DATA (may be empty)."""
        return self._channel_data.get("Caller-Caller-ID-Name", "")

    def wait_for_hangup(self, timeout: Optional[float] = None) -> bool:
        """Block until the call hangs up. Returns True if hung up."""
        return self._hung_up.wait(timeout=timeout)

    @property
    def is_hung_up(self) -> bool:
        return self._hung_up.is_set()

    # ── internal ──────────────────────────────────────────────────────────────

    def _handshake(self) -> None:
        """
        Perform the ESL outbound handshake (FS connects TO Python).

        ESL outbound protocol — Python MUST send first:
          1. Send: connect\n\n          (initiate; FS waits for this)
          2. Receive: CHANNEL_DATA      (text/event-plain with channel vars)
          3. Send: linger\n\n
          4. Receive: +OK
          5. Send: myevents\n\n
          6. Receive: +OK

        FS does NOT send anything on connect; it waits for the app to send
        "connect".  Waiting to read first causes a 25-second deadlock until
        FS times out and closes the socket.
        """
        # Initiate handshake — must send before reading anything
        self._sock.sendall(b"connect\n\n")
        logger.debug("ESL: sent connect, waiting for CHANNEL_DATA")

        # Read CHANNEL_DATA reply (or consume +OK if FS sends it first)
        headers, body = _recv_packet(self._sock, self._recv_buf)
        logger.debug("ESL: connect reply Content-Type=%r body_len=%d",
                     headers.get("Content-Type"), len(body))

        content_type = headers.get("Content-Type", "")
        if content_type == "command/reply":
            if headers.get("Unique-ID"):
                # Channel vars are embedded in the command/reply headers — use them directly
                self._channel_data.update(headers)
            else:
                # FS sent +OK first; CHANNEL_DATA arrives as the next packet
                headers, body = _recv_packet(self._sock, self._recv_buf)
                content_type = headers.get("Content-Type", "")
                if content_type == "text/event-plain":
                    self._channel_data.update(_parse_event_body(body))
                else:
                    self._channel_data.update(headers)
        elif content_type == "text/event-plain":
            self._channel_data.update(_parse_event_body(body))
        else:
            # Fallback: treat headers themselves as channel vars
            self._channel_data.update(headers)

        # linger — keep socket open after hangup for cleanup events
        self._sock.sendall(b"linger\n\n")
        _recv_packet(self._sock, self._recv_buf)

        # myevents — subscribe to all events for this channel
        self._sock.sendall(b"myevents\n\n")
        _recv_packet(self._sock, self._recv_buf)

        logger.debug(
            "ESL handshake complete: uuid=%s caller=%s",
            self.get_uuid(), self.get_caller_id(),
        )

    def _event_reader(self) -> None:
        """
        Daemon thread: read ESL packets forever, dispatch events.
        Sets _hung_up on CHANNEL_HANGUP / CHANNEL_HANGUP_COMPLETE.
        Wakes pending execute() callers on CHANNEL_EXECUTE_COMPLETE.
        """
        while not self._hung_up.is_set():
            try:
                headers, body = _recv_packet(self._sock, self._recv_buf)
            except socket.timeout:
                # 30 s idle — socket alive but no FS events (normal during hold/park).
                # Loop back and keep waiting; if the call really died FS will close.
                logger.debug("ESL event reader: socket idle (30 s timeout), continuing")
                continue
            except (ConnectionError, OSError) as exc:
                logger.debug("ESL event reader closed: %s", exc)
                self._hung_up.set()
                self._wake_all_pending()
                break

            content_type = headers.get("Content-Type", "")

            if content_type == "text/event-plain":
                event = _parse_event_body(body)
                event_name = event.get("Event-Name", "")

                if event_name in ("CHANNEL_HANGUP", "CHANNEL_HANGUP_COMPLETE"):
                    logger.debug("ESL: %s uuid=%s", event_name, self.get_uuid())
                    self._hung_up.set()
                    self._wake_all_pending()
                    break

                if event_name == "CHANNEL_EXECUTE_COMPLETE":
                    app = event.get("Application", "")
                    logger.debug("ESL: CHANNEL_EXECUTE_COMPLETE app=%s", app)
                    with self._pending_lock:
                        evt = self._pending.get(app)
                    if evt:
                        evt.set()

            elif content_type == "command/reply":
                # General +OK / -ERR replies — nothing to dispatch
                pass

    def _wake_all_pending(self) -> None:
        """Unblock all waiting execute() calls (called on hangup)."""
        with self._pending_lock:
            for evt in self._pending.values():
                evt.set()

    def run_handshake_and_start_reader(self) -> None:
        """
        Called by ESLOutboundServer after accepting the connection.
        Performs handshake then starts the background event reader thread.
        Does NOT block — returns immediately after starting the reader.
        """
        self._handshake()
        # Set a read timeout so _event_reader doesn't block forever if the
        # socket freezes (e.g. network partition without a RST).
        # socket.timeout is caught in _event_reader and treated as idle.
        self._sock.settimeout(30.0)
        self._reader = threading.Thread(
            target=self._event_reader,
            name=f"esl-reader-{self.get_uuid()[:8] or 'unknown'}",
            daemon=True,
        )
        self._reader.start()


# ── ESL outbound server ────────────────────────────────────────────────────────

class ESLOutboundServer:
    """
    TCP server that listens for FreeSWITCH outbound socket connections.

    For each connection (one per call) it:
      1. Creates an ESLOutboundHandler.
      2. Runs the ESL handshake.
      3. Calls call_callback(handler) in a dedicated daemon thread.

    Usage (from main.py lifespan):
        server = ESLOutboundServer(port=8085, call_callback=handle_esl_call)
        server.start_background()
        ...
        server.stop()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8085,
        call_callback: Optional[Callable[["ESLOutboundHandler"], None]] = None,
    ) -> None:
        self._host          = host
        self._port          = port
        self._call_callback = call_callback
        self._server_sock: Optional[socket.socket] = None
        self._stop_event    = threading.Event()

    def start(self) -> None:
        """Bind, listen, and block in the accept loop until stop() is called."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self._host, self._port))
        self._server_sock.listen(20)
        self._server_sock.settimeout(1.0)  # allows periodic stop check
        logger.info(
            "ESL Outbound Server listening on %s:%d", self._host, self._port
        )
        while not self._stop_event.is_set():
            try:
                conn, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(
                target=self._handle_connection,
                args=(conn, addr),
                daemon=True,
                name=f"esl-call-{addr[1]}",
            )
            t.start()
        try:
            self._server_sock.close()
        except OSError:
            pass
        logger.info("ESL Outbound Server stopped.")

    def start_background(self) -> threading.Thread:
        """Start the server in a daemon thread. Returns the thread."""
        t = threading.Thread(
            target=self.start,
            name="esl-outbound-server",
            daemon=True,
        )
        t.start()
        return t

    def stop(self) -> None:
        """Signal the accept loop to exit and close the server socket."""
        self._stop_event.set()
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass

    def _handle_connection(self, conn: socket.socket, addr: tuple) -> None:
        """Per-call thread: handshake then invoke the call callback."""
        handler = ESLOutboundHandler(conn, addr)
        try:
            handler.run_handshake_and_start_reader()
            logger.info(
                "ESL inbound call: uuid=%s caller=%s",
                handler.get_uuid(), handler.get_caller_id(),
            )
            if self._call_callback:
                self._call_callback(handler)
        except Exception as exc:
            logger.error(
                "ESL call handler error (addr=%s): %s", addr, exc, exc_info=True
            )
            try:
                handler.hangup()
            except Exception:
                pass
        finally:
            # After linger, we close the socket — FS cleans up its side
            try:
                conn.close()
            except OSError:
                pass
