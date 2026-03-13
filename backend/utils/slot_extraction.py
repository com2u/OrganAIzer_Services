"""
Semantic Slot Extraction Utilities

CRITICAL SEMANTIC PARSING RULES:
1. Extract ALL entities from EVERY user message
2. Lock slots once extracted - NEVER re-ask
3. Parse natural language sentences for structured data
4. Handle multiple slots in single message

Example:
User: "Meeting with Chef at 08:00"
Extract: title="Meeting with Chef", time="08:00"
FORBIDDEN: Re-asking for title
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class SlotExtractor:
    """
    Intelligent slot extraction from natural language.
    
    Extracts structured data (emails, dates, times, etc.) from conversational text.
    """
    
    @staticmethod
    def extract_calendar_slots(message: str, existing_slots: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        MANDATORY SEMANTIC PARSING for calendar events.
        
        Extracts from ANY user message:
        - title (event name)
        - date (today, tomorrow, weekday, explicit date)
        - start_time (08:00, 5pm, morning, evening)
        - end_time (explicit end time if provided)
        - provider (Google, Outlook)
        - duration (if mentioned)
        
        CRITICAL TIME PARSING RULES (FIX #1):
        - If BOTH start_time AND end_time are present, NEVER apply default duration
        - Apply default duration ONLY when end_time is missing
        - Parsing priority: a) explicit end_time, b) explicit duration, c) default duration
        
        CRITICAL RULES:
        1. Extract values even if they appear inside full sentences
        2. NEVER overwrite existing_slots unless explicitly changed
        3. Return all extracted slots, even if partial
        
        Args:
            message: User's input message
            existing_slots: Already-locked slots (won't be overwritten)
        
        Returns:
            Dict with extracted slots (only new/updated values)
        """
        existing = existing_slots or {}
        extracted = {}
        message_lower = message.lower().strip()

        logger.info("[CALENDAR_SLOT_EXTRACT] Parsing: '%s'", message[:120])
        
        # ==============================================
        # TITLE EXTRACTION (highest priority)
        # ==============================================
        # Phase A: Explicit title corrections — run REGARDLESS of existing title.
        # This handles "call it X", "name it X", etc. during the collecting state,
        # even when a system default like "Meeting" is already stored.
        explicit_title = SlotExtractor._extract_explicit_title_correction(message, message_lower)
        if explicit_title:
            extracted["title"] = explicit_title
            logger.info(f"[SLOT_EXTRACT] ✓ title (explicit correction): '{explicit_title}'")
        elif not existing.get("title"):
            # Phase B: Normal title extraction — only when no title is locked yet.
            title = SlotExtractor._extract_title(message, message_lower)
            if title:
                extracted["title"] = title
                logger.info(f"[SLOT_EXTRACT] ✓ title: '{title}'")

        # ── Post-extraction: STT title cleanup ────────────────────────────────
        # After STT (Whisper), titles sometimes arrive with leading/trailing
        # punctuation or contain patterns that strongly suggest a mishear
        # (e.g. "from 1011?", "call it 42", "what is").  Strip punctuation
        # and flag suspicious titles so the agent can ask for confirmation
        # rather than silently using a bad title.
        if "title" in extracted:
            cleaned, is_suspicious, reason = SlotExtractor._clean_and_validate_title(extracted["title"])
            extracted["title"] = cleaned
            if is_suspicious:
                extracted["title_needs_confirmation"] = True
                extracted["title_suspicious_reason"] = reason
                logger.warning(
                    "[SLOT_EXTRACT] ⚠ Suspicious STT title: '%s' — reason: %s",
                    cleaned, reason,
                )
        
        # ==============================================
        # TIME EXTRACTION (CRITICAL FIX: Extract both start and end times)
        # ==============================================
        if not existing.get("start_time") and not existing.get("time"):
            time_result = SlotExtractor._extract_time_range(message, message_lower)
            if time_result:
                if time_result.get("start_time"):
                    extracted["start_time"] = time_result["start_time"]
                    # Also set "time" for backward compatibility
                    extracted["time"] = time_result["start_time"]
                    logger.info(f"[SLOT_EXTRACT] ✓ start_time: {time_result['start_time']}")

                if time_result.get("end_time"):
                    extracted["end_time"] = time_result["end_time"]
                    logger.info(f"[SLOT_EXTRACT] ✓ end_time: {time_result['end_time']}")

                # Propagate ambiguity flag — the executive agent must ask the user
                # for clarification before creating the event.
                if time_result.get("ambiguous"):
                    extracted["time_ambiguous"] = True
                    extracted["time_ambiguity_hint"] = time_result.get("ambiguity_hint", "")
                    logger.warning(
                        "[SLOT_EXTRACT] ⚠ ambiguous time range — agent must ask: %s",
                        extracted["time_ambiguity_hint"],
                    )
        
        # ==============================================
        # DATE EXTRACTION
        # ==============================================
        if not existing.get("date"):
            date_str = SlotExtractor._extract_date(message, message_lower)
            if date_str:
                extracted["date"] = date_str
                logger.info(f"[SLOT_EXTRACT] ✓ date: {date_str}")
        
        # ==============================================
        # DURATION EXTRACTION (only if no end_time)
        # ==============================================
        if not extracted.get("end_time") and not existing.get("end_time"):
            duration = SlotExtractor._extract_duration(message, message_lower)
            if duration:
                extracted["duration"] = duration
                logger.info(f"[SLOT_EXTRACT] ✓ duration: {duration} minutes")
        
        # ==============================================
        # LOCATION EXTRACTION
        # ==============================================
        if not existing.get("location"):
            location = SlotExtractor._extract_location(message)
            if location:
                extracted["location"] = location
                logger.info(f"[SLOT_EXTRACT] ✓ location: '{location}'")
        
        # ==============================================
        # PROVIDER EXTRACTION (Google/Outlook) — locked if present
        # ==============================================
        if not existing.get("provider"):
            provider = SlotExtractor._extract_provider(message_lower)
            if provider:
                extracted["provider"] = provider
                logger.info("[CALENDAR_SLOT_EXTRACT] ✓ provider: %s (locked)", provider)

        # ==============================================
        # TIMEZONE EXTRACTION (optional, default = system TZ)
        # ==============================================
        if not existing.get("timezone"):
            tz = SlotExtractor._extract_timezone(message, message_lower)
            if tz:
                extracted["timezone"] = tz
                logger.info("[CALENDAR_SLOT_EXTRACT] ✓ timezone: %s", tz)

        logger.info(
            "[CALENDAR_SLOT_EXTRACT] Extracted %d slots: %s",
            len(extracted), list(extracted.keys()),
        )
        return extracted
    
    @staticmethod
    def _extract_title(message: str, message_lower: str) -> Optional[str]:
        """
        Extract event title from message with STRICT validation.
        
        CRITICAL RULES (NON-NEGOTIABLE):
        1. Title MUST be explicitly provided or clearly identifiable
        2. NEVER extract generic phrases like "create me an event"
        3. NEVER treat request verbs as titles
        4. Maximum length: 80 characters
        5. Preserve casing from quoted strings, Title Case otherwise
        
        PRIORITY ORDER (highest to lowest):
        1. Quoted strings: 'Project Meeting 2' → "Project Meeting 2"
        2. "call it X" / "name it X" / "rename it to X" patterns
        3. "called X" pattern: "event called Strategy Sync"
        4. Title before time marker: "Meeting with Chef at 08:00"
        5. Title before date marker: "Team meeting tomorrow"
        6. "schedule X" pattern with proper cleanup
        
        GARBAGE DETECTION:
        - Generic phrases: "an event", "a meeting", "create me"
        - Request verbs: "add", "schedule", "create"
        - Single letters or numbers
        → All default to "Meeting"
        """
        # PRIORITY 1: Quoted title (single or double quotes)
        # "Add an event tomorrow at 12:00; call it 'Project Meeting 2'"
        quoted = re.search(r'["\'](.+?)["\']', message)
        if quoted:
            title = quoted.group(1).strip()
            # Validate and truncate
            if len(title) > 80:
                title = title[:80]
            # Don't modify casing from quoted strings
            logger.info(f"[TITLE_EXTRACT] Found quoted title: '{title}'")
            return title
        
        # PRIORITY 2: "call it X" / "name it X" / "rename it to X" patterns
        # INTEGRITY FIX: search on original `message` to preserve user casing exactly.
        explicit_patterns = [
            r'call it\s+(.+?)(?:\s*;|\s*$)',
            r'name it\s+(.+?)(?:\s*;|\s*$)',
            r'rename it to\s+(.+?)(?:\s*;|\s*$)',
            r'title:\s*(.+?)(?:\s*;|\s*$)',
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                title = re.sub(r'[;,.]$', '', title).strip()
                if len(title) > 80:
                    title = title[:80]
                # INTEGRITY: Do NOT apply .title() — preserve exact user wording
                if len(title) > 0 and not SlotExtractor._is_garbage_title(title):
                    logger.info("[TITLE_EXTRACT] INTEGRITY: exact title from explicit pattern: '%s'", title)
                    return title

        # PRIORITY 3: "called X" pattern
        # "event called Strategy Sync"
        # INTEGRITY FIX: search on original `message` to preserve user casing exactly.
        called_match = re.search(
            r'(?:event|meeting)\s+called\s+(.+?)(?:\s+at|\s+on|\s+for|\s+tomorrow|\s+today|;|$)',
            message, re.IGNORECASE,
        )
        if called_match:
            title = called_match.group(1).strip()
            if len(title) > 80:
                title = title[:80]
            if not SlotExtractor._is_garbage_title(title):
                logger.info("[TITLE_EXTRACT] INTEGRITY: exact title from 'called' pattern: '%s'", title)
                return title
        
        # PRIORITY 4: "set up a [call|meeting|sync] with X" → "Call with X"
        call_setup_match = re.search(
            r'\bset\s+up\s+(?:a\s+)?(?:call|meeting|sync|chat|standup|check.?in)\s+with\s+(.+?)(?:\s+(?:at|on|for|tomorrow|today|next|\d)|;|$)',
            message_lower,
        )
        if call_setup_match:
            # INTEGRITY: preserve original casing of person name from original message
            call_setup_match_orig = re.search(
                r'\bset\s+up\s+(?:a\s+)?(?:call|meeting|sync|chat|standup|check.?in)\s+with\s+(.+?)(?:\s+(?:at|on|for|tomorrow|today|next|\d)|;|$)',
                message, re.IGNORECASE,
            )
            person = call_setup_match_orig.group(1).strip() if call_setup_match_orig else call_setup_match.group(1).strip()
            if 'call' in message_lower:
                title_candidate = f"Call with {person}"
            elif 'sync' in message_lower:
                title_candidate = f"Sync with {person}"
            else:
                title_candidate = f"Meeting with {person}"
            if not SlotExtractor._is_garbage_title(title_candidate):
                logger.info("[TITLE_EXTRACT] INTEGRITY: exact title from 'set up call with' pattern: '%s'", title_candidate)
                return title_candidate

        # PRIORITY 4b: "block X for [title]" — "block two hours tomorrow morning for deep work"
        # INTEGRITY FIX: use original message casing
        block_for_match = re.search(
            r'\bblock\s+.+?\bfor\s+(.+?)(?:\s+(?:on|at|tomorrow|today|next|\d)|;|$)',
            message, re.IGNORECASE,
        )
        if block_for_match:
            title_candidate = block_for_match.group(1).strip()
            if len(title_candidate) > 2 and not SlotExtractor._is_garbage_title(title_candidate):
                logger.info("[TITLE_EXTRACT] INTEGRITY: exact title from 'block for' pattern: '%s'", title_candidate)
                return title_candidate

        # PRIORITY 5: Title before time marker
        # "Meeting with Chef at 08:00" → extract "Meeting with Chef"
        # INTEGRITY FIX: use original `message` to preserve casing; do NOT call .title()
        time_markers = [r'\bat\s+\d', r'\b\d+:\d+', r'\b\d+\s*(?:am|pm)', r'\bfrom\s+\d']
        for marker in time_markers:
            parts = re.split(marker, message, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) > 1:
                potential_title = parts[0].strip()
                # Strip ONLY the command verb + optional article + optional "event"/"appointment"
                # IMPORTANT: do NOT strip "meeting" here — it may be part of the actual title
                # e.g. "Create event Meeting with Chef at 08:00" → we only strip "Create event "
                potential_title = re.sub(
                    r'^(?:schedule|set\s+up|block\s+(?:out\s+)?(?:\d+\s+\w+\s+)?|add|create)\s+(?:a\s+|an\s+)?(?:event\s+|appointment\s+)?',
                    '', potential_title, flags=re.IGNORECASE,
                ).strip()
                potential_title = re.sub(r';', '', potential_title).strip()
                if len(potential_title) > 2 and len(potential_title) <= 80 and not SlotExtractor._is_garbage_title(potential_title):
                    logger.info("[TITLE_EXTRACT] INTEGRITY: exact title before time marker: '%s'", potential_title)
                    return potential_title  # INTEGRITY: no .title() — preserve user wording

        # PRIORITY 6: Title before date marker
        # "Team meeting tomorrow" → "Team meeting" (preserve original casing)
        # INTEGRITY FIX: split on original casing `message`, not message_lower
        date_keywords = ['tomorrow', 'today', 'next week', 'next monday', 'next tuesday',
                         'next wednesday', 'next thursday', 'next friday', 'next saturday', 'next sunday']
        for keyword in date_keywords:
            if keyword in message_lower:
                # Split on case-insensitive keyword but keep original text
                parts = re.split(re.escape(keyword), message, maxsplit=1, flags=re.IGNORECASE)
                potential_title = parts[0].strip()
                potential_title = re.sub(
                    r'^(?:schedule|set\s+up|block\s+(?:out\s+)?|add|create)\s+(?:a\s+|an\s+)?(?:event\s+|appointment\s+)?',
                    '', potential_title, flags=re.IGNORECASE,
                ).strip()
                potential_title = re.sub(r';', '', potential_title).strip()
                if len(potential_title) > 2 and len(potential_title) <= 80 and not SlotExtractor._is_garbage_title(potential_title):
                    logger.info("[TITLE_EXTRACT] INTEGRITY: exact title before date keyword: '%s'", potential_title)
                    return potential_title  # INTEGRITY: no .title()

        # PRIORITY 7: "schedule X" or "add X" or "create X" with strict cleanup
        # INTEGRITY FIX: use original `message` to preserve casing; do NOT call .title()
        match = re.search(
            r'(?:schedule|add|create)\s+(?:a\s+)?(?:an\s+)?(?:event\s+)?(?:meeting\s+)?(?:with\s+)?(?:for\s+)?(.+?)(?:\s+at|\s+on|\s+for|\s+tomorrow|\s+today|\s+next|;|$)',
            message, re.IGNORECASE,
        )
        if match:
            title = match.group(1).strip()
            title = re.sub(r'\s+(at|on|for|tomorrow|today|next)\s+.*', '', title, flags=re.IGNORECASE).strip()
            if len(title) > 1 and len(title) <= 80 and not SlotExtractor._is_garbage_title(title):
                logger.info("[TITLE_EXTRACT] INTEGRITY: exact title from schedule/add pattern: '%s'", title)
                return title  # INTEGRITY: no .title()

        # PRIORITY 8: If message is short and specific, might be a title
        # INTEGRITY: preserve original message casing
        if len(message.split()) <= 5 and not re.search(r'\d|tomorrow|today|next', message_lower):
            if not any(message_lower.startswith(word) for word in ['what', 'when', 'where', 'who', 'why', 'how', 'is', 'are', 'can', 'do', 'add', 'schedule', 'create']):
                if not SlotExtractor._is_garbage_title(message):
                    logger.info("[TITLE_EXTRACT] INTEGRITY: using entire message as title: '%s'", message)
                    return message  # INTEGRITY: no .title()
        
        # No valid title found
        logger.info("[TITLE_EXTRACT] No valid title found - will default to 'Meeting'")
        return None
    
    @staticmethod
    def _is_garbage_title(title: str) -> bool:
        """
        Detect if a title is garbage/generic and should be rejected.

        Returns True if title is garbage, False if valid.
        """
        title_lower = title.lower().strip()

        # Empty or too short
        if len(title_lower) <= 1:
            return True

        # Generic / single-word titles that are NOT real titles
        garbage_phrases = {
            # Determiner + noun phrases
            'an event', 'a meeting', 'the event', 'the meeting',
            'create me', 'add me', 'schedule me',
            'me an', 'it', 'a', 'an', 'the', 'me',
            # Bare nouns — agent should use a default instead
            'event', 'meeting', 'appointment', 'something', 'anything',
            'thing', 'stuff',
            # Date words mistakenly extracted as titles
            'tomorrow', 'today', 'tonight', 'yesterday',
            'monday', 'tuesday', 'wednesday', 'thursday',
            'friday', 'saturday', 'sunday',
            'morning', 'afternoon', 'evening', 'noon', 'night',
        }
        if title_lower in garbage_phrases:
            return True

        # Just request verbs
        request_verbs = {'add', 'create', 'schedule', 'make', 'set', 'put', 'book'}
        if title_lower in request_verbs:
            return True

        # Contains request phrasing that makes it clearly NOT a title
        # e.g. "can you create an event for me", "please add a meeting"
        request_indicators = [
            'can you', 'could you', 'please ', 'would you', 'i need',
            'i want', 'i would like', 'i\'d like',
        ]
        for indicator in request_indicators:
            if indicator in title_lower:
                return True

        # Contains creation verbs — would mean we extracted the command, not the title
        creation_verb_pattern = re.compile(
            r'\b(create|schedule|add|make|set up|put|book|arrange)\b', re.IGNORECASE
        )
        if creation_verb_pattern.search(title_lower):
            return True

        # Single character or number
        if len(title_lower) == 1:
            return True

        # Titles starting with personal pronouns + article/noun are filler fragments,
        # not real event names.  Catches "me an event", "me a meeting", etc.
        # that slip through the exact-match check above.
        if re.match(r'^me\s+(a|an|the)\s+', title_lower):
            return True

        return False

    @staticmethod
    def _clean_and_validate_title(title: str):
        """
        Post-STT title cleanup and suspicious-title detection.

        Steps:
        1. Strip leading/trailing whitespace and common punctuation artefacts
           that Whisper often adds (? . , ! at the boundaries).
        2. Detect patterns that strongly suggest a mishear:
           - Starts with "from" (Whisper often outputs "from <garbled number>")
           - Contains only digits / numbers (e.g. "1011")
           - Contains a literal "?" (question mark in title = likely mishear)
           - Starts with a question word (what/where/who/why/when/how)
           - Ends with a question mark
           - Very short after stripping (< 2 meaningful chars)

        Returns:
            Tuple (cleaned_title: str, is_suspicious: bool, reason: str)
        """
        # ── Step 1: Strip punctuation artefacts at boundaries ────────────────
        cleaned = title.strip()
        # Strip leading/trailing: ? . , ! ; : – — 
        cleaned = re.sub(r'^[\?\.\,\!\;\:\-–—]+\s*', '', cleaned)
        cleaned = re.sub(r'\s*[\?\.\,\!\;\:\-–—]+$', '', cleaned)
        cleaned = cleaned.strip()

        if not cleaned:
            return title, True, "Empty after stripping punctuation"

        lower = cleaned.lower()

        # ── Step 2: Suspicious pattern detection ─────────────────────────────
        # Pattern A: starts with "from" — common Whisper mishear of "call it from…"
        if lower.startswith("from ") or lower == "from":
            return cleaned, True, f"Title starts with 'from' — likely STT mishear: '{cleaned}'"

        # Pattern B: only digits / digit-words
        if re.fullmatch(r'[\d\s]+', cleaned):
            return cleaned, True, f"Title is only numbers — likely STT mishear: '{cleaned}'"

        # Pattern C: contains literal "?" 
        if "?" in cleaned:
            return cleaned, True, f"Title contains '?' — likely STT question mishear: '{cleaned}'"

        # Pattern D: starts with a question word
        question_starters = ("what ", "where ", "who ", "why ", "when ", "how ", "is ", "are ", "did ")
        if any(lower.startswith(qs) for qs in question_starters):
            return cleaned, True, f"Title starts with question word — likely mishear: '{cleaned}'"

        # Pattern E: very short (1 char) after cleaning
        if len(cleaned) < 2:
            return cleaned, True, f"Title too short after cleanup: '{cleaned}'"

        return cleaned, False, ""

    @staticmethod
    def _extract_explicit_title_correction(message: str, message_lower: str) -> Optional[str]:
        """
        Extract EXPLICIT title-setting commands from user messages.

        This method runs BEFORE the existing-slot guard in extract_calendar_slots,
        so it applies even when a title is already stored (e.g., the system
        default "Meeting").  The patterns signal deliberate correction intent.

        Supported patterns (all via re.search → works anywhere in sentence):
        - "call it <title>"
        - "name it <title>"
        - "rename it to <title>" / "rename to <title>"
        - "make the title <title>" / "make it <title>" (as title)
        - "title: <title>" / "title should be <title>" / "title is <title>"

        Examples that MUST work:
        - "call it test frontend"               → "test frontend"
        - "i would like you to call it test frontend" → "test frontend"
        - "please name it Sprint Review"        → "Sprint Review"
        - "make the title Team Sync"            → "Team Sync"
        - "title should be Q2 Planning"         → "Q2 Planning"

        Returns:
            Extracted title string (original user casing), or None.
        """
        explicit_patterns = [
            # "call it X" / "name it X" — with optional prefix words via re.search
            r'call\s+it\s+(.+?)(?:\s*;|\s*$)',
            r'name\s+it\s+(.+?)(?:\s*;|\s*$)',
            # "rename it to X" / "rename to X"
            r'rename\s+(?:it\s+)?(?:to\s+)?(.+?)(?:\s*;|\s*$)',
            # "make the title X" / "make it title X"
            r'make\s+(?:the\s+)?title\s+(.+?)(?:\s*;|\s*$)',
            # "title: X" / "title should be X" / "title is X"
            r'title\s*(?::\s*|should\s+be\s+|is\s+)(.+?)(?:\s*;|\s*$)',
        ]

        for pattern in explicit_patterns:
            m = re.search(pattern, message, re.IGNORECASE)
            if not m:
                continue
            raw = m.group(1).strip().strip("'\"").strip()
            raw = re.sub(r'[;,.]$', '', raw).strip()
            if 1 < len(raw) <= 80 and not SlotExtractor._is_garbage_title(raw):
                logger.info("[TITLE_EXTRACT] Explicit title correction: '%s'", raw)
                return raw

        return None
    
    @staticmethod
    def _normalize_ampm(text: str) -> str:
        """
        Normalise written-out AM/PM variants to simple 'am'/'pm'.

        Handles: p.m., P.M., p. m., PM, pm, a.m., A.M., a. m., AM, am
        Called before all time-range regex so '11 p.m.' is treated as '11 pm'.
        """
        text = re.sub(r'\bp\s*\.\s*m\s*\.', 'pm', text, flags=re.IGNORECASE)
        text = re.sub(r'\ba\s*\.\s*m\s*\.', 'am', text, flags=re.IGNORECASE)
        # Remaining standalone PM/AM already handled by regex; ensure lower-case
        return text.lower()

    @staticmethod
    def _extract_time_range(message: str, message_lower: str) -> Optional[Dict[str, Any]]:
        """
        Extract start_time and end_time from message.

        Spoken-language support added:
        - Normalises "p.m." / "a.m." / "P.M." to "pm" / "am" before regex
        - Detects logically inconsistent or ambiguous ranges (e.g. "11pm till 12pm")
          and adds an "ambiguous" key so the agent can ask for clarification

        Range patterns:
          "from 10:00 to 18:00"  →  start: 10:00, end: 18:00
          "10am to 6pm"          →  start: 10:00, end: 18:00
          "11 p.m. till 12 p.m." →  ambiguous (23:00→12:00 is inconsistent)
          "11pm to midnight"     →  start: 23:00 (end extracted separately if present)

        Single-time patterns:
          "08:00"  →  start: 08:00
          "5pm"    →  start: 17:00
          "morning" → start: 09:00

        Returns:
            Dict with start_time, optional end_time, optional ambiguous:bool
            or None if no time found.
        """
        result: Dict[str, Any] = {}

        # Normalise p.m./a.m. variants in BOTH working strings
        norm_lower = SlotExtractor._normalize_ampm(message_lower)
        norm_msg   = SlotExtractor._normalize_ampm(message)

        # ── RANGE PATTERNS (checked first) ───────────────────────────────────

        # Pattern 1: "from HH:MM to HH:MM" (24-hour)
        range_match = re.search(
            r'(?:from\s+)?(\d{1,2}):(\d{2})\s*(?:to|until|till|-|–|—)\s*(\d{1,2}):(\d{2})',
            norm_msg,
        )
        if range_match:
            sh, sm, eh, em = range_match.groups()
            result["start_time"] = f"{int(sh):02d}:{sm}"
            result["end_time"]   = f"{int(eh):02d}:{em}"
            logger.info("[TIME_EXTRACT] Found 24h range: %s–%s", result["start_time"], result["end_time"])
            return result

        # Pattern 2: "H[:]MM am/pm to H[:]MM am/pm"  (spoken time)
        range_match = re.search(
            r'(?:from\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*(?:to|until|till|-|–|—)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            norm_lower,
        )
        if range_match:
            s_h, s_m, s_ap, e_h, e_m, e_ap = range_match.groups()

            # Convert start
            sh = int(s_h)
            sm = int(s_m) if s_m else 0
            if s_ap == 'pm' and sh < 12:
                sh += 12
            elif s_ap == 'am' and sh == 12:
                sh = 0

            # Convert end
            eh = int(e_h)
            em = int(e_m) if e_m else 0
            if e_ap == 'pm' and eh < 12:
                eh += 12
            elif e_ap == 'am' and eh == 12:
                eh = 0

            result["start_time"] = f"{sh:02d}:{sm:02d}"
            result["end_time"]   = f"{eh:02d}:{em:02d}"

            # ── Logical-inconsistency check ───────────────────────────────────
            # "11 pm till 12 pm" → start=23, end=12 → end < start → ambiguous.
            # The user likely said "12 pm" but meant "12 am" (midnight), OR they
            # genuinely want a 13-hour block ending at noon the next day.
            # Either way the agent must ask for clarification.
            start_mins = sh * 60 + sm
            end_mins   = eh * 60 + em
            if end_mins < start_mins:
                logger.warning(
                    "[TIME_EXTRACT] Ambiguous time range: %s → %s (end < start, "
                    "possible AM/PM confusion).  Will ask for clarification.",
                    result["start_time"], result["end_time"],
                )
                result["ambiguous"] = True
                result["ambiguity_hint"] = (
                    f"Did you mean {result['start_time']} to {result['end_time']} "
                    f"(next day / 13 h), or {result['start_time']} to "
                    f"{eh:02d}:00 AM (midnight, 1 h)?"
                )
            elif start_mins == end_mins:
                result["ambiguous"] = True
                result["ambiguity_hint"] = (
                    f"Start and end time are the same ({result['start_time']}). "
                    "Did you mean a different end time?"
                )

            logger.info(
                "[TIME_EXTRACT] Found spoken range: %s–%s  ambiguous=%s",
                result["start_time"], result["end_time"], result.get("ambiguous", False),
            )
            return result

        # ── SINGLE-TIME FALLBACK ──────────────────────────────────────────────

        # Pattern 3: HH:MM (24-hour)
        match = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', norm_msg)
        if match:
            hour, minute = match.groups()
            result["start_time"] = f"{int(hour):02d}:{minute}"
            logger.info("[TIME_EXTRACT] Found single time (24h): %s", result["start_time"])
            return result

        # Pattern 4: H[:]MM am/pm  or  H am/pm  (spoken)
        match = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', norm_lower)
        if match:
            h_str, m_str, ampm = match.groups()
            h = int(h_str)
            m = int(m_str) if m_str else 0
            if ampm == 'pm' and h < 12:
                h += 12
            elif ampm == 'am' and h == 12:
                h = 0
            result["start_time"] = f"{h:02d}:{m:02d}"
            logger.info("[TIME_EXTRACT] Found single spoken time: %s", result["start_time"])
            return result

        # Pattern 5: keyword times
        time_keywords = {
            'morning':   '09:00',
            'noon':      '12:00',
            'afternoon': '14:00',
            'evening':   '18:00',
            'night':     '20:00',
        }
        for keyword, default_time in time_keywords.items():
            if keyword in norm_lower:
                result["start_time"] = default_time
                logger.info("[TIME_EXTRACT] Found keyword time '%s' → %s", keyword, default_time)
                return result

        # Pattern 6: Fuzzy / partial AM-PM notation — "11 m", "11 p", "11 a"
        # Handles incomplete spoken input where the user typed only one letter
        # instead of the full "am" / "pm" suffix.
        # Rules:
        #   "11 p"  → likely PM   → tentative start_time=23:00 + ambiguous flag
        #   "11 a"  → likely AM   → tentative start_time=11:00 + ambiguous flag
        #   "11 m"  → ambiguous   → no start_time set          + ambiguous flag
        # Must be checked LAST to avoid false positives with real am/pm patterns
        # (Patterns 1-4 return early, so this is only reached when none matched).
        # Word-boundary `\b` after the suffix prevents matching "11 min", "11 months".
        fuzzy_match = re.search(r'\b(\d{1,2})\s+([apm])\b', norm_lower)
        if fuzzy_match:
            hour_str, suffix = fuzzy_match.group(1), fuzzy_match.group(2)
            h = int(hour_str)
            if 1 <= h <= 12:
                if suffix == 'p':
                    # Likely PM — set tentative time, still ask for confirmation
                    start_h = (h + 12) if h < 12 else 12
                    result["start_time"] = f"{start_h:02d}:00"
                elif suffix == 'a':
                    # Likely AM — set tentative time, still ask for confirmation
                    start_h = 0 if h == 12 else h
                    result["start_time"] = f"{start_h:02d}:00"
                # suffix == 'm': completely ambiguous — don't set start_time
                result["ambiguous"] = True
                result["ambiguity_hint"] = f"Did you mean {h} AM or {h} PM?"
                logger.info(
                    "[TIME_EXTRACT] Fuzzy partial AM/PM: '%s %s' → ambiguous, hint: %s",
                    hour_str, suffix, result["ambiguity_hint"],
                )
                return result

        return None if not result else result
    
    @staticmethod
    def _extract_time(message: str, message_lower: str) -> Optional[str]:
        """
        Extract time from message (legacy method for backward compatibility).
        
        Now delegates to _extract_time_range and returns only start_time.
        """
        time_result = SlotExtractor._extract_time_range(message, message_lower)
        if time_result and time_result.get("start_time"):
            return time_result["start_time"]
        return None
    
    @staticmethod
    def _extract_date(message: str, message_lower: str) -> Optional[str]:
        """
        Extract date from message.
        
        Patterns:
        - "today" → today's date
        - "tomorrow" → tomorrow's date
        - "yesterday" → yesterday's date
        - "next week" → 7 days from now
        - "last week" → 7 days ago
        - "next monday" / "last monday" → date of that weekday
        - "in X days" → X days from now
        - "2024-12-25" → explicit date
        - "December 25" → parsed date
        """
        today = datetime.now()

        # Relative dates
        if "today" in message_lower:
            return today.strftime("%Y-%m-%d")

        if "yesterday" in message_lower:
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")

        if "tomorrow" in message_lower:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")

        if "day after tomorrow" in message_lower:
            return (today + timedelta(days=2)).strftime("%Y-%m-%d")

        if "next week" in message_lower:
            return (today + timedelta(days=7)).strftime("%Y-%m-%d")

        if "last week" in message_lower:
            return (today - timedelta(days=7)).strftime("%Y-%m-%d")

        # "in X days" / "in 2 days"
        in_days_match = re.search(r'\bin\s+(\d+)\s+days?\b', message_lower)
        if in_days_match:
            n = int(in_days_match.group(1))
            return (today + timedelta(days=n)).strftime("%Y-%m-%d")

        # Weekday patterns ("next friday", "last monday", "this wednesday")
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }

        for day_name, day_num in weekdays.items():
            if f"last {day_name}" in message_lower:
                days_back = (today.weekday() - day_num) % 7
                if days_back == 0:
                    days_back = 7
                return (today - timedelta(days=days_back)).strftime("%Y-%m-%d")

            if f"next {day_name}" in message_lower or f"this {day_name}" in message_lower:
                days_ahead = day_num - today.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # FIX H-04: Bare weekday ("on friday", "friday", "meeting friday") →
        # next upcoming occurrence. Checked AFTER "next/last/this" prefixes so
        # those still win. Uses word-boundary regex to avoid partial matches.
        for day_name, day_num in weekdays.items():
            if re.search(r'\b' + day_name + r'\b', message_lower):
                days_ahead = (day_num - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # "friday" when today IS friday → next Friday
                return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # Explicit date formats
        # YYYY-MM-DD
        match = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', message)
        if match:
            return match.group(0)

        # MM/DD/YYYY or DD/MM/YYYY
        match = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', message)
        if match:
            # Assume MM/DD/YYYY format (US standard)
            month, day, year = match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # FIX H-03: Named month-day parsing ("March 31", "April 5",
        # "31st March", "31 March", "31st of March").
        # Resolves to the CURRENT year; if the resulting date is in the past
        # (i.e. the month already passed this year), it rolls forward to next year.
        _MONTHS = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
        }
        _MONTH_NAMES = '|'.join(_MONTHS.keys())
        # "March 31" / "March 31st"
        m = re.search(
            r'\b(' + _MONTH_NAMES + r')\s+(\d{1,2})(?:st|nd|rd|th)?\b',
            message_lower,
        )
        if not m:
            # "31 March" / "31st March" / "31st of March"
            m = re.search(
                r'\b(\d{1,2})(?:st|nd|rd|th)?(?:\s+of)?\s+(' + _MONTH_NAMES + r')\b',
                message_lower,
            )
            if m:
                # swap groups so month is always first
                day_part, month_part = m.group(1), m.group(2)
            else:
                day_part = month_part = None
        else:
            month_part, day_part = m.group(1), m.group(2)

        if month_part and day_part:
            try:
                month_num = _MONTHS[month_part]
                day_num2 = int(day_part)
                year = today.year
                candidate = datetime(year, month_num, day_num2)
                # If date already passed this year, use next year
                if candidate.date() < today.date():
                    candidate = datetime(year + 1, month_num, day_num2)
                return candidate.strftime("%Y-%m-%d")
            except ValueError:
                pass  # invalid day for month (e.g. Feb 31) — fall through

        return None
    
    @staticmethod
    def _extract_duration(message: str, message_lower: str) -> Optional[int]:
        """
        Extract duration in minutes.
        
        Patterns:
        - "one hour" / "1 hour" / "an hour" → 60
        - "2 hours" → 120
        - "30 minutes" / "half hour" → 30
        - "1.5 hours" → 90
        - "should take X" patterns
        """
        # Text-based hour patterns (order matters - check specific patterns first)
        text_hours_ordered = [
            ('half an hour', 30), ('half hour', 30),  # Must come before 'an hour'
            ('one hour', 60), ('an hour', 60), ('1 hour', 60),
            ('two hours', 120), ('2 hours', 120),
            ('three hours', 180), ('3 hours', 180),
        ]
        
        for pattern, minutes in text_hours_ordered:
            if pattern in message_lower:
                logger.info(f"[DURATION_EXTRACT] Found text pattern '{pattern}': {minutes} minutes")
                return minutes
        
        # "should take X" pattern
        take_match = re.search(r'(?:should take|take|last|be)\s+(\w+)\s+(?:hour|minute)', message_lower)
        if take_match:
            num_word = take_match.group(1)
            word_to_num = {
                'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'a': 1, 'an': 1, 'half': 0.5
            }
            if num_word in word_to_num:
                if 'hour' in message_lower[take_match.end()-10:take_match.end()+10]:
                    duration = int(word_to_num[num_word] * 60)
                    logger.info(f"[DURATION_EXTRACT] Found 'should take' pattern: {duration} minutes")
                    return duration
                else:
                    duration = int(word_to_num[num_word])
                    logger.info(f"[DURATION_EXTRACT] Found 'should take' pattern: {duration} minutes")
                    return duration
        
        # Numeric hours
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)', message_lower)
        if match:
            hours = float(match.group(1))
            duration = int(hours * 60)
            logger.info(f"[DURATION_EXTRACT] Found numeric hours: {duration} minutes")
            return duration
        
        # Numeric minutes
        match = re.search(r'(\d+)\s*(?:minutes?|mins?)', message_lower)
        if match:
            duration = int(match.group(1))
            logger.info(f"[DURATION_EXTRACT] Found numeric minutes: {duration} minutes")
            return duration
        
        return None
    
    @staticmethod
    def _extract_location(message: str) -> Optional[str]:
        """
        Extract location from message.
        
        Patterns:
        - "at Conference Room A" → "Conference Room A"
        - "in Building 5" → "Building 5"
        - "@ Main Office" → "Main Office"
        """
        # Pattern: at/in + location
        match = re.search(r'\b(?:at|in|@)\s+([A-Z][A-Za-z0-9\s]+(?:Room|Building|Office|Hall|Center)?(?:\s+\d+)?)', message)
        if match:
            return match.group(1).strip()
        
        return None
    
    @staticmethod
    def _extract_provider(message_lower: str) -> Optional[str]:
        """
        Extract calendar / mail provider preference and lock it.

        CRITICAL (task spec): If the user mentions a provider, lock it —
        never fall back to a different default.

        Supported aliases
        -----------------
        Microsoft / Outlook: outlook, microsoft, office 365, office365, o365,
                             ms calendar, ms cal
        Google:              google, gmail, gcal, google calendar (and typo
                             "google calender")

        Note: Outlook-family keywords are checked FIRST because "outlook" is
        more specific than "google" (no overlap).
        """
        # ── Microsoft / Outlook (check first – more specific) ─────────────
        ms_keywords = [
            "outlook", "microsoft", "office 365", "office365", "o365",
            "ms calendar", "ms cal",
        ]
        if any(kw in message_lower for kw in ms_keywords):
            logger.debug("[CALENDAR_SLOT_EXTRACT] Provider detected: outlook")
            return "outlook"

        # ── Google ────────────────────────────────────────────────────────
        google_keywords = [
            "google", "gmail", "gcal",
        ]
        if any(kw in message_lower for kw in google_keywords):
            logger.debug("[CALENDAR_SLOT_EXTRACT] Provider detected: google")
            return "google"

        return None

    @staticmethod
    def _extract_timezone(message: str, message_lower: str) -> Optional[str]:
        """
        Extract timezone hint from message.

        Supports:
        - Common abbreviations: UTC, GMT, CET, CEST, EST, EDT, PST, PDT, CST, MST, IST
        - IANA format embedded in text: "Europe/Berlin", "America/New_York"

        Returns:
            IANA timezone string or None if not found.
        """
        # ── IANA timezone: "Europe/Berlin", "America/New_York" ────────────
        iana_match = re.search(r'\b([A-Z][a-z]+/[A-Za-z_]+)\b', message)
        if iana_match:
            tz_candidate = iana_match.group(1)
            logger.debug("[CALENDAR_SLOT_EXTRACT] IANA timezone candidate: %s", tz_candidate)
            return tz_candidate

        # ── Common abbreviations (word-boundary aware) ────────────────────
        tz_abbr_map = {
            "utc": "UTC",
            "gmt": "UTC",
            "cet": "Europe/Berlin",
            "cest": "Europe/Berlin",
            "est": "America/New_York",
            "edt": "America/New_York",
            "pst": "America/Los_Angeles",
            "pdt": "America/Los_Angeles",
            "mst": "America/Denver",
            "cst": "America/Chicago",
            "ist": "Asia/Kolkata",
        }
        for abbr, iana in tz_abbr_map.items():
            # Match as standalone word (avoid matching "best" → "est")
            if re.search(r'\b' + abbr + r'\b', message_lower):
                logger.debug("[CALENDAR_SLOT_EXTRACT] Timezone abbreviation matched: %s → %s", abbr, iana)
                return iana

        return None
    
    @staticmethod
    def extract_email_slots(message: str, existing_slots: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        MANDATORY SEMANTIC PARSING for email drafting.
        
        Extracts from ANY user message:
        - to_email (validated email address)
        - to_name (optional display name)
        - subject (email subject)
        - body (email content)
        
        Args:
            message: User's input message
            existing_slots: Already-locked slots
        
        Returns:
            Dict with extracted slots
        """
        existing = existing_slots or {}
        extracted = {}
        message_lower = message.lower().strip()
        
        logger.info(f"[EMAIL_SLOT_EXTRACT] Parsing: '{message}'")
        
        # Extract email address (authoritative regex)
        if not existing.get("to_email"):
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, message)
            if email_match:
                extracted["to_email"] = email_match.group(0)
                logger.info(f"[EMAIL_SLOT_EXTRACT] ✓ to_email: {extracted['to_email']}")
        
        # Extract subject
        if not existing.get("subject"):
            # Pattern 1: "subject: X"
            subject_match = re.search(r'(?:subject|re|regarding):\s*(.+?)(?:\n|$|\.)', message, re.IGNORECASE)
            if subject_match:
                extracted["subject"] = subject_match.group(1).strip()
                logger.info(f"[EMAIL_SLOT_EXTRACT] ✓ subject: '{extracted['subject']}'")
            else:
                # Pattern 2: "about X"
                about_match = re.search(r'\babout\s+(.+?)(?:\n|$|\.|\?)', message, re.IGNORECASE)
                if about_match:
                    extracted["subject"] = about_match.group(1).strip()
                    logger.info(f"[EMAIL_SLOT_EXTRACT] ✓ subject (from 'about'): '{extracted['subject']}'")
        
        logger.info(f"[EMAIL_SLOT_EXTRACT] Extracted {len(extracted)} slots: {list(extracted.keys())}")
        return extracted
    
    @staticmethod
    def get_missing_slots(required_slots: List[str], current_slots: Dict[str, Any]) -> List[str]:
        """
        Get list of missing required slots.
        
        Args:
            required_slots: List of required slot names
            current_slots: Current slot values
        
        Returns:
            List of missing slot names
        """
        missing = []
        for slot in required_slots:
            if not current_slots.get(slot):
                missing.append(slot)
        return missing
    
    @staticmethod
    def format_confirmation(slot_type: str, slots: Dict[str, Any]) -> str:
        """
        Format extracted slots as confirmation message.
        
        Example:
        "📅 Got it! Here's what I understood:
        - Event: Meeting with Chef
        - Time: 08:00
        - Date: Tomorrow
        
        Which calendar should I add this to? (Google / Outlook)"
        
        Args:
            slot_type: Type of slots ('calendar' or 'email')
            slots: Extracted slot values
        
        Returns:
            Formatted confirmation message
        """
        if slot_type == "calendar":
            lines = ["📅 **Got it! Here's what I understood:**\n"]
            
            if slots.get("title"):
                lines.append(f"- **Event:** {slots['title']}")
            if slots.get("date"):
                # Format date nicely
                try:
                    date_obj = datetime.strptime(slots['date'], "%Y-%m-%d")
                    date_display = date_obj.strftime("%A, %B %d")
                    if date_obj.date() == datetime.now().date():
                        date_display = "Today"
                    elif date_obj.date() == (datetime.now() + timedelta(days=1)).date():
                        date_display = "Tomorrow"
                    lines.append(f"- **Date:** {date_display}")
                except:
                    lines.append(f"- **Date:** {slots['date']}")
            
            if slots.get("time"):
                lines.append(f"- **Time:** {slots['time']}")
            if slots.get("duration"):
                lines.append(f"- **Duration:** {slots['duration']} minutes")
            if slots.get("location"):
                lines.append(f"- **Location:** {slots['location']}")
            
            return "\n".join(lines)
        
        elif slot_type == "email":
            lines = ["📧 **Got it! Here's what I understood:**\n"]
            
            if slots.get("to_email"):
                recipient = slots['to_email']
                if slots.get("to_name"):
                    recipient = f"{slots['to_name']} <{recipient}>"
                lines.append(f"- **To:** {recipient}")
            
            if slots.get("subject"):
                lines.append(f"- **Subject:** {slots['subject']}")
            
            if slots.get("body"):
                preview = slots['body'][:100]
                if len(slots['body']) > 100:
                    preview += "..."
                lines.append(f"- **Message:** {preview}")
            
            return "\n".join(lines)
        
        return ""

    # =========================================================================
    # EMAIL READ SLOT EXTRACTION
    # =========================================================================

    @staticmethod
    def extract_calendar_update_slots(message: str) -> Dict[str, Any]:
        """
        Extract slots for CALENDAR_UPDATE intent.

        Extracts:
          - search_query  (str)  : event title/name fragment to find
          - search_date   (str)  : ISO date to narrow search
          - search_time   (str)  : HH:MM original time (to match event by start time)
          - update_type   (str)  : "time" | "title" | "location" | "multi"
          - new_time      (str)  : new start time HH:MM
          - new_end_time  (str)  : new end time HH:MM (optional)
          - new_date      (str)  : new date ISO (optional — for reschedule to different day)
          - new_title     (str)  : new event title/name
          - new_location  (str)  : new location

        Examples handled:
          "Move my 3pm meeting to 4pm"
            → search_time=15:00, new_time=16:00
          "Rename lunch with Anna to lunch with Patrick"
            → search_query="lunch with Anna", new_title="lunch with Patrick"
          "Change tomorrow's dentist appointment to 11:00"
            → search_query="dentist appointment", search_date=tomorrow, new_time=11:00
          "Update the location of my Friday interview to Berlin office"
            → search_query="friday interview", new_location="Berlin office"
        """
        msg_lower = message.lower().strip()
        today = datetime.now()
        slots: Dict[str, Any] = {}

        # ── 1. Rename pattern: "rename X to Y" ───────────────────────────────
        rename_match = re.search(
            r'\brename\s+(.+?)\s+to\s+(.+?)(?:\s*;|\s*$)',
            message, re.IGNORECASE,
        )
        if rename_match:
            original = rename_match.group(1).strip()
            new_name = rename_match.group(2).strip()
            # Strip leading "my " / "the "
            original = re.sub(r'^(?:my|the)\s+', '', original, flags=re.IGNORECASE)
            slots["search_query"] = original
            slots["new_title"] = new_name
            slots["update_type"] = "title"
            logger.info("[CAL_UPDATE_SLOTS] Rename: '%s' → '%s'", original, new_name)

        # ── 2. Location update: "update/change the location of X to Y" ────────
        if not slots.get("new_location"):
            loc_match = re.search(
                r'\b(?:update|change)\s+(?:the\s+)?location(?:\s+of\s+(.+?))?\s+to\s+(.+?)(?:\s*;|\s*$)',
                message, re.IGNORECASE,
            )
            if loc_match:
                event_ref = loc_match.group(1)
                new_loc = loc_match.group(2).strip()
                slots["new_location"] = new_loc
                if not slots.get("update_type"):
                    slots["update_type"] = "location"
                if event_ref and not slots.get("search_query"):
                    slots["search_query"] = re.sub(
                        r'^(?:my|the)\s+', '', event_ref.strip(), flags=re.IGNORECASE
                    )
                logger.info("[CAL_UPDATE_SLOTS] Location update: event=%r loc='%s'", event_ref, new_loc)

        # ── 3. Time change: "move/reschedule/push/change X [from T1] to T2" ──
        if not slots.get("new_time"):
            # Pattern A: "[verb] my NNpm [meeting] to NNpm"
            time_change = re.search(
                r'\b(?:move|reschedule|push|push\s+back|change|shift)\s+'
                r'(?:my\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*'
                r'(?:(?:am|pm)?\s*)?(?:\w+\s*)*?(?:meeting|appointment|event|call|sync)?\s*'
                r'to\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
                msg_lower, re.IGNORECASE,
            )
            if time_change:
                orig_time_str = time_change.group(1).strip()
                new_time_str  = time_change.group(2).strip()
                # Parse "original" time as search_time
                parsed_orig = SlotExtractor._parse_ampm_time(orig_time_str)
                parsed_new  = SlotExtractor._parse_ampm_time(new_time_str)
                if parsed_orig:
                    slots["search_time"] = parsed_orig
                if parsed_new:
                    slots["new_time"] = parsed_new
                    if not slots.get("update_type"):
                        slots["update_type"] = "time"
                logger.info("[CAL_UPDATE_SLOTS] Time shift: %s → %s", parsed_orig, parsed_new)

            # Pattern B: "to NNpm" / "to NN:MM" — used when event identified by name
            if not slots.get("new_time"):
                to_time = re.search(
                    r'\bto\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:;|$)',
                    msg_lower,
                )
                if to_time:
                    parsed = SlotExtractor._parse_ampm_time(to_time.group(1).strip())
                    if parsed:
                        slots["new_time"] = parsed
                        if not slots.get("update_type"):
                            slots["update_type"] = "time"

        # ── 4. Event-name search query ────────────────────────────────────────
        if not slots.get("search_query"):
            # Generic: "[verb] my [event_name] (from|at|to)..."
            name_match = re.search(
                r'\b(?:move|reschedule|change|update|push|shift|cancel|edit)\s+'
                r'(?:my\s+|the\s+|tomorrow\'?s?\s+|today\'?s?\s+)?'
                r'(.+?)'
                r'(?:\s+(?:from|at|to)\b|\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)|\s*;|$)',
                message, re.IGNORECASE,
            )
            if name_match:
                raw = name_match.group(1).strip()
                raw = re.sub(r'^(?:my|the)\s+', '', raw, flags=re.IGNORECASE)
                if len(raw) > 1 and not SlotExtractor._is_garbage_title(raw):
                    slots["search_query"] = raw
                    logger.info("[CAL_UPDATE_SLOTS] Event search from verb pattern: '%s'", raw)

        # ── 5. Date search context ────────────────────────────────────────────
        if "tomorrow" in msg_lower:
            slots["search_date"] = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "today" in msg_lower:
            slots["search_date"] = today.strftime("%Y-%m-%d")
        else:
            date_val = SlotExtractor._extract_date(message, msg_lower)
            if date_val:
                slots["search_date"] = date_val

        # ── 6. Determine update_type if multi-field ───────────────────────────
        if not slots.get("update_type"):
            kinds = sum([
                1 if slots.get("new_time") else 0,
                1 if slots.get("new_title") else 0,
                1 if slots.get("new_location") else 0,
            ])
            if kinds > 1:
                slots["update_type"] = "multi"
            elif kinds == 1:
                if slots.get("new_time"):
                    slots["update_type"] = "time"
                elif slots.get("new_title"):
                    slots["update_type"] = "title"
                elif slots.get("new_location"):
                    slots["update_type"] = "location"

        logger.info("[CAL_UPDATE_SLOTS] Extracted: %s", slots)
        return slots

    @staticmethod
    def _parse_ampm_time(time_str: str) -> Optional[str]:
        """Parse a spoken time string like '3pm', '15:00', '3:30pm' to HH:MM."""
        time_str = time_str.strip().lower()
        m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', time_str)
        if not m:
            return None
        h, mins, ampm = m.group(1), m.group(2), m.group(3)
        h = int(h)
        mins = int(mins) if mins else 0
        if ampm == 'pm' and h < 12:
            h += 12
        elif ampm == 'am' and h == 12:
            h = 0
        elif ampm is None and h < 8:
            # Ambiguous bare number < 8 — treat as PM heuristically
            h += 12
        return f"{h:02d}:{mins:02d}"

    @staticmethod
    def extract_email_read_slots(message: str) -> Dict[str, Any]:
        """
        Extract slots for EMAIL_READ intent.

        Extracts:
          - count        (int)   : how many emails to fetch, default 5
          - unread_only  (bool)  : filter to unread only
          - sender_filter(str)   : sender name or email to filter by
          - date_filter  (str)   : "today" | "yesterday" | "this_week" | "last_week" | None
          - start_date   (str)   : ISO date for date range start
          - end_date     (str)   : ISO date for date range end

        Args:
            message: Raw user message

        Returns:
            Dict with extracted read-email slots
        """
        msg = message.lower().strip()
        today = datetime.now()
        slots: Dict[str, Any] = {}

        # ── Count extraction ─────────────────────────────────────────────────
        # "last 3 emails", "show me 5 emails", "last 10"
        count_match = re.search(r'\b(?:last|show|get|fetch|read)?\s*(\d+)\s+(?:emails?|messages?|mails?)\b', msg)
        if count_match:
            slots["count"] = int(count_match.group(1))
        else:
            # "my last emails" without explicit number
            slots["count"] = 5  # safe default

        # ── Unread filter ────────────────────────────────────────────────────
        unread_kws = ["unread", "new email", "new message", "new emails", "any new"]
        slots["unread_only"] = any(kw in msg for kw in unread_kws)

        # ── Sender filter ────────────────────────────────────────────────────
        # Check for email address first (highest precision)
        email_match = re.search(r'\bfrom\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-zA-Z]{2,})', msg)
        if email_match:
            slots["sender_filter"] = email_match.group(1)
        else:
            # Match name patterns: "from John", "emails from sarah", "sent by Alex",
            # "messages from Bob", "what did john email me", "john sent me"
            sender_match = re.search(
                r'(?:from|emails?\s+from|mails?\s+from|messages?\s+from|sent\s+by|what\s+did\s+)'
                r'([A-Za-z][A-Za-z\s]{1,40}?)'
                r'(?:\s+(?:email|send|write|sent|today|yesterday|last|this|week|month|ago)|@|\s*$)',
                msg,
            )
            if sender_match:
                sender_raw = sender_match.group(1).strip()
                # Strip trailing time/quantity words that regex may have captured
                _TIME_WORDS = {"today", "yesterday", "last", "this", "week", "month", "ago", "recent", "recently", "sent"}
                parts = sender_raw.split()
                while parts and parts[-1].lower() in _TIME_WORDS:
                    parts.pop()
                sender_raw = " ".join(parts).strip()
                generic = {"me", "my", "i", "the", "a", "any", "do", "have", "give", "you", "did"}
                if sender_raw and sender_raw.lower() not in generic:
                    slots["sender_filter"] = sender_raw

        # ── Date filter ───────────────────────────────────────────────────────
        if "yesterday" in msg:
            d = today - timedelta(days=1)
            slots["date_filter"] = "yesterday"
            slots["start_date"] = d.strftime("%Y-%m-%d")
            slots["end_date"] = d.strftime("%Y-%m-%d")
        elif "today" in msg:
            slots["date_filter"] = "today"
            slots["start_date"] = today.strftime("%Y-%m-%d")
            slots["end_date"] = today.strftime("%Y-%m-%d")
        elif "this week" in msg:
            # Monday of current week
            monday = today - timedelta(days=today.weekday())
            slots["date_filter"] = "this_week"
            slots["start_date"] = monday.strftime("%Y-%m-%d")
            slots["end_date"] = today.strftime("%Y-%m-%d")
        elif "last week" in msg:
            monday = today - timedelta(days=today.weekday() + 7)
            sunday = monday + timedelta(days=6)
            slots["date_filter"] = "last_week"
            slots["start_date"] = monday.strftime("%Y-%m-%d")
            slots["end_date"] = sunday.strftime("%Y-%m-%d")

        logger.info("[EMAIL_READ_SLOTS] Extracted: %s", slots)
        return slots

    # =========================================================================
    # CALENDAR READ SLOT EXTRACTION
    # =========================================================================

    @staticmethod
    def extract_calendar_read_slots(message: str) -> Dict[str, Any]:
        """
        Extract slots for CALENDAR_READ intent.

        Extracts:
          - date         (str)  : single target date (ISO)
          - start_date   (str)  : range start (ISO)
          - end_date     (str)  : range end (ISO)
          - time_filter  (str)  : specific time to look for, e.g. "15:00"
          - next_event   (bool) : user wants the very next upcoming event
          - date_label   (str)  : human-readable label ("today", "tomorrow", …)

        Args:
            message: Raw user message

        Returns:
            Dict with extracted calendar-read slots
        """
        msg = message.lower().strip()
        today = datetime.now()
        slots: Dict[str, Any] = {}

        # ── Next event flag ───────────────────────────────────────────────────
        next_kws = ["next meeting", "when is my next", "next event", "what's next", "what is next"]
        if any(kw in msg for kw in next_kws):
            slots["next_event"] = True
            slots["start_date"] = today.strftime("%Y-%m-%d")
            slots["date_label"] = "upcoming"
            logger.info("[CAL_READ_SLOTS] next_event=True")
            return slots

        # ── Time filter ───────────────────────────────────────────────────────
        time_result = SlotExtractor._extract_time_range(message, msg)
        if time_result and time_result.get("start_time"):
            slots["time_filter"] = time_result["start_time"]

        # ── Date range detection ──────────────────────────────────────────────
        if "this week" in msg:
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            slots["start_date"] = monday.strftime("%Y-%m-%d")
            slots["end_date"] = sunday.strftime("%Y-%m-%d")
            slots["date_label"] = "this week"
        elif "next week" in msg:
            next_monday = today + timedelta(days=7 - today.weekday())
            next_sunday = next_monday + timedelta(days=6)
            slots["start_date"] = next_monday.strftime("%Y-%m-%d")
            slots["end_date"] = next_sunday.strftime("%Y-%m-%d")
            slots["date_label"] = "next week"
        elif "last week" in msg or "yesterday" in msg and "week" in msg:
            monday = today - timedelta(days=today.weekday() + 7)
            sunday = monday + timedelta(days=6)
            slots["start_date"] = monday.strftime("%Y-%m-%d")
            slots["end_date"] = sunday.strftime("%Y-%m-%d")
            slots["date_label"] = "last week"
        else:
            # single date resolution
            single = SlotExtractor._extract_date(message, msg)
            if single:
                slots["date"] = single
                slots["start_date"] = single
                slots["end_date"] = single
                # Human-readable label
                try:
                    d = datetime.strptime(single, "%Y-%m-%d").date()
                    if d == today.date():
                        slots["date_label"] = "today"
                    elif d == (today + timedelta(days=1)).date():
                        slots["date_label"] = "tomorrow"
                    elif d == (today - timedelta(days=1)).date():
                        slots["date_label"] = "yesterday"
                    else:
                        slots["date_label"] = d.strftime("%A, %B %d")
                except Exception:
                    slots["date_label"] = single
            else:
                # Default: today
                slots["date"] = today.strftime("%Y-%m-%d")
                slots["start_date"] = today.strftime("%Y-%m-%d")
                slots["end_date"] = today.strftime("%Y-%m-%d")
                slots["date_label"] = "today"

        logger.info("[CAL_READ_SLOTS] Extracted: %s", slots)
        return slots
