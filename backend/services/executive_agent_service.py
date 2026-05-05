"""
Executive Agent Service — LLM-Driven Core

The brain of OrganAIzer. Uses Gemini 2.5 Flash (via OpenRouter) with structured
tool-calling to handle calendar, email, and general conversation.

Architecture:
1. User message arrives
2. If a pending action exists, check for confirm / cancel
3. Otherwise, run the LLM tool-calling loop:
   a. LLM receives system prompt + conversation history + tool schemas
   b. LLM either responds with text OR calls one or more tools
   c. Read tools (list_calendar_events, read_emails) execute immediately;
      result is fed back to the LLM for a natural-language response
   d. Propose tools (propose_create_calendar_event, etc.) store the action
      as a pending_action and return a confirmation message to the user
4. On user confirmation, the pending action is executed against the real API
5. Memory (ConversationMemory) tracks history, pending actions, and context

Author: OrganAIzer Team
"""

import asyncio as _asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import pytz
from dataclasses import dataclass, field

from config.chat_limits import MAX_HISTORY, MAX_HISTORY_TOKENS
from services.chat_service import get_chat_service
from services.tool_definitions import (
    CONFIRMATION_REQUIRED_TOOLS,
    TOOLS,
    format_confirmation_message,
    is_cancel,
    is_confirm,
)

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
    preferred_provider: Optional[str] = None
    current_user_id: Optional[str] = None
    last_clarification_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    MAX_HISTORY = 20

    # Email context
    last_email_sender: Optional[str] = None
    last_email_sender_address: Optional[str] = None
    last_email_thread_id: Optional[str] = None
    last_email_message_id: Optional[str] = None
    last_email_subject: Optional[str] = None

    # Continuation tracking
    last_action_type: Optional[str] = None
    last_provider: Optional[str] = None

    def add_message(self, role: str, content: str):
        """Add message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self.conversation_history) > self.MAX_HISTORY:
            self.conversation_history = self.conversation_history[-self.MAX_HISTORY:]
        self.last_activity = datetime.now()

    def set_active_task(self, task_type: str, data: Dict[str, Any], status: str = "collecting"):
        self.active_task = {
            "type": task_type,
            "data": data,
            "status": status,
            "created_at": datetime.now().isoformat(),
        }

    def update_task_data(self, updates: Dict[str, Any]):
        if self.active_task:
            self.active_task["data"].update(updates)

    def update_task_status(self, status: str):
        if self.active_task:
            self.active_task["status"] = status

    def get_active_task(self) -> Optional[Dict[str, Any]]:
        return self.active_task

    def clear_active_task(self):
        self.active_task = None

    def is_task_locked(self) -> bool:
        if not self.active_task:
            return False
        return self.active_task.get("status") in ["collecting", "awaiting_confirmation", "drafted"]

    def set_pending_action(self, action_type: str, data: Dict[str, Any]):
        self.pending_action = {
            "type": action_type,
            "data": data,
            "status": "awaiting_confirmation",
            "created_at": datetime.now().isoformat(),
        }
        logger.info("[MEMORY] Pending action set: %s", action_type)

    def get_pending_action(self) -> Optional[Dict[str, Any]]:
        return self.pending_action

    def clear_pending_action(self):
        if self.pending_action:
            logger.info("[MEMORY] Clearing pending action: %s", self.pending_action.get("type"))
        self.pending_action = None

    def add_to_history(self, action: Dict[str, Any]):
        action["completed_at"] = datetime.now().isoformat()
        self.action_history.append(action)
        if len(self.action_history) > 20:
            self.action_history = self.action_history[-20:]

    def get_last_action(self) -> Optional[Dict[str, Any]]:
        return self.action_history[-1] if self.action_history else None

    def update_context(self, key: str, value: Any):
        self.context[key] = value


# ==============================================================================
# IDEMPOTENCY STORE — prevents duplicate calendar events on double-confirm
# ==============================================================================

_CALENDAR_IDEMPOTENCY_STORE: Dict[str, str] = {}
_CALENDAR_IDEMPOTENCY_LOCK = _asyncio.Lock()


def _compute_calendar_request_id(
    user_id: str,
    title: str,
    start: str,
    end: str,
    timezone_name: str = "UTC",
) -> str:
    raw = f"{user_id}|{title}|{start}|{end}|{timezone_name}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ==============================================================================
# EXECUTIVE AGENT
# ==============================================================================

class ExecutiveAgent:
    """
    LLM-driven executive assistant.

    The LLM (Gemini 2.5 Flash via OpenRouter) decides what to do using
    structured tool-calling. Rule-based intent classification is removed —
    the model's reasoning drives every decision.
    """

    sessions: Dict[str, ConversationMemory] = {}

    def __init__(self, session_id: str):
        self.session_id = session_id
        if session_id not in ExecutiveAgent.sessions:
            ExecutiveAgent.sessions[session_id] = ConversationMemory(session_id=session_id)
            logger.info("[AGENT] New session: %s", session_id)
        else:
            logger.info("[AGENT] Resuming session: %s", session_id)

        self.memory = ExecutiveAgent.sessions[session_id]
        self.chat_service = get_chat_service()
        self.timezone = pytz.timezone(os.getenv("TIMEZONE", "Europe/Berlin"))
        self.tz_name = os.getenv("TIMEZONE", "Europe/Berlin")

    # ── Main entry point ──────────────────────────────────────────────────────

    async def process_message(
        self,
        user_message: str,
        user_id: str = "default_user",
        provider: Optional[str] = None,
        mail_provider: Optional[str] = None,
        calendar_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the LLM-driven pipeline.

        Returns a standardised dict:
          {
              "message":       str,
              "success":       bool,
              "type":          str,
              "data":          dict,
              "action_needed": str | None,
              "intent":        str,
              "error":         str | None,
          }
        """
        logger.info("[AGENT] message received user=%s cal=%s mail=%s chars=%d",
                    user_id, calendar_provider, mail_provider, len(user_message or ""))

        self.memory.current_user_id = user_id
        self.memory.add_message("user", user_message)

        # Resolve providers (merge legacy single provider arg)
        _cal = calendar_provider or provider
        _mail = mail_provider or provider

        try:
            # ── Confirmation / cancellation gate ──────────────────────────────
            if self.memory.pending_action:
                if is_confirm(user_message):
                    result = await self._execute_pending_action(user_id, _cal, _mail)
                    self.memory.add_message("assistant", result["message"])
                    return result

                if is_cancel(user_message):
                    return await self._cancel_pending_action()

                # Anything else (e.g. "no, use outlook") → cancel pending and
                # continue to LLM so it can re-propose with the correction.
                logger.info("[AGENT] Non-confirm/cancel while pending → clearing pending and re-routing")
                self.memory.clear_pending_action()
                self.memory.clear_active_task()

            # ── LLM tool-calling loop ──────────────────────────────────────────
            messages = self._build_llm_messages(user_message, _cal, _mail)
            result = await self._run_llm_loop(messages, user_id, _cal, _mail)
            self.memory.add_message("assistant", result["message"])
            return result

        except Exception as e:
            logger.error("[AGENT] Error: %s", e, exc_info=True)
            return {
                "message": "I ran into an error processing your request. Please try again.",
                "success": False,
                "type": "error",
                "intent": "LLM_DRIVEN",
                "error": str(e),
            }

    # ── Message construction ──────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        calendar_provider: Optional[str] = None,
        mail_provider: Optional[str] = None,
    ) -> str:
        now = datetime.now(self.timezone)
        current_date = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%H:%M")
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        # Fall back to session memory when API params are None
        # (happens when both providers are connected and frontend sends null)
        effective_cal = calendar_provider or self.memory.preferred_provider
        effective_mail = mail_provider or (
            "gmail" if self.memory.preferred_provider == "google"
            else ("outlook" if self.memory.preferred_provider == "microsoft" else None)
        )

        if effective_cal and effective_mail:
            provider_info = f"Calendar: {effective_cal}. Email: {effective_mail}."
        elif effective_cal:
            provider_info = f"Calendar: {effective_cal}. Email: not specified — ask if needed."
        elif effective_mail:
            provider_info = f"Email: {effective_mail}. Calendar: not specified — ask if needed."
        else:
            provider_info = (
                "No provider specified. When the user wants a calendar or email action, "
                "ask: Which account would you like to use — Google or Microsoft?"
            )

        # Build session context block so the LLM knows recent events/emails
        # without always having to call list_calendar_events again.
        context_lines = []
        if self.memory.context.get("last_created_event_id"):
            ev_summary = self.memory.context.get("last_created_event_summary", "event")
            ev_id = self.memory.context["last_created_event_id"]
            ev_provider = self.memory.context.get("last_created_event_provider", effective_cal or "google")
            context_lines.append(
                f"Last calendar action: created '{ev_summary}' "
                f"(event_id={ev_id}, provider={ev_provider})"
            )
        if self.memory.last_email_subject:
            context_lines.append(
                f"Last email thread: subject='{self.memory.last_email_subject}' "
                f"from {self.memory.last_email_sender or 'unknown'} "
                f"(thread_id={self.memory.last_email_thread_id or 'unknown'})"
            )

        context_section = ""
        if context_lines:
            context_section = (
                "\nSession context (use this to avoid re-fetching known data):\n"
                + "\n".join(f"- {line}" for line in context_lines)
                + "\n"
            )

        return (
            "You are a smart, versatile executive assistant with broad general intelligence.\n"
            "You can discuss any topic — history, science, geography, technology, business, "
            "philosophy, and more — AND manage calendars and emails when asked.\n\n"
            f"Today is {current_date}. Current time: {current_time}. Tomorrow: {tomorrow}.\n"
            f"Timezone: {self.tz_name}.\n"
            f"Connected integrations: {provider_info}\n"
            f"{context_section}\n"
            "When using tools:\n"
            "- For read actions (list events, read emails): use the tool and summarise the result naturally.\n"
            "- For write actions (create, update, delete, send): use the propose_ tool. "
            "The system will show the user a confirmation request automatically — do NOT ask the user "
            "to confirm in your text response when calling a propose_ tool.\n"
            "- For update or delete: if you already know the event_id from session context above, "
            "use it directly without calling list_calendar_events again. "
            "Otherwise call list_calendar_events first to find it. "
            "The event_id is the 'id' field returned by list_calendar_events.\n"
            "- Before using propose_reply_email, check the session context above for the thread_id. "
            "If thread_id is unknown, call read_emails first to find it. "
            "If the user has explicitly dictated the full reply body, you may propose directly.\n"
            "- When the user wants to add or schedule an appointment from an email or thread: "
            "call read_email_detail or read_email_thread first to get the full body, "
            "then extract title, date, time, location, and attendees from the content. "
            "If the exact date or time is not clear from the email, ask one clarifying question before proposing. "
            "Use propose_create_calendar_event with the calendar provider (not the email provider) "
            "once you have title, start time, and end time. Never create the event directly.\n"
            "- Supply start/end times in ISO 8601 without timezone (e.g. 2026-03-23T10:00:00). "
            "The server applies the correct timezone.\n\n"
            "Response style:\n"
            "- Concise and direct, 1-3 sentences unless more detail is needed.\n"
            "- No markdown formatting (no **, no ##, no bullet lists).\n"
            "- No emojis.\n"
            "- Ask only one clarifying question at a time.\n"
            "- Never say you are limited to calendar or email tasks."
        )

    def _build_llm_messages(
        self,
        current_message: str,
        calendar_provider: Optional[str],
        mail_provider: Optional[str],
    ) -> List[Dict]:
        """Build the messages array for the LLM: system + history + current user message."""
        system_prompt = self._build_system_prompt(calendar_provider, mail_provider)

        # History excludes the current message (already added to memory, so [-1] is it)
        history = self.memory.conversation_history[:-1]

        # Apply turn cap and token budget
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]

        kept: list = []
        used_tokens = 0
        for msg in reversed(history):
            msg_tokens = len(msg.get("content", "")) // 4
            if used_tokens + msg_tokens > MAX_HISTORY_TOKENS:
                break
            kept.insert(0, msg)
            used_tokens += msg_tokens

        messages: List[Dict] = [{"role": "system", "content": system_prompt}]
        messages.extend({"role": m["role"], "content": m["content"]} for m in kept)
        messages.append({"role": "user", "content": current_message})
        return messages

    # ── LLM tool-calling loop ─────────────────────────────────────────────────

    async def _run_llm_loop(
        self,
        messages: List[Dict],
        user_id: str,
        calendar_provider: Optional[str],
        mail_provider: Optional[str],
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        """
        Run the LLM tool-calling loop.

        - If the LLM returns text, we return it.
        - If it calls a read tool, we execute and feed the result back.
        - If it calls a propose_ tool, we store a pending_action and return
          a confirmation message immediately (no further LLM call needed).
        """
        for iteration in range(max_iterations):
            logger.info("[LOOP] Iteration %d/%d | messages=%d", iteration + 1, max_iterations, len(messages))

            try:
                choice_msg = await self.chat_service.chat_with_tools(messages, TOOLS)
            except Exception as e:
                logger.error("[LOOP] LLM call failed: %s", e)
                return {
                    "message": "I had trouble connecting to my reasoning engine. Please try again.",
                    "success": False,
                    "type": "error",
                    "intent": "LLM_DRIVEN",
                }

            tool_calls = choice_msg.get("tool_calls")

            # Pure text response — we're done
            if not tool_calls:
                text = choice_msg.get("content") or "I'm not sure how to help with that."
                return {"message": text, "success": True, "type": "chat", "intent": "LLM_DRIVEN", "data": {}}

            # Add the assistant's tool-call message to the conversation
            messages.append({
                "role": "assistant",
                "content": choice_msg.get("content"),
                "tool_calls": tool_calls,
            })

            # Process each tool call
            propose_triggered = False
            for tool_call in tool_calls:
                name = tool_call["function"]["name"]
                raw_args = tool_call["function"]["arguments"]
                tool_call_id = tool_call.get("id", "")

                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    logger.warning("[LOOP] Could not parse tool args for %s", name)
                    args = {}

                logger.info("[LOOP] Tool call: %s | arg_count=%d", name, len(args))

                if name in CONFIRMATION_REQUIRED_TOOLS:
                    # Resolve provider before storing
                    _resolve_provider_in_args(args, name, calendar_provider, mail_provider, self.memory)

                    self.memory.set_pending_action(name, args)
                    confirm_msg = format_confirmation_message(name, args)

                    logger.info("[LOOP] Propose tool triggered, returning confirmation")
                    propose_triggered = True

                    # Return immediately — user must confirm
                    return {
                        "message": confirm_msg,
                        "success": True,
                        "type": "confirmation_required",
                        "action_needed": "confirmation",
                        "intent": "LLM_DRIVEN",
                        "data": args,
                    }

                else:
                    # Read tool — execute and add result to messages
                    tool_result = await self._execute_read_tool(
                        name, args, user_id, calendar_provider, mail_provider
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                    })

            # If we only processed read tools, loop back to get LLM's natural response
            if not propose_triggered:
                continue

        # Safety net if loop exhausts
        return {
            "message": "I was unable to complete your request. Please try again.",
            "success": False,
            "type": "error",
            "intent": "LLM_DRIVEN",
        }

    # ── Read tool execution ───────────────────────────────────────────────────

    async def _execute_read_tool(
        self,
        name: str,
        args: Dict[str, Any],
        user_id: str,
        calendar_provider: Optional[str],
        mail_provider: Optional[str],
    ) -> Dict[str, Any]:
        """Execute a read (non-mutating) tool and return its result as a dict."""
        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")

        if name == "list_calendar_events":
            provider = _normalize_provider(args.get("provider") or calendar_provider or "google")
            endpoint = f"{base_url}/api/integrations/{provider}/calendar/events"
            params = {
                "user_id": user_id,
                "time_min": _ensure_rfc3339(args.get("start_date"), self.timezone),
                "time_max": _ensure_rfc3339(args.get("end_date"), self.timezone),
            }
            logger.info("[READ] list_calendar_events provider=%s range=%s→%s",
                        provider, params["time_min"], params["time_max"])
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(endpoint, params=params)
                if response.is_success:
                    data = response.json()
                    # Endpoint returns CalendarEventsResponse: {"events": [...], "total": N}
                    events_list = data.get("events", data) if isinstance(data, dict) else data
                    self.memory.last_provider = provider
                    self.memory.preferred_provider = provider
                    return {"events": events_list, "provider": provider, "count": len(events_list)}
                return {"error": f"HTTP {response.status_code}", "events": [], "provider": provider}
            except Exception as e:
                logger.error("[READ] list_calendar_events error: %s", e)
                return {"error": str(e), "events": [], "provider": provider}

        if name == "read_emails":
            provider_raw = args.get("provider") or mail_provider or "gmail"
            provider = _normalize_provider(provider_raw)
            count = args.get("count", 5)
            if provider == "google":
                endpoint = f"{base_url}/api/integrations/google/gmail/messages"
            else:
                endpoint = f"{base_url}/api/integrations/microsoft/mail/messages"
            params = {"user_id": user_id, "max_results": count}
            if args.get("from_sender"):
                params["sender"] = args["from_sender"]
            if args.get("subject_contains"):
                params["subject"] = args["subject_contains"]
            if args.get("since_date"):
                params["date_after"] = args["since_date"]
            if args.get("unread_only"):
                params["unread_only"] = "true"
            logger.info("[READ] read_emails provider=%s count=%s", provider, count)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(endpoint, params=params)
                if response.is_success:
                    emails = response.json()
                    self.memory.last_provider = provider
                    self.memory.preferred_provider = provider
                    email_list = emails.get("emails", []) if isinstance(emails, dict) else emails
                    if email_list:
                        first = email_list[0]
                        self.memory.last_email_thread_id = first.get("thread_id", "")
                        self.memory.last_email_message_id = first.get("id", "")
                        self.memory.last_email_subject = first.get("subject", "")
                        from_raw = first.get("from", "")
                        self.memory.last_email_sender = from_raw
                        import re as _re
                        _addr = _re.search(r"<([^>]+)>", from_raw)
                        self.memory.last_email_sender_address = _addr.group(1) if _addr else from_raw
                    return {"emails": emails, "provider": provider}
                return {"error": f"HTTP {response.status_code}", "emails": [], "provider": provider}
            except Exception as e:
                logger.error("[READ] read_emails error: %s", e)
                return {"error": str(e), "emails": [], "provider": provider}

        if name == "lookup_contact":
            name_query = args.get("name", "")
            provider_raw = args.get("provider") or mail_provider or "gmail"
            provider = _normalize_provider(provider_raw)
            if provider == "google":
                endpoint = f"{base_url}/api/integrations/google/gmail/messages"
            else:
                endpoint = f"{base_url}/api/integrations/microsoft/mail/messages"
            # Search for emails from/to this name to find their email address
            params_from = {"user_id": user_id, "max_results": 5, "sender": name_query}
            contacts_found = {}
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.get(endpoint, params=params_from)
                if resp.is_success:
                    emails_data = resp.json()
                    email_list = emails_data if isinstance(emails_data, list) else emails_data.get("emails", [])
                    for email in email_list:
                        from_field = email.get("from", "")
                        # Extract "Name <email>" pattern
                        import re as _re
                        match = _re.search(r"([^<]+?)\s*<([^>]+)>", from_field)
                        if match:
                            contact_name = match.group(1).strip()
                            contact_email = match.group(2).strip()
                        else:
                            contact_name = from_field
                            contact_email = from_field
                        key = contact_email.lower()
                        if key not in contacts_found:
                            contacts_found[key] = {"name": contact_name, "email": contact_email}
            except Exception as e:
                logger.error("[READ] lookup_contact error: %s", e)
                return {"error": str(e), "contacts": [], "provider": provider}
            contacts = list(contacts_found.values())
            if not contacts:
                return {
                    "contacts": [],
                    "provider": provider,
                    "message": f"No emails found from '{name_query}'. They may not be in your recent mail.",
                }
            return {"contacts": contacts, "provider": provider}

        if name == "read_email_detail":
            message_id = args.get("message_id", "")
            provider_raw = args.get("provider") or mail_provider or "gmail"
            provider = _normalize_provider(provider_raw)
            if provider == "google":
                endpoint = f"{base_url}/api/integrations/google/gmail/messages/{message_id}"
            else:
                endpoint = f"{base_url}/api/integrations/microsoft/mail/messages/{message_id}"
            logger.info("[READ] read_email_detail provider=%s message_id=%s", provider, message_id)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(endpoint, params={"user_id": user_id})
                if response.is_success:
                    data = response.json()
                    data.pop("body_html", None)
                    if data.get("body_text"):
                        data["body_text"] = data["body_text"][:3000]
                    if data.get("thread_id"):
                        self.memory.last_email_thread_id = data["thread_id"]
                    if data.get("id"):
                        self.memory.last_email_message_id = data["id"]
                    if data.get("subject"):
                        self.memory.last_email_subject = data["subject"]
                    from_raw = data.get("from", "")
                    if from_raw:
                        self.memory.last_email_sender = from_raw
                        import re as _re
                        _addr = _re.search(r"<([^>]+)>", from_raw)
                        self.memory.last_email_sender_address = _addr.group(1) if _addr else from_raw
                    logger.info(
                        "[READ] read_email_detail ok provider=%s message_id=%s has_body=%s",
                        provider, message_id, bool(data.get("body_text")),
                    )
                    return data
                return {"error": f"HTTP {response.status_code}", "provider": provider}
            except Exception as e:
                logger.error("[READ] read_email_detail error: %s", e)
                return {"error": str(e), "provider": provider}

        if name == "read_email_thread":
            thread_id = args.get("thread_id", "")
            provider_raw = args.get("provider") or mail_provider or "gmail"
            provider = _normalize_provider(provider_raw)
            if provider == "google":
                endpoint = f"{base_url}/api/integrations/google/gmail/threads/{thread_id}"
            else:
                endpoint = f"{base_url}/api/integrations/microsoft/mail/threads/{thread_id}"
            logger.info("[READ] read_email_thread provider=%s thread_id=%s", provider, thread_id)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(endpoint, params={"user_id": user_id})
                if response.is_success:
                    data = response.json()
                    messages = data.get("messages", [])[:8]
                    for msg in messages:
                        msg.pop("body_html", None)
                        if msg.get("body_text"):
                            msg["body_text"] = msg["body_text"][:2000]
                    data["messages"] = messages
                    if messages:
                        first_msg = messages[0]
                        last_msg = messages[-1]
                        self.memory.last_email_thread_id = data.get("thread_id") or first_msg.get("thread_id", "")
                        self.memory.last_email_message_id = last_msg.get("id", "")
                        if first_msg.get("subject"):
                            self.memory.last_email_subject = first_msg["subject"]
                        from_raw = first_msg.get("from", "")
                        if from_raw:
                            self.memory.last_email_sender = from_raw
                            import re as _re
                            _addr = _re.search(r"<([^>]+)>", from_raw)
                            self.memory.last_email_sender_address = _addr.group(1) if _addr else from_raw
                    logger.info(
                        "[READ] read_email_thread ok provider=%s thread_id=%s message_count=%d",
                        provider, thread_id, len(messages),
                    )
                    return data
                return {"error": f"HTTP {response.status_code}", "provider": provider}
            except Exception as e:
                logger.error("[READ] read_email_thread error: %s", e)
                return {"error": str(e), "provider": provider}

        return {"error": f"Unknown read tool: {name}"}

    # ── Pending action execution ──────────────────────────────────────────────

    async def _execute_pending_action(
        self,
        user_id: str,
        calendar_provider: Optional[str],
        mail_provider: Optional[str],
    ) -> Dict[str, Any]:
        """Execute the stored pending action after user confirmation."""
        pending = self.memory.get_pending_action()
        if not pending:
            return {
                "message": "Nothing to confirm. What would you like to do?",
                "success": False,
                "type": "error",
                "intent": "LLM_DRIVEN",
            }

        tool_name = pending["type"]
        args = pending["data"]
        logger.info("[EXEC] Executing confirmed action: %s", tool_name)

        if tool_name == "propose_create_calendar_event":
            return await self._exec_create_calendar(args, user_id)
        if tool_name == "propose_update_calendar_event":
            return await self._exec_update_calendar(args, user_id)
        if tool_name == "propose_delete_calendar_event":
            return await self._exec_delete_calendar(args, user_id)
        if tool_name == "propose_send_email":
            return await self._exec_send_email(args, user_id)
        if tool_name == "propose_reply_email":
            return await self._exec_reply_email(args, user_id)
        if tool_name == "propose_create_recurring_event":
            return await self._exec_create_recurring_event(args, user_id)

        # Unknown propose_ tool — clear and acknowledge
        self.memory.clear_pending_action()
        self.memory.clear_active_task()
        return {"message": "Done.", "success": True, "type": "confirmation", "intent": "LLM_DRIVEN"}

    async def _cancel_pending_action(self) -> Dict[str, Any]:
        """Cancel the stored pending action."""
        self.memory.clear_pending_action()
        self.memory.clear_active_task()
        msg = "Got it, cancelled."
        self.memory.add_message("assistant", msg)
        return {"message": msg, "success": True, "type": "cancelled", "intent": "LLM_DRIVEN"}

    # ── Calendar create ───────────────────────────────────────────────────────

    async def _exec_create_calendar(self, args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute propose_create_calendar_event after user confirmation."""
        if not self.memory.get_pending_action():
            return {"message": "No pending calendar event to create.", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        title = args.get("title", "Meeting")
        start_str = args.get("start", "")
        end_str = args.get("end", "")
        provider = _normalize_provider(args.get("provider", "google"))

        try:
            start_dt = _parse_and_localize(start_str, self.timezone, self.tz_name)
            end_dt = _parse_and_localize(end_str, self.timezone, self.tz_name)
        except Exception as e:
            return {"message": f"Invalid event times: {e}", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        request_id = _compute_calendar_request_id(
            user_id, title, start_dt.isoformat(), end_dt.isoformat(), self.tz_name
        )

        async with _CALENDAR_IDEMPOTENCY_LOCK:
            if request_id in _CALENDAR_IDEMPOTENCY_STORE:
                cached = _CALENDAR_IDEMPOTENCY_STORE[request_id]
                if cached != "__pending__":
                    self.memory.clear_pending_action()
                    self.memory.clear_active_task()
                    return {
                        "message": f"This event already exists (ID: {cached}).",
                        "success": True,
                        "type": "calendar_created",
                        "data": {"event_id": cached, "idempotent": True},
                        "intent": "LLM_DRIVEN",
                    }
            _CALENDAR_IDEMPOTENCY_STORE[request_id] = "__pending__"

        payload: Dict[str, Any] = {
            "summary": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
        }
        if args.get("description"):
            payload["description"] = args["description"]
        if args.get("location"):
            payload["location"] = args["location"]
        if args.get("attendees"):
            payload["attendees"] = args["attendees"]
        payload["request_id"] = request_id

        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/integrations/{provider}/calendar/events"

        logger.info(
            "[EXEC] Calendar create requested provider=%s attendee_count=%d has_description=%s has_location=%s",
            provider,
            len(payload.get("attendees") or []),
            bool(payload.get("description")),
            bool(payload.get("location")),
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=payload, params={"user_id": user_id})

            logger.info("[EXEC] Calendar create ← status=%s", response.status_code)

            if response.is_success:
                event_data = response.json()
                event_id = event_data.get("id")
                if not event_id:
                    _CALENDAR_IDEMPOTENCY_STORE.pop(request_id, None)
                    return {
                        "message": "The calendar returned success but no event ID. Please check your calendar.",
                        "success": False,
                        "type": "error",
                        "intent": "LLM_DRIVEN",
                    }

                _CALENDAR_IDEMPOTENCY_STORE[request_id] = event_id
                self.memory.context["last_created_event_id"] = event_id
                self.memory.context["last_created_event_summary"] = title
                self.memory.context["last_created_event_provider"] = provider
                self.memory.preferred_provider = provider
                self.memory.add_to_history({**args, "type": "create_calendar_event", "event_id": event_id})
                self.memory.clear_pending_action()
                self.memory.clear_active_task()

                date_lbl = start_dt.strftime("%A, %B %d")
                time_lbl = start_dt.strftime("%H:%M")
                msg = f"Done. {title} is on your calendar for {date_lbl} at {time_lbl}."
                return {
                    "message": msg,
                    "success": True,
                    "type": "calendar_created",
                    "intent": "LLM_DRIVEN",
                    "data": {"event_id": event_id, "start": start_dt.isoformat(), "end": end_dt.isoformat()},
                }
            else:
                _CALENDAR_IDEMPOTENCY_STORE.pop(request_id, None)
                error_detail = _extract_error_detail(response)
                return {
                    "message": f"Failed to create the event (HTTP {response.status_code}): {error_detail}. Say yes to retry.",
                    "success": False,
                    "type": "error",
                    "intent": "LLM_DRIVEN",
                    "data": {"pending_action_preserved": True},
                }

        except httpx.TimeoutException:
            _CALENDAR_IDEMPOTENCY_STORE.pop(request_id, None)
            return {
                "message": "The calendar service timed out. Your event details are saved — say yes to retry.",
                "success": False,
                "type": "error",
                "intent": "LLM_DRIVEN",
                "data": {"pending_action_preserved": True},
            }
        except Exception as e:
            _CALENDAR_IDEMPOTENCY_STORE.pop(request_id, None)
            logger.error("[EXEC] Calendar create error: %s", e, exc_info=True)
            return {
                "message": f"Unexpected error: {e}. Your event details are saved — say yes to retry.",
                "success": False,
                "type": "error",
                "intent": "LLM_DRIVEN",
                "data": {"pending_action_preserved": True},
            }

    # ── Recurring calendar create ─────────────────────────────────────────────

    async def _exec_create_recurring_event(self, args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute propose_create_recurring_event after user confirmation."""
        title = args.get("title", "Meeting")
        start_str = args.get("start", "")
        end_str = args.get("end", "")
        provider = _normalize_provider(args.get("provider", "google"))

        try:
            start_dt = _parse_and_localize(start_str, self.timezone, self.tz_name)
            end_dt = _parse_and_localize(end_str, self.timezone, self.tz_name)
        except Exception as e:
            return {"message": f"Invalid event times: {e}", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        payload: Dict[str, Any] = {
            "summary": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "recurrence": args.get("recurrence", "weekly"),
        }
        if args.get("recurrence_end_date"):
            payload["recurrence_end_date"] = args["recurrence_end_date"]
        if args.get("recurrence_count"):
            payload["recurrence_count"] = args["recurrence_count"]
        if args.get("description"):
            payload["description"] = args["description"]
        if args.get("location"):
            payload["location"] = args["location"]

        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/integrations/{provider}/calendar/events"

        logger.info(
            "[EXEC] Recurring calendar create requested provider=%s recurrence=%s",
            provider,
            bool(payload.get("recurrence")),
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=payload, params={"user_id": user_id})

            if response.is_success:
                event_data = response.json()
                event_id = event_data.get("id")
                self.memory.context["last_created_event_id"] = event_id
                self.memory.context["last_created_event_summary"] = title
                self.memory.context["last_created_event_provider"] = provider
                self.memory.preferred_provider = provider
                self.memory.clear_pending_action()
                self.memory.clear_active_task()
                recurrence_label = {
                    "daily": "every day", "weekly": "every week", "biweekly": "every two weeks",
                    "monthly": "every month", "yearly": "every year",
                }.get(args.get("recurrence", "weekly"), args.get("recurrence", ""))
                date_lbl = start_dt.strftime("%A, %B %d")
                time_lbl = start_dt.strftime("%H:%M")
                msg = f"Done. '{title}' will repeat {recurrence_label}, starting {date_lbl} at {time_lbl}."
                return {"message": msg, "success": True, "type": "calendar_created", "intent": "LLM_DRIVEN",
                        "data": {"event_id": event_id, "start": start_dt.isoformat()}}
            else:
                error_detail = _extract_error_detail(response)
                return {
                    "message": f"Failed to create recurring event (HTTP {response.status_code}): {error_detail}. Say yes to retry.",
                    "success": False, "type": "error", "intent": "LLM_DRIVEN",
                    "data": {"pending_action_preserved": True},
                }
        except Exception as e:
            logger.error("[EXEC] Recurring calendar create error: %s", e, exc_info=True)
            return {
                "message": f"Error creating recurring event: {e}. Say yes to retry.",
                "success": False, "type": "error", "intent": "LLM_DRIVEN",
                "data": {"pending_action_preserved": True},
            }

    # ── Calendar update ───────────────────────────────────────────────────────

    async def _exec_update_calendar(self, args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute propose_update_calendar_event after user confirmation."""
        event_id = args.get("event_id")
        if not event_id:
            return {"message": "Lost track of which event to update. Please describe it again.", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        provider = _normalize_provider(args.get("provider", "google"))
        payload: Dict[str, Any] = {}

        if args.get("new_title"):
            payload["summary"] = args["new_title"]
        if args.get("new_description"):
            payload["description"] = args["new_description"]
        if args.get("new_location"):
            payload["location"] = args["new_location"]

        if args.get("new_start") or args.get("new_end"):
            try:
                if args.get("new_start"):
                    start_dt = _parse_and_localize(args["new_start"], self.timezone, self.tz_name)
                    payload["start"] = start_dt.isoformat()
                    # Default end to +1h from new start only when no explicit end given
                    if not args.get("new_end"):
                        payload["end"] = (start_dt + timedelta(hours=1)).isoformat()
                if args.get("new_end"):
                    end_dt = _parse_and_localize(args["new_end"], self.timezone, self.tz_name)
                    payload["end"] = end_dt.isoformat()
            except Exception as e:
                return {"message": f"Invalid time: {e}", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        if not payload:
            return {"message": "Nothing to update — no changes were specified.", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/integrations/{provider}/calendar/events/{event_id}"

        logger.info(
            "[EXEC] Calendar update requested provider=%s event_id=%s field_count=%d",
            provider,
            event_id,
            len(payload),
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(endpoint, json=payload, params={"user_id": user_id})

            if response.is_success:
                updated = response.json()
                self.memory.clear_pending_action()
                self.memory.clear_active_task()
                self.memory.preferred_provider = provider
                event_title = updated.get("summary", args.get("event_title", "the event"))
                # Keep context fresh so follow-up edits can reuse the same event_id
                self.memory.context["last_created_event_id"] = event_id
                self.memory.context["last_created_event_summary"] = event_title
                self.memory.context["last_created_event_provider"] = provider
                return {
                    "message": f'Done. "{event_title}" has been updated.',
                    "success": True,
                    "type": "calendar_updated",
                    "intent": "LLM_DRIVEN",
                    "data": updated,
                }
            else:
                error_detail = _extract_error_detail(response)
                return {
                    "message": f"Failed to update the event (HTTP {response.status_code}): {error_detail}.",
                    "success": False,
                    "type": "error",
                    "intent": "LLM_DRIVEN",
                }

        except Exception as e:
            logger.error("[EXEC] Calendar update error: %s", e, exc_info=True)
            return {"message": f"Unexpected error: {e}", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

    # ── Calendar delete ───────────────────────────────────────────────────────

    async def _exec_delete_calendar(self, args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute propose_delete_calendar_event after user confirmation."""
        event_id = args.get("event_id")
        if not event_id:
            return {"message": "Lost track of which event to delete. Please describe it again.", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        provider = _normalize_provider(args.get("provider", "google"))
        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/integrations/{provider}/calendar/events/{event_id}"

        logger.info("[EXEC] Calendar delete → DELETE %s", endpoint)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(endpoint, params={"user_id": user_id})

            if response.is_success:
                self.memory.clear_pending_action()
                self.memory.clear_active_task()
                title = args.get("event_title", "the event")
                return {
                    "message": f'Done. "{title}" has been removed from your calendar.',
                    "success": True,
                    "type": "calendar_deleted",
                    "intent": "LLM_DRIVEN",
                    "data": {},
                }
            else:
                error_detail = _extract_error_detail(response)
                return {
                    "message": f"Failed to delete the event (HTTP {response.status_code}): {error_detail}.",
                    "success": False,
                    "type": "error",
                    "intent": "LLM_DRIVEN",
                }

        except Exception as e:
            logger.error("[EXEC] Calendar delete error: %s", e, exc_info=True)
            return {"message": f"Unexpected error: {e}", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

    # ── Email send ────────────────────────────────────────────────────────────

    async def _exec_send_email(self, args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute propose_send_email after user confirmation."""
        if not self.memory.get_pending_action():
            return {"message": "No pending email to send.", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        to_list = args.get("to", [])
        if isinstance(to_list, str):
            to_list = [to_list]
        to_str = ", ".join(to_list)
        subject = args.get("subject", "(No Subject)")
        body = args.get("body", "")

        provider_raw = args.get("provider", "gmail")
        provider = _normalize_provider(provider_raw)

        payload: Dict[str, Any] = {
            "to": to_str if len(to_list) == 1 else to_list,
            "subject": subject,
            "body": body,
        }
        if args.get("cc"):
            payload["cc"] = args["cc"]

        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        if provider == "google":
            endpoint = f"{base_url}/api/integrations/google/gmail/send"
        else:
            endpoint = f"{base_url}/api/integrations/microsoft/mail/send"

        logger.info(
            "[EXEC] Email send requested provider=%s recipient_count=%d has_subject=%s",
            provider,
            len([addr for addr in to_str.split(",") if addr.strip()]),
            bool(subject),
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=payload, params={"user_id": user_id})

            if response.is_success:
                result_data = response.json()
                self.memory.clear_pending_action()
                self.memory.clear_active_task()
                self.memory.add_to_history({**args, "type": "send_email", "message_id": result_data.get("message_id")})
                to_name = to_list[0].split("@")[0].capitalize() if to_list else "them"
                return {
                    "message": f"Done, email sent to {to_name}.",
                    "success": True,
                    "type": "email_sent",
                    "intent": "LLM_DRIVEN",
                    "data": result_data,
                }
            else:
                error_detail = _extract_error_detail(response)
                return {
                    "message": f"Failed to send the email (HTTP {response.status_code}): {error_detail}. Say yes to retry.",
                    "success": False,
                    "type": "error",
                    "intent": "LLM_DRIVEN",
                    "data": {"pending_action_preserved": True},
                }

        except httpx.TimeoutException:
            return {
                "message": "The email service timed out. Your email is saved — say yes to retry.",
                "success": False,
                "type": "error",
                "intent": "LLM_DRIVEN",
                "data": {"pending_action_preserved": True},
            }
        except Exception as e:
            logger.error("[EXEC] Email send error: %s", e, exc_info=True)
            return {
                "message": f"Unexpected error: {e}. Your email is saved — say yes to retry.",
                "success": False,
                "type": "error",
                "intent": "LLM_DRIVEN",
                "data": {"pending_action_preserved": True},
            }

    # ── Email reply ───────────────────────────────────────────────────────────

    async def _exec_reply_email(self, args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute propose_reply_email after user confirmation."""
        if not self.memory.get_pending_action():
            return {"message": "No pending reply to send.", "success": False, "type": "error", "intent": "LLM_DRIVEN"}

        thread_id = args.get("thread_id", "")
        if not thread_id:
            self.memory.clear_pending_action()
            self.memory.clear_active_task()
            return {
                "message": (
                    "I need the thread ID to reply to this email. "
                    "Please read or select the email first, then I can send your reply."
                ),
                "success": False,
                "type": "error",
                "intent": "LLM_DRIVEN",
            }
        body = args.get("body", "")
        subject = args.get("original_subject", "")

        provider_raw = args.get("provider", "gmail")
        provider = _normalize_provider(provider_raw)

        payload: Dict[str, Any] = {"body": body, "subject": f"Re: {subject}"}
        if provider == "google":
            payload["thread_id"] = thread_id
            endpoint_path = "google/gmail/send"
        else:
            payload["reply_to_id"] = thread_id
            endpoint_path = "microsoft/mail/send"

        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        endpoint = f"{base_url}/api/integrations/{endpoint_path}"

        logger.info("[EXEC] Email reply requested provider=%s", provider)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(endpoint, json=payload, params={"user_id": user_id})

            if response.is_success:
                self.memory.clear_pending_action()
                self.memory.clear_active_task()
                return {
                    "message": "Reply sent.",
                    "success": True,
                    "type": "email_sent",
                    "intent": "LLM_DRIVEN",
                    "data": response.json(),
                }
            else:
                error_detail = _extract_error_detail(response)
                return {
                    "message": f"Failed to send the reply (HTTP {response.status_code}): {error_detail}.",
                    "success": False,
                    "type": "error",
                    "intent": "LLM_DRIVEN",
                }

        except Exception as e:
            logger.error("[EXEC] Email reply error: %s", e, exc_info=True)
            return {"message": f"Unexpected error: {e}", "success": False, "type": "error", "intent": "LLM_DRIVEN"}


# ==============================================================================
# MODULE-LEVEL HELPER FUNCTIONS
# ==============================================================================

def _normalize_provider(raw_provider: str) -> str:
    """Normalise a provider string to 'google' or 'microsoft'."""
    if not raw_provider:
        return "google"
    p = raw_provider.strip().lower()
    if p in ("google", "google calendar", "gcal"):
        return "google"
    if p in ("gmail", "google mail"):
        return "google"
    if p in ("microsoft", "outlook", "ms", "office365", "office 365", "outlook calendar"):
        return "microsoft"

    try:
        from services.nlu_service import MS_KEYWORDS, GOOGLE_KEYWORDS
        for kw in MS_KEYWORDS:
            if kw in p:
                return "microsoft"
        for kw in GOOGLE_KEYWORDS:
            if kw in p:
                return "google"
    except ImportError:
        pass

    return "google"


def _ensure_rfc3339(dt_str: Optional[str], tz_obj) -> Optional[str]:
    """
    Ensure a datetime string has timezone info as required by the Google Calendar API.

    The LLM generates naive ISO strings (e.g. '2026-03-22T00:00:00').
    Google requires RFC 3339 with offset (e.g. '2026-03-22T00:00:00+01:00').
    This function localizes naive strings using the server timezone.
    """
    if not dt_str:
        return dt_str
    try:
        clean = dt_str[:19]
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is not None:
            return dt.isoformat()
        try:
            aware = tz_obj.localize(dt, is_dst=None)
        except Exception:
            aware = tz_obj.localize(dt, is_dst=False)
        return aware.isoformat()
    except Exception:
        # Last resort: append Z (UTC) so Google doesn't reject it
        return dt_str if dt_str.endswith("Z") or "+" in dt_str[-6:] else dt_str + "Z"


def _parse_and_localize(iso_str: str, tz_obj, tz_name: str):
    """Parse an ISO 8601 datetime string and apply tz if naive."""
    clean = iso_str[:19]  # strip any trailing tz info the LLM may have added
    try:
        dt = datetime.fromisoformat(clean)
    except ValueError:
        dt = datetime.fromisoformat(iso_str)

    if dt.tzinfo is not None:
        return dt

    try:
        return tz_obj.localize(dt, is_dst=None)
    except Exception:
        return tz_obj.localize(dt, is_dst=False)


def _extract_error_detail(response) -> str:
    """Extract a human-readable error detail from an HTTP response."""
    try:
        error_json = response.json()
        if isinstance(error_json, dict):
            detail = error_json.get("detail", {})
            if isinstance(detail, dict):
                return detail.get("message", str(detail))
            return str(detail)
    except Exception:
        pass
    return response.text or f"HTTP {response.status_code}"


def _resolve_provider_in_args(
    args: Dict[str, Any],
    tool_name: str,
    calendar_provider: Optional[str],
    mail_provider: Optional[str],
    memory: ConversationMemory,
) -> None:
    """
    Fill in the provider field in tool args if the LLM left it out.
    Mutates args in place.
    """
    if args.get("provider"):
        return  # LLM already specified one

    # Use session preference if available
    if memory.preferred_provider:
        args["provider"] = memory.preferred_provider
        return

    # Use the API-supplied provider based on tool type
    is_email_tool = tool_name in ("propose_send_email", "propose_reply_email")
    if is_email_tool and mail_provider:
        args["provider"] = mail_provider
    elif not is_email_tool and calendar_provider:
        args["provider"] = calendar_provider


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
            return d.strftime("%A")
        return d.strftime("%A, %B %d")
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


def get_current_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_tomorrow_date_str() -> str:
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
