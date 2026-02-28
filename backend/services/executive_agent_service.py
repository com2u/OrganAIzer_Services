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

import logging
import os
import json
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
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    MAX_HISTORY = 10  # Keep last 10 messages for context
    
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
        provider: str = "google",          # legacy field – kept for backward compat
        mail_provider: str = "gmail",      # provider used for email actions
        calendar_provider: str = "google", # provider used for calendar actions
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
                "error": str(e)
            }
    
    async def _route_to_handler(
        self,
        intent_type: str,
        user_message: str,
        extracted_slots: Dict[str, Any],
        user_id: str,
        mail_provider: str = "gmail",
        calendar_provider: str = "google",
        # Accept legacy single-provider arg too for any internal call-sites
        provider: str = None,
    ) -> Dict[str, Any]:
        """
        Route to appropriate intent handler based on intent type.

        Uses mail_provider for email operations, calendar_provider for calendar ops.
        """
        # Derive convenient single-provider fallback (legacy support)
        _mail = mail_provider or provider or "gmail"
        _cal  = calendar_provider or provider or "google"

        # Confirmation handling
        if intent_type == IntentType.CONFIRM_ACTION:
            return await self._handle_confirmation(user_id, _cal)

        # Cancellation handling
        if intent_type == IntentType.CANCEL_ACTION:
            return await self._handle_cancellation()

        # Optional slot decline
        if intent_type == IntentType.DECLINE_OPTIONAL:
            return await self._handle_decline_optional()

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

        # Slot filling for active task
        if intent_type == IntentType.PROVIDE_SLOT_VALUE:
            return await self._handle_slot_filling(user_message, extracted_slots, user_id, _cal)

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
        mail_provider: str = "gmail",
        calendar_provider: str = "google",
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
        Build enhanced system prompt for LLM with intelligence guidelines.
        
        This is CRITICAL for AI behavior - defines:
        - Personality and tone
        - Capabilities
        - Knowledge domains
        - Safety protocols
        """
        current_date = self.current_datetime.strftime("%A, %B %d, %Y")
        current_time = self.current_datetime.strftime("%H:%M")
        
        return f"""You are the OrganAIzer Executive Agent, an intelligent, professional, and helpful AI assistant.

CURRENT CONTEXT:
- Date: {current_date}
- Time: {current_time}
- Timezone: {self.timezone}

YOUR PERSONALITY:
- Professional yet approachable
- Intelligent and knowledgeable
- Calm and reassuring
- Concise but not robotic
- Adaptable in tone (formal for business, friendly for casual chat)

YOUR CAPABILITIES:
1. **Calendar Management**: Create, modify, and query calendar events
2. **Email Management**: Read, summarize, draft, and send emails  
3. **Knowledge Companion**: Answer questions about history, geography, science, current events, etc.
4. **Productivity Assistant**: Help with planning, reminders, and organization

CRITICAL RULES:
1. **Dynamic Dates**: When user says "tomorrow", use {(self.current_datetime + timedelta(days=1)).strftime("%Y-%m-%d")}. Never use hardcoded years like 2024.
2. **Confirmation Required**: NEVER send emails or create calendar events without explicit user confirmation.
3. **Ambiguity Handling**: If request is unclear, ask smart clarifying questions.
4. **Context Awareness**: Remember what was discussed earlier in the conversation.
5. **Professional Tone for Work**: Use professional language for emails and calendar events.
6. **Friendly Tone for Chat**: Be conversational and witty for general questions.

RESPONSE STYLE:
- For calendar/email: Clear, structured, professional
- For knowledge queries: Concise, informative, occasionally witty
- For errors: Helpful, guide user to solution

EXAMPLE GOOD RESPONSES:
- Calendar: "I'll create a meeting titled 'Strategy Session' for tomorrow at 2 PM. Should I add this to your Google Calendar or Outlook?"
- Email: "I've drafted an email to your boss about the delay. Would you like to review it before sending?"
- Knowledge: "World War 2 ended in 1945 with the surrender of Japan. The war reshaped global politics and led to the formation of the UN. Quite the historical pivot point!"

Remember: You're not just executing commands - you're an intelligent companion who understands context, anticipates needs, and communicates professionally."""
    
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
        - Provider normalisation: "gmail" → "google", "microsoft" → "outlook", etc.
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

            # Build start datetime (ISO 8601)
            start_datetime_str = f"{date}T{time_str}:00"

            # Build end datetime
            if end_time:
                end_datetime_str = f"{date}T{end_time}:00"
            else:
                start_dt = datetime.fromisoformat(start_datetime_str)
                end_dt = start_dt + timedelta(minutes=duration)
                end_datetime_str = end_dt.isoformat()

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

                logger.info(
                    "[AUDIT] Calendar create ✅  event_id=%s  summary=%s",
                    event_id, event_summary
                )

                # Record in history ONLY after confirmed success
                self.memory.add_to_history({
                    **action_data,
                    "type": "create_calendar_event",
                    "result": event_data,
                    "event_id": event_id,
                })

                # Clear state only on success
                self.memory.clear_pending_action()
                self.memory.clear_active_task()

                # Build human-readable success message with proof
                success_msg = (
                    f"✅ Calendar event created successfully!\n\n"
                    f"**{event_summary}**\n"
                    f"- 📅 Date: {date}\n"
                    f"- 🕐 Start: {event_start}\n"
                    f"- 🕑 End: {event_end}\n"
                    f"- 📆 Calendar: {provider.title()} Calendar"
                )
                if event_id:
                    success_msg += f"\n- 🆔 Event ID: `{event_id}`"
                if html_link:
                    success_msg += f"\n- 🔗 [Open in Calendar]({html_link})"

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
          Outlook: POST /api/integrations/outlook/mail/send?user_id={user_id}

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

            # Choose endpoint based on provider
            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            if provider == "google":
                endpoint = f"{base_url}/api/integrations/google/gmail/send"
            else:
                endpoint = f"{base_url}/api/integrations/outlook/mail/send"

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

                success_msg = (
                    f"✅ Email sent successfully!\n\n"
                    f"- 📧 **To:** {to_email}\n"
                    f"- 📝 **Subject:** {subject}\n"
                    f"- 📨 **Provider:** {provider.title()}"
                )
                if message_id:
                    success_msg += f"\n- 🆔 **Message ID:** `{message_id}`"

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
                    "message": "📧 I'd be happy to send an email! Who should I send it to? (Please provide the email address)",
                    "success": True,
                    "type": "email_slot_request",
                    "data": {"missing_slot": "to_email", "current_slots": all_slots},
                }
            elif missing_slot == "subject":
                to_display = all_slots.get("to_email", "the recipient")
                return {
                    "message": f"📧 Got it — sending to **{to_display}**. What should the subject line be?",
                    "success": True,
                    "type": "email_slot_request",
                    "data": {"missing_slot": "subject", "current_slots": all_slots},
                }
            elif missing_slot == "body":
                return {
                    "message": "📧 Almost there! What should the body of the email say?",
                    "success": True,
                    "type": "email_slot_request",
                    "data": {"missing_slot": "body", "current_slots": all_slots},
                }

        # STEP 3: Check provider preference
        if not all_slots.get("provider"):
            logger.info("[ORCHESTRATION] Email provider not specified - using default 'gmail'")
            # Default to gmail so we don't block the flow with an extra question
            all_slots["provider"] = provider if provider else "gmail"

        # STEP 4: All slots present – request confirmation
        logger.info("[ORCHESTRATION] All email slots collected - requesting confirmation")

        body_preview = (all_slots.get("body", "") or "")[:200]
        if len(all_slots.get("body", "") or "") > 200:
            body_preview += "..."

        confirmation_msg = (
            f"📧 **Ready to send your email:**\n\n"
            f"- **To:** {all_slots['to_email']}\n"
            f"- **Subject:** {all_slots['subject']}\n"
            f"- **Provider:** {all_slots['provider'].title()}\n"
            f"- **Message:** {body_preview}"
        )
        if all_slots.get("cc"):
            confirmation_msg += f"\n- **CC:** {all_slots['cc']}"

        confirmation_msg += "\n\nShould I send this email? (yes/no)"

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
                "message": "No problem! I've cancelled that. What else can I help you with?",
                "success": True,
                "type": "cancellation"
            }
        else:
            return {
                "message": "There's nothing active to cancel right now. How can I assist you?",
                "success": True,
                "type": "info"
            }
    
    async def _handle_decline_optional(self) -> Dict[str, Any]:
        """Handle user declining optional information."""
        logger.info(f"[AGENT] Handling decline of optional: {self.memory.last_question_type}")
        
        # Continue with rest of flow
        return {
            "message": "Got it! Proceeding without that. What else would you like to add?",
            "success": True,
            "type": "acknowledge"
        }
    
    async def _handle_sender_selection(self, extracted_slots: Dict[str, Any]) -> Dict[str, Any]:
        """Handle email sender account selection."""
        provider = extracted_slots.get("provider")
        
        if not provider:
            return {
                "message": "I didn't catch that. Would you like to use Gmail or Outlook?",
                "success": False,
                "type": "clarification"
            }
        
        # Update active task with provider
        if self.memory.active_task:
            self.memory.update_task_data({"provider": provider})
            return {
                "message": f"✅ Great! I'll use {provider.title()}. What else do you need for this email?",
                "success": True,
                "type": "ack nowledge"
            }
        
        return {
            "message": f"Noted - {provider.title()} selected. What would you like to do?",
            "success": True,
            "type": "acknowledge"
        }
    
    async def _handle_calendar_provider_selection(self, extracted_slots: Dict[str, Any]) -> Dict[str, Any]:
        """Handle calendar provider selection."""
        provider = extracted_slots.get("provider")
        
        if not provider:
            return {
                "message": "I didn't catch that. Would you like to use Google Calendar or Outlook Calendar?",
                "success": False,
                "type": "clarification"
            }
        
        # Update active task with provider
        if self.memory.active_task:
            self.memory.update_task_data({"provider": provider})
            return {
                "message": f"✅ Perfect! I'll add it to your {provider.title()} Calendar. Ready to create the event?",
                "success": True,
                "type": "acknowledge"
            }
        
        return {
            "message": f"Noted - {provider.title()} Calendar selected. What would you like to do?",
            "success": True,
            "type": "acknowledge"
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
            "message": f"It looks like you want to switch topics. Should I save the current {task_type} task as a draft, or would you like to cancel it and start fresh?",
            "success": True,
            "type": "clarification",
            "action_needed": "confirm_topic_switch"
        }
    
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
        
        # Default title if not provided
        if "title" in missing_slots:
            all_slots["title"] = "Meeting"
            missing_slots.remove("title")
            logger.info("[ORCHESTRATION] Using default title: 'Meeting'")
        
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
                return {
                    "message": f"📅 I'm creating an event '{all_slots.get('title')}' on {all_slots.get('date')}. What time should it be?",
                    "success": True,
                    "type": "calendar_slot_request",
                    "data": {"missing_slot": "time", "current_slots": all_slots}
                }
            else:
                return {
                    "message": f"I need more information. What {missing_slot} would you like?",
                    "success": True,
                    "type": "calendar_slot_request",
                    "data": {"missing_slot": missing_slot, "current_slots": all_slots}
                }
        
        # STEP 4: Check provider preference
        if not all_slots.get("provider"):
            logger.info("[ORCHESTRATION] Provider not specified - asking user")
            
            # Create active task
            self.memory.set_active_task(
                task_type="calendar_event",
                data=all_slots,
                status="collecting"
            )
            
            return {
                "message": f"📅 Perfect! I'll create '{all_slots['title']}' on {all_slots['date']} at {all_slots['time']}.\n\nWhich calendar should I use? (Google Calendar / Outlook Calendar)",
                "success": True,
                "type": "calendar_provider_request",
                "data": all_slots
            }
        
        # STEP 5: All slots present - create pending_action and request confirmation
        logger.info("[ORCHESTRATION] All slots collected - requesting confirmation")
        
        # Format confirmation message
        confirmation_msg = f"""📅 **Ready to create your calendar event:**

- **Title:** {all_slots['title']}
- **Date:** {all_slots['date']}
- **Time:** {all_slots['time']}
- **Calendar:** {all_slots['provider'].title()}"""
        
        if all_slots.get("end_time"):
            confirmation_msg += f"\n- **End Time:** {all_slots['end_time']}"
        elif all_slots.get("duration"):
            confirmation_msg += f"\n- **Duration:** {all_slots['duration']} minutes"
        
        if all_slots.get("location"):
            confirmation_msg += f"\n- **Location:** {all_slots['location']}"
        
        confirmation_msg += "\n\nShould I create this event? (yes/no)"
        
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
          Outlook: GET /api/integrations/outlook/calendar/events

        Parses "tomorrow" / "today" from user_message to set time_min/time_max.
        Returns events formatted as a readable list.
        """
        import httpx

        logger.info("[ORCHESTRATION] Starting calendar list events workflow")

        normalized_provider = _normalize_provider(provider)
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


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _normalize_provider(raw_provider: str) -> str:
    """
    Normalise provider string to a valid URL segment for the integrations API.

    Accepted URL segments: "google" | "outlook"

    Maps:
      gmail / gcal / google calendar / google → "google"
      outlook / microsoft / ms / office365 / outlook calendar → "outlook"
    """
    p = raw_provider.lower().strip() if raw_provider else "google"
    if p in ("google", "gmail", "gcal", "google calendar", "google cal"):
        return "google"
    if p in ("outlook", "microsoft", "ms", "office365", "office 365", "outlook calendar"):
        return "outlook"
    logger.warning(
        "[ORCHESTRATION] Unknown provider '%s', defaulting to 'google'", raw_provider
    )
    return "google"


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
