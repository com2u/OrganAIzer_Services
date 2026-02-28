"""
Base provider interfaces for Email and Calendar services.

These abstract base classes define the contract that all providers (Google, Microsoft)
must implement, ensuring consistent behavior across different platforms.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


# ============================================================================
# EMAIL PROVIDER MODELS
# ============================================================================

class EmailMessage(BaseModel):
    """Standardized email message structure."""
    id: str
    thread_id: Optional[str] = None
    subject: str
    from_email: str
    to: List[str]
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    date: str
    snippet: str
    body: Optional[str] = None
    labels: Optional[List[str]] = None
    is_read: bool = False
    has_attachments: bool = False


class EmailDraft(BaseModel):
    """Email draft structure."""
    subject: str
    body: str
    tone: Optional[str] = None
    alternatives: Optional[List[Dict[str, str]]] = None


class EmailSendRequest(BaseModel):
    """Request to send an email."""
    to: List[str]
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    reply_to: Optional[str] = None
    dry_run: bool = True
    confirm: bool = False


# ============================================================================
# CALENDAR PROVIDER MODELS
# ============================================================================

class CalendarEvent(BaseModel):
    """Standardized calendar event structure."""
    id: str
    summary: str
    description: Optional[str] = None
    location: Optional[str] = None
    start: str  # ISO 8601 datetime
    end: str    # ISO 8601 datetime
    timezone: Optional[str] = None
    attendees: Optional[List[str]] = None
    organizer: Optional[str] = None
    status: Optional[str] = None
    is_all_day: bool = False


class CalendarEventRequest(BaseModel):
    """Request to create/update a calendar event."""
    summary: str
    description: Optional[str] = None
    location: Optional[str] = None
    start: str  # ISO 8601 datetime
    end: str    # ISO 8601 datetime
    timezone: Optional[str] = "UTC"
    attendees: Optional[List[str]] = None
    dry_run: bool = True
    confirm: bool = False


# ============================================================================
# PROVIDER INTERFACES
# ============================================================================

class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def list_messages(
        self,
        folder: str = "INBOX",
        limit: int = 20,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_message(self, message_id: str) -> EmailMessage:
        pass

    @abstractmethod
    async def search_messages(
        self,
        query: str,
        limit: int = 20
    ) -> List[EmailMessage]:
        pass

    @abstractmethod
    async def draft_email(
        self,
        context: Optional[Dict[str, Any]] = None,
        tone: str = "professional"
    ) -> EmailDraft:
        pass

    @abstractmethod
    async def send_email(
        self,
        request: EmailSendRequest
    ) -> Dict[str, Any]:
        pass

    async def get_user_email(self) -> str:
        """Return the authenticated user's email address. Override in subclasses."""
        return "unknown@unknown.com"


class CalendarProvider(ABC):
    """Abstract base class for calendar providers."""

    @abstractmethod
    async def list_events(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        limit: int = 50
    ) -> List[CalendarEvent]:
        pass

    @abstractmethod
    async def create_event(
        self,
        request: CalendarEventRequest
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def update_event(
        self,
        event_id: str,
        request: CalendarEventRequest
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def delete_event(
        self,
        event_id: str,
        dry_run: bool = True,
        confirm: bool = False
    ) -> Dict[str, Any]:
        pass
