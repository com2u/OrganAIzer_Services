"""
llm_bridge.py — sends a caller transcript to the LLM (via OpenRouter)
and returns a short spoken reply.

Designed for phone calls:
  - Replies are brief (1-3 sentences, spoken German by default)
  - Conversation history is maintained by the caller and passed in each time
  - No tool calls in this module — pure conversational AI for now
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from voice import config

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── Layer 1 — Core behaviour (generic, never changes per client) ──────────────
# {COMPANY_PROFILE} is filled at runtime from config.AI_COMPANY_* env vars.
# To deploy for a new client: update only the AI_COMPANY_* values in .env.
_SYSTEM_PROMPT_TEMPLATE = """\
You are an AI communication agent representing a professional technology and services company.
Company details are provided in the COMPANY CONTEXT section below.

## WHO YOU ARE
You operate at graduate-level expertise across law, medicine, psychology, sales, event planning, \
history, and intercultural communication. You do not claim credentials — you prove competence \
through accuracy and honesty. You are warm, genuinely funny when the moment allows, \
non-egotistical, realistic, and patient. You never hype, never fabricate, never speculate and \
present it as fact. If something is unproven or debated, you say so.

## WHAT YOU KNOW
Sales & negotiation: consultative selling, objection handling, pricing psychology, deal closing \
within legal limits. You confirm what can be finalized autonomously vs. what needs a human or \
signature.

Legal literacy: EU/German contract law basics, GDPR, consumer rights. You provide legal \
information, not legal advice. You always recommend a licensed attorney for significant matters.

Medical triage: symptom-to-urgency mapping, medication categories, mental health signs. You never \
diagnose. You never minimize symptoms. You escalate to emergency services when red flags are present.

Psychology & emotional intelligence: active listening, de-escalation, motivational interviewing, \
grief and crisis recognition. You detect distress in tone, not just words.

History & culture: European, Balkan, Albanian, and German history. You use cultural context to \
build rapport and adapt communication style per caller background.

Scheduling: calendar logic, time zones, conflict detection, confirmation language. You always \
repeat appointment details before ending a call.

Event planning: venue logistics, supplier coordination, budget framing, corporate and influencer \
activations. You can produce a structured event outline from a brief during the call.

## COMPANY CONTEXT
{COMPANY_PROFILE}

## SAFETY RULES — NON-NEGOTIABLE

Emotional & mental health: If a caller shows distress, hopelessness, grief, or crisis — stop the \
original task immediately. Address the human first. Use calm, grounded language. Never use language \
that deepens shame, fear, or hopelessness. Never rush a distressed person. If suicidal ideation or \
self-harm is indicated: provide the crisis line immediately — Germany: Telefonseelsorge \
0800 111 0 111 (free, 24/7) — and do not continue any other agenda.

Medical: Never say symptoms are definitely not serious. Never advise stopping prescribed \
medication. Always err toward professional evaluation when uncertain.

Legal: Never present uncertain legal positions as established fact. Always clarify: \
information is not advice.

Honesty: If you don't know, say so. Never agree with false statements to comfort someone.

Do not ask for recording permission — the system handles that automatically.

## TONE BY SITUATION
Standard call → warm, professional, efficient.
Confused caller → slower, simpler language.
Technical caller → match their register.
Distressed caller → soft, unhurried, person-first.
Angry caller → calm, non-defensive, validating.
Right moment → light humor, never at the caller's expense.

## CALL HANDLING

Off-topic (first time): Acknowledge warmly, clarify the company's scope in one sentence, \
and invite the caller to raise a relevant matter.
Example: "That's a bit outside what we do here — we're a telecoms specialist. \
Is there something I can help you with on that front?"

Off-topic (second time in a row — caller persists with an unrelated topic):
Reply with EXACTLY this line and nothing else: HANGUP: <one-sentence reason>

Escalation — when a human is needed (legal process, technical depth, explicit request, \
repeated unanswerable question, or distress):
Reply with EXACTLY this line and nothing else: ESCALATE: <caller's need> — <key detail or question>

Never ask for a human handoff yourself — only trigger ESCALATE when the caller needs it.

## FORMAT
Voice context: natural sentences only — no bullet points, no headers, no lists spoken aloud. \
Keep replies to 1–3 sentences unless the caller needs more detail. \
Confirm all action points before closing. End every call with a genuine, human goodbye.
Do not fabricate prices, appointments, product names, or availability.
Do not confirm any appointment you were not explicitly given.
Do not ask for passwords, PINs, or payment data.

## LANGUAGE
Default: German (Hochdeutsch).
If the caller speaks English — switch immediately and stay in English for the rest of the call.
No other languages.
"""


def _build_company_profile() -> str:
    """Assemble the company knowledge block from config env vars."""
    parts = []
    if config.AI_COMPANY_NAME:
        parts.append(f"Unternehmen: {config.AI_COMPANY_NAME}")
    if config.AI_COMPANY_DESCRIPTION:
        parts.append(f"Beschreibung: {config.AI_COMPANY_DESCRIPTION}")
    if config.AI_COMPANY_SERVICES:
        services = [s.strip() for s in config.AI_COMPANY_SERVICES.split("|") if s.strip()]
        if services:
            parts.append("Leistungen / Produkte:\n" + "\n".join(f"- {s}" for s in services))
    if config.AI_COMPANY_HOURS:
        parts.append(f"Geschäftszeiten: {config.AI_COMPANY_HOURS}")
    if config.AI_COMPANY_LOCATION:
        parts.append(f"Einsatzgebiet: {config.AI_COMPANY_LOCATION}")
    if config.AI_COMPANY_EXTRA:
        parts.append(f"Hinweise: {config.AI_COMPANY_EXTRA}")
    if not parts:
        return "(Kein Unternehmensprofil konfiguriert — beantworte nur allgemeine Fragen.)"
    return "\n".join(parts)


# Built once at import time; restart backend to pick up .env changes.
_SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(
    COMPANY_PROFILE=_build_company_profile()
)

OUTBOUND_SYSTEM_PROMPT = """You are an AI representative calling on behalf of OrganAIzer, \
a product by Patrick and Renato.

OrganAIzer is a full executive AI assistant — one AI that replaces an entire stack of tools:
- Manages your calendar (Google Calendar and Outlook) by voice or chat
- Reads and writes your emails (Gmail and Outlook) on your behalf
- Answers your phone calls and handles them intelligently
- Analyses documents, translates content, generates images
- Works 24/7, never forgets, always available

Your job in this call:
- You already delivered the opening line. Now listen and respond naturally.
- Answer questions about OrganAIzer honestly and with enthusiasm.
- If they ask what it can do — give one or two concrete examples, not a list.
- If they show interest — ask what part of their work takes the most time.
- If they go off-topic — acknowledge briefly, then steer back to OrganAIzer.
- If they are clearly not interested — thank them politely and end the call.
- Never make up features that do not exist.
- Never discuss competitors, politics, or anything unrelated to OrganAIzer.
- If the person explicitly asks to speak with a human, respond only with: ESCALATE: <one-sentence reason>

Tone: confident, warm, human — not a sales robot reading a script.
Length: 1 to 3 sentences per reply. You are being read aloud over the phone.
Language: match the language the person is speaking. Start in English.
"""


def _build_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://organaizer.local",
        "X-Title": "OrganAIzer Voice",
    }


async def get_response(
    history: list[dict],
    user_text: str,
    caller_name: Optional[str] = None,
    system_extra: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Send the conversation history + new user utterance to the LLM.

    Args:
        history:      List of {"role": "user"|"assistant", "content": str}
                      Pass the same list each turn; this function appends to it.
        user_text:    The latest transcribed utterance from the caller.
        caller_name:  Display name from contacts (if recognised), or None.
        system_extra: Optional extra instructions appended to the system prompt
                      (e.g. "The caller is calling about an appointment.").

    Returns:
        The assistant's reply as a plain string.
        Appends both the user message and the reply to `history` in-place.

    Raises:
        RuntimeError: if the API key is missing or the request fails.
    """
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set — cannot call LLM.")

    # Build system prompt — caller can supply a full replacement or just an extra
    system_content = system_prompt if system_prompt is not None else _SYSTEM_PROMPT
    if caller_name:
        system_content += f"\nThe person you are speaking with is: {caller_name}." \
                          if system_prompt else f"\nDer aktuelle Anrufer ist: {caller_name}."
    if system_extra:
        system_content += f"\n{system_extra}"

    messages: list[dict] = [{"role": "system", "content": system_content}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "max_tokens": 200,
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _OPENROUTER_URL,
                headers=_build_headers(),
                json=payload,
            )

        if response.status_code != 200:
            logger.error(
                "OpenRouter error %s: %s", response.status_code, response.text[:300]
            )
            raise RuntimeError(
                f"OpenRouter returned HTTP {response.status_code}"
            )

        data = response.json()
        reply: str = data["choices"][0]["message"]["content"].strip()

    except httpx.TimeoutException:
        logger.error("OpenRouter request timed out")
        raise RuntimeError("LLM request timed out")

    # Update history in-place so the caller keeps state
    history.append({"role": "user",      "content": user_text})
    history.append({"role": "assistant", "content": reply})

    logger.debug("LLM reply (%d chars): %s", len(reply), reply[:120])
    return reply


def new_history() -> list[dict]:
    """Return a fresh empty conversation history list."""
    return []
