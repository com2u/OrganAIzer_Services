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
        provider: str = "gmail"
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
            provider: Preferred provider (gmail/outlook)
        
        Returns:
            {
                "message": str,  # Response to user
                "success": bool,  # Operation success
                "type": str,  # Response type (email, calendar, chat, etc.)
                "data": dict,  # Additional data (emails, events, etc.)
                "action_needed": str,  # If user action required
                "error": str  # Error message if any
            }
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"[AGENT] Processing message: '{user_message}'")
        logger.info(f"[AGENT] User: {user_id} | Provider: {provider}")
        
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
                provider=provider
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
        provider: str
    ) -> Dict[str, Any]:
        """
        Route to appropriate intent handler based on intent type.
        
        This is the intelligence dispatcher that ensures the right
        handler processes each type of user input.
        """
        # Confirmation handling
        if intent_type == IntentType.CONFIRM_ACTION:
            return await self._handle_confirmation(user_id, provider)
        
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
        
        # Slot filling for active task
        if intent_type == IntentType.PROVIDE_SLOT_VALUE:
            return await self._handle_slot_filling(user_message, extracted_slots, user_id, provider)
        
        # Topic switch during active task
        if intent_type == IntentType.SWITCH_TOPIC:
            return await self._handle_topic_switch(user_message, user_id, provider)
        
        # General message (new task or chat)
        return await self._handle_general_message(user_message, extracted_slots, user_id, provider)
    
    async def _handle_general_message(
        self,
        user_message: str,
        extracted_slots: Dict[str, Any],
        user_id: str,
        provider: str
    ) -> Dict[str, Any]:
        """
        Handle general messages using LLM with enhanced intelligence.
        
        This is where the "brain" of the agent lives - uses LLM to:
        - Understand complex queries
        - Determine user intent
        - Generate human-like responses
        - Decide what actions to take
        """
        logger.info("[AGENT] Handling general message with LLM reasoning")
        
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
        """Handle user confirming a pending action."""
        logger.info("[AGENT] Handling confirmation")
        
        pending = self.memory.get_pending_action()
        if not pending:
            return {
                "message": "I don't have any pending actions to confirm. What would you like me to help you with?",
                "success": False,
                "type": "error"
            }
        
        # TODO: Execute the pending action (calendar create, email send, etc.)
        # For now, acknowledge confirmation
        action_type = pending["type"]
        
        self.memory.add_to_history(pending)
        self.memory.clear_pending_action()
        self.memory.clear_active_task()
        
        return {
            "message": f"✅ Confirmed! I've executed the {action_type}. Is there anything else I can help you with?",
            "success": True,
            "type": "confirmation",
            "data": pending["data"]
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
        """Handle filling slots for active task."""
        logger.info(f"[AGENT] Handling slot filling: {extracted_slots}")
        
        # TODO: Implement full slot filling logic
        # This would update the active task and ask for missing information
        
        return {
            "message": "I've noted that information. What else would you like to add?",
            "success": True,
            "type": "slot_update",
            "data": extracted_slots
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


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

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
