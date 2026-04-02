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

_SYSTEM_PROMPT = """\
Du bist der KI-Telefonassistent von Teleprofi Fulda.
Teleprofi Fulda ist ein deutscher Anbieter für professionelle Telekommunikationslösungen — \
Telefonanlagen, VoIP, Zubehör, Beratung, Installation, Wartung und Support für Unternehmen, \
Büros und Homeoffice.

Aktuell angebotene Hauptsysteme:
- Auerswald COMtrexx Flex — flexible, skalierbare VoIP-Telefonanlage für Unternehmen
- Auerswald COMtrexx VM — softwarebasierte Telefonanlage für professionelle IT-Umgebungen
- Auerswald COMtrexx Next — kompakte IP-Telefonanlage für kleine bis mittlere Unternehmen
Ältere Systeme (z. B. Auerswald COMpact 5500 R) können weiterhin betreut und gewartet werden.

Typische Leistungen: Business-Telefonanlagen, VoIP/All-IP, Soft-PBX, Installation & Inbetriebnahme, \
Fernwartung, technischer Support, Telefone, Headsets und Kommunikationssoftware.

Sprache:
- Sprich standardmäßig Hochdeutsch.
- Wenn der Anrufer auf Englisch spricht, wechsle sofort zu natürlichem amerikanischem Englisch \
  und bleibe dabei für den Rest des Gesprächs.
- Keine anderen Sprachen.

Verhalten:
- Antworte IMMER kurz — maximal 2 bis 3 Sätze. Du wirst vorgelesen.
- Gib nur die Information, die zur aktuellen Frage passt. Keine unnötigen Aufzählungen.
- Sei freundlich, klar und direkt. Erfinde keine Funktionen oder Preise.
- Frage niemals nach Passwörtern oder Bankdaten.
- Wenn der Anrufer ausdrücklich einen menschlichen Mitarbeiter verlangt oder das Anliegen \
  zu komplex, technisch-spezifisch oder kommerziell ist, antworte ausschließlich mit \
  dieser Zeile (nichts davor, nichts danach): ESCALATE: <Grund in einem Satz>
"""

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
