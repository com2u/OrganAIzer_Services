"""
Intent Router - Deterministic User Intent Classification

CRITICAL: This is the AUTHORITATIVE source of truth for intent classification.
Runs BEFORE LLM to prevent misinterpretation of user messages.

INTENT TYPES:
- CONFIRM_ACTION: User confirming a pending action ("yes", "send it")
- CANCEL_ACTION: User cancelling ("cancel", "stop", "abort")
- DECLINE_OPTIONAL: Declining optional slot ("no thanks" for reminders)
- SELECT_SENDER_ACCOUNT: Choosing email sender ("gmail", "outlook")
- SELECT_CALENDAR_PROVIDER: Choosing calendar ("google calendar", "outlook")
- PROVIDE_SLOT_VALUE: Providing data for active task
- SWITCH_TOPIC: User changing tasks
- GENERAL_MESSAGE: Chat/question unrelated to active task

RULES:
1. Keyword matching takes precedence over LLM interpretation
2. Context-aware: same word means different things in different states
3. Slot extraction happens regardless of intent type
4. NO task loss during active flows
"""

import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class IntentType:
    """Intent classification types."""
    CONFIRM_ACTION = "CONFIRM_ACTION"
    CANCEL_ACTION = "CANCEL_ACTION"
    DECLINE_OPTIONAL = "DECLINE_OPTIONAL"
    SELECT_SENDER_ACCOUNT = "SELECT_SENDER_ACCOUNT"
    SELECT_CALENDAR_PROVIDER = "SELECT_CALENDAR_PROVIDER"
    PROVIDE_SLOT_VALUE = "PROVIDE_SLOT_VALUE"
    SWITCH_TOPIC = "SWITCH_TOPIC"
    GENERAL_MESSAGE = "GENERAL_MESSAGE"
    # Dedicated calendar intents
    CALENDAR_CREATE = "CALENDAR_CREATE"
    CALENDAR_LIST = "CALENDAR_LIST"
    CALENDAR_UPDATE = "CALENDAR_UPDATE"
    CALENDAR_DELETE = "CALENDAR_DELETE"
    # Draft correction — user says "no, use outlook" / "no, call it X" / "make it 21:00"
    MODIFY_DRAFT = "MODIFY_DRAFT"
    # Reading intents (no write, no confirmation needed)
    EMAIL_READ = "EMAIL_READ"
    CALENDAR_READ = "CALENDAR_READ"
    # Email write intents
    EMAIL_SEND = "EMAIL_SEND"
    EMAIL_REPLY = "EMAIL_REPLY"
    EMAIL_FORWARD = "EMAIL_FORWARD"
    # Out-of-scope
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class IntentRouter:
    """
    Deterministic Intent Router
    
    Routes user messages to correct handlers based on:
    - Hard keyword rules
    - Active task context
    - State machine position
    - Slot filling requirements
    """
    
    # HARD KEYWORD RULES (NON-NEGOTIABLE)
    CONFIRM_KEYWORDS = [
        "yes", "y", "yep", "yeah", "yup", "sure",
        "send it", "create it", "add it", "schedule it",
        "looks good", "confirm", "approve", "go ahead",
        "do it", "okay", "ok", "please", "sounds good",
        "perfect", "great", "absolutely", "definitely",
        "let's do it", "go for it", "make it happen",
    ]

    CANCEL_KEYWORDS = [
        "cancel", "stop", "abort", "never mind", "nevermind",
        "forget it", "don't", "no don't", "quit", "nope",
        "drop it", "discard", "scrap it", "not anymore",
    ]

    DECLINE_OPTIONAL_KEYWORDS = [
        "no", "no thanks", "no thank you", "none", "nope",
        "skip", "not needed", "no one", "nobody", "nothing"
    ]
    
    SENDER_ACCOUNT_KEYWORDS = {
        "gmail": ["gmail", "google"],
        "outlook": ["outlook", "microsoft"]
    }
    
    CALENDAR_PROVIDER_KEYWORDS = {
        "google": ["google calendar", "google", "gmail"],
        "outlook": ["outlook calendar", "outlook", "microsoft"]
    }

    # ── Regex-based flexible calendar-create detection ─────────────────────
    # Handles "create ME an event", "add me a meeting", etc. by allowing
    # up to 6 arbitrary words between the action verb and the target noun.
    # This is the PRIMARY detector; the string patterns below are fallbacks.
    _CALENDAR_CREATE_RE: re.Pattern = re.compile(
        r'\b(?:create|add|make|schedule|book|put|set\s+up|arrange)\b'
        r'(?:\s+\w+){0,6}'
        r'\s*\b(?:event|meeting|appointment)\b',
        re.IGNORECASE,
    )

    # Known provider keywords that LOCK the provider (no default allowed)
    _CALENDAR_PROVIDER_RE: re.Pattern = re.compile(
        r'\b(?:outlook|microsoft|office\s*365|o365|ms\s+calendar|'
        r'google\s+cale?ndar?|gmail\s+calendar|google|gmail)\b',
        re.IGNORECASE,
    )

    # ── Calendar UPDATE patterns ──────────────────────────────────────────────
    CALENDAR_UPDATE_PATTERNS = [
        # Time-change patterns
        "move my", "reschedule my", "reschedule the", "change my meeting",
        "push back my", "push my meeting", "delay my meeting",
        "move the meeting", "change the time of", "shift my meeting",
        "change time to", "move it to", "push it to", "reschedule to",
        "update my meeting", "change my appointment",
        # Title-change / rename patterns
        "rename my", "rename the", "rename lunch", "rename meeting",
        "rename appointment", "rename event", "change the name",
        "change the title", "update the title", "update the name",
        # Location-change patterns
        "update the location", "change the location", "change location to",
        "update location of", "move the location",
        # Possessive date patterns like "change tomorrow's dentist"
        "change tomorrow's", "change today's", "update tomorrow's", "update today's",
        # Generic update
        "update the event", "update my event", "update my appointment",
        "update my calendar", "edit my meeting", "edit my event",
        "edit the event", "edit the meeting",
    ]

    # ── Calendar DELETE patterns ──────────────────────────────────────────────
    CALENDAR_DELETE_PATTERNS = [
        "cancel my meeting", "cancel my appointment", "cancel the meeting",
        "delete the event", "delete my event", "remove the meeting",
        "remove the event", "remove my appointment", "delete my meeting",
        "cancel the appointment", "cancel the event",
    ]

    # ── Email SEND patterns ──────────────────────────────────────────────────
    EMAIL_SEND_PATTERNS = [
        "shoot an email", "shoot a quick email", "shoot a note",
        "send an email to", "send a message to", "email to",
        "compose an email", "write an email to", "write to",
        "drop a note to", "drop an email to", "fire off an email",
        "dash off an email to", "message to", "reach out to",
        "let them know", "tell them that",
    ]

    # ── Email REPLY patterns ──────────────────────────────────────────────────
    EMAIL_REPLY_PATTERNS = [
        "reply to", "respond to", "write back to", "reply and say",
        "respond and say", "reply back", "get back to",
        "reply to his", "reply to her", "reply to their",
        "reply to the email", "answer the email",
    ]

    # ── Email FORWARD patterns ────────────────────────────────────────────────
    EMAIL_FORWARD_PATTERNS = [
        "forward", "fwd", "forward the email", "forward this email",
        "pass along", "send along to",
    ]

    # ── Out-of-scope patterns ─────────────────────────────────────────────────
    # SECTION 1 FIX: Only flag things that require external action APIs we don't have.
    # General knowledge questions (history, science, geography, etc.) MUST go to
    # GENERAL_MESSAGE so the LLM can answer them. Never block knowledge queries.
    OUT_OF_SCOPE_PATTERNS = [
        # External booking/ordering services that require third-party APIs
        "order food", "order pizza", "order uber", "book uber", "book a taxi",
        "book a flight", "book a hotel", "book a restaurant", "make a reservation",
        "call a cab", "hail a taxi",
        # Device control that we genuinely cannot do
        "play music", "set alarm", "set a timer", "set the timer",
        "turn on the lights", "turn off the lights",
    ]

    # ── Calendar intent detection patterns ────────────────────────────────────
    CALENDAR_CREATE_PATTERNS = [
        # Exact phrase fragments (order: longer first to avoid prefix issues)
        "create an event", "add an event", "create a calendar event",
        "add a calendar event", "create calendar event", "calendar event",
        "create event", "add event",
        "schedule an event", "schedule a meeting", "schedule meeting",
        "schedule event", "create meeting", "add meeting",
        "add to calendar", "put on my calendar", "put on the calendar",
        "meeting with", "appointment with",
        "book time", "block time", "new event", "new meeting",
        # Time-range patterns like "11:25 till 11:40" indicate event creation
        "till ", "until ",           # "X till Y" / "X until Y" with time context
    ]

    CALENDAR_LIST_PATTERNS = [
        "what events", "what's on my calendar", "what is on my calendar",
        "show my calendar", "show calendar", "list events", "list my events",
        "events tomorrow", "events today", "events for tomorrow", "events for today",
        "take a look at google calendar", "google calendar events",
        "check my calendar", "what do i have tomorrow", "what do i have today",
        "what meetings", "show events", "upcoming events",
        "what's happening", "what is happening",
        "look at calendar", "view calendar", "see my calendar",
    ]

    # ── Email READ intent patterns ─────────────────────────────────────────────
    EMAIL_READ_PATTERNS = [
        # Count-based queries
        "last 3 emails", "last 5 emails", "last 10 emails",
        "my last emails", "recent emails", "latest emails",
        "show me my emails", "show my emails", "list my emails",
        # Unread queries
        "any new emails", "do i have new emails", "any unread emails",
        "unread emails", "new emails", "new messages",
        "do i have any emails", "do i have any new",
        # Sender queries
        "what did john", "what did sarah", "emails from", "mail from",
        "what email", "what emails did",
        # Date-based queries
        "emails today", "emails yesterday", "today's emails",
        "emails this week", "emails last week",
        "summarize today", "summarize my emails",
        # Generic email read
        "check my email", "check my inbox", "inbox",
        "read my email", "read my emails",
        "what's in my inbox", "what is in my inbox",
        "show me my inbox", "any emails",
    ]

    # ── Calendar READ intent patterns ──────────────────────────────────────────
    CALENDAR_READ_PATTERNS = [
        # Flexible date queries not in CALENDAR_LIST_PATTERNS
        "what's on my calendar", "what is on my calendar",
        "do i have anything", "do i have any meetings",
        "what meetings do i have", "what do i have",
        "when is my next meeting", "next meeting",
        "what's scheduled", "what is scheduled",
        "show me my calendar", "show me my schedule",
        "what did i have", "did i have anything",
        "am i free", "am i busy",
        "any meetings", "any events",
        "calendar today", "calendar tomorrow",
        "my schedule", "my agenda",
        "do i have anything at", "do i have a meeting at",
        "events this week", "events next week",
        "what's next", "what is next",
        # Natural week-overview queries
        "what does my week look like", "what's my week look like",
        "what does the week look like", "week look like",
        "how does my week look",
    ]

    @staticmethod
    def _detect_email_send_intent(message: str) -> bool:
        """Detect if message is a request to SEND/COMPOSE an email."""
        for pattern in IntentRouter.EMAIL_SEND_PATTERNS:
            if pattern in message:
                return True
        # "email to <address>" pattern
        if re.search(r'\bemail\s+to\s+\w', message):
            return True
        # "email <name>" e.g. "email anna about the report"
        if re.search(r'\bemail\s+[A-Z][a-z]', message):
            return True
        return False

    @staticmethod
    def _detect_email_reply_intent(message: str) -> bool:
        """Detect if message is a request to REPLY to an email."""
        for pattern in IntentRouter.EMAIL_REPLY_PATTERNS:
            if pattern in message:
                return True
        return False

    @staticmethod
    def _detect_email_forward_intent(message: str) -> bool:
        """Detect if message is a request to FORWARD an email."""
        for pattern in IntentRouter.EMAIL_FORWARD_PATTERNS:
            if pattern in message:
                return True
        return False

    @staticmethod
    def _detect_out_of_scope(message: str) -> bool:
        """Detect if message is completely out of scope."""
        for pattern in IntentRouter.OUT_OF_SCOPE_PATTERNS:
            if pattern in message:
                return True
        return False

    @staticmethod
    def _detect_email_read_intent(message: str) -> bool:
        """
        Detect if the message is a request to READ emails (not send/draft).

        Returns True if EMAIL_READ intent is detected.
        """
        # Make sure it's not a SEND/REPLY/FORWARD intent first
        send_indicators = ["send", "draft", "write", "compose", "reply", "respond", "forward"]
        if any(v in message for v in send_indicators):
            return False

        for pattern in IntentRouter.EMAIL_READ_PATTERNS:
            if pattern in message:
                return True

        # Count-based pattern: "last N emails" / "show N emails"
        if re.search(r'\b(last|show|get|fetch|read)\s+\d+\s+email', message):
            return True

        # "email/emails" with read verbs
        if re.search(r'\b(email|emails|inbox|mail)\b', message):
            read_verbs = ["what", "show", "list", "check", "read", "any", "do i have", "have i", "summarize"]
            if any(v in message for v in read_verbs):
                return True

        return False

    # Date modifiers that indicate a CALENDAR_READ query rather than a simple CALENDAR_LIST
    _CALENDAR_DATE_MODIFIERS = re.compile(
        r'\b(yesterday|last week|this week|next week|next monday|next tuesday|next wednesday|'
        r'next thursday|next friday|next saturday|next sunday|last monday|last tuesday|'
        r'last wednesday|last thursday|last friday|last saturday|last sunday|'
        r'tomorrow|in \d+ days?|\d{4}-\d{2}-\d{2})\b'
    )

    @staticmethod
    def _detect_calendar_intent(message: str) -> Optional[str]:
        """
        Detect calendar-specific intents from free text.

        Returns CALENDAR_CREATE, CALENDAR_UPDATE, CALENDAR_DELETE, CALENDAR_LIST, CALENDAR_READ, or None.

        Detection order:
        0. DELETE patterns — "cancel my meeting with Sarah"
        0b. UPDATE patterns — "move my 10am to 11", "reschedule my meeting"
        1. Regex CREATE check  — catches "create ME an event", typos, flexible phrasing
        2. String CREATE patterns — legacy exact-phrase matches (backward compat)
        3. Natural create patterns — "set up a call", "block time for"
        4. LIST patterns  — upgrade to CALENDAR_READ when date modifier present
        5. READ patterns  — richer date/time queries
        """
        # ── Step 0: DELETE patterns (checked first — most specific intent) ──
        for pattern in IntentRouter.CALENDAR_DELETE_PATTERNS:
            if pattern in message:
                logger.debug("[CALENDAR_INTENT] CALENDAR_DELETE: '%s'", message[:80])
                return IntentType.CALENDAR_DELETE

        # ── Step 0b: UPDATE patterns ─────────────────────────────────────────
        for pattern in IntentRouter.CALENDAR_UPDATE_PATTERNS:
            if pattern in message:
                logger.debug("[CALENDAR_INTENT] CALENDAR_UPDATE: '%s'", message[:80])
                return IntentType.CALENDAR_UPDATE

        # Also catch "move my Xam to Y" / "move my Xpm meeting to Y" patterns
        if re.search(r'\bmove\s+my\s+\d{1,2}(?::\d{2})?\s*(am|pm)', message):
            return IntentType.CALENDAR_UPDATE

        # "rename [event] to [new name]" — catch rename without explicit prefix
        if re.search(r'\brename\b.{1,60}\bto\b', message, re.IGNORECASE):
            return IntentType.CALENDAR_UPDATE

        # "change [event] to [new time/value]"
        if re.search(r'\bchange\s+\w.{2,50}\bto\s+\d', message, re.IGNORECASE):
            return IntentType.CALENDAR_UPDATE

        # Tomorrow's / today's event change
        if re.search(r"\b(tomorrow|today)'?s\b.{3,50}\bto\b", message, re.IGNORECASE):
            return IntentType.CALENDAR_UPDATE

        # ── Step 1: Regex-based CREATE detection (PRIMARY) ─────────────────
        if IntentRouter._CALENDAR_CREATE_RE.search(message):
            logger.debug("[CALENDAR_INTENT] Regex-matched CALENDAR_CREATE: '%s'", message[:80])
            return IntentType.CALENDAR_CREATE

        # ── Step 2: String-based CREATE patterns (FALLBACK) ────────────────
        for pattern in IntentRouter.CALENDAR_CREATE_PATTERNS:
            if pattern in message:
                if pattern in ("till ", "until "):
                    if not re.search(r'\d{1,2}[:\.]?\d{0,2}\s*(till|until)', message):
                        continue
                return IntentType.CALENDAR_CREATE

        # ── Step 3: Natural CREATE patterns not covered by regex ─────────────
        # "set up a call with X", "set up a meeting with X"
        if re.search(r'\bset\s+up\s+(?:a\s+)?(?:call|meeting|chat|sync|standup|check.?in)\b', message, re.IGNORECASE):
            return IntentType.CALENDAR_CREATE
        # "block X hours/minutes for Y" / "block time for Y"
        if re.search(r'\bblock\s+(?:out\s+)?(?:\d+\s+(?:hours?|minutes?|hrs?|mins?)|\btime\b)\b', message, re.IGNORECASE):
            return IntentType.CALENDAR_CREATE
        # "schedule a call/sync/chat"
        if re.search(r'\bschedule\s+(?:a\s+)?(?:call|sync|chat|standup|check.?in)\b', message, re.IGNORECASE):
            return IntentType.CALENDAR_CREATE

        # ── Step 4: LIST patterns (upgrade to READ when date modifier present) ─
        for pattern in IntentRouter.CALENDAR_LIST_PATTERNS:
            if pattern in message:
                if IntentRouter._CALENDAR_DATE_MODIFIERS.search(message):
                    return IntentType.CALENDAR_READ
                return IntentType.CALENDAR_LIST

        # ── Step 5: READ patterns (richer date/time queries) ───────────────
        for pattern in IntentRouter.CALENDAR_READ_PATTERNS:
            if pattern in message:
                return IntentType.CALENDAR_READ

        return None

    @staticmethod
    def route_message(
        message: str,
        active_task: Optional[Dict[str, Any]],
        pending_action: Optional[Dict[str, Any]],
        last_question_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route user message to appropriate intent type.
        
        This is the MAIN ENTRY POINT for all intent classification.
        
        Args:
            message: User's input message
            active_task: Current active task (if any)
            pending_action: Pending action awaiting confirmation (if any)
            last_question_type: Type of last question asked by agent
                (e.g., "optional_reminders", "provider_selection", "confirmation")
        
        Returns:
            {
                "intent_type": str,  # IntentType constant
                "extracted_slots": dict,  # Slot values extracted from message
                "normalized_message": str,  # Cleaned message
                "confidence": float,  # 0.0 to 1.0
                "reasoning": str  # Why this intent was selected
            }
        """
        message_lower = message.lower().strip()
        
        # Log routing decision
        logger.info(f"[INTENT_ROUTER] Routing: '{message}'")
        logger.info(f"[INTENT_ROUTER] Context: active_task={active_task.get('type') if active_task else None}, "
                   f"pending_action={pending_action.get('type') if pending_action else None}, "
                   f"last_question={last_question_type}")
        
        # =================================================================
        # PRIORITY 1: CANCEL_ACTION (highest priority - always honored)
        # =================================================================
        if IntentRouter._is_cancel_intent(message_lower):
            logger.info("[INTENT_ROUTER] ✓ CANCEL_ACTION detected")
            return {
                "intent_type": IntentType.CANCEL_ACTION,
                "extracted_slots": {},
                "normalized_message": message,
                "confidence": 1.0,
                "reasoning": "Explicit cancel keyword detected"
            }
        
        # =================================================================
        # PRIORITY 2: STATE-SPECIFIC ROUTING
        # =================================================================
        
        # EMAIL_SELECT_SENDER state - ONLY accept provider selection
        if active_task and active_task.get("type") in ["draft_email", "send_email"]:
            task_data = active_task.get("data", {})
            if task_data.get("state") == "EMAIL_SELECT_SENDER":
                provider = IntentRouter._extract_sender_account(message_lower)
                if provider:
                    logger.info(f"[INTENT_ROUTER] ✓ SELECT_SENDER_ACCOUNT: {provider}")
                    return {
                        "intent_type": IntentType.SELECT_SENDER_ACCOUNT,
                        "extracted_slots": {"provider": provider},
                        "normalized_message": message,
                        "confidence": 1.0,
                        "reasoning": f"Provider selection in EMAIL_SELECT_SENDER state: {provider}"
                    }
                # Invalid input - still route as sender selection (handler will re-ask)
                logger.info("[INTENT_ROUTER] ✓ SELECT_SENDER_ACCOUNT (invalid, will re-ask)")
                return {
                    "intent_type": IntentType.SELECT_SENDER_ACCOUNT,
                    "extracted_slots": {},
                    "normalized_message": message,
                    "confidence": 0.5,
                    "reasoning": "In EMAIL_SELECT_SENDER state but no valid provider detected"
                }
        
        # CAL_PROVIDER_SELECT state - ONLY accept provider selection
        if active_task and active_task.get("type") == "calendar_event":
            task_data = active_task.get("data", {})
            if task_data.get("state") == "CAL_PROVIDER_SELECT":
                provider = IntentRouter._extract_calendar_provider(message_lower)
                if provider:
                    logger.info(f"[INTENT_ROUTER] ✓ SELECT_CALENDAR_PROVIDER: {provider}")
                    return {
                        "intent_type": IntentType.SELECT_CALENDAR_PROVIDER,
                        "extracted_slots": {"provider": provider},
                        "normalized_message": message,
                        "confidence": 1.0,
                        "reasoning": f"Provider selection in CAL_PROVIDER_SELECT state: {provider}"
                    }
                # Invalid input - still route as provider selection
                logger.info("[INTENT_ROUTER] ✓ SELECT_CALENDAR_PROVIDER (invalid, will re-ask)")
                return {
                    "intent_type": IntentType.SELECT_CALENDAR_PROVIDER,
                    "extracted_slots": {},
                    "normalized_message": message,
                    "confidence": 0.5,
                    "reasoning": "In CAL_PROVIDER_SELECT state but no valid provider detected"
                }
        
        # =================================================================
        # PRIORITY 3: CONFIRMATION vs DECLINE_OPTIONAL
        # =================================================================
        
        # Context-aware "no" handling
        if IntentRouter._is_decline_intent(message_lower):
            # CRITICAL: Determine if this is declining OPTIONAL slot or cancelling action
            
            # If last question was about optional feature, this is DECLINE_OPTIONAL
            if last_question_type in ["optional_reminders", "optional_attendees", "optional_location", "optional_description"]:
                logger.info(f"[INTENT_ROUTER] ✓ DECLINE_OPTIONAL (context: {last_question_type})")
                return {
                    "intent_type": IntentType.DECLINE_OPTIONAL,
                    "extracted_slots": {},
                    "normalized_message": message,
                    "confidence": 1.0,
                    "reasoning": f"Declining optional slot: {last_question_type}"
                }
            
            # If there's a pending confirmation:
            # — "no, use outlook" / "no, call it X" etc. → MODIFY_DRAFT (user is correcting, not cancelling)
            # — bare "no" → CANCEL_ACTION (user is rejecting)
            if pending_action and pending_action.get("status") == "awaiting_confirmation":
                from services.nlu_service import NLUExtractor
                if NLUExtractor._has_correction_words(message_lower):
                    logger.info("[INTENT_ROUTER] ✓ MODIFY_DRAFT (decline + correction content during confirmation)")
                    return {
                        "intent_type": IntentType.MODIFY_DRAFT,
                        "extracted_slots": {},
                        "normalized_message": message,
                        "confidence": 0.9,
                        "reasoning": "User said 'no' but with correction content — treating as draft modification"
                    }
                logger.info("[INTENT_ROUTER] ✓ CANCEL_ACTION (bare 'no' rejecting confirmation)")
                return {
                    "intent_type": IntentType.CANCEL_ACTION,
                    "extracted_slots": {},
                    "normalized_message": message,
                    "confidence": 0.9,
                    "reasoning": "Bare 'no' while awaiting confirmation — treating as cancellation"
                }
            
            # Default: treat as general negative response
            logger.info("[INTENT_ROUTER] ✓ GENERAL_MESSAGE (negative response, no context)")
            return {
                "intent_type": IntentType.GENERAL_MESSAGE,
                "extracted_slots": {},
                "normalized_message": message,
                "confidence": 0.7,
                "reasoning": "Negative response without clear context"
            }
        
        # Confirmation handling
        if IntentRouter._is_confirm_intent(message_lower):
            # MUST have pending action to confirm
            if pending_action and pending_action.get("status") == "awaiting_confirmation":
                logger.info("[INTENT_ROUTER] ✓ CONFIRM_ACTION")
                return {
                    "intent_type": IntentType.CONFIRM_ACTION,
                    "extracted_slots": {},
                    "normalized_message": message,
                    "confidence": 1.0,
                    "reasoning": "Confirmation keyword with pending action"
                }
            else:
                logger.info("[INTENT_ROUTER] ✓ GENERAL_MESSAGE (confirmation without pending action)")
                return {
                    "intent_type": IntentType.GENERAL_MESSAGE,
                    "extracted_slots": {},
                    "normalized_message": message,
                    "confidence": 0.8,
                    "reasoning": "Confirmation keyword but no pending action"
                }
        
        # =================================================================
        # PRIORITY 4: SLOT FILLING (when active task exists)
        # =================================================================
        
        if active_task and IntentRouter._is_task_locked(active_task):
            # Extract slots for active task
            from utils.slot_extraction import SlotExtractor
            
            task_type = active_task.get("type")
            task_data = active_task.get("data", {})
            extracted_slots = {}
            
            if task_type in ["draft_email", "send_email"]:
                extracted_slots = SlotExtractor.extract_email_slots(message, task_data)
            elif task_type == "calendar_event":
                extracted_slots = SlotExtractor.extract_calendar_slots(message, task_data)
            
            # FIX: _is_task_locked() already confirmed task is locked (collecting / awaiting_confirmation).
            # Always route as PROVIDE_SLOT_VALUE so free-text body/description messages are not
            # dropped into general chat.  The check on task_data["state"] was wrong – status is
            # stored at active_task["status"] level, not inside the data dict.
            logger.info(
                f"[INTENT_ROUTER] ✓ PROVIDE_SLOT_VALUE "
                f"(task locked, status={active_task.get('status')!r}, "
                f"extracted={list(extracted_slots.keys())})"
            )
            return {
                "intent_type": IntentType.PROVIDE_SLOT_VALUE,
                "extracted_slots": extracted_slots,
                "normalized_message": message,
                "confidence": 0.9,
                "reasoning": (
                    f"Task '{task_type}' is locked "
                    f"(status={active_task.get('status')!r}) – treating input as slot value"
                ),
            }
        
        # =================================================================
        # PRIORITY 5: TOPIC SWITCH DETECTION
        # =================================================================
        
        if active_task:
            # Check if user is trying to start a completely different task
            topic_switch = IntentRouter._detect_topic_switch(message_lower, active_task)
            if topic_switch:
                logger.info(f"[INTENT_ROUTER] ⚠ SWITCH_TOPIC detected: {topic_switch}")
                return {
                    "intent_type": IntentType.SWITCH_TOPIC,
                    "extracted_slots": {},
                    "normalized_message": message,
                    "confidence": 0.85,
                    "reasoning": f"Topic switch detected: {topic_switch}"
                }

        # =================================================================
        # PRIORITY 6: READ/WRITE INTENTS + CALENDAR (no locked task)
        # Runs before GENERAL_MESSAGE so phrases are never dropped into LLM.
        # =================================================================

        # Out-of-scope detection — respond gracefully, not with confusion
        if IntentRouter._detect_out_of_scope(message_lower):
            logger.info("[INTENT_ROUTER] ✓ OUT_OF_SCOPE detected")
            return {
                "intent_type": IntentType.OUT_OF_SCOPE,
                "extracted_slots": {},
                "normalized_message": message,
                "confidence": 0.90,
                "reasoning": "Out-of-scope topic detected",
            }

        # EMAIL write intents — checked before read so "reply" etc. don't fall through
        if IntentRouter._detect_email_forward_intent(message_lower):
            logger.info("[INTENT_ROUTER] ✓ EMAIL_FORWARD detected")
            return {
                "intent_type": IntentType.EMAIL_FORWARD,
                "extracted_slots": {},
                "normalized_message": message,
                "confidence": 0.90,
                "reasoning": "Email forward intent detected",
            }

        if IntentRouter._detect_email_reply_intent(message_lower):
            logger.info("[INTENT_ROUTER] ✓ EMAIL_REPLY detected")
            return {
                "intent_type": IntentType.EMAIL_REPLY,
                "extracted_slots": {},
                "normalized_message": message,
                "confidence": 0.92,
                "reasoning": "Email reply intent detected",
            }

        if IntentRouter._detect_email_send_intent(message_lower):
            logger.info("[INTENT_ROUTER] ✓ EMAIL_SEND detected")
            return {
                "intent_type": IntentType.EMAIL_SEND,
                "extracted_slots": {},
                "normalized_message": message,
                "confidence": 0.92,
                "reasoning": "Email send/compose intent detected",
            }

        # EMAIL_READ — checked after write intents
        if IntentRouter._detect_email_read_intent(message_lower):
            logger.info("[INTENT_ROUTER] ✓ EMAIL_READ detected")
            return {
                "intent_type": IntentType.EMAIL_READ,
                "extracted_slots": {},
                "normalized_message": message,
                "confidence": 0.93,
                "reasoning": "Email read intent detected via keyword patterns"
            }

        cal_intent = IntentRouter._detect_calendar_intent(message_lower)
        if cal_intent:
            # For CREATE intents: extract the provider hint immediately so it is
            # locked from the very first message (task spec: "no defaults").
            cal_slots: Dict[str, Any] = {}
            if cal_intent == IntentType.CALENDAR_CREATE:
                from utils.slot_extraction import SlotExtractor
                provider_hint = SlotExtractor._extract_provider(message_lower)
                if provider_hint:
                    cal_slots["provider"] = provider_hint
                    logger.info(
                        "[CALENDAR_INTENT] ✓ Provider locked from message: %s", provider_hint
                    )

            logger.info("[CALENDAR_INTENT] ✓ %s detected (provider=%s)",
                        cal_intent, cal_slots.get("provider", "<infer>"))
            logger.info("[INTENT_ROUTER] ✓ %s detected", cal_intent)
            return {
                "intent_type": cal_intent,
                "extracted_slots": cal_slots,
                "normalized_message": message,
                "confidence": 0.95,
                "reasoning": (
                    f"Calendar intent detected via keyword patterns: {cal_intent}"
                    + (f" | provider locked: {cal_slots['provider']}" if cal_slots.get("provider") else "")
                ),
            }

        # =================================================================
        # DEFAULT: GENERAL_MESSAGE
        # =================================================================

        logger.info("[INTENT_ROUTER] ✓ GENERAL_MESSAGE (default)")
        return {
            "intent_type": IntentType.GENERAL_MESSAGE,
            "extracted_slots": {},
            "normalized_message": message,
            "confidence": 0.6,
            "reasoning": "No specific intent detected - general chat"
        }
    
    @staticmethod
    def _is_confirm_intent(message: str) -> bool:
        """Check if message is a confirmation."""
        # Exact match or starts with keyword
        return any(
            message == keyword or message.startswith(keyword + " ")
            for keyword in IntentRouter.CONFIRM_KEYWORDS
        )
    
    @staticmethod
    def _is_cancel_intent(message: str) -> bool:
        """Check if message is a cancellation."""
        return any(keyword in message for keyword in IntentRouter.CANCEL_KEYWORDS)
    
    @staticmethod
    def _is_decline_intent(message: str) -> bool:
        """Check if message is declining/negative."""
        return any(
            message == keyword or message.startswith(keyword + " ")
            for keyword in IntentRouter.DECLINE_OPTIONAL_KEYWORDS
        )
    
    @staticmethod
    def _extract_sender_account(message: str) -> Optional[str]:
        """Extract email sender account selection."""
        for provider, keywords in IntentRouter.SENDER_ACCOUNT_KEYWORDS.items():
            if any(keyword in message for keyword in keywords):
                return provider
        return None
    
    @staticmethod
    def _extract_calendar_provider(message: str) -> Optional[str]:
        """Extract calendar provider selection."""
        for provider, keywords in IntentRouter.CALENDAR_PROVIDER_KEYWORDS.items():
            if any(keyword in message for keyword in keywords):
                return provider
        return None
    
    @staticmethod
    def _is_task_locked(active_task: Dict[str, Any]) -> bool:
        """Check if task is in a locked state (actively collecting info)."""
        status = active_task.get("status")
        return status not in ["completed", "cancelled", None]
    
    @staticmethod
    def _detect_topic_switch(message: str, active_task: Dict[str, Any]) -> Optional[str]:
        """
        Detect if user is switching to a new topic while task is active.
        
        Returns:
            Description of new topic if detected, None otherwise
        """
        task_type = active_task.get("type")
        
        # Email task active, but user asks about calendar
        if task_type in ["draft_email", "send_email"]:
            calendar_keywords = ["calendar", "schedule", "meeting", "event", "appointment"]
            if any(keyword in message for keyword in calendar_keywords):
                # Check if not just mentioning it in email body
                if any(phrase in message for phrase in ["add to calendar", "schedule", "create event"]):
                    return "switching to calendar management"
        
        # Calendar task active, but user asks about email
        if task_type == "calendar_event":
            email_keywords = ["email", "send", "draft", "message"]
            if any(keyword in message for keyword in email_keywords):
                # Check if not just mentioning it as attendee/description
                if any(phrase in message for phrase in ["send email", "draft email", "email to"]):
                    return "switching to email management"
        
        # Greeting during active task
        greetings = ["hello", "hi", "hey"]
        if any(message.startswith(greeting) for greeting in greetings):
            return "greeting (potential reset)"
        
        return None
    
    @staticmethod
    def should_prevent_fallback(active_task: Optional[Dict[str, Any]]) -> bool:
        """
        ACTIVE TASK LOCK: Determine if fallback responses should be prevented.
        
        When True, agent MUST NOT:
        - List events/emails unrelated to task
        - Say "no pending actions"
        - Reset to general chat mode
        
        Args:
            active_task: Current active task
        
        Returns:
            True if fallback responses should be blocked
        """
        if not active_task:
            return False
        
        status = active_task.get("status")
        locked_statuses = ["collecting", "awaiting_confirmation", "drafted"]
        
        is_locked = status in locked_statuses
        
        if is_locked:
            logger.info(f"[ACTIVE_TASK_LOCK] ⚠ Fallback responses BLOCKED (task: {active_task.get('type')}, status: {status})")
        
        return is_locked
    
    @staticmethod
    def validate_pending_action(pending_action: Optional[Dict[str, Any]]) -> bool:
        """
        Validate that pending action has required fields.
        
        Args:
            pending_action: Pending action to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not pending_action:
            return False
        
        required_fields = ["type", "data", "status"]
        has_required = all(field in pending_action for field in required_fields)
        
        if not has_required:
            logger.warning(f"[INTENT_ROUTER] ⚠ Invalid pending action: missing required fields")
            return False
        
        return True
    
    @staticmethod
    def extract_multi_slot_message(message: str, task_type: str) -> Dict[str, Any]:
        """
        Extract multiple slots from a single sentence.
        
        Example:
        "Meeting with Chef tomorrow at 08:00 in Google calendar"
        → {title: "Meeting with Chef", date: "tomorrow", time: "08:00", provider: "google"}
        
        Args:
            message: User's message
            task_type: Type of task (calendar_event, draft_email, etc.)
        
        Returns:
            Dict of extracted slots
        """
        from utils.slot_extraction import SlotExtractor
        
        if task_type == "calendar_event":
            return SlotExtractor.extract_calendar_slots(message, {})
        elif task_type in ["draft_email", "send_email"]:
            return SlotExtractor.extract_email_slots(message, {})
        
        return {}
