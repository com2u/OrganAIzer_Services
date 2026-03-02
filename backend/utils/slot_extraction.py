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
        if not existing.get("title"):
            title = SlotExtractor._extract_title(message, message_lower)
            if title:
                extracted["title"] = title
                logger.info(f"[SLOT_EXTRACT] ✓ title: '{title}'")
        
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
        explicit_patterns = [
            r'call it\s+(.+?)(?:\s*;|\s*$)',
            r'name it\s+(.+?)(?:\s*;|\s*$)',
            r'rename it to\s+(.+?)(?:\s*;|\s*$)',
            r'title:\s*(.+?)(?:\s*;|\s*$)',
        ]
        
        for pattern in explicit_patterns:
            match = re.search(pattern, message_lower)
            if match:
                title = match.group(1).strip()
                # Remove trailing punctuation
                title = re.sub(r'[;,.]$', '', title).strip()
                
                # Validate length
                if len(title) > 80:
                    title = title[:80]
                
                # Validate not garbage
                if len(title) > 0 and not SlotExtractor._is_garbage_title(title):
                    logger.info(f"[TITLE_EXTRACT] Found explicit title pattern: '{title}'")
                    return title.title()
        
        # PRIORITY 3: "called X" pattern
        # "event called Strategy Sync"
        called_match = re.search(r'(?:event|meeting)\s+called\s+(.+?)(?:\s+at|\s+on|\s+for|\s+tomorrow|\s+today|;|$)', message_lower)
        if called_match:
            title = called_match.group(1).strip()
            if len(title) > 80:
                title = title[:80]
            if not SlotExtractor._is_garbage_title(title):
                logger.info(f"[TITLE_EXTRACT] Found 'called' pattern: '{title}'")
                return title.title()
        
        # PRIORITY 4: Title before time marker
        # "Meeting with Chef at 08:00" → extract "Meeting with Chef"
        time_markers = [r'\bat\s+\d', r'\b\d+:\d+', r'\b\d+\s*(?:am|pm)', r'\bfrom\s+\d']
        for marker in time_markers:
            parts = re.split(marker, message, maxsplit=1)
            if len(parts) > 1:
                potential_title = parts[0].strip()
                # Remove common prefixes
                potential_title = re.sub(r'^(?:schedule|add|create|an event|a meeting)\s+(?:a\s+)?(?:an\s+)?(?:event\s+)?(?:meeting\s+)?', '', potential_title, flags=re.IGNORECASE).strip()
                # Remove semicolons
                potential_title = re.sub(r';', '', potential_title).strip()
                
                # Validate
                if len(potential_title) > 2 and len(potential_title) <= 80 and not SlotExtractor._is_garbage_title(potential_title):
                    logger.info(f"[TITLE_EXTRACT] Found title before time marker: '{potential_title}'")
                    return potential_title.title()
        
        # PRIORITY 5: Title before date marker
        # "Team meeting tomorrow" → "Team Meeting"
        date_keywords = ['tomorrow', 'today', 'next week', 'next monday', 'next tuesday', 'next wednesday', 'next thursday', 'next friday', 'next saturday', 'next sunday']
        for keyword in date_keywords:
            if keyword in message_lower:
                parts = message_lower.split(keyword, 1)
                potential_title = parts[0].strip()
                potential_title = re.sub(r'^(?:schedule|add|create|an event|a meeting)\s+(?:a\s+)?(?:an\s+)?(?:event\s+)?(?:meeting\s+)?', '', potential_title, flags=re.IGNORECASE).strip()
                potential_title = re.sub(r';', '', potential_title).strip()
                
                # Validate
                if len(potential_title) > 2 and len(potential_title) <= 80 and not SlotExtractor._is_garbage_title(potential_title):
                    logger.info(f"[TITLE_EXTRACT] Found title before date keyword: '{potential_title}'")
                    return potential_title.title()
        
        # PRIORITY 6: "schedule X" or "add X" or "create X" with strict cleanup
        match = re.search(r'(?:schedule|add|create)\s+(?:a\s+)?(?:an\s+)?(?:event\s+)?(?:meeting\s+)?(?:with\s+)?(?:for\s+)?(.+?)(?:\s+at|\s+on|\s+for|\s+tomorrow|\s+today|\s+next|;|$)', message_lower)
        if match:
            title = match.group(1).strip()
            # Clean up common words
            title = re.sub(r'\s+(at|on|for|tomorrow|today|next)\s+.*', '', title).strip()
            
            # Validate
            if len(title) > 1 and len(title) <= 80 and not SlotExtractor._is_garbage_title(title):
                logger.info(f"[TITLE_EXTRACT] Found 'schedule/add' pattern: '{title}'")
                return title.title()
        
        # PRIORITY 7: If message is short and specific, might be a title
        if len(message.split()) <= 5 and not re.search(r'\d|tomorrow|today|next', message_lower):
            # Check if it's not a question or command
            if not any(message_lower.startswith(word) for word in ['what', 'when', 'where', 'who', 'why', 'how', 'is', 'are', 'can', 'do', 'add', 'schedule', 'create']):
                if not SlotExtractor._is_garbage_title(message):
                    logger.info(f"[TITLE_EXTRACT] Using entire message as title: '{message}'")
                    return message.title()
        
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

        return False
    
    @staticmethod
    def _extract_time_range(message: str, message_lower: str) -> Optional[Dict[str, str]]:
        """
        Extract start_time and end_time from message (CRITICAL FIX #1).
        
        Patterns with explicit end time:
        - "from 10:00 to 18:00" → start: 10:00, end: 18:00
        - "10:00-18:00" → start: 10:00, end: 18:00
        - "10:00–18:00" (em dash) → start: 10:00, end: 18:00
        - "10am to 6pm" → start: 10:00, end: 18:00
        
        Single time patterns:
        - "08:00" → start: 08:00, end: None
        - "5pm" → start: 17:00, end: None
        - "morning" → start: 09:00, end: None
        
        Returns:
            Dict with start_time and optional end_time, or None if no time found
        """
        result = {}
        
        # CRITICAL: Check for time range patterns FIRST (explicit start AND end)
        # Pattern 1: "from HH:MM to HH:MM" or "HH:MM to HH:MM"
        range_match = re.search(
            r'(?:from\s+)?(\d{1,2}):(\d{2})\s*(?:to|until|till|-|–|—)\s*(\d{1,2}):(\d{2})',
            message
        )
        if range_match:
            start_hour, start_min, end_hour, end_min = range_match.groups()
            result["start_time"] = f"{int(start_hour):02d}:{start_min}"
            result["end_time"] = f"{int(end_hour):02d}:{end_min}"
            logger.info(f"[TIME_EXTRACT] Found time range: {result['start_time']} to {result['end_time']}")
            return result
        
        # Pattern 2: "from H:MM am/pm to H:MM am/pm" or "H:MM am/pm to H:MM am/pm"
        range_match = re.search(
            r'(?:from\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*(?:to|until|till|-|–)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            message_lower
        )
        if range_match:
            start_hour_str, start_min_str, start_ampm, end_hour_str, end_min_str, end_ampm = range_match.groups()
            
            # Convert start time
            start_hour = int(start_hour_str)
            start_min = int(start_min_str) if start_min_str else 0
            if start_ampm == 'pm' and start_hour < 12:
                start_hour += 12
            elif start_ampm == 'am' and start_hour == 12:
                start_hour = 0
            
            # Convert end time
            end_hour = int(end_hour_str)
            end_min = int(end_min_str) if end_min_str else 0
            if end_ampm == 'pm' and end_hour < 12:
                end_hour += 12
            elif end_ampm == 'am' and end_hour == 12:
                end_hour = 0
            
            result["start_time"] = f"{start_hour:02d}:{start_min:02d}"
            result["end_time"] = f"{end_hour:02d}:{end_min:02d}"
            logger.info(f"[TIME_EXTRACT] Found time range (am/pm): {result['start_time']} to {result['end_time']}")
            return result
        
        # FALLBACK: Single time extraction (no explicit end time)
        # Pattern 3: HH:MM format (24-hour)
        match = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', message)
        if match:
            hour, minute = match.groups()
            result["start_time"] = f"{int(hour):02d}:{minute}"
            logger.info(f"[TIME_EXTRACT] Found single time (24h): {result['start_time']}")
            return result
        
        # Pattern 4: H:MM am/pm or H am/pm
        match = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', message_lower)
        if match:
            hour_str, minute_str, ampm = match.groups()
            hour = int(hour_str)
            minute = int(minute_str) if minute_str else 0
            
            # Convert to 24-hour format
            if ampm == 'pm' and hour < 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            
            result["start_time"] = f"{hour:02d}:{minute:02d}"
            logger.info(f"[TIME_EXTRACT] Found single time (am/pm): {result['start_time']}")
            return result
        
        # Pattern 5: Time keywords
        time_keywords = {
            'morning': '09:00',
            'noon': '12:00',
            'afternoon': '14:00',
            'evening': '18:00',
            'night': '20:00',
        }
        for keyword, default_time in time_keywords.items():
            if keyword in message_lower:
                result["start_time"] = default_time
                logger.info(f"[TIME_EXTRACT] Found keyword time: {result['start_time']}")
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
        # "from John", "emails from sarah", "what did john email me"
        sender_match = re.search(
            r'(?:from|emails?\s+from|mail\s+from|what\s+did\s+)([A-Za-z][A-Za-z\s]{1,40})(?:\s+email|\s+send|\s+write|@|\s*$)',
            msg
        )
        if sender_match:
            sender_raw = sender_match.group(1).strip()
            # filter out generic words
            generic = {"me", "my", "i", "the", "a", "any", "do", "have", "give"}
            if sender_raw not in generic:
                slots["sender_filter"] = sender_raw

        # Also check for email address in sender position
        email_match = re.search(r'\bfrom\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-zA-Z]{2,})', msg)
        if email_match:
            slots["sender_filter"] = email_match.group(1)

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
