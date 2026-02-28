"""
Email and Calendar provider implementations.
"""

from .base import (
    EmailProvider, CalendarProvider,
    EmailMessage, EmailDraft, EmailSendRequest,
    CalendarEvent, CalendarEventRequest
)

__all__ = [
    "EmailProvider",
    "CalendarProvider",
    "EmailMessage",
    "EmailDraft",
    "EmailSendRequest",
    "CalendarEvent",
    "CalendarEventRequest",
]
