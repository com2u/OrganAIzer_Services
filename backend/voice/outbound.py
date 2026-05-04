"""
outbound.py — initiate AI-driven outbound calls via FreeSWITCH ESL originate.

Flow:
  1. originate_call() sends an ESL originate command to FreeSWITCH.
  2. FS dials the external number through the COMtrexx SIP gateway.
  3. When the remote answers, FS connects the call to our outbound socket (port 8085).
  4. handle_esl_call() in esl_call_handler.py picks it up — pop_outbound_context()
     matches the UUID and returns the configured opening line + system prompt.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from voice import config
from voice.call_trigger import mask_number
from voice.esl_client import send_api_command

logger = logging.getLogger(__name__)

_lock: threading.Lock = threading.Lock()
_pending: dict[str, dict] = {}   # uuid → call context


def originate_call(
    number: str,
    opening_line: str,
    system_prompt: str,
    lang: str = "de",
    caller_id: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Tell FreeSWITCH to dial *number* externally and handle the answered call
    with the AI using *opening_line* and *system_prompt*.

    Args:
        number:       E.164 or local number to dial, e.g. "+4966198765432" or "0661…"
        opening_line: First sentence the AI speaks when the call is answered.
        system_prompt: Full system prompt for the LLM (use OUTBOUND_SYSTEM_PROMPT
                       from llm_bridge or supply a custom one).
        lang:         Conversation language — "de" or "en".
        caller_id:    Outbound caller ID to present. Falls back to
                      config.COMTREXX_CALLER_ID if not provided.

    Returns:
        (True, uuid)   if FS accepted the originate command.
        (False, error) if FS returned an error or is unreachable.
    """
    if not config.FREESWITCH_ESL_OUTBOUND_HOST:
        return False, "FREESWITCH_ESL_OUTBOUND_HOST is not set in .env"

    cid = caller_id or config.COMTREXX_CALLER_ID or ""
    vars_parts = [
        "hangup_after_bridge=false",
        "rtp_secure_media=true",
        # Do not treat ringback / early media as an answered call.
        # Without this, FreeSWITCH connects the outbound socket immediately
        # and the recording captures 30 s of ringback tone instead of speech.
        "ignore_early_media=true",
    ]
    if cid:
        vars_parts.append(f"origination_caller_id_number={cid}")
        vars_parts.append(f"origination_caller_id_name=Teleprofi+Fulda")

    vars_str = "{" + ",".join(vars_parts) + "}"
    socket_addr = (
        f"{config.FREESWITCH_ESL_OUTBOUND_HOST}:{config.FREESWITCH_ESL_OUTBOUND_PORT}"
    )
    endpoint = f"sofia/gateway/comtrexx/{number}"
    cmd = f"originate {vars_str}{endpoint} &socket({socket_addr} async full)"

    logger.info("ESL originate → masked_number=%s", mask_number(number))
    result = send_api_command(cmd)

    if not result:
        return False, "FreeSWITCH did not respond to originate command"

    result = result.strip()
    if not result.startswith("+OK"):
        logger.warning("ESL originate failed: %s", result[:200])
        return False, result

    uuid = result[3:].strip()   # "+OK <uuid>" → "<uuid>"
    logger.info("ESL originate accepted: uuid=%s masked_number=%s", uuid, mask_number(number))

    with _lock:
        _pending[uuid] = {
            "number":       number,
            "opening_line": opening_line,
            "system_prompt": system_prompt,
            "lang":         lang,
        }

    return True, uuid


def pop_outbound_context(uuid: str) -> Optional[dict]:
    """
    Return and remove the pending outbound context for *uuid*.
    Returns None if *uuid* is not a pending outbound call (i.e. it's inbound).
    """
    with _lock:
        return _pending.pop(uuid, None)
