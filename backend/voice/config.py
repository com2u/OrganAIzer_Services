"""
Voice module configuration — reads everything from environment variables.
Never import credentials directly; always go through this module.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ── COMtrexx / SIP ────────────────────────────────────────────────────────────
COMTREXX_IP: str          = os.environ.get("COMTREXX_IP", "172.20.0.244")
COMTREXX_SIP_PORT: int    = int(os.environ.get("COMTREXX_SIP_PORT", "5060"))
# Local SIP port pyVoIP binds to.  Use 5080 to avoid clashing with the
# Windows built-in SIP stack which reserves port 5060.
COMTREXX_LOCAL_SIP_PORT: int = int(os.environ.get("COMTREXX_LOCAL_SIP_PORT", "5080"))
# Local IP to advertise in SIP Via/Contact headers.  Leave blank to
# auto-detect the interface that has a route to COMTREXX_IP.
COMTREXX_LOCAL_IP: str    = os.environ.get("COMTREXX_LOCAL_IP", "")
COMTREXX_SIP_USER: str    = os.environ.get("COMTREXX_SIP_USER", "")
COMTREXX_SIP_PASS: str    = os.environ.get("COMTREXX_SIP_PASS", "")
COMTREXX_SIP_DOMAIN: str  = os.environ.get("COMTREXX_SIP_DOMAIN", COMTREXX_IP)
COMTREXX_EXTENSION: str   = os.environ.get("COMTREXX_EXTENSION", "")
COMTREXX_CALLER_ID: str   = os.environ.get("COMTREXX_CALLER_ID", "")

# ── AI behaviour ─────────────────────────────────────────────────────────────
# Canonical INBOUND greeting — spoken when the AI answers an incoming call.
AI_GREETING: str          = os.environ.get(
    "AI_GREETING",
    "Guten Tag, Sie sprechen mit dem digitalen Assistenten von Teleprofi Fulda. "
    "Wie kann ich Ihnen helfen?",
)
# Canonical OUTBOUND greetings — kept deliberately different from the inbound
# greeting because outbound calls are initiated by Teleprofi. The purpose variant
# embeds the call purpose verbatim via {purpose}.
AI_OUTBOUND_GREETING: str = os.environ.get(
    "AI_OUTBOUND_GREETING",
    "Guten Tag, hier ist der digitale Assistent von Teleprofi Fulda. "
    "Ich melde mich kurz bezüglich Ihrer Anfrage.",
)
AI_OUTBOUND_GREETING_PURPOSE: str = os.environ.get(
    "AI_OUTBOUND_GREETING_PURPOSE",
    "Guten Tag, hier ist der digitale Assistent von Teleprofi Fulda. "
    "Ich rufe an wegen: {purpose}",
)
AI_LANGUAGE: str          = os.environ.get("AI_LANGUAGE", "de")
AI_MAX_CALL_SECONDS: int  = int(os.environ.get("AI_MAX_CALL_SECONDS", "300"))
AI_RING_TIMEOUT_SECONDS: int = int(os.environ.get("AI_RING_TIMEOUT_SECONDS", "15"))
AI_TRANSFER_EXTENSION: str = os.environ.get("AI_TRANSFER_EXTENSION", "")
AI_AFTER_HOURS_START: int = int(os.environ.get("AI_AFTER_HOURS_START", "18"))
AI_AFTER_HOURS_END: int   = int(os.environ.get("AI_AFTER_HOURS_END", "8"))

# ── Escalation / waiting room ─────────────────────────────────────────────────
AI_WAITING_ROOM_PRIMARY: str   = os.environ.get("AI_WAITING_ROOM_PRIMARY", "")
AI_WAITING_ROOM_SECONDARY: str = os.environ.get("AI_WAITING_ROOM_SECONDARY", "")

# Optional webhook called when a call starts ringing (for push notification).
# POST {"event": "ringing", "caller": str, "caller_name": str|null, "ringing_since": ISO-8601}
AI_RING_WEBHOOK_URL: str = os.environ.get("AI_RING_WEBHOOK_URL", "")

# ── Escalation email / SMTP ───────────────────────────────────────────────────
ESCALATION_EMAIL_TO: str   = os.environ.get("ESCALATION_EMAIL_TO", "")
ESCALATION_EMAIL_FROM: str = os.environ.get("ESCALATION_EMAIL_FROM", "")
ESCALATION_SMTP_HOST: str  = os.environ.get("ESCALATION_SMTP_HOST", "")
ESCALATION_SMTP_PORT: int  = int(os.environ.get("ESCALATION_SMTP_PORT", "587"))
ESCALATION_SMTP_USER: str  = os.environ.get("ESCALATION_SMTP_USER", "")
ESCALATION_SMTP_PASS: str  = os.environ.get("ESCALATION_SMTP_PASS", "")

# ── FreeSWITCH ESL ────────────────────────────────────────────────────────────
FREESWITCH_ESL_HOST: str     = os.environ.get("FREESWITCH_ESL_HOST", "127.0.0.1")
FREESWITCH_ESL_PORT: int     = int(os.environ.get("FREESWITCH_ESL_PORT", "8021"))
FREESWITCH_ESL_PASSWORD: str = os.environ.get("FREESWITCH_ESL_PASSWORD", "ClueCon")

# Silence threshold for recording (raised to 500+ for noisy VoIP lines)
AI_RECORD_SILENCE_THRESHOLD_MS: int = int(os.environ.get("AI_RECORD_SILENCE_THRESHOLD_MS", "500"))

# ── Per-turn recording behaviour ─────────────────────────────────────────────
# Upper bound on a single user-utterance recording (seconds). Lowered from the
# old hard-coded 20 so short utterances no longer wait for the full window
# before the AI starts processing. Silence detection still ends most turns
# earlier than this cap.
AI_RECORD_MAX_SECONDS: int = int(os.environ.get("AI_RECORD_MAX_SECONDS", "8"))

# Trailing-silence duration that ends the recording (seconds). Converted to
# FreeSWITCH "silence hits" (consecutive 20 ms frames) internally. Larger
# values give callers more think-time before the AI starts processing.
# Bumped from 1.2 → 1.8 so real callers who pause mid-sentence (especially
# annoyed/hesitant ones) are not cut off prematurely.
AI_RECORD_SILENCE_SECONDS: float = float(
    os.environ.get("AI_RECORD_SILENCE_SECONDS", "1.8")
)

# Extra slack added to the ESL execute() timeout on top of AI_RECORD_MAX_SECONDS,
# so FreeSWITCH has time to flush the WAV and return after the recording cap is
# reached. Increase only if you see "record timed out" warnings on slow links.
AI_RECORD_INITIAL_TIMEOUT_SECONDS: int = int(
    os.environ.get("AI_RECORD_INITIAL_TIMEOUT_SECONDS", "5")
)

# ── FreeSWITCH ESL Outbound Socket ────────────────────────────────────────────
# Port on which our Python app listens for FreeSWITCH outbound connections.
# Configure the FS dialplan with: <action application="socket" data="HOST:8085 async full"/>
FREESWITCH_ESL_OUTBOUND_PORT: int = int(
    os.environ.get("FREESWITCH_ESL_OUTBOUND_PORT", "8085")
)
# IP that FreeSWITCH uses to connect back to Python (used in originate commands).
# When FS runs in WSL2 and Python on Windows, this is the WSL2 gateway (Windows host IP).
# Find it in WSL2: cat /etc/resolv.conf | grep nameserver
FREESWITCH_ESL_OUTBOUND_HOST: str = os.environ.get(
    "FREESWITCH_ESL_OUTBOUND_HOST", "172.21.224.1"
)
# Directory for temporary WAV files exchanged with FreeSWITCH (recordings + TTS).
# Must be writable by the Python process and readable by FreeSWITCH.
# On Windows both processes run locally so the same absolute path works for both.
FREESWITCH_AUDIO_TEMP_DIR: str = os.environ.get(
    "FREESWITCH_AUDIO_TEMP_DIR", "./data/esl_audio"
)

# ── LLM ──────────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str   = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL: str            = os.environ.get("MODEL", "google/gemini-2.5-pro-preview")

# ── Contacts ─────────────────────────────────────────────────────────────────
CONTACTS_FILE: str        = os.environ.get("CONTACTS_FILE", "AI_Phone_Contacts.xlsx")

# ── Company Profile (Layer 2 — injectable per client via .env) ───────────────
# Swap these variables per deployment. The AI core behaviour (Layer 1) in
# llm_bridge.py stays untouched; only these values change per client.
AI_COMPANY_NAME: str        = os.environ.get("AI_COMPANY_NAME", "")
AI_COMPANY_DESCRIPTION: str = os.environ.get("AI_COMPANY_DESCRIPTION", "")
# Pipe-separated list of services/products, e.g. "VoIP|Headsets|Support"
AI_COMPANY_SERVICES: str    = os.environ.get("AI_COMPANY_SERVICES", "")
AI_COMPANY_HOURS: str       = os.environ.get("AI_COMPANY_HOURS", "")
AI_COMPANY_LOCATION: str    = os.environ.get("AI_COMPANY_LOCATION", "")
# Free-text notes: pricing policy, legacy systems, special instructions
AI_COMPANY_EXTRA: str       = os.environ.get("AI_COMPANY_EXTRA", "")

# ── Client Knowledge File (Layer 3 — long-form markdown per client) ──────────
# Path to a Markdown file containing the AI's authoritative client knowledge
# (identity, services, products, triage, escalation rules, etc.). Loaded once
# at import time by voice/llm_bridge.py and injected into both the inbound and
# outbound system prompts. Leave empty to use the default location:
#   backend/voice/knowledge/teleprofi_fulda.md
AI_KNOWLEDGE_FILE: str      = os.environ.get("AI_KNOWLEDGE_FILE", "")

# ── Validation (called at startup) ───────────────────────────────────────────
REQUIRED = {
    # SIP credentials are now managed in FreeSWITCH gateway XML, not Python.
    # Only the LLM key is required for the Python process to start.
    "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
}


def validate() -> list[str]:
    """Return list of missing required env var names."""
    return [k for k, v in REQUIRED.items() if not v]
