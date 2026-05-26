"""
Tool definitions for the LLM-driven Executive Agent.

These are passed to the LLM via the OpenAI-compatible function-calling API
(supported by Gemini 2.5 Flash through OpenRouter).

Rules:
- list_* and read_* tools execute immediately and return results to the LLM
- propose_* tools require user confirmation before being executed
"""

from datetime import datetime
from typing import Any, Dict

# ── Tool schemas (OpenAI function-calling format) ──────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": (
                "List calendar events within a date range. "
                "Use this to answer questions about upcoming or past events, "
                "and also before proposing an update or delete so you know the event ID. "
                "Each returned event has an 'id' field — that value is the event_id "
                "required by propose_update_calendar_event and propose_delete_calendar_event."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start of range in ISO 8601 format, e.g. 2026-03-22T00:00:00",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End of range in ISO 8601 format, e.g. 2026-03-22T23:59:59",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["google", "outlook"],
                        "description": "Calendar provider. Omit if unknown — the system will resolve it.",
                    },
                },
                "required": ["start_date", "end_date"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_calendar_event",
            "description": (
                "Propose creating a new calendar event. "
                "The user must confirm before the event is actually created. "
                "Only call this when you have a title, start, and end time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title"},
                    "start": {
                        "type": "string",
                        "description": "Start time in ISO 8601 format without timezone, e.g. 2026-03-23T10:00:00",
                    },
                    "end": {
                        "type": "string",
                        "description": "End time in ISO 8601 format without timezone, e.g. 2026-03-23T11:00:00",
                    },
                    "description": {"type": "string", "description": "Event description (optional)"},
                    "location": {"type": "string", "description": "Event location (optional)"},
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Attendee email addresses (optional)",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["google", "outlook"],
                        "description": "Calendar provider",
                    },
                },
                "required": ["title", "start", "end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_calendar_event",
            "description": (
                "Propose updating an existing calendar event. "
                "Always call list_calendar_events first to obtain the event_id. "
                "The user must confirm before the change is applied."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "ID of the event to update"},
                    "event_title": {"type": "string", "description": "Current title of the event (for display)"},
                    "new_title": {"type": "string", "description": "New title (optional)"},
                    "new_start": {
                        "type": "string",
                        "description": "New start time ISO 8601 without timezone (optional)",
                    },
                    "new_end": {
                        "type": "string",
                        "description": "New end time ISO 8601 without timezone (optional)",
                    },
                    "new_location": {"type": "string", "description": "New location (optional)"},
                    "new_description": {"type": "string", "description": "New description (optional)"},
                    "provider": {
                        "type": "string",
                        "enum": ["google", "outlook"],
                        "description": "Calendar provider",
                    },
                },
                "required": ["event_id", "event_title"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete_calendar_event",
            "description": (
                "Propose deleting a calendar event. "
                "Always call list_calendar_events first to obtain the event_id. "
                "The user must confirm before the event is removed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "ID of the event to delete"},
                    "event_title": {"type": "string", "description": "Title of the event (for confirmation display)"},
                    "provider": {
                        "type": "string",
                        "enum": ["google", "outlook"],
                        "description": "Calendar provider",
                    },
                },
                "required": ["event_id", "event_title"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_emails",
            "description": (
                "Read recent emails. By default reads the inbox (scope='inbox'). "
                "Use scope='sent' to read messages the user has sent, or scope='both' "
                "for a merged timeline of inbound + outbound — essential for follow-up, "
                "last-contact, and conversation-history questions. "
                "Supports filtering by sender, subject keywords, date, and read/unread status. "
                "Each returned email has a 'direction' field of 'inbound' or 'outbound'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of emails to fetch (default 5)",
                    },
                    "from_sender": {
                        "type": "string",
                        "description": "Filter by sender name or email address (optional). Matches the 'From' field.",
                    },
                    "recipient": {
                        "type": "string",
                        "description": (
                            "Filter by recipient name or email. Use for sent-mail "
                            "conversation lookups: combined with scope='sent' or scope='both', "
                            "this finds messages the user sent to a specific person."
                        ),
                    },
                    "subject_contains": {
                        "type": "string",
                        "description": "Filter emails whose subject contains this text (optional)",
                    },
                    "since_date": {
                        "type": "string",
                        "description": "Return only emails received on or after this date, ISO 8601 e.g. 2026-03-01 (optional)",
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "When true, return only unread emails (optional, default false)",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["inbox", "sent", "both"],
                        "description": (
                            "Which mailbox to read. 'inbox' (default) for received messages, "
                            "'sent' for messages the user has sent, 'both' for a merged "
                            "inbound+outbound timeline. Use 'both' or 'sent' when answering "
                            "'did I write to X?', 'did they reply?', or 'when did we last talk?'."
                        ),
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["gmail", "outlook"],
                        "description": "Email provider",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email_detail",
            "description": (
                "Read the full content of a single email by message ID. "
                "Use this when you need the email body to extract appointment details, "
                "understand full context, or draft a reply. "
                "Call read_emails first to get the message_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The message ID of the email to read (from read_emails result)",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["gmail", "outlook"],
                        "description": "Email provider",
                    },
                },
                "required": ["message_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email_thread",
            "description": (
                "Read all messages in an email thread by thread ID. "
                "Use this to get full conversation context before replying or "
                "extracting meeting details from a thread. "
                "Call read_emails first to get the thread_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {
                        "type": "string",
                        "description": "The thread ID (from read_emails result)",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["gmail", "outlook"],
                        "description": "Email provider",
                    },
                },
                "required": ["thread_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_send_email",
            "description": (
                "Propose sending an email. "
                "The user must confirm before it is sent. "
                "Only call this when you have recipients, subject, and body."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient email addresses",
                    },
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body (plain text)"},
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CC recipients (optional)",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["gmail", "outlook"],
                        "description": "Email provider",
                    },
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_reply_email",
            "description": (
                "Propose replying to an email. "
                "The user must confirm before it is sent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Thread ID of the email to reply to"},
                    "original_subject": {
                        "type": "string",
                        "description": "Subject of the original email (for display)",
                    },
                    "body": {"type": "string", "description": "Reply body (plain text)"},
                    "provider": {
                        "type": "string",
                        "enum": ["gmail", "outlook"],
                        "description": "Email provider",
                    },
                },
                "required": ["thread_id", "original_subject", "body"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_unanswered_followups",
            "description": (
                "Find sent emails that have no later inbound reply in the same thread — "
                "i.e. messages the user is awaiting a response on. Use for questions like "
                "'who am I waiting on', 'who should I follow up with', 'did Patrick reply', "
                "'what follow-ups are open'. Read-only: never sends or drafts anything. "
                "Returns a sorted (newest sent first) list of followups with person, email, "
                "subject, sent_date, thread_id, message_id, preview, days_waiting and a "
                "reason string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "person": {
                        "type": "string",
                        "description": (
                            "Optional. Limit follow-up detection to a single recipient "
                            "(name or email). Applied as recipient on sent queries and as "
                            "sender on inbox queries."
                        ),
                    },
                    "days": {
                        "type": "integer",
                        "description": (
                            "Look back this many days. Default 14, clamped to [1, 90]."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Maximum number of followups to return. Default 20, clamped to [1, 50]."
                        ),
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["gmail", "outlook"],
                        "description": "Email provider",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_contact",
            "description": (
                "Look up a contact's email address by name. "
                "Searches your email history to find the most recent email address "
                "associated with the given name. Use this before propose_send_email "
                "when the user refers to someone by name but you don't have their email address."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name or partial name of the contact to look up",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["gmail", "outlook"],
                        "description": "Email provider to search (optional)",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_recurring_event",
            "description": (
                "Propose creating a recurring calendar event. "
                "The user must confirm before the event is created. "
                "Use this for events that repeat (daily, weekly, monthly, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title"},
                    "start": {
                        "type": "string",
                        "description": "First occurrence start time ISO 8601, e.g. 2026-03-23T10:00:00",
                    },
                    "end": {
                        "type": "string",
                        "description": "First occurrence end time ISO 8601, e.g. 2026-03-23T11:00:00",
                    },
                    "recurrence": {
                        "type": "string",
                        "enum": ["daily", "weekly", "biweekly", "monthly", "yearly"],
                        "description": "How often the event repeats",
                    },
                    "recurrence_end_date": {
                        "type": "string",
                        "description": "Last date of recurrence in ISO 8601 format, e.g. 2026-12-31 (optional — omit for indefinite)",
                    },
                    "recurrence_count": {
                        "type": "integer",
                        "description": "Number of occurrences (optional — use instead of recurrence_end_date)",
                    },
                    "description": {"type": "string", "description": "Event description (optional)"},
                    "location": {"type": "string", "description": "Event location (optional)"},
                    "provider": {
                        "type": "string",
                        "enum": ["google", "outlook"],
                        "description": "Calendar provider",
                    },
                },
                "required": ["title", "start", "end", "recurrence"],
                "additionalProperties": False,
            },
        },
    },
]

# Tools that need user confirmation before execution
CONFIRMATION_REQUIRED_TOOLS = frozenset([
    "propose_create_calendar_event",
    "propose_update_calendar_event",
    "propose_delete_calendar_event",
    "propose_send_email",
    "propose_reply_email",
    "propose_create_recurring_event",
])

# Words that mean "yes, go ahead"
CONFIRM_WORDS = frozenset([
    "yes", "y", "yep", "yeah", "sure", "ok", "okay",
    "confirm", "proceed", "affirmative", "correct", "right",
    "do it", "go ahead", "send it", "create it", "sounds good", "looks good",
])

# Words that mean "no, cancel"
CANCEL_WORDS = frozenset([
    "no", "cancel", "stop", "abort", "nope", "nah",
    "never mind", "nevermind", "discard", "skip", "dont", "don't",
])


def is_confirm(text: str) -> bool:
    """Return True if the text is a clear confirmation."""
    lower = text.strip().lower()
    if lower in CONFIRM_WORDS:
        return True
    return any(phrase in lower for phrase in [
        "go ahead", "do it", "send it", "create it", "sounds good", "looks good",
    ])


def is_cancel(text: str) -> bool:
    """Return True if the text is a clear cancellation (with no other intent)."""
    lower = text.strip().lower()
    # Only treat as pure cancel if the message is short (long messages likely modify)
    if len(lower.split()) > 4:
        return False
    if lower in CANCEL_WORDS:
        return True
    return any(phrase in lower for phrase in [
        "never mind", "don't do it", "cancel that", "forget it",
    ])


def format_confirmation_message(tool_name: str, args: Dict[str, Any]) -> str:
    """
    Build a clean confirmation message from tool arguments.
    No markdown, no emojis — consistent with existing agent style.
    """
    from services.executive_agent_service import _normalize_provider

    if tool_name == "propose_create_calendar_event":
        title = args.get("title", "event")
        start = args.get("start", "")
        try:
            dt = datetime.fromisoformat(start[:19])
            date_str = dt.strftime("%A, %B %d")
            time_str = dt.strftime("%H:%M")
            time_part = f" at {time_str}"
        except Exception:
            date_str = start
            time_part = ""
        provider_label = "Outlook" if _normalize_provider(args.get("provider", "google")) == "microsoft" else "Google"
        return f'Create "{title}" on {date_str}{time_part} in {provider_label} Calendar. Shall I go ahead?'

    if tool_name == "propose_update_calendar_event":
        event_title = args.get("event_title", "the event")
        changes = []
        if args.get("new_title"):
            changes.append(f'rename to "{args["new_title"]}"')
        if args.get("new_start"):
            try:
                dt = datetime.fromisoformat(args["new_start"][:19])
                changes.append(f"move to {dt.strftime('%A %H:%M')}")
            except Exception:
                changes.append(f"move to {args['new_start']}")
        if args.get("new_end"):
            try:
                dt = datetime.fromisoformat(args["new_end"][:19])
                changes.append(f"end at {dt.strftime('%H:%M')}")
            except Exception:
                pass
        if args.get("new_location"):
            changes.append(f'change location to "{args["new_location"]}"')
        if args.get("new_description"):
            changes.append("update description")
        changes_str = ", ".join(changes) if changes else "update"
        return f'Update "{event_title}" — {changes_str}. Shall I go ahead?'

    if tool_name == "propose_delete_calendar_event":
        title = args.get("event_title", "this event")
        return f'Delete "{title}" from your calendar. Are you sure?'

    if tool_name == "propose_send_email":
        to_list = args.get("to", [])
        to_str = ", ".join(to_list) if isinstance(to_list, list) else str(to_list)
        subject = args.get("subject", "(no subject)")
        body = args.get("body", "") or ""
        body_preview = body if len(body) <= 600 else body[:600].rstrip() + "…"
        provider_label = (
            "Outlook"
            if _normalize_provider(args.get("provider", "gmail")) == "microsoft"
            else "Gmail"
        )
        return (
            f"Draft to {to_str} via {provider_label}\n"
            f"Subject: {subject}\n"
            f"---\n"
            f"{body_preview}\n"
            f"---\n"
            f'Reply "yes" to send, "cancel" to discard, or tell me what to change.'
        )

    if tool_name == "propose_reply_email":
        subject = args.get("original_subject", "the email")
        body = args.get("body", "") or ""
        body_preview = body if len(body) <= 600 else body[:600].rstrip() + "…"
        provider_label = (
            "Outlook"
            if _normalize_provider(args.get("provider", "gmail")) == "microsoft"
            else "Gmail"
        )
        return (
            f'Reply to "{subject}" via {provider_label}\n'
            f"---\n"
            f"{body_preview}\n"
            f"---\n"
            f'Reply "yes" to send, "cancel" to discard, or tell me what to change.'
        )

    if tool_name == "propose_create_recurring_event":
        title = args.get("title", "event")
        start = args.get("start", "")
        recurrence = args.get("recurrence", "")
        try:
            dt = datetime.fromisoformat(start[:19])
            date_str = dt.strftime("%A, %B %d")
            time_str = dt.strftime("%H:%M")
            time_part = f" at {time_str}"
        except Exception:
            date_str = start
            time_part = ""
        recurrence_label = {
            "daily": "every day",
            "weekly": "every week",
            "biweekly": "every two weeks",
            "monthly": "every month",
            "yearly": "every year",
        }.get(recurrence, recurrence)
        provider_label = "Outlook" if _normalize_provider(args.get("provider", "google")) == "microsoft" else "Google"
        end_clause = ""
        if args.get("recurrence_end_date"):
            end_clause = f" until {args['recurrence_end_date']}"
        elif args.get("recurrence_count"):
            end_clause = f" ({args['recurrence_count']} times)"
        return (
            f'Create recurring "{title}" starting {date_str}{time_part}, '
            f'{recurrence_label}{end_clause} in {provider_label} Calendar. Shall I go ahead?'
        )

    return "Shall I go ahead?"
