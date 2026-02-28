"""
Models for external integrations (Google, Outlook).
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime


class AuthStartResponse(BaseModel):
    """Response when starting OAuth flow."""
    auth_url: str = Field(..., description="URL to redirect user for OAuth authorization")
    state: str = Field(..., description="OAuth state parameter for security")


class AuthCallbackRequest(BaseModel):
    """OAuth callback request."""
    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="OAuth state parameter")


class AuthCallbackResponse(BaseModel):
    """OAuth callback response."""
    success: bool = Field(..., description="Whether authentication was successful")
    message: str = Field(..., description="Success or error message")
    user_info: Optional[Dict[str, Any]] = Field(None, description="User information if available")


class CalendarEvent(BaseModel):
    """Calendar event model."""
    id: Optional[str] = Field(None, description="Event ID")
    summary: str = Field(..., description="Event title/summary")
    description: Optional[str] = Field(None, description="Event description")
    start: str = Field(..., description="Event start time (ISO 8601)")
    end: str = Field(..., description="Event end time (ISO 8601)")
    location: Optional[str] = Field(None, description="Event location")
    attendees: Optional[List[str]] = Field(None, description="List of attendee email addresses")


class CalendarEventsResponse(BaseModel):
    """Response for listing calendar events."""
    events: List[CalendarEvent] = Field(..., description="List of calendar events")
    total: int = Field(..., description="Total number of events")


class CalendarEventCreateRequest(BaseModel):
    """Request to create a calendar event."""
    summary: str = Field(..., description="Event title/summary")
    description: Optional[str] = Field(None, description="Event description")
    start: str = Field(..., description="Event start time (ISO 8601)")
    end: str = Field(..., description="Event end time (ISO 8601)")
    location: Optional[str] = Field(None, description="Event location")
    attendees: Optional[List[str]] = Field(None, description="List of attendee email addresses")


class MailSendRequest(BaseModel):
    """Request to send email."""
    to: Union[str, List[str]] = Field(..., description="Recipient email address(es) - string or list")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email plain-text body")
    html: Optional[str] = Field(None, description="Optional HTML body (overrides plain-text rendering)")
    cc: Optional[Union[str, List[str]]] = Field(None, description="CC recipients")
    bcc: Optional[Union[str, List[str]]] = Field(None, description="BCC recipients")

    def to_list(self) -> List[str]:
        """Normalize `to` to a list."""
        return [self.to] if isinstance(self.to, str) else list(self.to)

    def cc_list(self) -> List[str]:
        if self.cc is None:
            return []
        return [self.cc] if isinstance(self.cc, str) else list(self.cc)

    def bcc_list(self) -> List[str]:
        if self.bcc is None:
            return []
        return [self.bcc] if isinstance(self.bcc, str) else list(self.bcc)


class MailSendResponse(BaseModel):
    """Response after sending email."""
    success: bool = Field(..., description="Whether email was sent successfully")
    message: str = Field(..., description="Success or error message")
    message_id: Optional[str] = Field(None, description="Sent message ID if available")
