"""
Voice module configuration — reads everything from environment variables.
Never import credentials directly; always go through this module.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# ── COMtrexx / SIP ────────────────────────────────────────────────────────────
COMTREXX_IP: str          = os.environ.get("COMTREXX_IP", "172.20.0.244")
COMTREXX_SIP_PORT: int    = int(os.environ.get("COMTREXX_SIP_PORT", "5060"))
COMTREXX_SIP_USER: str    = os.environ.get("COMTREXX_SIP_USER", "")
COMTREXX_SIP_PASS: str    = os.environ.get("COMTREXX_SIP_PASS", "")
COMTREXX_SIP_DOMAIN: str  = os.environ.get("COMTREXX_SIP_DOMAIN", COMTREXX_IP)
COMTREXX_EXTENSION: str   = os.environ.get("COMTREXX_EXTENSION", "")
COMTREXX_CALLER_ID: str   = os.environ.get("COMTREXX_CALLER_ID", "")

# ── AI behaviour ─────────────────────────────────────────────────────────────
AI_GREETING: str          = os.environ.get(
    "AI_GREETING", "Hallo, hier ist Ihr KI-Assistent. Wie kann ich helfen?"
)
AI_LANGUAGE: str          = os.environ.get("AI_LANGUAGE", "de")
AI_MAX_CALL_SECONDS: int  = int(os.environ.get("AI_MAX_CALL_SECONDS", "300"))
AI_RING_TIMEOUT_SECONDS: int = int(os.environ.get("AI_RING_TIMEOUT_SECONDS", "15"))
AI_TRANSFER_EXTENSION: str = os.environ.get("AI_TRANSFER_EXTENSION", "")
AI_AFTER_HOURS_START: int = int(os.environ.get("AI_AFTER_HOURS_START", "18"))
AI_AFTER_HOURS_END: int   = int(os.environ.get("AI_AFTER_HOURS_END", "8"))

# ── LLM ──────────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str   = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL: str            = os.environ.get("MODEL", "google/gemini-2.5-pro-preview")

# ── Contacts ─────────────────────────────────────────────────────────────────
CONTACTS_FILE: str        = os.environ.get("CONTACTS_FILE", "AI_Phone_Contacts.xlsx")

# ── Validation (called at startup) ───────────────────────────────────────────
REQUIRED = {
    "COMTREXX_SIP_USER": COMTREXX_SIP_USER,
    "COMTREXX_SIP_PASS": COMTREXX_SIP_PASS,
    "COMTREXX_EXTENSION": COMTREXX_EXTENSION,
    "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
}


def validate() -> list[str]:
    """Return list of missing required env var names."""
    return [k for k, v in REQUIRED.items() if not v]
