"""
Executive Agent Service - Core Intelligence Layer

This is the brain of the OrganAIzer platform. Provides human-like, contextual,
and professional AI assistance for calendar, email, and general queries.

ARCHITECTURE:
1. Intent Detection → Route to appropriate handler
2. Entity Extraction → Extract structured data from natural language
3. Reasoning Layer → LLM-powered decision making with context
4. Confirmation Logic → Safe execution with user approval
5. Response Generation → Human-like, professional responses

CRITICAL DESIGN PRINCIPLES:
- Dynamic date/time handling (NO hardcoded years)
- Context-aware conversations (session memory)
- Tone adaptation (professional for work, friendly for chat)
- Robust ambiguity handling
- Explicit confirmations for risky actions

Author: OrganAIzer Team
Version: 2.0.0 - Intelligence Upgrade
Date: February 13, 2026
"""

import hashlib
import logging
import os
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import pytz

from services.chat_service import get_chat_service
from utils.intent_router import IntentRouter, IntentType
from utils.slot_extraction import SlotExtractor

logger = logging.getLogger(__name__)


# ==============================================================================
# SESSION & MEMORY MANAGEMENT
# ==============================================================================

@dataclass
class ConversationMemory:
    """
    Session-based conversation memory for contextual interactions.
    
    Tracks:
    - Conversation history (last N messages)
    - Active tasks (email drafting, calendar creation)
    - Pending actions (awaiting user confirmation)
    - Action history (completed actions)
    - Context variables (last mentioned topics, entities)
    """
    session_id: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    active_task: Optional[Dict[str, Any]] = None
    pending_action: Optional[Dict[str, Any]] = None
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    last_question_type: Optional[str] = None
    # Remembered provider preference — set after successful execution, used next time
    preferred_provider: Optional[str] = None
    # Current user_id — stored on each process_message() call so sub-handlers
    # (e.g. provider-selection re-dispatch) can access it without an extra param.
    current_user_id: Optional[str] = None
    # Last clarification message sent — used to detect and break stuck loops (group 10)
    last_clarification_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    MAX_HISTORY = 20  # Keep last 20 messages for context (needed for context memory)

    # Context memory for email flows
    last_email_sender: Optional[str] = None    # e.g. "Patrick"
    last_email_sender_address: Optional[str] = None
    last_email_thread_id: Optional[str] = None
    last_email_message_id: Optional[str] = None
    last_email_subject: Optional[str] = None

    # Conversation continuation tracking (Section 7)
    last_action_type: Optional[str] = None   # "email_read" | "calendar_read" | etc.
    last_provider: Optional[str] = None      # last successfully used provider

    def add_message(self, role: str, content: str):
        """Add message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last N messages
        if len(self.conversation_history) > self.MAX_HISTORY:
            self.conversation_history = self.conversation_history[-self.MAX_HISTORY:]
        
        self.last_activity = datetime.now()
    
    def set_active_task(self, task_type: str, data: Dict[str, Any], status: str = "collecting"):
        """Set or update active task."""
        self.active_task = {
            "type": task_type,
            "data": data,
            "status": status,
            "created_at": datetime.now().isoformat()
        }
        logger.info(f"[MEMORY] Active task set: {task_type} (status: {status})")
    
    def update_task_data(self, updates: Dict[str, Any]):
        """Update active task data."""
        if self.active_task:
            self.active_task["data"].update(updates)
            logger.info(f"[MEMORY] Task data updated: {list(updates.keys())}")
    
    def update_task_status(self, status: str):
        """Update active task status."""
        if self.active_task:
            self.active_task["status"] = status
            logger.info(f"[MEMORY] Task status updated: {status}")
    
    def get_active_task(self) -> Optional[Dict[str, Any]]:
        """Get current active task."""
        return self.active_task
    
    def clear_active_task(self):
        """Clear active task."""
        if self.active_task:
            logger.info(f"[MEMORY] Clearing active task: {self.active_task.get('type')}")
        self.active_task = None
    
    def is_task_locked(self) -> bool:
        """Check if there's an active task that shouldn't be interrupted."""
        if not self.active_task:
            return False
        status = self.active_task.get("status")
        return status in ["collecting", "awaiting_confirmation", "drafted"]
    
    def set_pending_action(self, action_type: str, data: Dict[str, Any]):
        """Set pending action awaiting confirmation."""
        self.pending_action = {
            "type": action_type,
            "data": data,
            "status": "awaiting_confirmation",
            "created_at": datetime.now().isoformat()
        }
        logger.info(f"[MEMORY] Pending action set: {action_type}")
    
    def get_pending_action(self) -> Optional[Dict[str, Any]]:
        """Get pending action."""
        return self.pending_action
    
    def clear_pending_action(self):
        """Clear pending action."""
        if self.pending_action:
            logger.info(f"[MEMORY] Clearing pending action: {self.pending_action.get('type')}")
        self.pending_action = None
    
    def add_to_history(self, action: Dict[str, Any]):
        """Add completed action to history."""
        action["completed_at"] = datetime.now().isoformat()
        self.action_history.append(action)
        
        # Keep last 20 actions
        if len(self.action_history) > 20:
            self.action_history = self.action_history[-20:]
        
        logger.info(f"[MEMORY] Action added to history: {action.get('type')}")
    
    def get_last_action(self) -> Optional[Dict[str, Any]]:
        """Get last completed action."""
        return self.action_history[-1] if self.action_history else None
    
    def update_context(self, key: str, value: Any):
        """Update context variable."""
        self.context[key] = value
        logger.debug(f"[MEMORY] Context updated: {key} = {value}")


# ==============================================================================
# IDEMPOTENCY STORE
# ==============================================================================

# In-process cache: request_id (SHA-256 hash) → event_id returned by the
# calendar API.  Prevents duplicate events when the user confirms twice or
# the client retries after a network hiccup.
# For multi-instance deployments replace with Redis / a shared DB.
_CALENDAR_IDEMPOTENCY_STORE: Dict[str, str] = {}

# FIX C-01: asyncio.Lock to make idempotency check + store atomic across
# await boundaries.  Without this, two simultaneous "yes" confirmations for
# the same event both pass the cache-miss check before either one stores the
# result, creating duplicate calendar events.
import asyncio as _asyncio
_CALENDAR_IDEMPOTENCY_LOCK = _asyncio.Lock()

def _compute_calendar_request_id(
    user_id: str,
    title: str,
    start: str,
    end: str,
    timezone_name: str = "UTC",
) -> str:
    """
    Compute a deterministic SHA-256 request_id for a calendar create call.

    Two calls with identical (user_id, title, start, end, timezone_name)
    produce the same request_id, enabling idempotent deduplication.
    """
    raw = f"{user_id}|{title}|{start}|{end}|{timezone_name}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ==============================================================================
# EXECUTIVE AGENT - MAIN CLASS
# ==============================================================================

class ExecutiveAgent:
    """
    Executive Agent - The intelligent core of OrganAIzer.
    
    Capabilities:
    - Natural language understanding with context awareness
    - Calendar management (create, modify, query events)
    - Email management (read, draft, send emails)
    - General knowledge and conversation
    - Multi-turn dialogues with session memory
    - Professional tone adaptation
    
    Intelligence Features (v2.0):
    - Dynamic date/time parsing (understands "tomorrow" = actual tomorrow)
    - Robust intent classification (knows user wants vs technical glitches)
    - Ambiguity handling (asks clarifying questions naturally)
    - Context memory (remembers conversation flow)
    - Confirmation logic (safe execution of actions)
    """
    
    # Class-level session storage
    sessions: Dict[str, ConversationMemory] = {}
    
    def __init__(self, session_id: str):
        """
        Initialize Executive Agent with session.
        
        Args:
            session_id: Unique identifier for this conversation session
        """
        self.session_id = session_id
        
        # Get or create session memory
        if session_id not in ExecutiveAgent.sessions:
            ExecutiveAgent.sessions[session_id] = ConversationMemory(session_id=session_id)
            logger.info(f"[AGENT] New session created: {session_id}")
        else:
            logger.info(f"[AGENT] Resuming session: {session_id}")
        
        self.memory = ExecutiveAgent.sessions[session_id]
        self.chat_service = get_chat_service()
        
        # Get current date/time for dynamic parsing
        self.current_datetime = datetime.now()
        self.timezone = pytz.timezone(os.getenv("TIMEZONE", "Europe/Berlin"))
        
        logger.info(f"[AGENT] Initialized | Current date: {self.current_datetime.date()} | Timezone: {self.timezone}")
    
    async def process_message(
        self,
        user_message: str,
        user_id: str = "default_user",
        provider: Optional[str] = None,          # legacy field – kept for backward compat
        mail_provider: Optional[str] = None,      # provider used for email actions
        calendar_provider: Optional[str] = None, # provider used for calendar actions
    ) -> Dict[str, Any]:
        """
        MAIN ENTRY POINT: Process user message with full intelligence pipeline.

        Pipeline:
        1. Intent Detection (deterministic rules + context)
        2. Entity Extraction (dates, times, names, emails)
        3. Reasoning (LLM-powered contextual understanding)
        4. Action Planning (what needs to be done)
        5. Confirmation Logic (ask user if needed)
        6. Execution (perform action)
        7. Response Generation (human-like reply)

        Args:
            user_message: Natural language input from user
            user_id: User identifier for OAuth tokens
            provider: Legacy field – kept for backward compat
            mail_provider: Provider for email operations (gmail/outlook)
            calendar_provider: Provider for calendar operations (google/outlook)

        Returns:
            {
                "message": str,
                "success": bool,
                "type": str,
                "data": dict,
                "action_needed": str,
                "error": str
            }
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"[AGENT] Processing message: '{user_message}'")
        logger.info(f"[AGENT] User: {user_id} | mail_provider: {mail_provider} | calendar_provider: {calendar_provider}")

        # Store user_id in session memory so provider-selection re-dispatch handlers
        # can retrieve it without requiring an extra parameter.
        self.memory.current_user_id = user_id

        try:
            # Add user message to memory
            self.memory.add_message("user", user_message)

            # STEP 1: Intent Detection
            intent_result = IntentRouter.route_message(
                message=user_message,
                active_task=self.memory.get_active_task(),
                pending_action=self.memory.get_pending_action(),
                last_question_type=self.memory.last_question_type
            )

            intent_type = intent_result["intent_type"]
            extracted_slots = intent_result["extracted_slots"]

            logger.info(f"[AGENT] Intent: {intent_type} | Slots: {list(extracted_slots.keys())}")

            # STEP 2: Route to appropriate handler
            response = await self._route_to_handler(
                intent_type=intent_type,
                user_message=user_message,
                extracted_slots=extracted_slots,
                user_id=user_id,
                mail_provider=mail_provider,
                calendar_provider=calendar_provider,
            )

            # Stamp the detected intent onto the response so the API endpoint
            # can include it in the standardized envelope without re-deriving it.
            response.setdefault("intent", intent_type)

            # Add agent response to memory
            self.memory.add_message("assistant", response["message"])

            logger.info(f"[AGENT] Response generated: {response['type']}")
            logger.info(f"{'='*80}\n")

            return response

        except Exception as e:
            logger.error(f"[AGENT] Error processing message: {e}", exc_info=True)
            return {
                "message": "I apologize, but I encountered an error processing your request. Please try rephrasing or contact support if the issue persists.",
                "success": False,
                "type": "error",
                "intent": "GENERAL_MESSAGE",
                "error": str(e)
            }
    
    async def _route_to_handler(
        self,
        intent_type: str,
        user_message: str,
        extracted_slots: Dict[str, Any],
        user_id: str,
        mail_provider: Optional[str] = None,
        calendar_provider: Optional[str] = None,
        # Accept legacy single-provider arg too for any internal call-sites
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Route to appropriate intent handler based on intent type.

        Uses mail_provider for email operations, calendar_provider for calendar ops.
        """
        # Derive providers — None propagates to handlers which will request
        # clarification when no provider can be resolved from message or session.
        _mail = mail_provider or provider   # None → triggers clarification in handler
        _cal  = calendar_provider or provider  # None → triggers clarification in handler

        # Confirmation handling
        if intent_type == IntentType.CONFIRM_ACTION:
            return await self._handle_confirmation(user_id, _cal)

        # Cancellation handling
        if intent_type == IntentType.CANCEL_ACTION:
            return await self._handle_cancellation()

        # Optional slot decline
        if intent_type == IntentType.DECLINE_OPTIONAL:
            return await self._handle_decline_optional(user_id, _cal, _mail)

        # Provider selection
        if intent_type == IntentType.SELECT_SENDER_ACCOUNT:
            return await self._handle_sender_selection(extracted_slots)

        if intent_type == IntentType.SELECT_CALENDAR_PROVIDER:
            return await self._handle_calendar_provider_selection(extracted_slots)

        # Dedicated calendar create intent (from intent router)
        if intent_type == IntentType.CALENDAR_CREATE:
            logger.info("[AGENT] ✓ Calendar event creation intent detected (CALENDAR_CREATE)")
            return await self._handle_calendar_event_creation(
                user_message, extracted_slots, user_id, _cal
            )

        # Dedicated calendar list intent (from intent router)
        if intent_type == IntentType.CALENDAR_LIST:
            logger.info("[AGENT] ✓ Calendar list intent detected (CALENDAR_LIST)")
            return await self._handle_calendar_list_events(user_id, _cal, user_message)

        # Email READ intent — read/summarize emails, no write action
        if intent_type == IntentType.EMAIL_READ:
            logger.info("[AGENT] ✓ Email read intent detected (EMAIL_READ)")
            return await self._handle_email_read(user_message, user_id, _mail)

        # Calendar READ intent — richer date-range queries
        if intent_type == IntentType.CALENDAR_READ:
            logger.info("[AGENT] ✓ Calendar read intent detected (CALENDAR_READ)")
            return await self._handle_calendar_read(user_message, user_id, _cal)

        # Draft correction — "no, use outlook" / "no, call it X" / "make it 21:00"
        if intent_type == IntentType.MODIFY_DRAFT:
            return await self._handle_modify_draft(user_message, extracted_slots, user_id, _cal, _mail)

        # Slot filling for active task.
        # During awaiting_confirmation, any new input is treated as a slot CORRECTION
        # (the user saw the confirmation and wants to change something).
        if intent_type == IntentType.PROVIDE_SLOT_VALUE:
            active_task = self.memory.get_active_task()
            if active_task and active_task.get("status") == "awaiting_confirmation":
                logger.info(
                    "[AGENT] PROVIDE_SLOT_VALUE during awaiting_confirmation → _handle_modify_draft"
                )
                return await self._handle_modify_draft(user_message, extracted_slots, user_id, _cal, _mail)
            return await self._handle_slot_filling(user_message, extracted_slots, user_id, _cal)

        # New email write intents
        if intent_type == IntentType.EMAIL_SEND:
            logger.info("[AGENT] ✓ Email send intent detected (EMAIL_SEND)")
            return await self._handle_send_email(user_message, extracted_slots, user_id, _mail)

        if intent_type == IntentType.EMAIL_REPLY:
            logger.info("[AGENT] ✓ Email reply intent detected (EMAIL_REPLY)")
            return await self._handle_email_reply(user_message, user_id, _mail)

        if intent_type == IntentType.EMAIL_FORWARD:
            logger.info("[AGENT] ✓ Email forward intent detected (EMAIL_FORWARD)")
            return await self._handle_email_forward(user_message, user_id, _mail)

        # New calendar mutation intents
        if intent_type == IntentType.CALENDAR_UPDATE:
            logger.info("[AGENT] ✓ Calendar update intent detected (CALENDAR_UPDATE)")
            return await self._handle_calendar_update(user_message, user_id, _cal)

        if intent_type == IntentType.CALENDAR_DELETE:
            logger.info("[AGENT] ✓ Calendar delete intent detected (CALENDAR_DELETE)")
            return await self._handle_calendar_delete(user_message, user_id, _cal)

        # Out-of-scope topics
        if intent_type == IntentType.OUT_OF_SCOPE:
            logger.info("[AGENT] ✓ Out-of-scope detected")
            return await self._handle_out_of_scope(user_message)

        # Topic switch during active task
        if intent_type == IntentType.SWITCH_TOPIC:
            return await self._handle_topic_switch(user_message, user_id, _cal)

        # General message (new task or chat) – pass both providers
        return await self._handle_general_message(user_message, extracted_slots, user_id, _mail, _cal)
    
    async def _handle_general_message(
        self,
        user_message: str,
        extracted_slots: Dict[str, Any],
        user_id: str,
        mail_provider: Optional[str] = None,
        calendar_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle general messages with intent detection for calendar/email operations.

        This is a fallback after the intent router has already had a chance to
        detect CALENDAR_CREATE / CALENDAR_LIST.  Keeps legacy keyword detection
        as a safety net.
        """
        logger.info("[AGENT] Handling general message - checking for calendar/email intent")

        message_lower = user_message.lower()

        # ── Calendar event creation (legacy fallback) ─────────────────────────
        calendar_create_keywords = [
            "create event", "create an event", "add event", "add an event",
            "create calendar", "calendar event", "schedule event",
            "create meeting", "schedule meeting", "add meeting",
            "add to calendar", "meeting with", "appointment with",
        ]

        if any(keyword in message_lower for keyword in calendar_create_keywords):
            logger.info("[AGENT] ✓ Calendar event creation intent detected (fallback)")
            return await self._handle_calendar_event_creation(
                user_message, extracted_slots, user_id, calendar_provider
            )

        # ── Calendar list events (legacy fallback) ────────────────────────────
        calendar_list_keywords = [
            "what events", "what's on my calendar", "show my calendar",
            "events tomorrow", "events today", "google calendar events",
            "check my calendar", "upcoming events",
        ]

        if any(keyword in message_lower for keyword in calendar_list_keywords):
            logger.info("[AGENT] ✓ Calendar list intent detected (fallback)")
            return await self._handle_calendar_list_events(
                user_id, calendar_provider, user_message
            )

        # ── Email send detection ──────────────────────────────────────────────
        email_send_keywords = [
            "send email", "send an email", "email to", "draft email",
            "write email", "compose email", "send message",
            "draft a message", "write a message", "send mail",
            "shoot an email", "fire off an email",
        ]

        if any(keyword in message_lower for keyword in email_send_keywords):
            logger.info("[AGENT] ✓ Email send intent detected")
            return await self._handle_send_email(
                user_message, extracted_slots, user_id, mail_provider
            )
        
        # ==========================================
        # DEFAULT: LLM CHAT
        # ==========================================
        logger.info("[AGENT] No specific intent - using LLM reasoning")
        
        # Build system prompt with current context
        system_prompt = self._build_intelligent_system_prompt()
        
        # Build user prompt with conversation history
        user_prompt = self._build_contextual_user_prompt(user_message)
        
        # Get LLM response
        from models.chat import ChatRequest, ChatMessage
        
        chat_request = ChatRequest(
            prompt=user_prompt,
            conversation_history=[
                ChatMessage(role="system", content=system_prompt)
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        llm_response = await self.chat_service.chat_completion(chat_request)
        
        return {
            "message": llm_response.response,
            "success": True,
            "type": "chat",
            "data": {}
        }
    
    def _build_intelligent_system_prompt(self) -> str:
        """
        Build the system prompt for the LLM.

        SECTION 1 FIX: The assistant is a GENERAL-INTELLIGENCE executive assistant.
        It can discuss ANY topic — history, science, geography, technology, business,
        philosophy, daily conversation — AND also manage calendars and emails.
        It must NEVER say it is limited to email/calendar tasks.

        Natural assistant persona — no markdown, no emojis, direct and friendly.
        """
        current_date = self.current_datetime.strftime("%A, %B %d, %Y")
        current_time = self.current_datetime.strftime("%H:%M")
        tomorrow = (self.current_datetime + timedelta(days=1)).strftime("%Y-%m-%d")

        return (
            "You are a smart, versatile executive assistant with broad general intelligence. "
            "You can discuss ANY topic: history, science, geography, technology, business, "
            "philosophy, daily conversation, current events, and much more. "
            "You also manage calendars and emails via integrated tools when the user asks for productivity actions.\n\n"
            f"Today is {current_date}. Current time: {current_time}. Tomorrow: {tomorrow}.\n\n"
            "Behavior rules:\n"
            "- For general knowledge and conversational questions: respond naturally and helpfully "
            "using your full knowledge — do NOT say you are limited to email/calendar.\n"
            "- For productivity actions (create event, send email, read calendar, etc.): "
            "guide the user through the appropriate workflow.\n"
            "- Keep responses concise, direct, and friendly — 1-3 sentences when possible.\n"
            "- No markdown formatting (no **, no ##, no bullet lists).\n"
            "- No emojis.\n"
            "- Ask only one clarifying question at a time.\n"
            "- Never repeat back everything the user just said word for word.\n"
            "- When a productivity provider (Google/Outlook) is not connected, say: "
            "'Your [Provider] account isn't connected yet. You can link it in the Integrations page.'\n"
            "- Confirmation is required before creating events or sending emails.\n"
            "- Ask 'Which account — Google or Microsoft?' only when the user wants a productivity "
            "action and hasn't specified a provider."
        )
    
    def _build_contextual_user_prompt(self, current_message: str) -> str:
        """
        Build user prompt with conversation history for context.
        """
        # Include last few messages for context
        history_context = ""
        if len(self.memory.conversation_history) > 1:
            recent_messages = self.memory.conversation_history[-5:-1]  # Last 4 messages before current
            history_context = "\n\nRECENT CONVERSATION:\n"
            for msg in recent_messages:
                role = "User" if msg["role"] == "user" else "You"
                history_context += f"{role}: {msg['content']}\n"
        
        # Include active task context if any
        task_context = ""
        if self.memory.active_task:
            task = self.memory.active_task
            task_context = f"\n\nACTIVE TASK:\nYou are currently helping the user with: {task['type']}\nStatus: {task['status']}\n"
        
        return f"{history_context}{task_context}\nUser: {current_message}\n\nYour response:"
    
    async def _handle_confirmation(self, user_id: str, provider: str) -> Dict[str, Any]:
        """
        Handle user confirming a pending action.
        
        CRITICAL: This executes the integration endpoint!
        """
        logger.info("[AGENT] Handling confirmation")
        
        pending = self.memory.get_pending_action()
        if not pending:
            return {
                "message": "I don't have any pending actions to confirm. What would you like me to help you with?",
                "success": False,
                "type": "error"
            }
        
        action_type = pending["type"]
        action_data = pending["data"]
        
        logger.info(f"[ORCHESTRATION] Executing confirmed action: {action_type}")
        
        # Execute based on action type
        if action_type == "create_calendar_event":
            return await self._execute_calendar_event_creation(action_data, user_id)
        elif action_type == "send_email":
            return await self._execute_email_send(action_data, user_id)
        elif action_type == "update_calendar_event":
            return await self._execute_calendar_update(action_data, user_id)
        else:
            logger.warning(f"[ORCHESTRATION] Unknown action type: {action_type}")
            self.memory.clear_pending_action()
            self.memory.clear_active_task()
            return {
                "message": f"✅ Confirmed! (Note: Action type '{action_type}' not yet implemented)",
                "success": True,
                "type": "confirmation",
                "data": action_data
            }
    
    async def _execute_calendar_event_creation(
        self,
        action_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute calendar event creation via integration endpoint.

        CRITICAL: Only returns type="calendar_created" after a verified 2xx HTTP
        response from /api/integrations/{provider}/calendar/events.

        FIX NOTES:
        - Guard: refuses to proceed if pending_action is already gone
        - 2xx check: uses response.is_success (covers 200, 201, …)
        - Audit log: endpoint, payload, params, status, and body around every call
        - Execution proof: includes event_id, htmlLink, start, end in response data
        - Error handling: preserves pending_action on failure so user can retry;
          only clears it after confirmed success
        - Provider normalisation: "gmail" → "google", "outlook" → "microsoft", etc.
        """
        import httpx
        from datetime import datetime, timedelta

        logger.info("[ORCHESTRATION] Executing calendar event creation")

        # ── Guard: must have a real pending action ────────────────────────────
        if not self.memory.get_pending_action():
            logger.warning(
                "[ORCHESTRATION] _execute_calendar_event_creation called but no "
                "pending_action found in session – refusing to claim success"
            )
            return {
                "message": (
                    "There is no pending calendar event to create. "
                    "Please describe the event again so I can set it up for you."
                ),
                "success": False,
                "type": "error",
                "error": "No pending action found",
            }

        try:
            # ── Extract data ──────────────────────────────────────────────────
            title = action_data.get("title", "Meeting")
            date = action_data.get("date")
            time_str = action_data.get("time")
            end_time = action_data.get("end_time")
            duration = action_data.get("duration", 60)  # default 60 min
            location = action_data.get("location")

            # Normalise provider → valid URL segment ("google" or "outlook")
            raw_provider = action_data.get("provider", "google")
            provider = _normalize_provider(raw_provider)

            # FIX M-06: Use ONE tz_name value for BOTH timezone localization
            # AND the idempotency hash. The original code had two os.getenv()
            # calls with DIFFERENT defaults ("Europe/Berlin" vs "UTC"), meaning
            # the hash used a different timezone than the event was created with.
            tz_name = os.getenv("TIMEZONE", "Europe/Berlin")
            try:
                tz_obj = pytz.timezone(tz_name)
            except Exception:
                tz_obj = pytz.UTC
                tz_name = "UTC"

            # FIX H-01: Guard pytz.localize() against already-aware datetimes
            # (e.g. if time_str ever contains "+01:00") and catch DST-ambiguous
            # times (e.g. "02:30" on the clock-change night in Europe/Berlin).
            start_dt_naive = datetime.fromisoformat(f"{date}T{time_str}:00")
            if start_dt_naive.tzinfo is not None:
                # Already timezone-aware — use as-is
                start_dt_aware = start_dt_naive
            else:
                try:
                    start_dt_aware = tz_obj.localize(start_dt_naive, is_dst=None)
                except Exception:
                    # AmbiguousTimeError or NonExistentTimeError during DST transition
                    # → fall back to non-DST interpretation (the later/canonical offset)
                    start_dt_aware = tz_obj.localize(start_dt_naive, is_dst=False)
                    logger.warning(
                        "[ORCHESTRATION] DST-ambiguous time '%sT%s' — using is_dst=False",
                        date, time_str,
                    )
            start_datetime_str = start_dt_aware.isoformat()

            # Build end datetime (also timezone-aware)
            if end_time:
                end_dt_naive = datetime.fromisoformat(f"{date}T{end_time}:00")
                if end_dt_naive.tzinfo is not None:
                    end_dt_aware = end_dt_naive
                else:
                    try:
                        end_dt_aware = tz_obj.localize(end_dt_naive, is_dst=None)
                    except Exception:
                        end_dt_aware = tz_obj.localize(end_dt_naive, is_dst=False)
                end_datetime_str = end_dt_aware.isoformat()
            else:
                end_dt_aware = start_dt_aware + timedelta(minutes=duration)
                end_datetime_str = end_dt_aware.isoformat()

            # ── FIX C-01: Atomic idempotency check-call-store using asyncio.Lock ──
            # Without the lock, two simultaneous "yes" confirmations both pass the
            # cache-miss check before either stores the result → duplicate events.
            request_id = _compute_calendar_request_id(
                user_id=user_id,
                title=title,
                start=start_datetime_str,
                end=end_datetime_str,
                timezone_name=tz_name,
            )
            logger.info("[IDEMPOTENCY] request_id=%s", request_id)

            async with _CALENDAR_IDEMPOTENCY_LOCK:
                # Re-check inside the lock — another coroutine may have stored it
                # between our pre-lock check and acquiring the lock.
                if request_id in _CALENDAR_IDEMPOTENCY_STORE:
                    cached_event_id = _CALENDAR_IDEMPOTENCY_STORE[request_id]
                    logger.info(
                        "[IDEMPOTENCY] Duplicate request detected (inside lock) – returning cached "
                        "event_id=%s (no API call made)", cached_event_id
                    )
                    self.memory.clear_pending_action()
                    self.memory.clear_active_task()
                    return {
                        "message": (
                            f"✅ This event was already created!\n\n"
                            f"**{title}**\n"
                            f"- 📅 Date: {date}\n"
                            f"- 🕐 Start: {start_datetime_str}\n"
                            f"- 🕑 End: {end_datetime_str}\n"
                            f"- 📆 Calendar: {provider.title()} Calendar\n"
                            f"- 🆔 Event ID: `{cached_event_id}` (existing)"
                        ),
                        "success": True,
                        "type": "calendar_created",
                        "data": {
                            "event_id": cached_event_id,
                            "start": start_datetime_str,
                            "end": end_datetime_str,
                            "idempotent": True,
                        },
                    }

                # ── Placeholder sentinel — prevents a second concurrent request
                # from seeing a "miss" while the first is still awaiting the API.
                _CALENDAR_IDEMPOTENCY_STORE[request_id] = "__pending__"
            # Lock released — proceed with API call

            # Build request payload (omit None fields to keep it clean)
            from models.integrations import CalendarEventCreateRequest

            event_request = CalendarEventCreateRequest(
                summary=title,
                description=action_data.get("description"),
                start=start_datetime_str,
                end=end_datetime_str,
                location=location,
                attendees=action_data.get("attendees"),
            )
            payload = event_request.dict(exclude_none=True)
            # Include request_id so providers can do server-side dedup if supported
            payload["request_id"] = request_id

            # Call integration endpoint
            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            endpoint = f"{base_url}/api/integrations/{provider}/calendar/events"
            params = {"user_id": user_id}

            # ── AUDIT LOG – before call ───────────────────────────────────────
            logger.info("[AUDIT] Calendar create → endpoint=%s", endpoint)
            logger.info("[AUDIT] Calendar create → params=%s", params)
            logger.info("[AUDIT] Calendar create → payload=%s", json.dumps(payload))

            response_status: Optional[int] = None
            response_body_text: Optional[str] = None

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    params=params,
                    timeout=30.0,
                )

            response_status = response.status_code
            response_body_text = response.text

            # ── AUDIT LOG – after call ────────────────────────────────────────
            logger.info("[AUDIT] Calendar create ← status=%s", response_status)
            logger.info("[AUDIT] Calendar create ← body=%s", response_body_text[:500])

            # ── FIX: accept any 2xx (200, 201, …) as success ─────────────────
            if response.is_success:
                event_data = response.json()

                event_id = event_data.get("id")
                event_summary = event_data.get("summary", title)
                event_start = event_data.get("start", start_datetime_str)
                event_end = event_data.get("end", end_datetime_str)
                # htmlLink is returned by Google but not in our CalendarEvent
                # model; grab it from raw JSON when present
                html_link = event_data.get("htmlLink")

                # ── TRUTHFULNESS CHECK: 2xx without event_id = unreliable ────
                # The calendar API must return a real event_id.  Without it we
                # cannot confirm the event actually exists, so we treat it as a
                # failure rather than silently claiming success.
                if not event_id:
                    logger.error(
                        "[AUDIT] Calendar create ❌  HTTP %s returned but no "
                        "event_id found in response body: %s",
                        response_status, response_body_text[:300]
                    )
                    # FIX: Remove the "__pending__" sentinel so a retry can proceed
                    _CALENDAR_IDEMPOTENCY_STORE.pop(request_id, None)
                    return {
                        "message": (
                            "❌ The calendar API returned a success status but did not "
                            "provide an event ID. The event may or may not have been created.\n\n"
                            "Please check your calendar directly. "
                            "If the event is missing, say **yes** to try again."
                        ),
                        "success": False,
                        "type": "error",
                        "error": "event_id missing from API response",
                        "data": {
                            "status_code": response_status,
                            "raw_response": response_body_text[:300],
                            "pending_action_preserved": True,
                        },
                    }

                logger.info(
                    "[AUDIT] Calendar create ✅  event_id=%s  summary=%s",
                    event_id, event_summary
                )

                # ── Write idempotency store so duplicate requests return same ID ─
                _CALENDAR_IDEMPOTENCY_STORE[request_id] = event_id
                logger.info(
                    "[IDEMPOTENCY] Stored request_id=%s → event_id=%s",
                    request_id, event_id
                )

                # Record in history ONLY after confirmed success
                self.memory.add_to_history({
                    **action_data,
                    "type": "create_calendar_event",
                    "result": event_data,
                    "event_id": event_id,
                })

                # Remember provider for next calendar event in this session
                self.memory.preferred_provider = provider
                logger.info("[MEMORY] preferred_provider updated → '%s'", provider)

                # Clear state only on success
                self.memory.clear_pending_action()
                self.memory.clear_active_task()

                # Natural success message — no markdown, no emojis
                _date_lbl = _format_date_natural(date) if date else date
                _start_raw = str(event_start)
                _time_lbl = _format_time_natural(_start_raw.split("T")[1][:5]) if "T" in _start_raw else _start_raw
                success_msg = f"Done. {event_summary} is on your calendar for {_date_lbl} at {_time_lbl}."

                return {
                    "message": success_msg,
                    "success": True,
                    "type": "calendar_created",
                    "data": {
                        **event_data,
                        # Ensure key proof fields are always at top level of data
                        "event_id": event_id,
                        "htmlLink": html_link,
                        "start": event_start,
                        "end": event_end,
                    },
                }

            else:
                # ── HTTP error – preserve pending_action so user can retry ────
                error_detail: str = f"HTTP {response_status}"
                try:
                    error_json = response.json()
                    if isinstance(error_json, dict):
                        detail = error_json.get("detail", {})
                        if isinstance(detail, dict):
                            error_detail = detail.get("message", str(detail))
                        else:
                            error_detail = str(detail)
                except Exception:
                    error_detail = response_body_text or f"HTTP {response_status}"

                logger.error(
                    "[AUDIT] Calendar create ❌  status=%s  detail=%s",
                    response_status, error_detail
                )

                # DO NOT clear pending_action – allow user to retry after
                # fixing OAuth or transient errors
                return {
                    "message": (
                        f"❌ Failed to create the calendar event "
                        f"(HTTP {response_status}): {error_detail}\n\n"
                        "Your event details are still saved. "
                        "Please check your calendar connection and say **yes** to try again."
                    ),
                    "success": False,
                    "type": "error",
                    "error": f"HTTP {response_status}: {error_detail}",
                    "data": {
                        "status_code": response_status,
                        "pending_action_preserved": True,
                    },
                }

        except httpx.TimeoutException as e:
            logger.error("[ORCHESTRATION] ❌ Timeout calling integration endpoint: %s", e)
            # Preserve pending_action – user can retry
            return {
                "message": (
                    "❌ The calendar service timed out. "
                    "Your event details are still saved – please say **yes** to try again."
                ),
                "success": False,
                "type": "error",
                "error": f"Timeout: {e}",
                "data": {"pending_action_preserved": True},
            }

        except Exception as e:
            logger.error(
                "[ORCHESTRATION] ❌ Unexpected error executing calendar creation: %s",
                e, exc_info=True
            )
            # Preserve pending_action for retry on unexpected failures too
            return {
                "message": (
                    f"❌ Unexpected error while creating the event: {e}\n\n"
                    "Your event details are still saved – please say **yes** to try again."
                ),
                "success": False,
                "type": "error",
                "error": str(e),
                "data": {"pending_action_preserved": True},
            }
    
    async def _execute_email_send(
        self,
        action_data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute email send via Gmail or Outlook integration endpoint.

        Calls:
          Gmail:   POST /api/integrations/google/gmail/send?user_id={user_id}
          Outlook: POST /api/integrations/microsoft/mail/send?user_id={user_id}

        Mirrors _execute_calendar_event_creation pattern exactly:
        - Guard: refuses if no pending_action
        - Audit log before + after
        - Accepts any 2xx as success
        - Preserves pending_action on failure so user can retry
        """
        import httpx

        logger.info("[ORCHESTRATION] Executing email send")

        # ── Guard ─────────────────────────────────────────────────────────────
        if not self.memory.get_pending_action():
            logger.warning("[ORCHESTRATION] _execute_email_send called but no pending_action found")
            return {
                "message": (
                    "There is no pending email to send. "
                    "Please compose an email first."
                ),
                "success": False,
                "type": "error",
                "error": "No pending action found",
            }

        try:
            # ── Extract data ──────────────────────────────────────────────────
            to_email = action_data.get("to_email")
            subject = action_data.get("subject", "(No Subject)")
            body = action_data.get("body", "")
            html = action_data.get("html")
            cc = action_data.get("cc")
            bcc = action_data.get("bcc")
            thread_id = action_data.get("thread_id")       # Gmail reply threading
            reply_to_id = action_data.get("reply_to_id")   # Outlook reply threading

            # Normalise provider → "google" or "outlook"
            raw_provider = action_data.get("provider", "gmail")
            provider = _normalize_provider(raw_provider)

            # Build payload matching MailSendRequest model
            payload: Dict[str, Any] = {
                "to": to_email,
                "subject": subject,
                "body": body,
            }
            if html:
                payload["html"] = html
            if cc:
                payload["cc"] = cc
            if bcc:
                payload["bcc"] = bcc
            if thread_id:
                payload["thread_id"] = thread_id
            if reply_to_id:
                payload["reply_to_id"] = reply_to_id

            # Choose endpoint based on provider
            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            if provider == "google":
                endpoint = f"{base_url}/api/integrations/google/gmail/send"
            else:
                endpoint = f"{base_url}/api/integrations/microsoft/mail/send"

            params = {"user_id": user_id}

            # ── AUDIT LOG – before call ───────────────────────────────────────
            logger.info("[AUDIT] Email send → endpoint=%s", endpoint)
            logger.info("[AUDIT] Email send → params=%s", params)
            logger.info("[AUDIT] Email send → to=%s  subject=%s", to_email, subject)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    params=params,
                    timeout=30.0,
                )

            response_status = response.status_code
            response_body_text = response.text

            # ── AUDIT LOG – after call ────────────────────────────────────────
            logger.info("[AUDIT] Email send ← status=%s", response_status)
            logger.info("[AUDIT] Email send ← body=%s", response_body_text[:500])

            if response.is_success:
                result_data = response.json()
                message_id = result_data.get("message_id")

                logger.info("[AUDIT] Email send ✅  message_id=%s  to=%s", message_id, to_email)

                # Record in history ONLY after confirmed success
                self.memory.add_to_history({
                    **action_data,
                    "type": "send_email",
                    "result": result_data,
                    "message_id": message_id,
                })

                # Clear state only on success
                self.memory.clear_pending_action()
                self.memory.clear_active_task()

                # Natural success message
                _to_name = to_email.split("@")[0].capitalize() if to_email and "@" in to_email else (to_email or "them")
                success_msg = f"Done, email sent to {_to_name}."

                return {
                    "message": success_msg,
                    "success": True,
                    "type": "email_sent",
                    "data": {
                        **result_data,
                        "message_id": message_id,
                        "to": to_email,
                        "subject": subject,
                    },
                }

            else:
                # HTTP error – preserve pending_action so user can retry
                error_detail: str = f"HTTP {response_status}"
                try:
                    error_json = response.json()
                    if isinstance(error_json, dict):
                        detail = error_json.get("detail", {})
                        if isinstance(detail, dict):
                            error_detail = detail.get("message", str(detail))
                        else:
                            error_detail = str(detail)
                except Exception:
                    error_detail = response_body_text or f"HTTP {response_status}"

                logger.error("[AUDIT] Email send ❌  status=%s  detail=%s", response_status, error_detail)

                return {
                    "message": (
                        f"❌ Failed to send the email "
                        f"(HTTP {response_status}): {error_detail}\n\n"
                        "Your email details are still saved. "
                        "Please check your email connection and say **yes** to try again."
                    ),
                    "success": False,
                    "type": "error",
                    "error": f"HTTP {response_status}: {error_detail}",
                    "data": {
                        "status_code": response_status,
                        "pending_action_preserved": True,
                    },
                }

        except httpx.TimeoutException as e:
            logger.error("[ORCHESTRATION] ❌ Timeout calling email endpoint: %s", e)
            return {
                "message": (
                    "❌ The email service timed out. "
                    "Your email details are still saved – please say **yes** to try again."
                ),
                "success": False,
                "type": "error",
                "error": f"Timeout: {e}",
                "data": {"pending_action_preserved": True},
            }

        except Exception as e:
            logger.error("[ORCHESTRATION] ❌ Unexpected error executing email send: %s", e, exc_info=True)
            return {
                "message": (
                    f"❌ Unexpected error while sending the email: {e}\n\n"
                    "Your email details are still saved – please say **yes** to try again."
                ),
                "success": False,
                "type": "error",
                "error": str(e),
                "data": {"pending_action_preserved": True},
            }

    async def _handle_send_email(
        self,
        user_message: str,
        extracted_slots: Dict[str, Any],
        user_id: str,
        provider: str
    ) -> Dict[str, Any]:
        """
        ORCHESTRATION: Handle email send with full slot-collection → confirmation → execution workflow.

        Mirrors _handle_calendar_event_creation pattern:
        1. Extract slots (to_email, subject, body, provider)
        2. Check for missing required slots → ask one at a time
        3. Check provider preference
        4. Set pending_action + request confirmation
        5. On confirmation → _execute_email_send
        """
        logger.info("[ORCHESTRATION] Starting email send workflow")

        # STEP 1: Extract email slots (merge with any prior extracted_slots)
        email_slots = SlotExtractor.extract_email_slots(user_message, extracted_slots)
        all_slots = {**extracted_slots, **email_slots}

        logger.info("[ORCHESTRATION] Extracted email slots: %s", list(all_slots.keys()))

        # STEP 2: Check required slots
        required_slots = ["to_email", "subject", "body"]
        missing_slots = [slot for slot in required_slots if not all_slots.get(slot)]

        if missing_slots:
            logger.info("[ORCHESTRATION] Missing email slots: %s", missing_slots)

            self.memory.set_active_task(
                task_type="send_email",
                data=all_slots,
                status="collecting"
            )

            missing_slot = missing_slots[0]
            if missing_slot == "to_email":
                return {
                    "message": "Who should I send it to?",
                    "success": True,
                    "type": "email_slot_request",
                    "data": {"missing_slot": "to_email", "current_slots": all_slots},
                }
            elif missing_slot == "subject":
                if all_slots.get("body"):
                    body_words = (all_slots["body"] or "").split()[:5]
                    all_slots["subject"] = " ".join(body_words).rstrip(".,!?")
                    logger.info("[ORCHESTRATION] Subject inferred from body: '%s'", all_slots["subject"])
                else:
                    return {
                        "message": "What's it about?",
                        "success": True,
                        "type": "email_slot_request",
                        "data": {"missing_slot": "subject", "current_slots": all_slots},
                    }
            elif missing_slot == "body":
                return {
                    "message": "What should the message say?",
                    "success": True,
                    "type": "email_slot_request",
                    "data": {"missing_slot": "body", "current_slots": all_slots},
                }

        # STEP 3: Resolve email provider.
        # Order: (1) explicit message slot  (2) session preferred_provider
        #        (3) API-supplied provider param  (4) MUST ASK — no silent default
        if not all_slots.get("provider"):
            if self.memory.preferred_provider:
                all_slots["provider"] = self.memory.preferred_provider
                logger.info(
                    "[EXEC_PROVIDER_DECISION] Email: pre-filled from session "
                    "preferred_provider='%s'", self.memory.preferred_provider,
                )
            elif provider:
                all_slots["provider"] = provider
                logger.info(
                    "[EXEC_PROVIDER_DECISION] Email: pre-filled from API param '%s'", provider,
                )

        if not all_slots.get("provider"):
            logger.info(
                "[EXEC_PROVIDER_DECISION] Email: provider unknown — "
                "requesting mandatory user clarification"
            )
            self.memory.set_active_task(
                task_type="send_email",
                data=all_slots,
                status="collecting",
            )
            return {
                "message": "Which account would you like to use — Google or Microsoft?",
                "success": True,
                "type": "provider_clarification",
                "data": {"missing_slot": "provider", "current_slots": all_slots},
            }

        logger.info(
            "[EXEC_PROVIDER_DECISION] Email: resolved provider='%s'",
            all_slots.get("provider"),
        )

        # STEP 4: All slots present – request confirmation
        logger.info("[ORCHESTRATION] All email slots collected - requesting confirmation")

        to_display = all_slots["to_email"]
        to_name = to_display.split("@")[0].capitalize() if "@" in to_display else to_display
        subj_display = all_slots.get("subject", "")
        prov_label_e = "Outlook" if _normalize_provider(all_slots.get("provider", "gmail")) == "microsoft" else "Gmail"
        confirmation_msg = f'Send "{subj_display}" to {to_name} via {prov_label_e}. Want me to go ahead?'

        # Set pending action
        self.memory.set_pending_action(
            action_type="send_email",
            data={**all_slots, "user_id": user_id}
        )

        # Set active task state
        self.memory.set_active_task(
            task_type="send_email",
            data=all_slots,
            status="awaiting_confirmation"
        )

        return {
            "message": confirmation_msg,
            "success": True,
            "type": "email_confirmation",
            "data": all_slots,
            "action_needed": "confirmation",
        }
    
    async def _handle_cancellation(self) -> Dict[str, Any]:
        """Handle user cancelling current operation."""
        logger.info("[AGENT] Handling cancellation")
        
        active_task = self.memory.get_active_task()
        pending_action = self.memory.get_pending_action()
        
        self.memory.clear_active_task()
        self.memory.clear_pending_action()
        self.memory.last_question_type = None
        
        if active_task or pending_action:
            return {
                "message": "Cancelled. Anything else?",
                "success": True,
                "type": "cancellation"
            }
        else:
            return {
                "message": "Nothing to cancel. What can I help you with?",
                "success": True,
                "type": "info"
            }
    
    async def _handle_decline_optional(
        self,
        user_id: str,
        calendar_provider: str,
        mail_provider: str,
    ) -> Dict[str, Any]:
        """
        Handle user declining an optional slot.

        Clears the last question type and re-dispatches to the appropriate
        task handler so it can check for remaining required slots or advance
        to confirmation — rather than leaving the workflow in a dead-end.
        """
        logger.info(f"[AGENT] Handling decline of optional: {self.memory.last_question_type}")
        self.memory.last_question_type = None

        active_task = self.memory.get_active_task()
        if not active_task:
            return {
                "message": "Got it! What would you like to do?",
                "success": True,
                "type": "acknowledge",
            }

        task_type    = active_task.get("type", "")
        existing_data = active_task.get("data", {})

        # Re-dispatch with the slots already collected so the handler can
        # evaluate what's still missing or move straight to confirmation.
        if task_type == "calendar_event":
            return await self._handle_calendar_event_creation(
                user_message="", extracted_slots=existing_data,
                user_id=user_id, provider=calendar_provider,
            )
        elif task_type in ("send_email", "draft_email"):
            return await self._handle_send_email(
                user_message="", extracted_slots=existing_data,
                user_id=user_id, provider=mail_provider,
            )
        else:
            return {
                "message": "Got it! Proceeding without that. What else would you like to add?",
                "success": True,
                "type": "acknowledge",
            }
    
    async def _handle_sender_selection(self, extracted_slots: Dict[str, Any]) -> Dict[str, Any]:
        """Handle email sender account selection — lock provider and re-dispatch workflow."""
        provider = extracted_slots.get("provider")
        if not provider:
            return {
                "message": "I didn't catch that. Would you like to use Gmail or Outlook?",
                "success": False,
                "type": "clarification",
            }
        logger.info(
            "[EXEC_PROVIDER_DECISION] Email provider selected by user: '%s' — locking in session",
            provider,
        )
        # Lock provider into session memory so it persists across turns
        self.memory.preferred_provider = _normalize_provider(provider)
        if self.memory.active_task:
            task_data = dict(self.memory.active_task.get("data", {}))
            task_data["provider"] = provider
            self.memory.update_task_data({"provider": provider})
            task_type = self.memory.active_task.get("type", "")
            if task_type in ("send_email", "draft_email"):
                user_id = self.memory.current_user_id or "default_user"
                return await self._handle_send_email("", task_data, user_id, provider)
        return {
            "message": f"Got it — using {_normalize_provider(provider).title()}. What would you like to do?",
            "success": True,
            "type": "acknowledge",
        }

    async def _handle_calendar_provider_selection(self, extracted_slots: Dict[str, Any]) -> Dict[str, Any]:
        """Handle calendar provider selection — lock provider and re-dispatch to creation workflow."""
        provider = extracted_slots.get("provider")
        if not provider:
            return {
                "message": "I didn't catch that. Would you like to use Google Calendar or Outlook Calendar?",
                "success": False,
                "type": "clarification",
            }
        logger.info(
            "[EXEC_PROVIDER_DECISION] Calendar provider selected by user: '%s' — locking in session",
            provider,
        )
        # Lock provider into session memory so it persists across turns
        self.memory.preferred_provider = _normalize_provider(provider)
        if self.memory.active_task:
            task_data = dict(self.memory.active_task.get("data", {}))
            task_data["provider"] = provider
            self.memory.update_task_data({"provider": provider})
            task_type = self.memory.active_task.get("type", "")
            if task_type == "calendar_event":
                user_id = self.memory.current_user_id or "default_user"
                return await self._handle_calendar_event_creation("", task_data, user_id, provider)
        return {
            "message": (
                f"Got it — using {_normalize_provider(provider).title()} Calendar. "
                "Describe the event and I'll set it up."
            ),
            "success": True,
            "type": "acknowledge",
        }
    
    async def _handle_slot_filling(
        self,
        user_message: str,
        extracted_slots: Dict[str, Any],
        user_id: str,
        provider: str
    ) -> Dict[str, Any]:
        """
        Handle filling slots for active task.

        Updates the active task data with newly extracted slots, then
        re-dispatches to the appropriate workflow handler so it can
        check for remaining missing slots or advance to confirmation.
        """
        logger.info("[AGENT] Handling slot filling: %s", list(extracted_slots.keys()))

        active_task = self.memory.get_active_task()
        if not active_task:
            # No active task – treat as general message
            return await self._handle_general_message(user_message, extracted_slots, user_id, provider)

        task_type = active_task.get("type")
        current_data = active_task.get("data", {})

        # Re-extract slots from raw message so we capture more than the
        # intent router may have found (belt-and-suspenders)
        if task_type in ("send_email", "draft_email"):
            fresh_slots = SlotExtractor.extract_email_slots(user_message, current_data)
        elif task_type == "calendar_event":
            fresh_slots = SlotExtractor.extract_calendar_slots(user_message, current_data)
        else:
            fresh_slots = extracted_slots

        # Merge: existing data takes lower priority than freshly extracted slots
        merged = {**current_data, **fresh_slots, **extracted_slots}

        # FIX: SlotExtractor.extract_email_slots never extracts 'body' from free text.
        # When no structured slots were found AND we know which slot is missing,
        # treat the entire user_message as the answer for that missing slot.
        if task_type in ("send_email", "draft_email") and not fresh_slots and not extracted_slots:
            required_email = ["to_email", "subject", "body"]
            missing_email = [s for s in required_email if not merged.get(s)]
            if missing_email:
                target_slot = missing_email[0]  # answer the first missing slot
                merged[target_slot] = user_message
                logger.info(
                    "[AGENT] No structured slot extracted – treating raw message as '%s' value: '%s'",
                    target_slot, user_message[:80],
                )

        logger.info("[AGENT] Slot filling merged data keys: %s", list(merged.keys()))

        # Persist merged slots back to active task
        self.memory.update_task_data(merged)

        # Re-dispatch to the correct orchestration handler so it can check
        # for any remaining missing slots or move to confirmation
        if task_type in ("send_email", "draft_email"):
            return await self._handle_send_email(user_message, merged, user_id, provider)
        elif task_type == "calendar_event":
            return await self._handle_calendar_event_creation(user_message, merged, user_id, provider)
        else:
            return {
                "message": "I've noted that information. What else would you like to add?",
                "success": True,
                "type": "slot_update",
                "data": merged,
            }

    async def _handle_topic_switch(
        self,
        user_message: str,
        user_id: str,
        provider: str
    ) -> Dict[str, Any]:
        """Handle user switching topics during active task."""
        logger.info("[AGENT] Handling topic switch")
        
        active_task = self.memory.get_active_task()
        task_type = active_task.get("type") if active_task else "unknown"
        
        # Ask user if they want to abandon current task
        return {
            "message": f"It looks like you want to switch topics. Would you like to cancel the current {task_type} task and start fresh?",
            "success": True,
            "type": "clarification",
            "action_needed": "confirm_topic_switch",
        }
    
    # ── Draft modification (slot correction) ─────────────────────────────────

    async def _handle_modify_draft(
        self,
        user_message: str,
        extracted_slots: Dict[str, Any],
        user_id: str,
        calendar_provider: str,
        mail_provider: str,
    ) -> Dict[str, Any]:
        """
        Handle user correcting a slot in an active draft.

        Called when:
          - IntentRouter → MODIFY_DRAFT  ("no, use outlook" / "no, call it X")
          - PROVIDE_SLOT_VALUE while task status is awaiting_confirmation
            ("make it 21:00 instead")

        Steps:
          1. Run NLUExtractor on the raw message (bypasses existing-slot guards)
          2. Patch task data with the extracted updates
          3. Clear pending action (fresh one created by re-dispatch)
          4. Reset status → collecting
          5. Re-dispatch to appropriate handler → advances back to confirmation
        """
        logger.info("[AGENT] Handling draft modification: '%s'", user_message)

        active_task = self.memory.get_active_task()
        if not active_task:
            return await self._handle_general_message(
                user_message, extracted_slots, user_id, mail_provider, calendar_provider
            )

        task_type   = active_task.get("type")
        current_data = active_task.get("data", {})

        # Run NLU — no existing-slot guards, so corrections always apply
        from services.nlu_service import NLUExtractor
        nlu = await NLUExtractor.extract(
            message=user_message,
            task_type=task_type,
            current_slots=current_data,
            chat_service=self.chat_service,
        )

        logger.info(
            "[AGENT] NLU result: intent=%s updates=%s confidence=%.2f",
            nlu.intent, list(nlu.updates.keys()), nlu.confidence,
        )

        # Honour unexpected cancel / confirm signals from NLU
        if nlu.intent == "cancel":
            return await self._handle_cancellation()
        if nlu.intent == "confirm":
            return await self._handle_confirmation(user_id, calendar_provider)

        updates = nlu.updates or {}

        # Normalize provider if it was extracted
        if "provider" in updates:
            updates["provider"] = _normalize_provider(updates["provider"])

        # If NLU found nothing, detect general edit intent and ask what to change
        if not updates:
            logger.warning("[AGENT] _handle_modify_draft: NLU found no updates for: '%s'", user_message)

            # ── Group 10: edit-intent detection ──────────────────────────────
            # "No, I would like you to edit this event" → transition to collecting,
            # ask user what specifically to change.  Prevent repeating the same
            # clarification twice in a row to avoid infinite loops.
            _EDIT_RE = re.compile(
                r"\b(edit|modify|update|adjust|fix|change\s*it|change\s*this|"
                r"i\s+want\s+to|i\s+would\s+like\s+to|i\s*'d\s+like\s+to|"
                r"please\s+edit|please\s+change|please\s+modify)\b",
                re.IGNORECASE,
            )
            if _EDIT_RE.search(user_message):
                self.memory.clear_pending_action()
                self.memory.update_task_status("collecting")
                ask_msg = "What would you like to change? (e.g. title, time, date, or calendar provider)"
                if self.memory.last_clarification_message == ask_msg:
                    # Already asked exactly this — give detailed examples to break the loop
                    ask_msg = (
                        "I'm ready to update the event. Please tell me specifically:\n"
                        "- **Title**: say `call it <new title>`\n"
                        "- **Time**: say `change time to 14:00`\n"
                        "- **Date**: say `make it tomorrow`\n"
                        "- **Calendar**: say `use Google` or `use Outlook`"
                    )
                self.memory.last_clarification_message = ask_msg
                logger.info("[AGENT] Edit intent detected — asking what to change")
                return {"message": ask_msg, "success": True, "type": "edit_prompt"}

            # No edit intent either — ask to rephrase
            self.memory.last_clarification_message = None
            return {
                "message": (
                    "I'm not sure what you'd like to change. Could you rephrase?\n\n"
                    "Examples:\n"
                    "- `call it 'Sprint Review'`\n"
                    "- `use outlook`\n"
                    "- `at 14:00`\n"
                    "- `make it tomorrow`"
                ),
                "success": True,
                "type": "clarification",
            }

        # Real updates found — reset clarification loop tracker
        self.memory.last_clarification_message = None

        # Patch task data
        merged = {**current_data, **updates}
        logger.info("[AGENT] Patching task '%s' with %s", task_type, updates)

        self.memory.update_task_data(merged)
        self.memory.clear_pending_action()          # fresh pending_action from re-dispatch
        self.memory.update_task_status("collecting")  # allow re-dispatch to reach confirmation

        # Re-dispatch with an EMPTY message so the slot extractor cannot
        # accidentally parse anything from the correction phrase (e.g. "no, use
        # outlook") as a new slot. All needed data is already in `merged`.
        if task_type in ("send_email", "draft_email"):
            return await self._handle_send_email("", merged, user_id, mail_provider)
        elif task_type == "calendar_event":
            return await self._handle_calendar_event_creation(
                "", merged, user_id, calendar_provider
            )
        else:
            return {
                "message": "✅ Updated! Ready to proceed?",
                "success": True,
                "type": "draft_updated",
                "data": merged,
            }

    def _check_provider_connected(self, user_id: str, provider: str) -> bool:
        """
        Synchronous check: does this user have stored tokens for the given provider?
        Fast file read — no HTTP call.
        """
        try:
            from utils.token_storage import TokenStorage
            ts = TokenStorage()
            tokens = ts.load_tokens(user_id, provider)
            return bool(tokens and tokens.get("access_token"))
        except Exception as exc:
            logger.warning("[AGENT] Provider connection check failed (%s): %s", provider, exc)
            return False

    # ── Calendar event creation flow ──────────────────────────────────────────

    async def _handle_calendar_event_creation(
        self,
        user_message: str,
        extracted_slots: Dict[str, Any],
        user_id: str,
        provider: str
    ) -> Dict[str, Any]:
        """
        ORCHESTRATION: Handle calendar event creation with full workflow.
        
        Workflow:
        1. Extract slots (title, date, time, provider)
        2. Check for missing required slots
        3. Ask for missing slots OR
        4. Set pending_action and request confirmation
        5. On confirmation -> execute integration endpoint
        """
        logger.info("[ORCHESTRATION] Starting calendar event creation workflow")
        
        # STEP 1: Extract slots from user message
        calendar_slots = SlotExtractor.extract_calendar_slots(user_message, extracted_slots)
        
        # Merge with any existing extracted slots
        all_slots = {**extracted_slots, **calendar_slots}
        
        logger.info(f"[ORCHESTRATION] Extracted slots: {list(all_slots.keys())}")
        
        # STEP 2: Check required slots
        required_slots = ["title", "date", "time"]
        missing_slots = [slot for slot in required_slots if not all_slots.get(slot)]
        
        # SECTION 3 FIX: NEVER default title to "Meeting" silently.
        # If no title was extracted, ask the user explicitly.
        if "title" in missing_slots:
            self.memory.set_active_task(task_type="calendar_event", data=all_slots, status="collecting")
            self.memory.last_question_type = "title"
            logger.info("[EXEC_EVENT_TITLE_EXTRACTED] No title extracted — asking user for title")
            return {
                "message": "What should I call this event?",
                "success": True,
                "type": "calendar_slot_request",
                "data": {"missing_slot": "title", "current_slots": all_slots},
            }

        # ── Group 9: Suspicious STT title — ask user to confirm before proceeding ──
        if all_slots.get("title_needs_confirmation") and not all_slots.get("title_confirmed"):
            current_title = all_slots.get("title", "Meeting")
            self.memory.set_active_task(task_type="calendar_event", data=all_slots, status="collecting")
            self.memory.last_question_type = "title_confirm"
            logger.warning("[AGENT] Suspicious STT title '%s' — asking user to confirm", current_title)
            return {
                "message": (
                    f"I heard the event title as **\"{current_title}\"**, but that might not be right.\n\n"
                    "Please say the title again clearly, or reply **yes** if it's correct."
                ),
                "success": True,
                "type": "calendar_slot_request",
                "data": {"missing_slot": "title_confirm", "current_slots": all_slots},
            }

        # Default date to today if not provided
        if "date" in missing_slots:
            all_slots["date"] = get_current_date_str()
            missing_slots.remove("date")
            logger.info(f"[ORCHESTRATION] Using default date: {all_slots['date']}")
        
        # STEP 3: If missing critical slots, ask for them
        if missing_slots:
            logger.info(f"[ORCHESTRATION] Missing slots: {missing_slots}")
            
            # Create active task to track state
            self.memory.set_active_task(
                task_type="calendar_event",
                data=all_slots,
                status="collecting"
            )
            
            # Ask for first missing slot
            missing_slot = missing_slots[0]
            if missing_slot == "time":
                # Special case: the user gave a partial/ambiguous time like "11 m" or "11 p".
                # Ask for clarification instead of a generic "What time?" question.
                if all_slots.get("time_ambiguous"):
                    hint = all_slots.get(
                        "time_ambiguity_hint",
                        "Could you clarify the time? Did you mean AM or PM?"
                    )
                    return {
                        "message": hint,
                        "success": True,
                        "type": "calendar_slot_request",
                        "data": {"missing_slot": "time", "current_slots": all_slots}
                    }
                date_label_q = _format_date_natural(all_slots.get("date", ""))
                return {
                    "message": f"What time on {date_label_q}?",
                    "success": True,
                    "type": "calendar_slot_request",
                    "data": {"missing_slot": "time", "current_slots": all_slots}
                }
            else:
                return {
                    "message": "What should I call it?",
                    "success": True,
                    "type": "calendar_slot_request",
                    "data": {"missing_slot": missing_slot, "current_slots": all_slots}
                }
        
        # STEP 4: Check provider preference
        # Order: explicit slot > session memory (preferred_provider) > API param
        if not all_slots.get("provider"):
            if self.memory.preferred_provider:
                # Reuse the provider the user chose last time in this session
                all_slots["provider"] = self.memory.preferred_provider
                logger.info(
                    "[ORCHESTRATION] Provider pre-filled from session preference: '%s'",
                    self.memory.preferred_provider,
                )
            elif provider:
                all_slots["provider"] = provider
                logger.info(
                    "[ORCHESTRATION] Provider pre-filled from API parameter: '%s'", provider
                )

        if not all_slots.get("provider"):
            # Provider is not known — MUST ask the user (no silent default allowed)
            logger.info(
                "[EXEC_PROVIDER_DECISION] Calendar: provider unknown — "
                "requesting mandatory user clarification"
            )
            self.memory.set_active_task(
                task_type="calendar_event",
                data=all_slots,
                status="collecting",
            )
            return {
                "message": "Which account would you like to use — Google or Microsoft?",
                "success": True,
                "type": "provider_clarification",
                "data": {"missing_slot": "provider", "current_slots": all_slots},
            }

        logger.info(
            "[EXEC_PROVIDER_DECISION] Calendar: resolved provider='%s'",
            all_slots.get("provider"),
        )
        # Log finalized event title for integrity tracking
        logger.info(
            "[EXEC_EVENT_TITLE_EXTRACTED] Locked title='%s' for user=%s",
            all_slots.get("title", "(none)"), user_id,
        )

        # STEP 5: All slots present — pre-check provider connection, then request confirmation
        logger.info("[ORCHESTRATION] All slots collected - pre-checking provider connection")

        selected_provider = _normalize_provider(all_slots.get("provider", "google"))
        if not self._check_provider_connected(user_id, selected_provider):
            provider_label = "Microsoft / Outlook" if selected_provider == "microsoft" else "Google"
            # Keep the draft alive so user can retry after connecting
            self.memory.set_active_task(
                task_type="calendar_event",
                data=all_slots,
                status="collecting",
            )
            return {
                "message": (
                    f"Your {provider_label} account isn't connected yet. "
                    "You can link it in the Integrations page."
                ),
                "success": False,
                "type": "provider_not_connected",
                "data": {**all_slots},
            }

        logger.info("[ORCHESTRATION] Provider '%s' connected — requesting confirmation", selected_provider)

        # Apply default 60-minute duration when neither explicit end_time nor duration given
        if not all_slots.get("end_time") and not all_slots.get("duration"):
            all_slots["duration"] = 60
            logger.info("[ORCHESTRATION] Default duration applied: 60 minutes")

        # Build natural confirmation — no markdown, no emojis
        date_label_c = _format_date_natural(all_slots.get("date", ""))
        time_label_c = _format_time_natural(all_slots.get("time") or all_slots.get("start_time", ""))
        dur_val = all_slots.get("duration", 60)
        try:
            dur_val = int(dur_val)
        except Exception:
            dur_val = 60
        provider_label_c = "Outlook Calendar" if selected_provider == "microsoft" else "Google Calendar"

        if all_slots.get("end_time"):
            end_label_c = _format_time_natural(all_slots["end_time"])
            time_range_c = f"{time_label_c} to {end_label_c}"
        else:
            time_range_c = f"{time_label_c} for {_format_duration_natural(dur_val)}"

        title_c = all_slots["title"]
        confirmation_msg = f"Got it — {title_c} on {date_label_c} at {time_range_c} on {provider_label_c}. Shall I create it?"
        
        # Set pending action
        self.memory.set_pending_action(
            action_type="create_calendar_event",
            data={
                **all_slots,
                "user_id": user_id
            }
        )
        
        # Set agent state to WAITING_CONFIRMATION
        self.memory.set_active_task(
            task_type="calendar_event",
            data=all_slots,
            status="awaiting_confirmation"
        )
        
        return {
            "message": confirmation_msg,
            "success": True,
            "type": "calendar_confirmation",
            "data": all_slots,
            "action_needed": "confirmation"
        }


    async def _handle_calendar_list_events(
        self,
        user_id: str,
        provider: str,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        List calendar events via the integration endpoint.

        Calls:
          Google:  GET /api/integrations/google/calendar/events
          Outlook: GET /api/integrations/microsoft/calendar/events

        Parses "tomorrow" / "today" from user_message to set time_min/time_max.
        Returns events formatted as a readable list.
        """
        import httpx

        logger.info("[ORCHESTRATION] Starting calendar list events workflow")

        # ── Mandatory provider guard ──────────────────────────────────────────
        if not provider and not self.memory.preferred_provider:
            logger.info("[EXEC_PROVIDER_DECISION] Calendar list: provider unknown — asking user")
            return {
                "message": "Which account would you like to use — Google or Microsoft?",
                "success": True,
                "type": "provider_clarification",
                "data": {"missing_slot": "provider"},
            }
        resolved_list_provider = provider or self.memory.preferred_provider

        normalized_provider = _normalize_provider(resolved_list_provider)
        logger.info("[EXEC_PROVIDER_DECISION] Calendar list: resolved provider='%s'", normalized_provider)
        message_lower = user_message.lower()

        # ── Date range from message ───────────────────────────────────────────
        now = datetime.now()
        date_desc = "upcoming"
        time_min: Optional[str] = None
        time_max: Optional[str] = None

        if "tomorrow" in message_lower:
            target = now + timedelta(days=1)
            date_desc = "tomorrow"
        elif "today" in message_lower:
            target = now
            date_desc = "today"
        else:
            target = None

        if target is not None:
            time_min = target.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
            time_max = target.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + "Z"
        else:
            time_min = now.isoformat() + "Z"

        # ── Call integration endpoint ─────────────────────────────────────────
        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/integrations/{normalized_provider}/calendar/events"
        params: Dict[str, Any] = {"user_id": user_id, "max_results": 15}
        if time_min:
            params["time_min"] = time_min

        logger.info("[AUDIT] Calendar list → endpoint=%s params=%s", endpoint, params)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=params, timeout=30.0)

            logger.info("[AUDIT] Calendar list ← status=%s body=%s",
                        response.status_code, response.text[:300])

            if not response.is_success:
                error_detail = response.text[:300]
                return {
                    "message": (
                        f"❌ Failed to fetch calendar events "
                        f"(HTTP {response.status_code}): {error_detail}\n\n"
                        "Please ensure your Google/Outlook account is connected."
                    ),
                    "success": False,
                    "type": "error",
                    "error": f"HTTP {response.status_code}: {error_detail}",
                }

            data = response.json()
            events = data.get("events", [])
            total = data.get("total", len(events))

            # ── Filter to time_max if set (Google API ignores timeMax in list) ─
            if time_max:
                time_max_dt = datetime.fromisoformat(time_max.replace("Z", "+00:00"))
                filtered = []
                for evt in events:
                    start_str = evt.get("start", "")
                    if start_str:
                        try:
                            start_dt = datetime.fromisoformat(
                                start_str.replace("Z", "+00:00")
                            )
                            if start_dt <= time_max_dt:
                                filtered.append(evt)
                        except Exception:
                            filtered.append(evt)
                    else:
                        filtered.append(evt)
                events = filtered
                total = len(events)

            if not events:
                return {
                    "message": (
                        f"📅 No events found for **{date_desc}** in your "
                        f"{normalized_provider.title()} Calendar."
                    ),
                    "success": True,
                    "type": "calendar_list",
                    "data": {"events": [], "total": 0},
                }

            # ── Format readable list ──────────────────────────────────────────
            lines = []
            for evt in events:
                summary = evt.get("summary", "Untitled")
                start_str = evt.get("start", "")
                end_str = evt.get("end", "")
                try:
                    start_dt = datetime.fromisoformat(
                        start_str.replace("Z", "+00:00")
                    )
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    time_label = f"{start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')}"
                except Exception:
                    time_label = start_str

                loc = evt.get("location")
                line = f"  - **{summary}** | {time_label}"
                if loc:
                    line += f" @ {loc}"
                lines.append(line)

            msg = (
                f"📅 **Your {date_desc} calendar events** "
                f"({total} event{'s' if total != 1 else ''}):\n\n"
                + "\n".join(lines)
            )

            return {
                "message": msg,
                "success": True,
                "type": "calendar_list",
                "data": {"events": events, "total": total},
            }

        except httpx.TimeoutException:
            logger.error("[ORCHESTRATION] Timeout fetching calendar events")
            return {
                "message": "❌ The calendar service timed out. Please try again.",
                "success": False,
                "type": "error",
                "error": "Timeout",
            }
        except Exception as e:
            logger.error("[ORCHESTRATION] Error fetching calendar events: %s", e, exc_info=True)
            return {
                "message": f"❌ Error fetching calendar events: {e}",
                "success": False,
                "type": "error",
                "error": str(e),
            }


    # ── Email READ handler ────────────────────────────────────────────────────

    async def _handle_email_read(
        self,
        user_message: str,
        user_id: str,
        provider: str,
    ) -> Dict[str, Any]:
        """
        Read and summarize emails from Gmail or Outlook.

        Flow:
        1. Extract read-email slots (count, unread_only, sender_filter, date range)
        2. Verify provider connection
        3. Call correct read endpoint
        4. Format structured response

        Never fabricates emails — returns real data from the API only.
        """
        import httpx

        logger.info("[ORCHESTRATION] Starting email read workflow")

        normalized_provider = _normalize_provider(provider)

        # STEP 1: Extract slots
        from utils.slot_extraction import SlotExtractor
        slots = SlotExtractor.extract_email_read_slots(user_message)

        count = slots.get("count", 5)
        unread_only = slots.get("unread_only", False)
        sender_filter = slots.get("sender_filter")
        start_date = slots.get("start_date")
        end_date = slots.get("end_date")
        date_filter = slots.get("date_filter")

        # STEP 2: Verify provider connection
        if not self._check_provider_connected(user_id, normalized_provider):
            provider_label = "Microsoft / Outlook" if normalized_provider == "microsoft" else "Google"
            return {
                "message": (
                    f"⚠️ Your **{provider_label}** account is not connected.\n\n"
                    "Would you like to connect it? Go to the **Integrations** page to set it up."
                ),
                "success": False,
                "type": "provider_not_connected",
                "data": {"provider": normalized_provider},
            }

        # STEP 3: Call read endpoint
        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        if normalized_provider == "google":
            endpoint = f"{base_url}/api/integrations/google/gmail/messages"
        else:
            endpoint = f"{base_url}/api/integrations/microsoft/mail/messages"

        params: Dict[str, Any] = {
            "user_id": user_id,
            "max_results": count,
            "unread_only": unread_only,
        }
        if sender_filter:
            params["sender"] = sender_filter
        if start_date:
            params["date_after"] = start_date
        if end_date:
            params["date_before"] = end_date

        logger.info("[AUDIT] Email read → endpoint=%s params=%s", endpoint, params)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=params, timeout=30.0)

            logger.info(
                "[AUDIT] Email read ← status=%s body_preview=%s",
                response.status_code, response.text[:200],
            )

            if not response.is_success:
                error_body = response.text[:300]
                # Handle auth failure gracefully
                if response.status_code in (401, 403):
                    provider_label = "Microsoft / Outlook" if normalized_provider == "microsoft" else "Google"
                    return {
                        "message": (
                            f"⚠️ Your **{provider_label}** account is not connected or the token has expired.\n\n"
                            "Please reconnect it via the **Integrations** page."
                        ),
                        "success": False,
                        "type": "provider_not_connected",
                        "data": {"provider": normalized_provider},
                    }
                return {
                    "message": f"❌ Failed to read emails (HTTP {response.status_code}): {error_body}",
                    "success": False,
                    "type": "error",
                    "error": f"HTTP {response.status_code}",
                }

            data = response.json()
            emails = data.get("emails", [])
            total = data.get("total", len(emails))

            # STEP 4: Format response
            if not emails:
                qualifier = "unread " if unread_only else ""
                date_label = f" for **{date_filter}**" if date_filter else ""
                sender_label = f" from **{sender_filter}**" if sender_filter else ""
                return {
                    "message": (
                        f"📭 You have no {qualifier}emails{sender_label}{date_label}."
                    ),
                    "success": True,
                    "type": "email_list",
                    "data": {"emails": [], "total": 0},
                }

            # Build structured summary
            lines = [f"📩 Here are your last **{len(emails)}** email{'s' if len(emails) != 1 else ''}:\n"]
            for idx, email in enumerate(emails, 1):
                from_raw = email.get("from", "Unknown")
                subject = email.get("subject", "(No Subject)")
                received = email.get("received", "")
                preview = email.get("preview", "")
                unread_flag = " 🔵" if email.get("unread") else ""

                # Try to format received time nicely
                received_label = received
                try:
                    from email.utils import parsedate_to_datetime as _pdt
                    dt = _pdt(received)
                    now = datetime.now()
                    if dt.date() == now.date():
                        received_label = f"Today at {dt.strftime('%H:%M')}"
                    elif dt.date() == (now - timedelta(days=1)).date():
                        received_label = f"Yesterday at {dt.strftime('%H:%M')}"
                    else:
                        received_label = dt.strftime("%b %d at %H:%M")
                except Exception:
                    # Non-RFC 2822 format (e.g. ISO from Outlook)
                    try:
                        dt = datetime.fromisoformat(received.replace("Z", "+00:00"))
                        now = datetime.now()
                        if dt.date() == now.date():
                            received_label = f"Today at {dt.strftime('%H:%M')}"
                        else:
                            received_label = dt.strftime("%b %d at %H:%M")
                    except Exception:
                        received_label = received[:20] if received else "Unknown time"

                lines.append(
                    f"**{idx}.{unread_flag} From:** {from_raw}\n"
                    f"   **Subject:** {subject}\n"
                    f"   **Received:** {received_label}\n"
                    f"   **Preview:** _{preview[:120]}{'…' if len(preview) > 120 else ''}_\n"
                )

            return {
                "message": "\n".join(lines),
                "success": True,
                "type": "email_list",
                "data": {"emails": emails, "total": total},
            }

        except httpx.TimeoutException:
            return {
                "message": "❌ The email service timed out. Please try again.",
                "success": False,
                "type": "error",
                "error": "Timeout",
            }
        except Exception as e:
            logger.error("[ORCHESTRATION] Error reading emails: %s", e, exc_info=True)
            return {
                "message": f"❌ Error reading emails: {e}",
                "success": False,
                "type": "error",
                "error": str(e),
            }

    # ── Calendar READ handler ─────────────────────────────────────────────────

    async def _handle_calendar_read(
        self,
        user_message: str,
        user_id: str,
        provider: str,
    ) -> Dict[str, Any]:
        """
        Read and summarize calendar events with rich date-range support.

        Handles:
        - Single day (today, tomorrow, yesterday, specific date, next Friday)
        - Date ranges (this week, next week, last week)
        - Next-event query ("when is my next meeting?")
        - Time filter ("do I have anything at 3pm?")

        Never fabricates events — returns real data from the API only.
        """
        import httpx

        logger.info("[ORCHESTRATION] Starting calendar read workflow")

        # ── Mandatory provider guard ──────────────────────────────────────────
        if not provider and not self.memory.preferred_provider:
            logger.info("[EXEC_PROVIDER_DECISION] Calendar read: provider unknown — asking user")
            return {
                "message": "Which account would you like to use — Google or Microsoft?",
                "success": True,
                "type": "provider_clarification",
                "data": {"missing_slot": "provider"},
            }
        resolved_read_provider = provider or self.memory.preferred_provider

        normalized_provider = _normalize_provider(resolved_read_provider)
        logger.info("[EXEC_PROVIDER_DECISION] Calendar read: resolved provider='%s'", normalized_provider)

        # STEP 1: Extract slots
        from utils.slot_extraction import SlotExtractor
        slots = SlotExtractor.extract_calendar_read_slots(user_message)

        next_event = slots.get("next_event", False)
        start_date = slots.get("start_date")
        end_date = slots.get("end_date")
        date_label = slots.get("date_label", "today")
        time_filter = slots.get("time_filter")

        # STEP 2: Verify provider connection
        if not self._check_provider_connected(user_id, normalized_provider):
            provider_label = "Microsoft / Outlook" if normalized_provider == "microsoft" else "Google"
            return {
                "message": (
                    f"⚠️ Your **{provider_label}** account is not connected.\n\n"
                    "Would you like to connect it? Go to the **Integrations** page to set it up."
                ),
                "success": False,
                "type": "provider_not_connected",
                "data": {"provider": normalized_provider},
            }

        # STEP 3: Call calendar events endpoint
        now = datetime.now()
        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/integrations/{normalized_provider}/calendar/events"

        # For "next event" we fetch 1 future event
        if next_event:
            time_min = now.isoformat() + "Z"
            max_results = 1
        else:
            # Build time_min from start_date or default to now
            if start_date:
                time_min = f"{start_date}T00:00:00Z"
            else:
                time_min = now.isoformat() + "Z"
            max_results = 20

        params: Dict[str, Any] = {
            "user_id": user_id,
            "max_results": max_results,
            "time_min": time_min,
        }

        logger.info("[AUDIT] Calendar read → endpoint=%s params=%s", endpoint, params)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=params, timeout=30.0)

            logger.info(
                "[AUDIT] Calendar read ← status=%s body_preview=%s",
                response.status_code, response.text[:200],
            )

            if not response.is_success:
                error_body = response.text[:300]
                if response.status_code in (401, 403):
                    provider_label = "Microsoft / Outlook" if normalized_provider == "microsoft" else "Google"
                    return {
                        "message": (
                            f"⚠️ Your **{provider_label}** account is not connected or the token has expired.\n\n"
                            "Please reconnect it via the **Integrations** page."
                        ),
                        "success": False,
                        "type": "provider_not_connected",
                        "data": {"provider": normalized_provider},
                    }
                return {
                    "message": f"❌ Failed to read calendar (HTTP {response.status_code}): {error_body}",
                    "success": False,
                    "type": "error",
                    "error": f"HTTP {response.status_code}",
                }

            data = response.json()
            events = data.get("events", [])

            # ── Filter to end_date if set ─────────────────────────────────────
            if end_date and not next_event:
                end_dt_boundary = datetime.fromisoformat(f"{end_date}T23:59:59")
                filtered = []
                for evt in events:
                    start_str = evt.get("start", "")
                    try:
                        evt_start = datetime.fromisoformat(
                            start_str.replace("Z", "+00:00").replace("+00:00", "")
                        )
                        if evt_start <= end_dt_boundary:
                            filtered.append(evt)
                    except Exception:
                        filtered.append(evt)
                events = filtered

            # ── Additional time filter ────────────────────────────────────────
            if time_filter and events:
                target_hour, target_min = map(int, time_filter.split(":"))
                matched = []
                for evt in events:
                    start_str = evt.get("start", "")
                    try:
                        evt_start = datetime.fromisoformat(
                            start_str.replace("Z", "+00:00").replace("+00:00", "")
                        )
                        if evt_start.hour == target_hour:
                            matched.append(evt)
                    except Exception:
                        pass
                events = matched if matched else events

            total = len(events)

            # STEP 4: Format response
            if not events:
                if next_event:
                    return {
                        "message": "📅 You have no upcoming events scheduled.",
                        "success": True,
                        "type": "calendar_list",
                        "data": {"events": [], "total": 0},
                    }
                return {
                    "message": f"📅 You have no events scheduled for **{date_label}**.",
                    "success": True,
                    "type": "calendar_list",
                    "data": {"events": [], "total": 0},
                }

            if next_event:
                evt = events[0]
                summary = evt.get("summary", "Untitled")
                start_str = evt.get("start", "")
                end_str = evt.get("end", "")
                location = evt.get("location")
                try:
                    start_dt = datetime.fromisoformat(
                        start_str.replace("Z", "+00:00").replace("+00:00", "")
                    )
                    end_dt = datetime.fromisoformat(
                        end_str.replace("Z", "+00:00").replace("+00:00", "")
                    )
                    duration_min = int((end_dt - start_dt).total_seconds() / 60)
                    time_label = (
                        f"{start_dt.strftime('%A, %B %d')} at "
                        f"{start_dt.strftime('%H:%M')} "
                        f"({duration_min} min)"
                    )
                except Exception:
                    time_label = start_str

                msg = f"📅 Your next meeting is **{summary}**\n- 🕐 {time_label}"
                if location:
                    msg += f"\n- 📍 {location}"
                return {
                    "message": msg,
                    "success": True,
                    "type": "calendar_list",
                    "data": {"events": events, "total": total},
                }

            # Multiple events
            lines = [
                f"📅 **You have {total} event{'s' if total != 1 else ''}"
                f" for {date_label}:**\n"
            ]
            for evt in events:
                summary = evt.get("summary", "Untitled")
                start_str = evt.get("start", "")
                end_str = evt.get("end", "")
                location = evt.get("location")
                try:
                    start_dt = datetime.fromisoformat(
                        start_str.replace("Z", "+00:00").replace("+00:00", "")
                    )
                    end_dt = datetime.fromisoformat(
                        end_str.replace("Z", "+00:00").replace("+00:00", "")
                    )
                    duration_min = int((end_dt - start_dt).total_seconds() / 60)
                    time_label = (
                        f"{start_dt.strftime('%H:%M')} "
                        f"({duration_min} min)"
                    )
                except Exception:
                    time_label = start_str

                line = f"  • **{summary}** — {time_label}"
                if location:
                    line += f" — 📍 {location}"
                lines.append(line)

            return {
                "message": "\n".join(lines),
                "success": True,
                "type": "calendar_list",
                "data": {"events": events, "total": total},
            }

        except httpx.TimeoutException:
            return {
                "message": "❌ The calendar service timed out. Please try again.",
                "success": False,
                "type": "error",
                "error": "Timeout",
            }
        except Exception as e:
            logger.error("[ORCHESTRATION] Error reading calendar: %s", e, exc_info=True)
            return {
                "message": f"❌ Error reading calendar: {e}",
                "success": False,
                "type": "error",
                "error": str(e),
            }


# ==============================================================================
# NATURAL LANGUAGE FORMATTING HELPERS
# ==============================================================================

def _format_date_natural(date_str: str) -> str:
    """Format a YYYY-MM-DD date string into natural language."""
    try:
        today = datetime.now().date()
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        if d == today:
            return "today"
        if d == today + timedelta(days=1):
            return "tomorrow"
        if d == today - timedelta(days=1):
            return "yesterday"
        days_ahead = (d - today).days
        if 2 <= days_ahead <= 6:
            return d.strftime("%A")  # e.g. "Thursday"
        return d.strftime("%A, %B %d")  # e.g. "Thursday, March 12"
    except Exception:
        return date_str


def _format_time_natural(time_str: str) -> str:
    """Format HH:MM (24-hour) into natural language e.g. '10am', '2:30pm'."""
    try:
        parts = time_str.split(":")
        hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        suffix = "am" if hour < 12 else "pm"
        h12 = hour % 12 or 12
        if minute == 0:
            return f"{h12}{suffix}"
        return f"{h12}:{minute:02d}{suffix}"
    except Exception:
        return time_str


def _format_duration_natural(minutes: int) -> str:
    """Format a duration in minutes into natural language."""
    if minutes == 30:
        return "30 minutes"
    if minutes == 60:
        return "an hour"
    if minutes == 90:
        return "an hour and a half"
    if minutes % 60 == 0:
        h = minutes // 60
        return f"{h} hours"
    h = minutes // 60
    m = minutes % 60
    if h > 0:
        return f"{h} hour{'s' if h > 1 else ''} {m} minutes"
    return f"{minutes} minutes"


# ==============================================================================
# NEW HANDLER METHODS — injected into ExecutiveAgent
# ==============================================================================

async def _handle_email_reply(self, user_message: str, user_id: str, provider: str) -> Dict[str, Any]:
    """Handle EMAIL_REPLY — reply to the last email in context."""
    logger.info("[AGENT] Handling email reply intent")

    sender = self.memory.last_email_sender
    sender_address = self.memory.last_email_sender_address
    thread_id = self.memory.last_email_thread_id
    subject = self.memory.last_email_subject

    if not sender and not sender_address:
        m = re.search(r"reply\s+to\s+(\w+)(?:'s|s)?\s+(?:last\s+)?email", user_message, re.IGNORECASE)
        if m:
            sender = m.group(1)

    if not sender and not sender_address:
        return {
            "message": "Who should I reply to? I don't have a recent email in context.",
            "success": False,
            "type": "email_slot_request",
            "data": {"missing_slot": "sender"},
        }

    body_m = re.search(r"(?:say|tell\s+(?:them|him|her)|and\s+say)\s+(.+)$", user_message, re.IGNORECASE)
    body = body_m.group(1).strip() if body_m else user_message

    recipient = sender_address or sender
    reply_subject = f"Re: {subject}" if subject else "Re: your email"

    slots = {
        "to_email": recipient,
        "subject": reply_subject,
        "body": body,
        "provider": _normalize_provider(provider),
    }
    if thread_id:
        slots["thread_id"] = thread_id

    return await self._handle_send_email(user_message="", extracted_slots=slots, user_id=user_id, provider=provider)


async def _handle_email_forward(self, user_message: str, user_id: str, provider: str) -> Dict[str, Any]:
    """Handle EMAIL_FORWARD — note that full forwarding is not yet implemented."""
    logger.info("[AGENT] Handling email forward intent")
    return {
        "message": (
            "Forwarding emails isn't wired up yet. "
            "You can do it directly from your email client for now."
        ),
        "success": False,
        "type": "not_supported",
        "data": {"feature": "email_forward"},
    }


async def _handle_calendar_update(self, user_message: str, user_id: str, provider: str) -> Dict[str, Any]:
    """
    Handle CALENDAR_UPDATE — full search → select → confirm → PATCH workflow.

    Multi-turn flow:
    Phase 1 (new intent, no active update task):
      Extract update params from message → search calendar → present matches
    Phase 2 (active calendar_update task, status=collecting, has matched_events):
      User selects which event → confirm changes
    Phase 3 (active calendar_update task, status=awaiting_confirmation):
      Execute PATCH
    """
    import httpx

    logger.info("[CAL_UPDATE] _handle_calendar_update provider=%r message='%s'", provider, user_message[:80])

    # Resolve provider — session preference > API param > must ask
    resolved_provider = provider or self.memory.preferred_provider
    if not resolved_provider:
        self.memory.set_active_task(
            task_type="calendar_update",
            data={"pending_message": user_message},
            status="collecting",
        )
        logger.info("[EXEC_PROVIDER_DECISION] Calendar update: provider unknown — asking user")
        return {
            "message": "Which account would you like to use — Google or Microsoft?",
            "success": True,
            "type": "provider_clarification",
            "data": {"missing_slot": "provider"},
        }

    normalized_provider = _normalize_provider(resolved_provider)
    logger.info("[EXEC_PROVIDER_DECISION] Calendar update: resolved provider='%s'", normalized_provider)

    # Phase 2 check: active calendar_update task with matched_events list
    active_task = self.memory.get_active_task()
    if (active_task and active_task.get("type") == "calendar_update"
            and active_task.get("data", {}).get("matched_events")
            and active_task.get("status") == "collecting"):
        # User is selecting from the event list
        task_data = active_task.get("data", {})
        matched = task_data.get("matched_events", [])
        selected = _parse_event_selection(user_message, matched)
        if selected is None:
            return {
                "message": (
                    f"Please select an event by number (1–{len(matched)}), "
                    "or say 'cancel' to start over."
                ),
                "success": True,
                "type": "calendar_update_select",
                "data": {"matched_events": matched},
            }
        # Got a selection — advance to confirmation
        task_data["selected_event"] = selected
        task_data.pop("matched_events", None)
        self.memory.update_task_data(task_data)
        return _build_update_confirmation(self, selected, task_data, normalized_provider)

    # Phase 1: Fresh intent — extract update params and search calendar
    from utils.slot_extraction import SlotExtractor
    update_slots = SlotExtractor.extract_calendar_update_slots(user_message)

    search_query  = update_slots.get("search_query", "")
    search_date   = update_slots.get("search_date")
    search_time   = update_slots.get("search_time")
    new_time      = update_slots.get("new_time")
    new_title     = update_slots.get("new_title")
    new_location  = update_slots.get("new_location")

    logger.info(
        "[CAL_UPDATE] Parsed: query=%r date=%r time=%r new_time=%r new_title=%r new_loc=%r",
        search_query, search_date, search_time, new_time, new_title, new_location,
    )

    # If nothing extractable at all, prompt the user
    if not search_query and not search_time and not new_time and not new_title and not new_location:
        return {
            "message": (
                "What would you like to change? "
                "Please tell me the event name or time, and what to update "
                "(e.g. 'Move my 3pm meeting to 4pm' or 'Rename lunch with Anna to lunch with Patrick')."
            ),
            "success": True,
            "type": "calendar_update_prompt",
            "data": {},
        }

    # Check provider connection
    if not self._check_provider_connected(user_id, normalized_provider):
        provider_label = "Microsoft / Outlook" if normalized_provider == "microsoft" else "Google"
        return {
            "message": (
                f"Your {provider_label} account isn't connected yet. "
                "You can link it in the Integrations page."
            ),
            "success": False,
            "type": "provider_not_connected",
            "data": {"provider": normalized_provider},
        }

    # Search for matching events
    now = datetime.now()
    base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    endpoint = f"{base_url}/api/integrations/{normalized_provider}/calendar/events"

    if search_date:
        time_min = f"{search_date}T00:00:00Z"
        time_max_str = f"{search_date}T23:59:59Z"
    else:
        time_min = now.isoformat() + "Z"
        time_max_str = (now + timedelta(days=14)).isoformat() + "Z"

    params: Dict[str, Any] = {"user_id": user_id, "max_results": 25, "time_min": time_min}

    logger.info("[CAL_UPDATE AUDIT] Search → endpoint=%s params=%s", endpoint, params)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(endpoint, params=params, timeout=30.0)

        logger.info("[CAL_UPDATE AUDIT] Search ← status=%s body=%s", resp.status_code, resp.text[:200])

        if not resp.is_success:
            return {
                "message": f"I couldn't search your calendar (HTTP {resp.status_code}). Please check your connection.",
                "success": False,
                "type": "error",
                "error": f"HTTP {resp.status_code}",
            }

        all_events = resp.json().get("events", [])

        # Filter by time_max
        time_max_dt = datetime.fromisoformat(time_max_str.replace("Z", "+00:00"))
        filtered = []
        for evt in all_events:
            try:
                start_dt = datetime.fromisoformat(evt.get("start", "").replace("Z", "+00:00"))
                if start_dt <= time_max_dt:
                    filtered.append(evt)
            except Exception:
                filtered.append(evt)
        all_events = filtered

        # Filter by search_query (fuzzy title match)
        if search_query:
            query_lower = search_query.lower()
            matched = [e for e in all_events if query_lower in (e.get("summary") or "").lower()]
            if not matched:
                query_words = [w for w in query_lower.split() if len(w) > 2]
                matched = [e for e in all_events
                           if any(w in (e.get("summary") or "").lower() for w in query_words)]
            if matched:
                all_events = matched

        # Filter by search_time (original event start hour)
        if search_time:
            target_h = int(search_time.split(":")[0])
            time_filtered = []
            for evt in all_events:
                try:
                    start_dt = datetime.fromisoformat(
                        evt.get("start", "").replace("Z", "+00:00").replace("+00:00", "")
                    )
                    if start_dt.hour == target_h:
                        time_filtered.append(evt)
                except Exception:
                    pass
            if time_filtered:
                all_events = time_filtered

        logger.info("[CAL_UPDATE] Found %d matching events", len(all_events))

        if not all_events:
            qualifier = f" '{search_query}'" if search_query else ""
            date_hint = f" on {search_date}" if search_date else " in the next 2 weeks"
            return {
                "message": (
                    f"I couldn't find an event{qualifier}{date_hint}. "
                    "Can you give me more details — the exact name, date, or time?"
                ),
                "success": True,
                "type": "calendar_update_no_match",
                "data": update_slots,
            }

        if len(all_events) == 1:
            # Single match — straight to confirmation
            selected = all_events[0]
            task_data = {
                **update_slots,
                "selected_event": selected,
                "provider": normalized_provider,
                "user_id": user_id,
            }
            self.memory.set_active_task(
                task_type="calendar_update",
                data=task_data,
                status="awaiting_confirmation",
            )
            return _build_update_confirmation(self, selected, task_data, normalized_provider)

        # Multiple matches — list and ask user to pick
        lines = [f"I found {len(all_events[:5])} matching events. Which one would you like to update?\n"]
        for i, evt in enumerate(all_events[:5], 1):
            summary = evt.get("summary", "Untitled")
            start_str = evt.get("start", "")
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00").replace("+00:00", ""))
                time_label = start_dt.strftime("%a %b %d at %H:%M")
            except Exception:
                time_label = start_str
            lines.append(f"  {i}. {summary} — {time_label}")

        task_data = {
            **update_slots,
            "matched_events": all_events[:5],
            "provider": normalized_provider,
            "user_id": user_id,
        }
        self.memory.set_active_task(
            task_type="calendar_update",
            data=task_data,
            status="collecting",
        )
        return {
            "message": "\n".join(lines),
            "success": True,
            "type": "calendar_update_select",
            "data": {"matched_events": all_events[:5]},
        }

    except httpx.TimeoutException:
        return {
            "message": "The calendar service timed out while searching. Please try again.",
            "success": False,
            "type": "error",
            "error": "Timeout",
        }
    except Exception as e:
        logger.error("[CAL_UPDATE] Search error: %s", e, exc_info=True)
        return {
            "message": f"Error searching calendar: {e}",
            "success": False,
            "type": "error",
            "error": str(e),
        }


async def _execute_calendar_update(self, action_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Execute calendar event PATCH via integration endpoint.
    Preserves original event duration when only the start time is changed.
    """
    import httpx

    logger.info("[CAL_UPDATE] Executing PATCH on calendar event")

    selected_event = action_data.get("selected_event", {})
    event_id = selected_event.get("id")
    provider_raw = action_data.get("provider", "google")
    normalized_provider = _normalize_provider(provider_raw)

    if not event_id:
        return {
            "message": "I lost track of which event to update. Please describe it again.",
            "success": False,
            "type": "error",
            "error": "No event_id in pending action",
        }

    new_time = action_data.get("new_time")
    new_title = action_data.get("new_title")
    new_location = action_data.get("new_location")

    # Build ISO datetimes for new start/end if time is changing
    patch_start: Optional[str] = None
    patch_end: Optional[str] = None

    if new_time:
        tz_name = os.getenv("TIMEZONE", "Europe/Berlin")
        try:
            tz_obj = pytz.timezone(tz_name)
        except Exception:
            tz_obj = pytz.UTC
            tz_name = "UTC"

        # Use original event date unless a new date was supplied
        new_date = action_data.get("new_date")
        if not new_date:
            orig_start = selected_event.get("start", "")
            try:
                orig_start_dt = datetime.fromisoformat(orig_start.replace("Z", "+00:00"))
                new_date = orig_start_dt.strftime("%Y-%m-%d")
            except Exception:
                new_date = datetime.now().strftime("%Y-%m-%d")

        try:
            start_naive = datetime.fromisoformat(f"{new_date}T{new_time}:00")
            start_aware = tz_obj.localize(start_naive)
            patch_start = start_aware.isoformat()

            # Preserve original duration for end time
            orig_start_str = selected_event.get("start", "")
            orig_end_str = selected_event.get("end", "")
            if orig_start_str and orig_end_str:
                try:
                    o_start = datetime.fromisoformat(orig_start_str.replace("Z", "+00:00"))
                    o_end = datetime.fromisoformat(orig_end_str.replace("Z", "+00:00"))
                    duration = o_end - o_start
                    patch_end = (start_aware + duration).isoformat()
                except Exception:
                    patch_end = (start_aware + timedelta(hours=1)).isoformat()
            else:
                patch_end = (start_aware + timedelta(hours=1)).isoformat()
        except Exception as e:
            logger.warning("[CAL_UPDATE] Failed to build new datetime: %s", e)

    # Construct the patch payload using CalendarEventUpdateRequest fields
    payload: Dict[str, Any] = {}
    if new_title:
        payload["summary"] = new_title
    if patch_start:
        payload["start"] = patch_start
    if patch_end:
        payload["end"] = patch_end
    if new_location:
        payload["location"] = new_location

    if not payload:
        return {
            "message": "Nothing to update — no changes were specified.",
            "success": False,
            "type": "error",
            "error": "Empty patch payload",
        }

    base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    endpoint = f"{base_url}/api/integrations/{normalized_provider}/calendar/events/{event_id}"
    params = {"user_id": user_id}

    logger.info("[CAL_UPDATE AUDIT] PATCH → %s payload=%s", endpoint, json.dumps(payload))

    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(endpoint, json=payload, params=params, timeout=30.0)

        logger.info("[CAL_UPDATE AUDIT] PATCH ← status=%s body=%s",
                    response.status_code, response.text[:300])

        if response.is_success:
            updated = response.json()
            self.memory.clear_pending_action()
            self.memory.clear_active_task()
            self.memory.preferred_provider = normalized_provider

            event_summary = updated.get("summary", selected_event.get("summary", "the event"))
            change_parts = []
            if new_time:
                change_parts.append(f"moved to {_format_time_natural(new_time)}")
            if new_title:
                change_parts.append(f"renamed to \"{new_title}\"")
            if new_location:
                change_parts.append(f"location changed to \"{new_location}\"")
            changes_str = ", ".join(change_parts) if change_parts else "updated"

            logger.info("[CAL_UPDATE AUDIT] PATCH ✅ event_id=%s summary='%s'", event_id, event_summary)
            return {
                "message": f"Done. \"{event_summary}\" has been {changes_str}.",
                "success": True,
                "type": "calendar_updated",
                "data": {**updated, "event_id": event_id},
            }
        else:
            error_body = response.text[:300]
            logger.error("[CAL_UPDATE AUDIT] PATCH ❌ status=%s body=%s", response.status_code, error_body)
            return {
                "message": f"Failed to update the event (HTTP {response.status_code}): {error_body}",
                "success": False,
                "type": "error",
                "error": f"HTTP {response.status_code}",
                "data": {"pending_action_preserved": True},
            }

    except httpx.TimeoutException:
        return {
            "message": "The calendar service timed out. Please try again.",
            "success": False,
            "type": "error",
            "error": "Timeout",
        }
    except Exception as e:
        logger.error("[CAL_UPDATE] PATCH exception: %s", e, exc_info=True)
        return {
            "message": f"Error updating the event: {e}",
            "success": False,
            "type": "error",
            "error": str(e),
        }


async def _handle_calendar_delete(self, user_message: str, user_id: str, provider: str) -> Dict[str, Any]:
    """Handle CALENDAR_DELETE — ask which event to cancel."""
    logger.info("[AGENT] Handling calendar delete intent")
    name_m = re.search(
        r"(?:cancel|delete|remove)\s+my\s+(?:meeting|appointment|event)\s+with\s+(\w+)",
        user_message, re.IGNORECASE,
    )
    if name_m:
        event_name = name_m.group(1)
        return {
            "message": f"What date is the meeting with {event_name}?",
            "success": True,
            "type": "calendar_delete_prompt",
            "data": {"search_term": event_name},
        }
    return {
        "message": "Which event would you like to cancel? Give me the title or date.",
        "success": True,
        "type": "calendar_delete_prompt",
        "data": {},
    }


async def _handle_out_of_scope(self, user_message: str) -> Dict[str, Any]:
    """
    SECTION 1 FIX: Route truly out-of-scope requests to LLM for graceful response.

    The OUT_OF_SCOPE_PATTERNS have been drastically reduced to only external action
    APIs (ordering food/uber, device control). For those, we still let the LLM
    respond naturally explaining the limitation — no hard-coded refusals.
    """
    logger.info("[AGENT] Handling out-of-scope — routing to LLM for graceful response")

    # Let the LLM respond naturally, acknowledging the limitation without being rude
    system_prompt = self._build_intelligent_system_prompt()
    user_prompt = self._build_contextual_user_prompt(user_message)

    from models.chat import ChatRequest, ChatMessage
    chat_request = ChatRequest(
        prompt=user_prompt,
        conversation_history=[ChatMessage(role="system", content=system_prompt)],
        temperature=0.7,
        max_tokens=300,
    )

    try:
        llm_response = await self.chat_service.chat_completion(chat_request)
        return {
            "message": llm_response.response,
            "success": True,
            "type": "chat",
            "data": {},
        }
    except Exception as e:
        logger.warning("[AGENT] LLM fallback in out-of-scope failed: %s", e)
        return {
            "message": "I'm not able to help with that specific request, but I can assist with your calendar, emails, and general questions.",
            "success": False,
            "type": "out_of_scope",
            "data": {},
        }


# Inject new methods into ExecutiveAgent
ExecutiveAgent._handle_email_reply = _handle_email_reply
ExecutiveAgent._handle_email_forward = _handle_email_forward
ExecutiveAgent._handle_calendar_update = _handle_calendar_update
ExecutiveAgent._execute_calendar_update = _execute_calendar_update
ExecutiveAgent._handle_calendar_delete = _handle_calendar_delete
ExecutiveAgent._handle_out_of_scope = _handle_out_of_scope


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _normalize_provider(raw_provider: str) -> str:
    """
    Normalise provider string to a valid URL segment for the integrations API.
    Handles exact names, aliases, and common typos via fuzzy keyword matching.

    Accepted URL segments: "google" | "microsoft"
    """
    p = raw_provider.lower().strip() if raw_provider else "google"

    # ── Exact / common alias match (fast path) ────────────────────────────────
    if p in ("google", "gmail", "gcal", "google calendar", "google cal"):
        return "google"
    if p in ("microsoft", "outlook", "ms", "office365", "office 365", "outlook calendar"):
        return "microsoft"

    # ── Fuzzy match using shared NLU keyword lists (handles typos like "otlook") ─
    try:
        from services.nlu_service import MS_KEYWORDS, GOOGLE_KEYWORDS
        for kw in MS_KEYWORDS:
            if kw in p:
                logger.info("[ORCHESTRATION] Fuzzy matched '%s' → microsoft (via '%s')", p, kw)
                return "microsoft"
        for kw in GOOGLE_KEYWORDS:
            if kw in p:
                logger.info("[ORCHESTRATION] Fuzzy matched '%s' → google (via '%s')", p, kw)
                return "google"
    except ImportError:
        pass  # nlu_service not available — fall through to default

    logger.warning("[ORCHESTRATION] Unknown provider '%s', defaulting to 'google'", raw_provider)
    return "google"


def _parse_event_selection(user_message: str, events: list) -> Optional[dict]:
    """
    Parse a user's event selection from a numbered list.
    Supports: "1", "number 1", "the first one", "first", ordinals, etc.
    Returns the selected event dict or None if not parseable.
    """
    msg = user_message.strip().lower()
    # Direct numeric: "1", "2", ...
    m = re.match(r'^(\d+)$', msg)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(events):
            return events[idx]
        return None
    # "number 2", "option 2", "#2"
    m = re.search(r'(?:number|option|#)\s*(\d+)', msg)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(events):
            return events[idx]
    # Ordinal words
    ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}
    for word, idx in ordinals.items():
        if word in msg and 0 <= idx < len(events):
            return events[idx]
    return None


def _build_update_confirmation(agent, selected_event: dict, task_data: dict, provider: str) -> dict:
    """
    Build the confirmation message for a calendar update and store the pending action.
    """
    summary = selected_event.get("summary", "Untitled")
    start_str = selected_event.get("start", "")
    try:
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00").replace("+00:00", ""))
        orig_time = start_dt.strftime("%H:%M")
        orig_date = start_dt.strftime("%A, %B %d")
    except Exception:
        orig_time = start_str
        orig_date = ""

    changes = []
    new_time = task_data.get("new_time")
    new_title = task_data.get("new_title")
    new_location = task_data.get("new_location")

    if new_time:
        changes.append(f"move to {_format_time_natural(new_time)}")
    if new_title:
        changes.append(f"rename to \"{new_title}\"")
    if new_location:
        changes.append(f"change location to \"{new_location}\"")

    changes_str = ", ".join(changes) if changes else "update"
    orig_label = f"{orig_date}" + (f" at {_format_time_natural(orig_time)}" if orig_time else "")

    msg = f'"{summary}" ({orig_label}) — {changes_str}. Shall I go ahead?'

    agent.memory.set_pending_action(
        action_type="update_calendar_event",
        data={**task_data, "selected_event": selected_event, "provider": provider},
    )
    agent.memory.update_task_status("awaiting_confirmation")

    return {
        "message": msg,
        "success": True,
        "type": "calendar_update_confirmation",
        "data": {"selected_event": selected_event, "changes": task_data},
        "action_needed": "confirmation",
    }


def get_current_date_str() -> str:
    """Get current date as YYYY-MM-DD string."""
    return datetime.now().strftime("%Y-%m-%d")


def get_tomorrow_date_str() -> str:
    """Get tomorrow's date as YYYY-MM-DD string."""
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def parse_natural_date(date_str: str) -> Optional[str]:
    """
    Parse natural language date to YYYY-MM-DD format.
    
    CRITICAL: Uses DYNAMIC dates based on actual current time.
    NO hardcoded years!
    """
    today = datetime.now()
    date_lower = date_str.lower().strip()
    
    if date_lower == "today":
        return today.strftime("%Y-%m-%d")
    
    if date_lower == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    
    if "next week" in date_lower:
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Add more natural date parsing as needed
    return None
