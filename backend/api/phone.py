"""
Phone API — status, contacts, and dial endpoints for the AI voice-call module.

Endpoints:
  GET  /api/phone/status    — SIP registration state + active call info
  GET  /api/phone/contacts  — contact list loaded from AI_Phone_Contacts.xlsx
  POST /api/phone/dial      — initiate an outbound call (503 until Phase 3)
"""

import asyncio
import logging
import queue as _queue
import re
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from voice import contacts as _contacts
from voice.call_trigger import is_german_number, mask_number

logger = logging.getLogger(__name__)

router = APIRouter(tags=["phone"])

_AFFIRMATIVE_MESSAGE_RE = re.compile(
    r"^(yes|ja|ok|okay|yep|yeah|sure|yup|"
    r"klar|genau|stimmt|gerne|bitte|los|weiter|mach es|ruf an|anrufen)$",
    re.IGNORECASE,
)

# ── shared state ──────────────────────────────────────────────────────────────
# sip_client.py / call_handler.py import and mutate this dict.
# All values here are safe offline defaults.
phone_state: dict = {
    "registered":      False,
    "extension":       "",
    "server":          "",
    "active_call":     None,   # None or {"caller": str, "started_at": str}
    "ringing_call":    None,   # None or {"caller": str, "caller_name": str|None,
                               #          "ringing_since": str, "direction": "inbound"|"outbound"}
    "whisper_queue":   _queue.Queue(),  # thread-safe queue of operator instructions
    "bridge_call":     None,   # ESLOutboundHandler when operator takes the call
    "esl_handler":     None,   # ESLOutboundHandler for the current call (AI or human)
    "last_escalation": None,   # set when escalation fires; cleared by POST /ring/escalation/dismiss
                               # {"caller": str, "caller_name": str|None, "reason": str,
                               #  "summary": str, "email_sent": bool, "at": ISO-8601}
}

# ── ring decision synchronisation ─────────────────────────────────────────────
# call_handler / sip_client block on _ring_event.wait() while the operator
# decides whether the AI or the human will handle the call.
_ring_event: threading.Event = threading.Event()
_ring_decision: list = [None]   # ["ai"] or ["human"]


def set_ring_decision(decision: str) -> None:
    """Called by ring endpoints to unblock the waiting call thread."""
    _ring_decision[0] = decision
    _ring_event.set()


def wait_for_ring_decision(timeout: float) -> str:
    """
    Block until the operator picks a decision or timeout expires.
    Returns "ai" (operator chose AI, or timed out) or "human".
    Resets state for the next call.
    """
    _ring_event.wait(timeout=timeout)
    _ring_event.clear()
    decision = _ring_decision[0] or "ai"   # default: AI answers on timeout
    _ring_decision[0] = None
    return decision


# ── models ────────────────────────────────────────────────────────────────────

class ActiveCall(BaseModel):
    caller: str
    caller_name: Optional[str] = None
    started_at: str            # ISO-8601
    mode: str = "ai"           # "ai" or "human"


class RingingCall(BaseModel):
    caller: str
    caller_name: Optional[str] = None
    ringing_since: str          # ISO-8601
    direction: str              # "inbound" or "outbound"


class EscalationAlert(BaseModel):
    caller: str
    caller_name: Optional[str] = None
    reason: str
    summary: str
    email_sent: bool
    at: str   # ISO-8601


class PhoneStatus(BaseModel):
    registered: bool
    extension: str
    server: str
    active_call: Optional[ActiveCall] = None
    ringing_call: Optional[RingingCall] = None
    last_escalation: Optional[EscalationAlert] = None


class ContactEntry(BaseModel):
    name: str
    number: str
    status: str


class DialRequest(BaseModel):
    number: str
    display_name: Optional[str] = None
    opening_line: Optional[str] = None   # first thing the AI says when answered
    lang: Optional[str] = None           # "de" or "en" — defaults to AI_LANGUAGE
    system_prompt: Optional[str] = None  # override the default outbound system prompt


class WhisperRequest(BaseModel):
    instruction: str


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
            mode=raw_call.get("mode", "ai"),
        )

    raw_ring = phone_state.get("ringing_call")
    ringing: Optional[RingingCall] = None
    if raw_ring:
        ringing = RingingCall(
            caller=raw_ring.get("caller", ""),
            caller_name=raw_ring.get("caller_name"),
            ringing_since=raw_ring.get("ringing_since", ""),
            direction=raw_ring.get("direction", "inbound"),
        )

    raw_esc = phone_state.get("last_escalation")
    escalation: Optional[EscalationAlert] = None
    if raw_esc:
        escalation = EscalationAlert(
            caller=raw_esc.get("caller", ""),
            caller_name=raw_esc.get("caller_name"),
            reason=raw_esc.get("reason", ""),
            summary=raw_esc.get("summary", ""),
            email_sent=raw_esc.get("email_sent", False),
            at=raw_esc.get("at", ""),
        )

    return PhoneStatus(
        registered=phone_state.get("registered", False),
        extension=phone_state.get("extension", ""),
        server=phone_state.get("server", ""),
        active_call=active,
        ringing_call=ringing,
        last_escalation=escalation,
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
    Initiate an AI-driven outbound call via FreeSWITCH ESL originate.

    FreeSWITCH dials *number* through the COMtrexx gateway.  When the call is
    answered, the AI speaks *opening_line* first, then continues the conversation
    using the configured outbound system prompt.

    Returns 409 if a call is already active.
    Returns 502 if FreeSWITCH rejects the originate command.
    """
    from voice.outbound import originate_call
    from voice.llm_bridge import _SYSTEM_PROMPT as _INBOUND_SYSTEM_PROMPT
    from voice import config as _vc

    if phone_state.get("active_call") is not None or phone_state.get("ringing_call") is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CALL_IN_PROGRESS", "message": "A call is already active."},
        )

    if not is_german_number(request.number):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NON_GERMAN_NUMBER",
                "message": "Ich kann aktuell nur deutsche Telefonnummern anrufen.",
            },
        )

    lang = request.lang or _vc.AI_LANGUAGE
    # Outbound calls use the Teleprofi Fulda outbound persona prompt.
    from voice.llm_bridge import OUTBOUND_SYSTEM_PROMPT
    system_prompt = request.system_prompt or OUTBOUND_SYSTEM_PROMPT

    opening_line = request.opening_line or (
        "Hello, this is the digital assistant from Teleprofi Fulda. "
        "I'm calling regarding your enquiry."
        if lang == "en"
        else _vc.AI_OUTBOUND_GREETING
    )

    # Append a short context note so the LLM knows this is an outbound call it placed.
    outbound_note = (
        "\n\n[Context: You placed this outbound call. You already delivered the opening line. "
        "The person has answered — continue the conversation naturally from there. "
        "Do not re-introduce yourself. Respond to whatever they say next.]"
    )
    system_prompt_out = system_prompt + outbound_note

    success, result = originate_call(
        number=request.number,
        opening_line=opening_line,
        system_prompt=system_prompt_out,
        lang=lang,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "DIAL_FAILED", "message": result},
        )

    logger.info("Outbound call initiated: masked_number=%s uuid=%s", mask_number(request.number), result)
    return {"status": "dialing", "number": request.number, "uuid": result}


@router.post("/ring/ai")
async def ring_ai():
    """
    Tell the AI to answer the currently ringing or pending call.
    Can also be used after an outbound call is answered to let the AI handle the conversation.
    Returns 409 if no call is waiting for a decision.
    """
    if phone_state.get("ringing_call") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NO_RINGING_CALL", "message": "No call is waiting for a decision."},
        )
    set_ring_decision("ai")
    logger.info("Operator chose: AI handles the call")
    return {"status": "ai_answering"}


@router.post("/ring/human")
async def ring_human():
    """
    Tell the AI to step aside — the operator will handle the call.
    For inbound calls the AI denies/ignores, so the PBX routes to the operator's phone.
    For outbound calls the AI hangs up its leg so the operator can call back directly.
    Returns 409 if no call is waiting for a decision.
    """
    if phone_state.get("ringing_call") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NO_RINGING_CALL", "message": "No call is waiting for a decision."},
        )
    set_ring_decision("human")
    logger.info("Operator chose: human handles the call")
    return {"status": "human_answering"}


@router.post("/whisper")
async def whisper(request: WhisperRequest):
    """
    Inject an operator instruction into the active call.
    The instruction is silently added to the AI's context on the next LLM turn —
    the caller never hears it, but the AI uses it to shape its next reply.
    Returns 409 if no call is currently active.
    """
    if phone_state.get("active_call") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NO_ACTIVE_CALL", "message": "No call is currently active."},
        )
    instruction = request.instruction.strip()
    if not instruction:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "EMPTY_INSTRUCTION", "message": "Instruction cannot be empty."},
        )
    phone_state["whisper_queue"].put_nowait(instruction)
    logger.info("Operator whisper queued: length=%d", len(instruction))
    return {"status": "queued", "instruction": instruction}


@router.post("/escalation/dismiss")
async def dismiss_escalation():
    """
    Clear the last_escalation alert so the frontend banner disappears.
    Safe to call even if there is no pending escalation.
    """
    phone_state["last_escalation"] = None
    return {"status": "dismissed"}


@router.post("/hangup")
async def hangup():
    """
    Hang up the currently active call.
    Works regardless of whether the call is in AI or human mode.
    Returns 409 if no call is active.
    """
    handler = phone_state.get("esl_handler")
    if handler is None or phone_state.get("active_call") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NO_ACTIVE_CALL", "message": "No call is currently active."},
        )
    handler.hangup()
    logger.info("Operator hung up the call")
    return {"status": "hanging_up"}


@router.get("/log")
async def get_call_log(limit: int = 50):
    """
    Return the most recent call log entries (newest first).
    Reads from logs/call_log.jsonl written by voice/call_log.py.
    """
    import json as _json
    from pathlib import Path as _Path

    log_file = _Path(__file__).resolve().parent.parent / "logs" / "call_log.jsonl"
    if not log_file.exists():
        return []

    try:
        lines = log_file.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(_json.loads(line))
            except _json.JSONDecodeError:
                continue
            if len(entries) >= limit:
                break
        return entries
    except Exception as exc:
        logger.error("Failed to read call log: %s", exc)
        return []


@router.websocket("/call-audio")
async def call_audio_ws(websocket: WebSocket):
    """
    WebSocket audio bridge — operator talks to the caller through the browser.

    Active only when phone_state["bridge_call"] is set (operator chose "I'll take it").

    Wire protocol (both directions):
      Each binary message is exactly 320 bytes of raw 16-bit signed PCM, 8 kHz, mono
      (160 samples = 20 ms per frame).

    Implementation:
      Caller → browser: FreeSWITCH uuid_record writes a growing WAV file; Python
                        tails it in 20-ms frames and forwards them over the WebSocket.
      Browser → caller: incoming PCM frames are buffered, wrapped in a minimal WAV,
                        and injected into the caller's leg via uuid_broadcast.
      Both directions use the inbound ESL API channel (send_api_command) so the
      per-call outbound ESL socket is not blocked.
    """
    await websocket.accept()

    handler = phone_state.get("bridge_call")
    if handler is None or handler.is_hung_up:
        await websocket.close(1008, "No active bridged call")
        return

    uuid = handler.get_uuid()
    loop = asyncio.get_running_loop()

    from pathlib import Path as _Path
    import struct as _struct
    from voice import config as _vc
    from voice.esl_client import send_api_command

    def _to_fs_path(p: _Path) -> str:
        """Windows absolute path → /mnt/<drive>/... for FreeSWITCH running in WSL."""
        s = str(p)
        if len(s) >= 2 and s[1] == ":":
            return f"/mnt/{s[0].lower()}{s[2:].replace(chr(92), '/')}"
        return s.replace("\\", "/")

    audio_dir = _Path(_vc.FREESWITCH_AUDIO_TEMP_DIR).resolve()
    audio_dir.mkdir(parents=True, exist_ok=True)

    rec_wav = audio_dir / f"{uuid}_bridge.wav"

    # Start recording the caller's leg to a growing WAV file via the ESL API channel.
    # FS writes continuously; Python reads it like `tail -f`, sending 20-ms frames.
    await loop.run_in_executor(
        None, send_api_command, f"uuid_record {uuid} start {_to_fs_path(rec_wav)}"
    )
    logger.info("Operator bridge open: uuid=%s", uuid)

    stop = asyncio.Event()
    _op_seq = [0]   # mutable counter for operator WAV filenames

    # ── helpers ───────────────────────────────────────────────────────────────

    def _write_wav(pcm: bytes, path: _Path, rate: int = 8000) -> None:
        """Wrap raw s16le PCM in a minimal WAV file."""
        n = len(pcm)
        with open(path, "wb") as f:
            f.write(b"RIFF")
            f.write(_struct.pack("<I", 36 + n))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(_struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16))
            f.write(b"data")
            f.write(_struct.pack("<I", n))
            f.write(pcm)

    async def _broadcast_op(pcm: bytes) -> None:
        """Write operator PCM to a temp WAV and broadcast it to the caller's leg."""
        seq = _op_seq[0]
        _op_seq[0] += 1
        wav = audio_dir / f"{uuid}_op_{seq}.wav"
        await loop.run_in_executor(None, _write_wav, pcm, wav)
        await loop.run_in_executor(
            None, send_api_command,
            f"uuid_broadcast {uuid} {_to_fs_path(wav)} aleg",
        )
        # Remove the temp file after generous playback headroom
        async def _rm() -> None:
            await asyncio.sleep(15)
            try:
                wav.unlink(missing_ok=True)
            except Exception:
                pass
        asyncio.create_task(_rm())

    # ── task: stream caller audio to browser ──────────────────────────────────

    async def _stream_caller() -> None:
        WAV_HEADER = 44     # standard WAV header size
        FRAME = 320         # 20 ms @ 8 kHz, s16le, mono

        # Wait up to 5 s for FS to create and populate the recording file
        for _ in range(100):
            if rec_wav.exists() and rec_wav.stat().st_size > WAV_HEADER:
                break
            await asyncio.sleep(0.05)

        if not rec_wav.exists():
            logger.warning("Bridge recorder: WAV never appeared for uuid=%s", uuid)
            return

        read_pos = WAV_HEADER

        def _read(pos: int) -> bytes:
            try:
                with open(rec_wav, "rb") as f:
                    f.seek(pos)
                    return f.read(FRAME * 8)   # up to 8 frames (160 ms) per syscall
            except OSError:
                return b""

        while not stop.is_set() and not handler.is_hung_up:
            raw = await loop.run_in_executor(None, _read, read_pos)
            if not raw:
                await asyncio.sleep(0.02)
                continue
            i = 0
            while i + FRAME <= len(raw):
                try:
                    await websocket.send_bytes(raw[i: i + FRAME])
                except Exception:
                    stop.set()
                    return
                i += FRAME
                read_pos += FRAME
            if i < len(raw):
                # Partial frame — wait for FS to write more
                await asyncio.sleep(0.01)

    # ── task: receive operator audio and play it to the caller ────────────────

    async def _recv_operator() -> None:
        FLUSH_BYTES = 8 * 320   # broadcast every 160 ms to balance latency vs overhead
        buf = bytearray()
        while not stop.is_set() and not handler.is_hung_up:
            try:
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=0.2)
                buf.extend(data)
                while len(buf) >= FLUSH_BYTES:
                    await _broadcast_op(bytes(buf[:FLUSH_BYTES]))
                    del buf[:FLUSH_BYTES]
            except asyncio.TimeoutError:
                # Flush any partial buffer so the caller hears the tail end of speech
                if buf:
                    await _broadcast_op(bytes(buf))
                    buf.clear()
            except (WebSocketDisconnect, Exception):
                break
        stop.set()

    # ── run both directions concurrently ──────────────────────────────────────

    try:
        await asyncio.gather(_stream_caller(), _recv_operator())
    finally:
        stop.set()
        await loop.run_in_executor(
            None, send_api_command,
            f"uuid_record {uuid} stop {_to_fs_path(rec_wav)}",
        )
        try:
            rec_wav.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("Operator bridge closed: uuid=%s", uuid)


class CallMessageRequest(BaseModel):
    message: str
    session_id: str = "default"


@router.post("/message")
async def handle_call_message(request: CallMessageRequest):
    """
    Natural-language call trigger.

    Detects call intent in *message*, resolves the target, manages a
    per-session confirmation state, and fires originate_call() on approval.
    Returns 409 if action == "calling" but a call is already active.
    """
    if _AFFIRMATIVE_MESSAGE_RE.match(request.message.strip()):
        if phone_state.get("active_call") or phone_state.get("ringing_call"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "CALL_IN_PROGRESS", "message": "A call is already active."},
            )

    from voice.call_trigger import handle_message

    result = handle_message(request.message, request.session_id)

    if result.get("action") == "calling":
        if phone_state.get("active_call") or phone_state.get("ringing_call"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "CALL_IN_PROGRESS", "message": "A call is already active."},
            )

    return result
