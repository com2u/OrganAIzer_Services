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

    # Conversation / person context (Batch 2B — in-session only, no persistence)
    last_contact_name: Optional[str] = None
    last_contact_email: Optional[str] = None
    last_conversation_summary: Optional[str] = None
    last_thread_ids: List[str] = field(default_factory=list)

    # Draft review (Batch 4 — in-session only, no persistence).
    # Shape: {"kind": "send"|"reply", "args": {... full body ...}, "updated_at": iso}.
    # Lifecycle: set when propose_send/reply_email enters the pending state;
    # cleared on successful send OR on explicit cancel. SURVIVES non-confirm /
    # non-cancel edit turns so the LLM can iterate without losing the body.
    draft: Optional[Dict[str, Any]] = None

    MAX_THREAD_IDS = 20

    def set_draft(self, kind: str, args: Dict[str, Any]) -> None:
        """Store the full draft (including body) for in-session edits."""
        self.draft = {
            "kind": kind,
            "args": dict(args),
            "updated_at": datetime.now().isoformat(),
        }
        logger.info("[MEMORY] Draft set: kind=%s body_chars=%d",
                    kind, len(args.get("body", "") or ""))

    def clear_draft(self) -> None:
        if self.draft:
            logger.info("[MEMORY] Draft cleared (kind=%s)", self.draft.get("kind"))
        self.draft = None

    def remember_thread_id(self, thread_id: Optional[str]) -> None:
        """Record a thread_id in MRU order, capped at MAX_THREAD_IDS."""
        if not thread_id:
            return
        if thread_id in self.last_thread_ids:
            self.last_thread_ids.remove(thread_id)
        self.last_thread_ids.insert(0, thread_id)
        if len(self.last_thread_ids) > self.MAX_THREAD_IDS:
            self.last_thread_ids = self.last_thread_ids[: self.MAX_THREAD_IDS]

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
        if self.memory.last_contact_name:
            contact_line = f"Last person discussed: {self.memory.last_contact_name}"
            if self.memory.last_contact_email:
                contact_line += f" ({self.memory.last_contact_email})"
            context_lines.append(contact_line)
        if self.memory.last_thread_ids:
            shown = ", ".join(self.memory.last_thread_ids[:5])
            context_lines.append(f"Recent thread_ids: {shown}")
        if self.memory.last_conversation_summary:
            context_lines.append(
                f"Last conversation summary: {self.memory.last_conversation_summary[:240]}"
            )
        if self.memory.draft:
            d_args = self.memory.draft.get("args", {})
            d_kind = self.memory.draft.get("kind", "send")
            if d_kind == "reply":
                d_subject = d_args.get("original_subject", "")
                d_to_display = "(thread reply)"
            else:
                d_subject = d_args.get("subject", "")
                d_to_raw = d_args.get("to", [])
                if isinstance(d_to_raw, list):
                    d_to_display = ", ".join(str(x) for x in d_to_raw)
                else:
                    d_to_display = str(d_to_raw)
            d_body_chars = len(d_args.get("body", "") or "")
            # Metadata only — do NOT embed the body string. The full body lives
            # in memory.draft["args"]["body"] and is used when the user confirms.
            context_lines.append(
                f"Pending draft ({d_kind}): subject='{d_subject}', "
                f"to={d_to_display}, body_chars={d_body_chars}"
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
            "- Draft review loop: when a 'Pending draft' line appears in session context "
            "above, the user already has an email draft awaiting send. Treat the user's "
            "next message as one of: (a) explicit confirmation — the system handles 'yes' "
            "and equivalents and will send; (b) explicit cancellation — the system handles "
            "'cancel'/'no' and discards the draft; (c) an edit request like 'make it "
            "shorter', 'drop the apology', 'add the deadline'. For edits, call "
            "propose_send_email (or propose_reply_email for a thread reply) again with the "
            "FULL updated body — the system replaces the pending draft and re-shows the "
            "user a fresh confirmation containing the new body. Never silently send: the "
            "user must always respond 'yes' to a fresh confirmation message before anything "
            "is actually sent. If the user asks an unrelated question while a draft is "
            "pending, answer normally — the draft stays in memory and the user can resume.\n"
            "- read_emails has a 'scope' parameter: 'inbox' (default), 'sent', or 'both'. "
            "Use scope='sent' or scope='both' for questions about follow-ups, last contact, "
            "conversation history, what the user previously wrote, or whether someone has replied. "
            "Do not assume the inbox alone covers these — outbound messages live in 'sent'. "
            "Each email's 'direction' field is 'inbound' or 'outbound'.\n"
            "- For conversation history with a specific person (relationship context, "
            "'did Patrick reply', 'what did I last send Bernd', 'status with legal'): "
            "call read_emails with scope='both' and pass the person's name or email as "
            "from_sender — the system mirrors it to 'recipient' on the sent side so you "
            "get inbound and outbound with one call. Use from_sender for the inbound side, "
            "recipient for the outbound side, or both. If you have only a name and lookups "
            "feel imprecise (or if multiple people share a first name), call lookup_contact "
            "first to resolve the email address, then use that email with read_emails. "
            "For deeper context on a specific thread surfaced by the timeline, follow up "
            "with read_email_thread(thread_id).\n"
            "- Person/conversation reasoning steps:\n"
            "  1. Resolve ambiguous names via lookup_contact when needed.\n"
            "  2. Pull the inbound + outbound timeline with read_emails(scope='both').\n"
            "  3. Inspect each message's 'direction' and 'received' to order events.\n"
            "  4. For substantive questions ('what was agreed', 'what's pending'), call "
            "read_email_thread on the most relevant thread_id for full body context.\n"
            "  5. Derive and surface, in plain prose: last contact date, who wrote last, "
            "whether a reply appears pending, the key discussion themes, commitments or "
            "promises either side made, and one suggested next action.\n"
            "- Reply-status reasoning rules:\n"
            "  * If the newest message has direction='outbound', a reply from the other "
            "party is likely pending — say so unless the body clearly closed the loop.\n"
            "  * If the newest message has direction='inbound', no reply is owed by them; "
            "the ball is in the user's court if they previously promised an action.\n"
            "  * Always check the actual thread body before declaring 'no reply' — a single "
            "message thread can already contain a complete answer.\n"
            "- Follow-up detection ('who am I waiting on', 'who should I follow up "
            "with', 'did Patrick reply', 'show sent emails nobody answered', "
            "'open follow-ups from last week'): call find_unanswered_followups. "
            "Pass person to scope to one recipient, days to widen or narrow the "
            "window (default 14, max 90). The tool is read-only — it never sends "
            "or drafts anything. After surfacing follow-ups, summarize them and "
            "ask whether the user wants to draft a reply or a nudge. Only use "
            "propose_send_email or propose_reply_email after the user explicitly "
            "asks to draft/send, and let the standard confirmation flow run.\n"
            "- Meeting prep behavior ('prepare me for my meeting with Patrick', "
            "'context for my call with Bernd'): pull conversation history with "
            "read_emails(scope='both') for the person, optionally drill into the most "
            "recent thread with read_email_thread, then produce a brief: (a) relationship "
            "context in one sentence, (b) open items / unanswered questions, (c) anything "
            "the user promised that is still outstanding, (d) two or three suggested "
            "talking points. Do not propose calendar actions unless the user asks.\n"
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
                    # Draft review (Batch 4): mirror email proposals into the
                    # draft slot so they survive non-confirm edit turns.
                    if name == "propose_send_email":
                        self.memory.set_draft("send", args)
                    elif name == "propose_reply_email":
                        self.memory.set_draft("reply", args)
                    confirm_msg = format_confirmation_message(name, args)

                    if name == "propose_create_calendar_event":
                        conflict_warning = await self._check_calendar_conflicts(
                            args.get("start", ""),
                            args.get("end", ""),
                            args.get("provider", "google"),
                            user_id,
                        )
                        if conflict_warning:
                            confirm_msg = confirm_msg + " " + conflict_warning

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

    # ── Calendar conflict check ───────────────────────────────────────────────

    async def _check_calendar_conflicts(
        self,
        start: str,
        end: str,
        provider: str,
        user_id: str,
    ) -> str:
        """
        Return a human-readable warning if any timed events overlap [start, end].
        Returns "" on no conflict, on auth failure, or on any exception — never
        blocks the confirmation gate.
        """
        if not start or not end:
            return ""
        try:
            norm = _normalize_provider(provider)
            base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            endpoint = f"{base_url}/api/integrations/{norm}/calendar/events"
            params = {
                "user_id": user_id,
                "time_min": _ensure_rfc3339(start, self.timezone),
                "time_max": _ensure_rfc3339(end, self.timezone),
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(endpoint, params=params)
            if not resp.is_success:
                return ""
            data = resp.json()
            events = data.get("events", []) if isinstance(data, dict) else data
            # Exclude bare-date all-day events (their start has no "T")
            timed = [e for e in events if "T" in str(e.get("start", ""))]
            if not timed:
                return ""
            logger.info("[CONFLICT] %d overlapping event(s) found", len(timed))
            names = [e.get("summary", "an event") for e in timed[:3]]
            if len(names) == 1:
                return f'Note: you already have "{names[0]}" during this time.'
            return (
                f"Note: you already have {len(timed)} event(s) during this time: "
                + ", ".join(f'"{n}"' for n in names) + "."
            )
        except Exception:
            return ""

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
            scope_raw = (args.get("scope") or "inbox").strip().lower()
            if scope_raw not in ("inbox", "sent", "both"):
                scope_raw = "inbox"
            if provider == "google":
                endpoint = f"{base_url}/api/integrations/google/gmail/messages"
            else:
                endpoint = f"{base_url}/api/integrations/microsoft/mail/messages"
            base_params: Dict[str, Any] = {"user_id": user_id, "max_results": count}
            if args.get("subject_contains"):
                base_params["subject"] = args["subject_contains"]
            if args.get("since_date"):
                base_params["date_after"] = args["since_date"]
            if args.get("unread_only"):
                base_params["unread_only"] = "true"

            # Person-aware filters. For scope='both' with only one side given,
            # mirror it: the LLM saying "Patrick" almost always means "the other
            # party", so inbound is filtered by from:Patrick and outbound by
            # to:Patrick, which is the symmetric thing to do.
            from_sender_arg = args.get("from_sender")
            recipient_arg = args.get("recipient")
            if scope_raw == "both" and (from_sender_arg or recipient_arg):
                inbox_sender = from_sender_arg or recipient_arg
                inbox_recipient = None
                sent_sender = None
                sent_recipient = recipient_arg or from_sender_arg
            else:
                inbox_sender = from_sender_arg
                inbox_recipient = recipient_arg
                sent_sender = from_sender_arg
                sent_recipient = recipient_arg

            async def _fetch_folder(folder: str) -> List[Dict[str, Any]]:
                params = dict(base_params)
                params["folder"] = folder
                if folder == "inbox":
                    if inbox_sender:
                        params["sender"] = inbox_sender
                    if inbox_recipient:
                        params["recipient"] = inbox_recipient
                else:  # sent
                    if sent_sender:
                        params["sender"] = sent_sender
                    if sent_recipient:
                        params["recipient"] = sent_recipient
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(endpoint, params=params)
                if not response.is_success:
                    logger.warning(
                        "[READ] read_emails folder=%s HTTP %s",
                        folder, response.status_code,
                    )
                    return []
                payload = response.json()
                items = payload.get("emails", []) if isinstance(payload, dict) else payload
                default_dir = "outbound" if folder == "sent" else "inbound"
                # List endpoints never include body fields, but strip defensively
                # so the LLM never receives body_text/body_html from a list result.
                for item in items:
                    item.setdefault("direction", default_dir)
                    item.pop("body_text", None)
                    item.pop("body_html", None)
                return items

            logger.info(
                "[READ] read_emails provider=%s scope=%s count=%s has_sender=%s has_recipient=%s",
                provider, scope_raw, count,
                bool(from_sender_arg), bool(recipient_arg),
            )
            try:
                if scope_raw == "both":
                    inbox_items = await _fetch_folder("inbox")
                    sent_items = await _fetch_folder("sent")
                    merged = inbox_items + sent_items
                    # Dedupe by id (same message can in rare cases appear in
                    # both result sets) and sort newest-first by received date.
                    seen: set = set()
                    deduped: List[Dict[str, Any]] = []
                    for item in merged:
                        eid = item.get("id")
                        if eid and eid in seen:
                            continue
                        if eid:
                            seen.add(eid)
                        deduped.append(item)
                    deduped.sort(key=lambda e: e.get("received", "") or "", reverse=True)
                    email_list = deduped
                else:
                    email_list = await _fetch_folder(scope_raw)

                self.memory.last_provider = provider
                self.memory.preferred_provider = provider
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
                # Conversation memory: when the caller scoped the query to a
                # specific person, record them as the current contact and
                # remember the threads we just touched so later read_email_thread
                # calls can reuse them without another list pass.
                conversation_person = from_sender_arg or recipient_arg
                if conversation_person:
                    self.memory.last_contact_name = conversation_person
                    if "@" in conversation_person:
                        self.memory.last_contact_email = conversation_person
                for item in email_list:
                    self.memory.remember_thread_id(item.get("thread_id"))
                return {
                    "emails": {
                        "emails": email_list,
                        "total": len(email_list),
                        "scope": scope_raw,
                    },
                    "provider": provider,
                    "scope": scope_raw,
                }
            except Exception as e:
                logger.error("[READ] read_emails error: %s", e)
                return {"error": str(e), "emails": [], "provider": provider, "scope": scope_raw}

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
            # Remember the first resolved contact so subsequent person-scoped
            # tool calls in the same session can prefer the canonical email.
            top = contacts[0]
            self.memory.last_contact_name = top.get("name") or name_query
            self.memory.last_contact_email = top.get("email")
            return {"contacts": contacts, "provider": provider}

        if name == "find_unanswered_followups":
            # Clamp inputs. Use explicit None check so 0 stays 0 (and clamps
            # to the floor) instead of being swallowed by `or 14`.
            person = (args.get("person") or "").strip() or None
            days_arg = args.get("days")
            if days_arg is None:
                days = 14
            else:
                try:
                    days = int(days_arg)
                except (TypeError, ValueError):
                    days = 14
            days = max(1, min(90, days))
            limit_arg = args.get("limit")
            if limit_arg is None:
                limit = 20
            else:
                try:
                    limit = int(limit_arg)
                except (TypeError, ValueError):
                    limit = 20
            limit = max(1, min(50, limit))

            provider_raw = args.get("provider") or mail_provider or "gmail"
            provider = _normalize_provider(provider_raw)
            if provider == "google":
                endpoint = f"{base_url}/api/integrations/google/gmail/messages"
            else:
                endpoint = f"{base_url}/api/integrations/microsoft/mail/messages"

            now_dt = datetime.now(self.timezone)
            date_after = (now_dt - timedelta(days=days)).strftime("%Y-%m-%d")

            base_p: Dict[str, Any] = {
                "user_id": user_id,
                "max_results": 50,
                "date_after": date_after,
            }
            sent_p: Dict[str, Any] = dict(base_p, folder="sent")
            inbox_p: Dict[str, Any] = dict(base_p, folder="inbox")
            if person:
                sent_p["recipient"] = person
                inbox_p["sender"] = person

            async def _fetch(params: Dict[str, Any]) -> List[Dict[str, Any]]:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(endpoint, params=params)
                if not resp.is_success:
                    logger.warning(
                        "[READ] find_unanswered_followups HTTP %s folder=%s",
                        resp.status_code, params.get("folder"),
                    )
                    return []
                payload = resp.json()
                items = payload.get("emails", []) if isinstance(payload, dict) else payload
                # List endpoints never include body fields — strip defensively
                # so they never escape this tool either.
                for it in items:
                    it.pop("body_text", None)
                    it.pop("body_html", None)
                return items

            logger.info(
                "[READ] find_unanswered_followups provider=%s person=%s days=%d limit=%d",
                provider, bool(person), days, limit,
            )
            try:
                sent_items = await _fetch(sent_p)
                inbox_items = await _fetch(inbox_p)
            except Exception as e:
                logger.error("[READ] find_unanswered_followups fetch error: %s", e)
                return {"error": str(e), "followups": [], "count": 0, "provider": provider}

            # Build {thread_id: newest_inbound_datetime}
            latest_inbound: Dict[str, datetime] = {}
            for m in inbox_items:
                tid = m.get("thread_id") or ""
                if not tid:
                    continue
                dt = _parse_email_date(m.get("received", ""))
                if dt is None:
                    continue
                prev = latest_inbound.get(tid)
                if prev is None or _safe_dt_lt(prev, dt):
                    latest_inbound[tid] = dt

            # Process sent newest first, one follow-up per thread.
            sent_sorted = sorted(
                sent_items,
                key=lambda m: m.get("received") or "",
                reverse=True,
            )

            import re as _re

            followups: List[Dict[str, Any]] = []
            seen_threads: set = set()
            for m in sent_sorted:
                tid = m.get("thread_id") or ""
                if tid and tid in seen_threads:
                    continue
                if tid:
                    seen_threads.add(tid)

                sent_dt = _parse_email_date(m.get("received", ""))
                latest_in = latest_inbound.get(tid)
                awaiting = (
                    latest_in is None
                    or (sent_dt is not None and _safe_dt_lt(latest_in, sent_dt))
                )
                if not awaiting:
                    continue

                # Extract recipient as person/email
                to_field = m.get("to", "") or ""
                email_addr = ""
                display_name = ""
                match = _re.search(r"<([^>]+)>", to_field)
                if match:
                    email_addr = match.group(1)
                    display_name = to_field.split("<")[0].strip().strip('"')
                elif "@" in to_field:
                    email_addr = to_field.split(",")[0].strip()
                    display_name = email_addr
                else:
                    display_name = to_field
                    email_addr = to_field

                days_waiting: Optional[int] = None
                if sent_dt is not None:
                    try:
                        if sent_dt.tzinfo is None:
                            sent_aware = self.timezone.localize(sent_dt)
                        else:
                            sent_aware = sent_dt
                        delta = (now_dt - sent_aware).days
                        days_waiting = max(0, delta)
                    except Exception:
                        days_waiting = None

                followups.append({
                    "person": display_name or email_addr or to_field or "unknown",
                    "email": email_addr or to_field or "",
                    "subject": m.get("subject", "(No Subject)"),
                    "sent_date": m.get("received", ""),
                    "thread_id": tid,
                    "message_id": m.get("id", ""),
                    "preview": (m.get("preview", "") or "")[:200],
                    "days_waiting": days_waiting,
                    "reason": "No later inbound reply found in this thread",
                })
                if len(followups) >= limit:
                    break

            return {
                "followups": followups,
                "count": len(followups),
                "provider": provider,
            }

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
                    # Record this thread in the MRU list so it stays accessible
                    # if the user pivots to another topic and back.
                    self.memory.remember_thread_id(
                        data.get("thread_id") or thread_id
                    )
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
        """Cancel the stored pending action and discard any in-flight draft."""
        self.memory.clear_pending_action()
        self.memory.clear_active_task()
        self.memory.clear_draft()
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
                self.memory.clear_draft()
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
                self.memory.clear_draft()
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

def _parse_email_date(s: Optional[str]) -> Optional[datetime]:
    """Best-effort parse of an email Date/receivedDateTime string.

    Handles ISO 8601 with trailing 'Z' (Outlook style) and RFC 2822 (Gmail style).
    Returns None when both attempts fail — callers should treat that as
    'unknown date' rather than zero.
    """
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s)
    except Exception:
        return None


def _safe_dt_lt(a: datetime, b: datetime) -> bool:
    """Compare two datetimes safely even when one is naive and one is aware."""
    if (a.tzinfo is None) != (b.tzinfo is None):
        a = a.replace(tzinfo=None)
        b = b.replace(tzinfo=None)
    return a < b


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
