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
        "do it", "okay", "ok", "please"
    ]
    
    CANCEL_KEYWORDS = [
        "cancel", "stop", "abort", "never mind", "nevermind",
        "forget it", "don't", "no don't", "quit"
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
            
            # If there's a pending confirmation, treat as cancellation
            if pending_action and pending_action.get("status") == "awaiting_confirmation":
                logger.info("[INTENT_ROUTER] ✓ CANCEL_ACTION (rejecting confirmation)")
                return {
                    "intent_type": IntentType.CANCEL_ACTION,
                    "extracted_slots": {},
                    "normalized_message": message,
                    "confidence": 0.9,
                    "reasoning": "Rejecting pending confirmation"
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
            
            # If we extracted any slots OR task is in collecting state, route as slot value
            if extracted_slots or task_data.get("state") in ["EMAIL_COLLECTING", "CAL_COLLECTING", "collecting"]:
                logger.info(f"[INTENT_ROUTER] ✓ PROVIDE_SLOT_VALUE (extracted: {list(extracted_slots.keys())})")
                return {
                    "intent_type": IntentType.PROVIDE_SLOT_VALUE,
                    "extracted_slots": extracted_slots,
                    "normalized_message": message,
                    "confidence": 0.9,
                    "reasoning": f"Providing slot values for active {task_type} task"
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
