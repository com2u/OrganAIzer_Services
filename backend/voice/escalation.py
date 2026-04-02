"""
escalation.py — handle mid-call escalation to a human agent.

Responsibilities:
  1. Generate a brief summary of the call (via LLM) for the operator.
  2. Send an internal escalation email via SMTP.
  3. Provide a transfer stub — real transfer plugs in here during FreeSWITCH phase.

All functions are safe to call from a sync thread (asyncio.run() used internally).
None of these functions raise — errors are logged and degraded gracefully.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from voice import config
from voice.esl_client import ESLOutboundHandler

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SUMMARY_SYSTEM = """\
Du bist ein internes Hilfssystem für Teleprofi-Fulda.
Schreibe eine kurze interne Zusammenfassung (2–4 Sätze) eines Anrufs für den Mitarbeiter, \
der die Eskalation übernimmt.
Fasse das Anliegen sachlich zusammen. Keine Floskeln, kein Smalltalk.
Antworte nur mit der Zusammenfassung, ohne Einleitung oder Unterschrift.
"""


def _format_transcript(transcript: list[dict]) -> str:
    lines = []
    for turn in transcript:
        role = turn.get("role", "")
        text = turn.get("content") or turn.get("text", "")
        if not text:
            continue
        speaker = "Anrufer" if role in ("user", "caller") else "KI"
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines) if lines else "(kein Gesprächsverlauf)"


async def _llm_summary(
    transcript: list[dict],
    caller: str,
    caller_name: Optional[str],
    escalation_reason: str,
) -> str:
    """Generate a brief call summary via LLM. Returns empty string on failure."""
    if not config.OPENROUTER_API_KEY:
        return ""

    transcript_text = _format_transcript(transcript)
    display = caller_name or caller

    user_content = (
        f"Anrufer: {display}\n"
        f"Eskalationsgrund: {escalation_reason or 'nicht angegeben'}\n\n"
        f"Gesprächsverlauf:\n{transcript_text}"
    )

    payload = {
        "model":       config.LLM_MODEL,
        "messages":    [
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user",   "content": user_content},
        ],
        "max_tokens":  300,
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://organaizer.local",
        "X-Title":       "OrganAIzer Voice",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(_OPENROUTER_URL, headers=headers, json=payload)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        logger.error("LLM summary error %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.error("LLM summary request failed: %s", exc)
    return ""


def _send_smtp_email(subject: str, body: str) -> bool:
    """Send an email via SMTP. Returns True on success."""
    if not all([
        config.ESCALATION_EMAIL_TO,
        config.ESCALATION_EMAIL_FROM,
        config.ESCALATION_SMTP_HOST,
        config.ESCALATION_SMTP_USER,
        config.ESCALATION_SMTP_PASS,
    ]):
        logger.info(
            "Escalation email not sent — SMTP not configured "
            "(set ESCALATION_EMAIL_TO/FROM/SMTP_HOST/USER/PASS)"
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.ESCALATION_EMAIL_FROM
    msg["To"]      = config.ESCALATION_EMAIL_TO
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(config.ESCALATION_SMTP_HOST, config.ESCALATION_SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(config.ESCALATION_SMTP_USER, config.ESCALATION_SMTP_PASS)
            server.sendmail(
                config.ESCALATION_EMAIL_FROM,
                [config.ESCALATION_EMAIL_TO],
                msg.as_string(),
            )
        logger.info("Escalation email sent to %s", config.ESCALATION_EMAIL_TO)
        return True
    except Exception as exc:
        logger.error("Escalation email failed: %s", exc)
        return False


def transfer_to_extension(
    extension: str,
    call_uuid: str = "",
    handler: Optional[ESLOutboundHandler] = None,
) -> bool:
    """
    Transfer the active call to a COMtrexx extension via FreeSWITCH ESL.

    When call_uuid is provided, uses uuid_transfer to redirect the existing
    channel — the caller is immediately routed to the extension and the AI
    leg ends cleanly.  This is a blind transfer (agent must answer).

    Falls back to originate+park when no call_uuid is available (legacy path).

    Prerequisites (FreeSWITCH side, not handled here):
      - mod_event_socket loaded and listening on FREESWITCH_ESL_PORT
      - FreeSWITCH dialplan has a rule routing the extension number to COMtrexx
        (e.g. via the comtrexx_gateway)

    Returns True if FreeSWITCH accepted the command (+OK), False otherwise.
    """
    if handler:
        # Transfer on the existing outbound ESL socket
        logger.info("ESL outbound transfer uuid=%s → extension %s", handler.get_uuid(), extension)
        return handler.execute("transfer", extension)

    elif call_uuid:
        # Transfer the existing channel via inbound ESL — caller hears hold music until agent answers
        from voice.esl_client import send_api_command
        cmd = f"uuid_transfer {call_uuid} {extension} XML default"
        logger.info("ESL inbound uuid_transfer uuid=%s → extension %s", call_uuid, extension)
        response = send_api_command(cmd)
        if response.strip().startswith("+OK"):
            logger.info("Transfer accepted for extension %s", extension)
            return True
        logger.warning("Inbound ESL uuid_transfer failed for extension %s: %r", extension, response[:200])
        return False

    else:
        # Legacy fallback: originate a new call to the extension (no direct bridge)
        # This path should ideally be removed once all calls are handled by outbound ESL.
        from voice.esl_client import send_api_command
        sip_target = f"sofia/internal/{extension}@{config.COMTREXX_IP}"
        cmd = (
            f"originate {{origination_caller_id_name=KI-Eskalation}}"
            f"{sip_target} &park()"
        )
        logger.info("ESL originate (no uuid) → %s", sip_target)
        response = send_api_command(cmd)
        if response.strip().startswith("+OK"):
            logger.info("Originate accepted for extension %s", extension)
            return True
        logger.warning("Originate failed for extension %s: %r", extension, response[:200])
        return False


def handle_escalation(
    caller: str,
    caller_name: Optional[str],
    transcript: list[dict],
    escalation_reason: str,
    started_at: datetime,
    call_uuid: str = "",
    esl_handler: Optional[ESLOutboundHandler] = None,
) -> dict:
    """
    Full escalation flow called after the AI decides to escalate.

    Steps:
      1. Generate LLM call summary
      2. Send escalation email
      3. Attempt transfer (stub — always False until FreeSWITCH)

    Returns:
        {
            "summary":          str,    # LLM-generated summary
            "email_sent":       bool,
            "transfer_target":  str,    # extension attempted, or ""
            "transfer_ok":      bool,
        }

    Never raises.
    """
    display = caller_name or caller
    now     = datetime.now(timezone.utc)
    duration_s = int((now - started_at).total_seconds())

    # 1. Generate summary
    try:
        summary = asyncio.run(
            _llm_summary(transcript, caller, caller_name, escalation_reason)
        )
    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        summary = ""

    if not summary:
        # Fallback: build a minimal summary from transcript
        summary = (
            f"Anruf von {display} (Dauer: {duration_s}s). "
            f"Eskalationsgrund: {escalation_reason or 'unbekannt'}. "
            f"Anzahl Gesprächsrunden: {len([t for t in transcript if t.get('role') == 'caller'])}."
        )

    # 2. Send escalation email
    subject = f"KI-Eskalation: {display} – {escalation_reason or 'Eskalation'}"
    transcript_block = _format_transcript(transcript)
    body = (
        f"Teleprofi-Fulda KI-Telefonassistent — Eskalation\n"
        f"{'=' * 50}\n\n"
        f"Anrufer:        {display}\n"
        f"Nummer:         {caller}\n"
        f"Anrufbeginn:    {started_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"Dauer:          {duration_s}s\n"
        f"Grund:          {escalation_reason or 'nicht angegeben'}\n\n"
        f"Zusammenfassung:\n{summary}\n\n"
        f"Gesprächsverlauf:\n{transcript_block}\n"
    )
    email_sent = _send_smtp_email(subject, body)

    # 3. Transfer — try waiting room primary, then secondary.
    # Requires FREESWITCH_ESL_* env vars and FreeSWITCH running with a SIP route to COMtrexx.
    transfer_target = ""
    transfer_ok = False
    for candidate in (config.AI_WAITING_ROOM_PRIMARY, config.AI_WAITING_ROOM_SECONDARY):
        if not candidate:
            continue
        transfer_ok = transfer_to_extension(candidate, call_uuid=call_uuid, handler=esl_handler)
        if transfer_ok:
            transfer_target = candidate
            break
        logger.info("Transfer to %s failed — trying next target", candidate)

    if not transfer_ok:
        transfer_target = config.AI_WAITING_ROOM_PRIMARY or ""
        logger.warning(
            "Call transfer failed for caller %s — no waiting room extension reachable. "
            "Email escalation is the only active handoff path.",
            display,
        )

    logger.info(
        "Escalation handled: caller=%s reason=%s email_sent=%s transfer_target=%s transfer_ok=%s",
        display, escalation_reason, email_sent, transfer_target or "none", transfer_ok,
    )

    return {
        "summary":         summary,
        "email_sent":      email_sent,
        "transfer_target": transfer_target,
        "transfer_ok":     transfer_ok,
    }
