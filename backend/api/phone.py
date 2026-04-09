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
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from voice import contacts as _contacts

logger = logging.getLogger(__name__)

router = APIRouter(tags=["phone"])

# ── shared state ──────────────────────────────────────────────────────────────
# sip_client.py / call_handler.py import and mutate this dict.
# All values here are safe offline defaults.
phone_state: dict = {
    "registered":    False,
    "extension":     "",
    "server":        "",
    "active_call":   None,   # None or {"caller": str, "started_at": str}
    "ringing_call":  None,   # None or {"caller": str, "caller_name": str|None,
                             #          "ringing_since": str, "direction": "inbound"|"outbound"}
    "whisper_queue": _queue.Queue(),  # thread-safe queue of operator instructions
    "bridge_call":   None,   # ESLOutboundHandler when operator takes the call
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


class PhoneStatus(BaseModel):
    registered: bool
    extension: str
    server: str
    active_call: Optional[ActiveCall] = None
    ringing_call: Optional[RingingCall] = None


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

    return PhoneStatus(
        registered=phone_state.get("registered", False),
        extension=phone_state.get("extension", ""),
        server=phone_state.get("server", ""),
        active_call=active,
        ringing_call=ringing,
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
    from voice.llm_bridge import OUTBOUND_SYSTEM_PROMPT
    from voice import config as _vc

    if phone_state.get("active_call") is not None or phone_state.get("ringing_call") is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CALL_IN_PROGRESS", "message": "A call is already active."},
        )

    lang = request.lang or _vc.AI_LANGUAGE
    system_prompt = request.system_prompt or OUTBOUND_SYSTEM_PROMPT

    opening_line = request.opening_line or (
        "Hello! This is the AI assistant from Teleprofi Fulda calling. "
        "I hope I'm not disturbing you — do you have a moment?"
        if lang == "en"
        else "Guten Tag! Hier ist der KI-Assistent von Teleprofi Fulda. "
             "Ich hoffe ich störe nicht — hätten Sie kurz einen Moment?"
    )

    success, result = originate_call(
        number=request.number,
        opening_line=opening_line,
        system_prompt=system_prompt,
        lang=lang,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "DIAL_FAILED", "message": result},
        )

    logger.info("Outbound call initiated: number=%s uuid=%s", request.number, result)
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
    logger.info("Operator whisper queued: %s", instruction[:120])
    return {"status": "queued", "instruction": instruction}


@router.websocket("/call-audio")
async def call_audio_ws(websocket: WebSocket):
    """
    WebSocket audio bridge for operator-in-browser calls.
    Connects only when phone_state["bridge_call"] is set (operator chose "I'll take it").

    Binary protocol (both directions):
      - Each message is a raw 320-byte chunk of 16-bit signed PCM, 8 kHz, mono.
        (160 samples × 2 bytes — one 20 ms RTP frame, same format as pyVoIP.)
    """
    # pyVoIP is no longer used (replaced by FreeSWITCH ESL).
    # The operator audio bridge over ESL is not yet implemented.
    try:
        from pyVoIP.VoIP import CallState as _CS
        _pyvoip_available = True
    except ImportError:
        _pyvoip_available = False

    await websocket.accept()

    if not _pyvoip_available:
        await websocket.close(1011, "Operator audio bridge not available (pyVoIP removed; ESL bridge pending)")
        return

    call = phone_state.get("bridge_call")
    if call is None or call.state == _CS.ENDED:
        await websocket.close(1008, "No active bridged call")
        return

    logger.info("Operator audio bridge connected")

    # Queue for SIP→browser direction (filled by a reader thread, drained by the coroutine)
    sip_audio: _queue.Queue = _queue.Queue(maxsize=100)
    stop_flag = threading.Event()

    def _sip_reader():
        """Dedicated thread: pull PCM from pyVoIP and enqueue."""
        while not stop_flag.is_set() and getattr(call, "state", None) != _CS.ENDED:
            try:
                pcm = call.read_audio(160, blocking=True)   # blocks ~20 ms
                try:
                    sip_audio.put_nowait(pcm)
                except _queue.Full:
                    pass   # drop frame if browser is too slow
            except Exception:
                break
        stop_flag.set()

    reader = threading.Thread(target=_sip_reader, daemon=True, name="sip-audio-bridge-rx")
    reader.start()

    async def send_to_browser():
        """Drain sip_audio queue → WebSocket."""
        while not stop_flag.is_set():
            try:
                pcm = sip_audio.get_nowait()
                await websocket.send_bytes(pcm)
            except _queue.Empty:
                await asyncio.sleep(0.005)   # 5 ms poll — fine for 20 ms frames
            except (WebSocketDisconnect, Exception):
                break
        stop_flag.set()

    async def recv_from_browser():
        """WebSocket → pyVoIP write_audio in 320-byte chunks."""
        while not stop_flag.is_set() and getattr(call, "state", None) != _CS.ENDED:
            try:
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=1.0)
                for i in range(0, len(data), 320):
                    chunk = data[i: i + 320]
                    if len(chunk) == 320 and getattr(call, "state", None) != _CS.ENDED:
                        call.write_audio(chunk)
            except asyncio.TimeoutError:
                continue
            except (WebSocketDisconnect, Exception):
                break
        stop_flag.set()

    try:
        await asyncio.gather(send_to_browser(), recv_from_browser())
    finally:
        stop_flag.set()
        logger.info("Operator audio bridge disconnected")
        try:
            await websocket.close()
        except Exception:
            pass
