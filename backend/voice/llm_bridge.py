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
from pathlib import Path
from typing import Optional

import httpx

from voice import config

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── Layer 3 — Client knowledge file ───────────────────────────────────────────
# Long-form markdown (e.g. Teleprofi Fulda) loaded once at import time and
# injected into both the inbound and outbound system prompts. Configure the
# path via AI_KNOWLEDGE_FILE; default is backend/voice/knowledge/teleprofi_fulda.md.
# Capped at _MAX_KNOWLEDGE_CHARS to keep token usage bounded. Missing file is
# tolerated — the module always imports cleanly.

_MAX_KNOWLEDGE_CHARS = 16000
_DEFAULT_KNOWLEDGE_PATH = (
    Path(__file__).resolve().parent / "knowledge" / "teleprofi_fulda.md"
)


def _resolve_knowledge_path(path: Optional[Path] = None) -> Path:
    if path is not None:
        return Path(path)
    configured = (config.AI_KNOWLEDGE_FILE or "").strip()
    if configured:
        return Path(configured)
    return _DEFAULT_KNOWLEDGE_PATH


def _load_knowledge_file(path: Optional[Path] = None) -> str:
    """Read the client knowledge markdown into a string.

    Returns "" on any failure (missing file, read error, unsupported encoding).
    Never raises — import must succeed even with no knowledge configured.
    """
    target = _resolve_knowledge_path(path)
    try:
        if not target.is_file():
            logger.info(
                "Knowledge file not found at %s — using empty knowledge.", target
            )
            return ""
        text = target.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not read knowledge file %s: %s", target, exc)
        return ""
    if len(text) > _MAX_KNOWLEDGE_CHARS:
        logger.info(
            "Knowledge file %s truncated from %d → %d chars",
            target, len(text), _MAX_KNOWLEDGE_CHARS,
        )
        text = text[:_MAX_KNOWLEDGE_CHARS]
    return text


_KNOWLEDGE_BLOCK_TEMPLATE = """\
## COMPANY KNOWLEDGE — Teleprofi Fulda

Use the Teleprofi Fulda knowledge below as the authoritative source for company \
identity, service region, opening hours, services, products, common issues, \
intake fields, and escalation rules. Treat it as the truth for this client.

Rules when using this knowledge:
- Address every caller with the formal German "Sie". Never switch to "du".
- If the answer is not in this knowledge, say so honestly. Do not invent \
prices, appointment dates, model numbers, firmware versions, availability, \
warranty terms, or features.
- Do not ask for passwords, PINs, access credentials, or payment data.
- When the situation requires a human — the caller asks for one, total outage, \
medical office unreachable, emergency, credentials needed, quote or pricing \
negotiation, complex technical issue you cannot triage, or low confidence — \
reply with exactly: ESCALATE: <reason> — <key detail>

--- BEGIN KNOWLEDGE ---
{KNOWLEDGE}
--- END KNOWLEDGE ---
"""


def _build_knowledge_block(content: str) -> str:
    body = content.strip() if content else "(no knowledge file loaded)"
    return _KNOWLEDGE_BLOCK_TEMPLATE.format(KNOWLEDGE=body)


_KNOWLEDGE_CONTENT = _load_knowledge_file()
_KNOWLEDGE_BLOCK = _build_knowledge_block(_KNOWLEDGE_CONTENT)

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

Answer naturally on any topic — general questions, small talk, company enquiries, \
technical help, anything. You are not restricted to company topics. Be genuinely helpful.

If you cannot answer something honestly (e.g. you don't know a specific fact), say so \
briefly and offer what you can.

Escalation — only when the caller explicitly asks to speak with a person / team member, \
or when the situation clearly requires a human (emergency, legal process needing a signature, \
or distress that cannot be handled by AI):
Reply with EXACTLY this line and nothing else: ESCALATE: <caller's need> — <key detail>

Never suggest a handoff unprompted — the caller decides when they want a human.

## FORMAT
Voice context: natural sentences only — no bullet points, no headers, no lists spoken aloud. \
Keep replies to 1–2 short sentences max, unless the caller needs more detail. \
Ask only one question at a time. Avoid long explanations. Do not repeat the caller's full request.
Confirm all action points before closing. End every call with a genuine, human goodbye.
Do not fabricate prices, appointments, product names, or availability.
Do not confirm any appointment you were not explicitly given.
Do not ask for passwords, PINs, or payment data.

## LANGUAGE
Default: German (Hochdeutsch).
If the caller speaks English — switch immediately and stay in English for the rest of the call.
If the caller switches back to German mid-call — follow them.
No other languages. Never mix languages within a single reply.
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
_SYSTEM_PROMPT = (
    _SYSTEM_PROMPT_TEMPLATE.format(COMPANY_PROFILE=_build_company_profile())
    + "\n\n"
    + _KNOWLEDGE_BLOCK
)

# Dedicated outbound prompt focused on sales/demo conversation flow.
# This avoids conflicts with the generic system prompt while keeping conversation natural.
# The Teleprofi Fulda knowledge block is appended below at import time.
_OUTBOUND_SYSTEM_PROMPT_BASE = """You are an AI representative calling on behalf of OrganAIzer.

OrganAIzer offers AI and automation solutions for businesses:
- custom AI agents
- AI phone agents
- automated phone calls
- event and appointment handling
- meeting and team coordination
- workflow automation
- integrations with calendar, email, CRM, and business tools
- practical automation like the system we are building now

Your role:
- Your opening line has already been delivered and is your first message in the conversation history. Do not repeat your introduction. Continue naturally from where you left off.
- If the conversation history is empty and you have not yet spoken, start with a brief German introduction: "Guten Tag, ich bin der KI-Assistent von OrganAIzer. Wir helfen Unternehmen, Kommunikation und Abläufe zu automatisieren. Haben Sie kurz Zeit?"
- Listen and respond naturally to the caller.
- Answer questions about OrganAIzer honestly and with enthusiasm.
- If they ask what it can do — give one concrete example, then ask a question back.
- If they show interest — ask what part of their work takes the most time.
- If they go off-topic — acknowledge briefly, then steer back to OrganAIzer.
- If they are clearly not interested — thank them politely and end the call.
- Never make up features that do not exist.
- Never discuss competitors, politics, or anything unrelated to OrganAIzer.
- If the person explicitly asks to speak with a human, respond only with: ESCALATE: <one-sentence reason>

Tone: confident, warm, human — not a sales robot reading a script.
Length: 1 to 3 sentences per reply. You are being read aloud over the phone.
Language: match the language of the opening line. Default to German.
Switch to English only if the person responds in English.
"""

OUTBOUND_SYSTEM_PROMPT = _OUTBOUND_SYSTEM_PROMPT_BASE + "\n\n" + _KNOWLEDGE_BLOCK


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
