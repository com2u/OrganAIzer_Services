"""
NLU Service — intent + slot-patch extraction for active tasks.

Called ONLY when an active task exists. Detects:
  - Corrections / slot patches  (modify_draft)
  - Confirmations               (confirm)
  - Cancellations               (cancel)
  - New slot values             (provide_slot)
  - Unrelated messages          (general)

Strategy: deterministic pattern matching first (zero cost), LLM fallback only
for ambiguous "no, …" messages that patterns couldn't resolve.
Never executes tools — classification and extraction only.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Provider keyword lists (also exported for _normalize_provider) ─────────────

MS_KEYWORDS = [
    "outlook", "microsoft", "otlook", "outlok", "outloook", "outllook",
    "mircosoft", "microfost", "microft", "microsft", "microsoftt",
    "office365", "office 365", "hotmail", "ms teams",
    "work calendar", "work email", "work mail",
]
GOOGLE_KEYWORDS = [
    "google", "gmail", "gcal", "goggle", "gmaill", "gogle", "g mail",
    "google calendar", "personal calendar", "personal email",
]

# ── Confirm / Cancel signals ───────────────────────────────────────────────────

_CONFIRM_EXACT = frozenset({
    "yes", "y", "yep", "yeah", "yup", "sure", "ok", "okay",
    "perfect", "correct", "send it", "create it", "do it", "add it",
    "looks good", "confirm", "go ahead", "approve", "please", "proceed",
    "sounds good", "that's right", "that's correct", "great",
})

_CANCEL_EXACT = frozenset({
    "cancel", "stop", "abort", "never mind", "nevermind", "forget it", "quit",
    "no thanks", "no thank you", "don't", "don't do it",
})

# ── Time shortcut map ─────────────────────────────────────────────────────────

_TIME_KEYWORDS: Dict[str, str] = {
    "midnight":     "00:00",
    "early morning": "07:00",
    "morning":      "09:00",
    "noon":         "12:00",
    "lunch time":   "12:00",
    "lunchtime":    "12:00",
    "lunch":        "12:00",
    "afternoon":    "14:00",
    "evening time": "18:00",
    "evening":      "18:00",
    "night":        "20:00",
    "end of day":   "17:00",
    "eod":          "17:00",
    "start of day": "08:00",
    "sod":          "08:00",
}


@dataclass
class NLUResult:
    """Structured output from the NLU step."""
    intent: str          # "modify_draft" | "confirm" | "cancel" | "provide_slot" | "general"
    updates: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    needs_clarification: bool = False
    clarifying_question: Optional[str] = None
    raw_input: str = ""


class NLUExtractor:
    """Deterministic-first NLU with optional LLM fallback."""

    # ── Main entry point ──────────────────────────────────────────────────────

    @staticmethod
    async def extract(
        message: str,
        task_type: str,
        current_slots: Dict[str, Any],
        chat_service,
    ) -> NLUResult:
        """
        1. Fast deterministic extraction.
        2. LLM fallback only for ambiguous "no + content" messages.
        """
        result = NLUExtractor._deterministic(message, task_type, current_slots)
        if result is not None:
            return result
        return await NLUExtractor._llm_fallback(message, task_type, current_slots, chat_service)

    # ── Deterministic layer ───────────────────────────────────────────────────

    @staticmethod
    def _deterministic(
        message: str,
        task_type: str,
        current_slots: Dict[str, Any],
    ) -> Optional[NLUResult]:
        """
        Pattern-based extraction. Returns None to signal: use LLM fallback.
        Runs WITHOUT existing-slot guards so corrections always apply.
        """
        msg = message.strip()
        msg_lower = msg.lower()

        # ── CONFIRM ───────────────────────────────────────────────────────────
        if msg_lower in _CONFIRM_EXACT or any(
            msg_lower.startswith(c + " ") for c in _CONFIRM_EXACT if len(c) > 2
        ):
            return NLUResult(intent="confirm", confidence=1.0, raw_input=message)

        # ── CANCEL (bare / explicit) ───────────────────────────────────────────
        if msg_lower in _CANCEL_EXACT:
            return NLUResult(intent="cancel", confidence=1.0, raw_input=message)

        # Bare "no" or "no" + filler words — treat as cancel only when nothing else follows
        words = [w for w in msg_lower.split() if w not in ("please", "the", "a", "an")]
        if words and words[0] == "no" and len(words) <= 2:
            if not NLUExtractor._has_correction_words(msg_lower):
                return NLUResult(intent="cancel", confidence=0.95, raw_input=message)

        # ── SLOT EXTRACTION (bypass existing-slot guards) ─────────────────────
        updates: Dict[str, Any] = {}

        title = NLUExtractor._extract_title(msg, msg_lower)
        if title:
            updates["title"] = title

        provider = NLUExtractor._extract_provider(msg_lower)
        if provider:
            updates["provider"] = provider

        time_val = NLUExtractor._extract_time(msg, msg_lower)
        if time_val:
            updates["time"] = time_val

        date_val = NLUExtractor._extract_date(msg_lower)
        if date_val:
            updates["date"] = date_val

        if task_type in ("send_email", "draft_email"):
            subject = NLUExtractor._extract_subject(msg)
            if subject:
                updates["subject"] = subject

        if updates:
            return NLUResult(
                intent="modify_draft",
                updates=updates,
                confidence=0.92,
                raw_input=message,
            )

        # "no, <something we couldn't parse>" → defer to LLM
        if msg_lower.startswith("no,") or (words and words[0] == "no" and len(words) > 2):
            return None   # LLM fallback

        return NLUResult(intent="general", confidence=0.5, raw_input=message)

    # ── Individual extractors (NO existing-slot guards) ───────────────────────

    @staticmethod
    def _extract_title(msg: str, msg_lower: str) -> Optional[str]:
        """
        Extract an explicit title correction from the message.

        Patterns covered (live-log bugs fixed):
        - Quoted string anywhere: "call it 'Sprint Review'"
        - "call it X" / "name it X" / "rename (it) to X"
        - "change the title to X" / "change title to X"   ← new (live-log bug)
        - "set the title to X" / "set title to X"         ← new
        - "update the title to X" / "update title to X"   ← new
        - "the title is X" / "title: X" / "title should be X"
        """
        patterns = [
            # Quoted string anywhere
            r"""["']([^"']{1,80})["']""",
            # "call it X", "name it X", "rename (it) to X", "let's call it X"
            r"(?:call\s+it|name\s+it|rename(?:\s+it)?\s+to|name(?:\s+the\s+event)?\s+to|"
            r"let(?:'s|\s+us)?\s+call\s+it)\s+(.{1,80})$",
            # "change the title to X" / "change title to X"  (live-log bug fix)
            r"change\s+(?:the\s+)?title\s+to\s+(.{1,80})$",
            # "set the title to X" / "set title to X"
            r"set\s+(?:the\s+)?title\s+(?:to\s+)?(.{1,80})$",
            # "update the title to X" / "update title to X"
            r"update\s+(?:the\s+)?title\s+(?:to\s+)?(.{1,80})$",
            # "title: X" / "title should be X" / "the title is X"
            r"(?:title|entitle[sd]?)\s*:?\s*(.{1,80})$",
        ]
        for pat in patterns:
            m = re.search(pat, msg, re.IGNORECASE)
            if not m:
                continue
            raw = m.group(1).strip().strip("'\"").strip()
            raw = re.sub(r"[;,.]$", "", raw).strip()
            if 1 < len(raw) <= 80:
                return raw
        return None

    @staticmethod
    def _extract_provider(msg_lower: str) -> Optional[str]:
        """Fuzzy provider extraction — handles common typos."""
        for kw in MS_KEYWORDS:
            if kw in msg_lower:
                return "microsoft"
        for kw in GOOGLE_KEYWORDS:
            if kw in msg_lower:
                return "google"
        return None

    @staticmethod
    def _extract_time(msg: str, msg_lower: str) -> Optional[str]:
        """Extract time correction — bypasses existing-slot guards."""
        # Keyword shortcuts (longest first to avoid prefix clashes)
        for kw in sorted(_TIME_KEYWORDS, key=len, reverse=True):
            if kw in msg_lower:
                return _TIME_KEYWORDS[kw]

        # Explicit correction phrases + standalone HH:MM
        time_pats = [
            r"(?:make\s+it|change\s+(?:it\s+)?to|move\s+(?:it\s+)?to|at|from)\s+(\d{1,2}[:.]\d{2})",
            r"(?:make\s+it|change\s+(?:it\s+)?to|move\s+(?:it\s+)?to)\s+(\d{1,2})\s*(?:h\b|uhr)",
            r"(\d{1,2}[:.]\d{2})\s+instead",
            r"(\d{1,2})\s*(?:o'clock|uhr)\b",
            r"\b(\d{1,2}:\d{2})\b",
        ]
        for pat in time_pats:
            m = re.search(pat, msg_lower)
            if not m:
                continue
            raw = m.group(1).replace(".", ":").strip()
            parts = raw.split(":")
            try:
                if len(parts) == 2:
                    return f"{int(parts[0]):02d}:{parts[1].zfill(2)}"
                if len(parts) == 1 and parts[0].isdigit():
                    return f"{int(parts[0]):02d}:00"
            except ValueError:
                pass

        # "in X hours" relative
        m = re.search(r"\bin\s+(\d+)\s+hours?\b", msg_lower)
        if m:
            t = datetime.now() + timedelta(hours=int(m.group(1)))
            return t.strftime("%H:%M")

        return None

    @staticmethod
    def _extract_date(msg_lower: str) -> Optional[str]:
        """Extract date correction."""
        today = datetime.now()
        if "tomorrow" in msg_lower:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        if re.search(r"\btoday\b", msg_lower):
            return today.strftime("%Y-%m-%d")
        if "next week" in msg_lower:
            return (today + timedelta(days=7)).strftime("%Y-%m-%d")
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", msg_lower)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _extract_subject(msg: str) -> Optional[str]:
        """Extract email subject correction."""
        m = re.search(r"(?:subject|re|regarding)\s*:\s*(.+?)(?:\n|$|\.)", msg, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _has_correction_words(msg_lower: str) -> bool:
        """
        Returns True if the text after 'no' contains correction/edit content.

        Also covers "edit", "modify", "update", "i want to" so that messages
        like "No, I would like you to edit this event" are classified as
        MODIFY_DRAFT rather than CANCEL (group-10 stuck-state fix).
        """
        stripped = re.sub(r"^no[,.]?\s*", "", msg_lower).strip()
        if not stripped:
            return False
        triggers = [
            "call it", "name it", "rename", "title",
            "use ", "switch", "make it", "change",
            "instead", "at ", "tomorrow", "today",
            "morning", "evening", "noon",
            "outlook", "google", "microsoft",
            # ── Group 10 additions: edit-intent words ────────────────────────
            "edit", "modify", "update", "adjust", "fix",
            "i want", "i'd like", "would like", "i would like",
        ]
        for t in triggers:
            if t in stripped:
                return True
        # >2 meaningful words also counts
        meaningful = [w for w in stripped.split() if w not in ("please", "the", "it", "a", "an")]
        return len(meaningful) >= 2

    # ── LLM fallback ──────────────────────────────────────────────────────────

    @staticmethod
    async def _llm_fallback(
        message: str,
        task_type: str,
        current_slots: Dict[str, Any],
        chat_service,
    ) -> NLUResult:
        """LLM-based extraction for ambiguous messages."""
        from models.chat import ChatRequest, ChatMessage

        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        system = (
            f"You are a slot-extraction model. Today={today}, tomorrow={tomorrow}.\n"
            f"Active task: {task_type} | current slots: {json.dumps(current_slots, ensure_ascii=False)}\n"
            "Return ONLY valid JSON (no markdown). Schema:\n"
            '{"intent":"modify_draft|confirm|cancel|provide_slot|general",'
            '"updates":{},"confidence":0.0}\n'
            "intent: modify_draft=user corrects a slot, confirm=yes/ok, cancel=no/stop.\n"
            "updates keys: title(str), time(HH:MM), date(YYYY-MM-DD), "
            "provider(google|microsoft), subject(str), body(str), to_email(str).\n"
            "provider map: outlook/ms/microsoft/work→microsoft, google/gmail/gcal/personal→google."
        )

        try:
            from models.chat import ChatRequest, ChatMessage
            req = ChatRequest(
                prompt=f'User: "{message}"\nJSON:',
                conversation_history=[ChatMessage(role="system", content=system)],
                temperature=0.0,
                max_tokens=200,
            )
            resp = await chat_service.chat_completion(req)
            raw = resp.response.strip()
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
            data = json.loads(raw)
            return NLUResult(
                intent=data.get("intent", "general"),
                updates=data.get("updates", {}),
                confidence=float(data.get("confidence", 0.7)),
                raw_input=message,
            )
        except Exception as exc:
            logger.warning("[NLU] LLM fallback failed: %s", exc)
            return NLUResult(intent="general", confidence=0.4, raw_input=message)
