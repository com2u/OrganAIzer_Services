"""
Microsoft Provider: Outlook Mail + Outlook Calendar implementation.
Implements EmailProvider and CalendarProvider interfaces for Microsoft services.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from msal import ConfidentialClientApplication
import requests

from .base import (
    EmailProvider, CalendarProvider,
    EmailMessage, EmailDraft, EmailSendRequest,
    CalendarEvent, CalendarEventRequest
)
from utils.token_storage import get_token_storage
from utils.ms_token import get_valid_ms_token, _refresh_ms_token, _ms_authority

logger = logging.getLogger(__name__)

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def _validate_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


class MicrosoftEmailProvider(EmailProvider):
    """Outlook Mail implementation using Microsoft Graph API."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.token_storage = get_token_storage()
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")

    # ------------------------------------------------------------------
    # Token management — delegates to centralized helper
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        """
        Get a valid access token via the centralized ms_token helper.
        Handles expiry check, structured logging, and auto-refresh.
        Raises fastapi.HTTPException on failure (converted to ValueError for
        callers that don't use FastAPI).
        """
        try:
            return get_valid_ms_token(self.user_id)
        except Exception as e:
            # Re-raise as ValueError so non-FastAPI callers get a clean error
            raise ValueError(str(e)) from e

    # ------------------------------------------------------------------
    # Internal HTTP helper
    # ------------------------------------------------------------------

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an authenticated request to Microsoft Graph.

        Builds headers from scratch on every call (never reuses old header objects).
        Logs full error diagnostics (status, body, WWW-Authenticate, request-id) on
        any non-2xx response BEFORE raising, so the body is never lost.
        """
        access_token = self._get_access_token()
        m = method.upper()
        # Build headers from scratch — never reuse a stale object
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        # Only add Content-Type for methods that send a body
        if m in ("POST", "PATCH", "PUT"):
            headers["Content-Type"] = "application/json"

        url = f"{GRAPH_API_ENDPOINT}{endpoint}"
        token_prefix = access_token[:20] + "..." if len(access_token) > 20 else "(short)"
        logger.debug(
            "[MS_PROVIDER] → %s %s  token_prefix=%s",
            m, url, token_prefix,
        )

        response = requests.request(method=m, url=url, headers=headers, **kwargs)

        logger.debug("[MS_PROVIDER] ← %s %s  status=%s", m, url, response.status_code)

        if not response.ok:
            # Eagerly capture body + diagnostic headers before raise_for_status()
            # consumes / discards them.
            resp_body = response.text
            www_auth = response.headers.get("WWW-Authenticate", "(not present)")
            req_id = response.headers.get(
                "request-id",
                response.headers.get(
                    "x-ms-request-id",
                    response.headers.get("client-request-id", "(not present)")
                )
            )
            logger.error(
                "[MS_PROVIDER] Graph error.\n"
                "  method          = %s\n"
                "  endpoint        = %s\n"
                "  status          = %s\n"
                "  body            = %.500s\n"
                "  WWW-Authenticate= %s\n"
                "  request-id      = %s",
                m, url, response.status_code, resp_body, www_auth, req_id,
            )
            # Re-raise as HTTPError with the full body in the message
            response.raise_for_status()

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # EmailProvider interface
    # ------------------------------------------------------------------

    async def get_user_email(self) -> str:
        """Return the authenticated user's email address."""
        try:
            result = self._make_request("GET", "/me", params={"$select": "mail,userPrincipalName"})
            return result.get("mail") or result.get("userPrincipalName", "unknown")
        except Exception as e:
            logger.error(f"Could not fetch user email: {e}")
            raise

    async def list_messages(
        self,
        folder: str = "INBOX",
        limit: int = 20,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        folder_map = {
            "INBOX": "inbox",
            "SENT": "sentitems",
            "DRAFTS": "drafts",
            "DELETED": "deleteditems",
        }
        folder_id = folder_map.get(folder.upper(), folder.lower())
        endpoint = f"/me/mailFolders/{folder_id}/messages"
        params = {
            "$top": limit,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview",
        }
        if page_token:
            params["$skip"] = page_token

        result = self._make_request("GET", endpoint, params=params)
        messages = []
        for msg in result.get("value", []):
            messages.append({
                "id": msg["id"],
                "thread_id": msg.get("conversationId"),
                "subject": msg.get("subject", "(No Subject)"),
                "from_email": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                "to": [r.get("emailAddress", {}).get("address", "") for r in msg.get("toRecipients", [])],
                "cc": [r.get("emailAddress", {}).get("address", "") for r in msg.get("ccRecipients", [])] or None,
                "date": msg.get("receivedDateTime", ""),
                "snippet": msg.get("bodyPreview", ""),
                "is_read": msg.get("isRead", False),
                "has_attachments": msg.get("hasAttachments", False),
            })
        return {"messages": messages, "next_page_token": result.get("@odata.nextLink")}

    async def get_message(self, message_id: str) -> EmailMessage:
        endpoint = f"/me/messages/{message_id}"
        params = {"$select": "id,conversationId,subject,from,toRecipients,ccRecipients,bccRecipients,receivedDateTime,isRead,hasAttachments,body,bodyPreview"}
        msg = self._make_request("GET", endpoint, params=params)
        return EmailMessage(
            id=msg["id"],
            thread_id=msg.get("conversationId"),
            subject=msg.get("subject", "(No Subject)"),
            from_email=msg.get("from", {}).get("emailAddress", {}).get("address", ""),
            to=[r.get("emailAddress", {}).get("address", "") for r in msg.get("toRecipients", [])],
            cc=[r.get("emailAddress", {}).get("address", "") for r in msg.get("ccRecipients", [])] or None,
            bcc=[r.get("emailAddress", {}).get("address", "") for r in msg.get("bccRecipients", [])] or None,
            date=msg.get("receivedDateTime", ""),
            snippet=msg.get("bodyPreview", ""),
            body=msg.get("body", {}).get("content", ""),
            is_read=msg.get("isRead", False),
            has_attachments=msg.get("hasAttachments", False),
        )

    async def search_messages(self, query: str, limit: int = 20) -> List[EmailMessage]:
        endpoint = "/me/messages"
        params = {"$search": f'"{query}"', "$top": limit}
        result = self._make_request("GET", endpoint, params=params)
        messages = []
        for msg_data in result.get("value", []):
            try:
                msg = await self.get_message(msg_data["id"])
                messages.append(msg)
            except Exception as e:
                logger.warning(f"Failed to fetch message {msg_data['id']}: {e}")
        return messages

    async def draft_email(
        self,
        context: Optional[Dict[str, Any]] = None,
        tone: str = "professional",
    ) -> EmailDraft:
        """Generate a draft (placeholder - AI drafting not implemented here)."""
        return EmailDraft(subject="", body="")

    async def send_email(self, request: EmailSendRequest) -> Dict[str, Any]:
        """Send email via Microsoft Graph /me/sendMail."""
        if not request.confirm:
            raise ValueError(
                "Email sending requires explicit confirmation. Set confirm=true"
            )
        if not request.to:
            raise ValueError("At least one recipient required in 'to' field")
        for email in request.to:
            if not _validate_email(email):
                raise ValueError(f"Invalid email address: {email}")
        if not request.subject or not request.subject.strip():
            raise ValueError("Email subject cannot be empty")
        if not request.body or not request.body.strip():
            raise ValueError("Email body cannot be empty")

        if request.dry_run:
            return {
                "status": "preview",
                "dry_run": True,
                "preview": {
                    "to": request.to,
                    "cc": request.cc,
                    "bcc": request.bcc,
                    "subject": request.subject,
                    "body": request.body,
                },
                "message": "Dry run - no email sent. Set dry_run=false and confirm=true to send.",
            }

        logger.info(f"Sending Outlook email: user={self.user_id}, to={request.to}, subject='{request.subject}'")
        message_body: Dict[str, Any] = {
            "message": {
                "subject": request.subject,
                "body": {"contentType": "Text", "content": request.body},
                "toRecipients": [{"emailAddress": {"address": e}} for e in request.to],
            },
            "saveToSentItems": True,
        }
        if request.cc:
            message_body["message"]["ccRecipients"] = [
                {"emailAddress": {"address": e}} for e in request.cc
            ]
        if request.bcc:
            message_body["message"]["bccRecipients"] = [
                {"emailAddress": {"address": e}} for e in request.bcc
            ]
        if getattr(request, "reply_to", None):
            message_body["message"]["replyTo"] = [
                {"emailAddress": {"address": request.reply_to}}
            ]

        self._make_request("POST", "/me/sendMail", json=message_body)
        logger.info(f"✅ Outlook email sent: user={self.user_id}, to={request.to}")
        return {
            "status": "sent",
            "message": f"Email sent via Outlook to {', '.join(request.to)}",
        }


class MicrosoftCalendarProvider(CalendarProvider):
    """Outlook Calendar implementation using Microsoft Graph API."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._email_provider = MicrosoftEmailProvider(user_id)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self._email_provider._make_request(method, endpoint, **kwargs)

    async def list_events(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        limit: int = 50,
    ) -> List[CalendarEvent]:
        now = datetime.utcnow()
        if not time_min:
            time_min = now.isoformat() + "Z"
        if not time_max:
            time_max = (now + timedelta(days=30)).isoformat() + "Z"

        endpoint = "/me/calendarView"
        params = {
            "startDateTime": time_min,
            "endDateTime": time_max,
            "$top": limit,
            "$orderby": "start/dateTime",
            "$select": "id,subject,bodyPreview,location,start,end,attendees,organizer,showAs,isAllDay",
        }
        result = self._make_request("GET", endpoint, params=params)
        events = []
        for event_data in result.get("value", []):
            attendees = []
            if event_data.get("attendees"):
                attendees = [
                    a.get("emailAddress", {}).get("address", "")
                    for a in event_data["attendees"]
                ]
            events.append(CalendarEvent(
                id=event_data["id"],
                summary=event_data.get("subject", "(No title)"),
                description=event_data.get("bodyPreview", ""),
                location=event_data.get("location", {}).get("displayName", ""),
                start=event_data["start"]["dateTime"],
                end=event_data["end"]["dateTime"],
                timezone=event_data["start"].get("timeZone", "UTC"),
                attendees=attendees or None,
                organizer=event_data.get("organizer", {}).get("emailAddress", {}).get("address"),
                status=event_data.get("showAs"),
                is_all_day=event_data.get("isAllDay", False),
            ))
        return events

    async def create_event(self, request: CalendarEventRequest) -> Dict[str, Any]:
        if not request.confirm:
            raise ValueError("Event creation requires confirm=true")

        try:
            start_dt = datetime.fromisoformat(request.start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(request.end.replace("Z", "+00:00"))
            if start_dt >= end_dt:
                raise ValueError("Event start time must be before end time")
        except ValueError as e:
            raise ValueError(f"Invalid datetime format: {e}")

        if not request.summary or not request.summary.strip():
            raise ValueError("Event summary/title cannot be empty")

        if request.dry_run:
            return {
                "status": "preview",
                "dry_run": True,
                "preview": {
                    "summary": request.summary,
                    "start": request.start,
                    "end": request.end,
                    "timezone": request.timezone,
                },
                "message": "Dry run - no event created. Set dry_run=false and confirm=true.",
            }

        event_body: Dict[str, Any] = {
            "subject": request.summary,
            "start": {"dateTime": request.start, "timeZone": request.timezone},
            "end": {"dateTime": request.end, "timeZone": request.timezone},
        }
        if request.description:
            event_body["body"] = {"contentType": "Text", "content": request.description}
        if request.location:
            event_body["location"] = {"displayName": request.location}
        if request.attendees:
            event_body["attendees"] = [
                {"emailAddress": {"address": e}, "type": "required"}
                for e in request.attendees
            ]

        result = self._make_request("POST", "/me/calendar/events", json=event_body)
        logger.info(f"✅ Outlook calendar event created: {result['id']}")
        return {
            "status": "created",
            "event_id": result["id"],
            "web_link": result.get("webLink"),
            "message": "Event created successfully",
        }

    async def update_event(self, event_id: str, request: CalendarEventRequest) -> Dict[str, Any]:
        if not request.confirm:
            raise ValueError("Event update requires confirm=true")
        if request.dry_run:
            return {"status": "preview", "dry_run": True, "event_id": event_id}

        event_body: Dict[str, Any] = {
            "subject": request.summary,
            "start": {"dateTime": request.start, "timeZone": request.timezone},
            "end": {"dateTime": request.end, "timeZone": request.timezone},
        }
        result = self._make_request("PATCH", f"/me/calendar/events/{event_id}", json=event_body)
        return {"status": "updated", "event_id": result.get("id", event_id)}

    async def delete_event(
        self, event_id: str, dry_run: bool = True, confirm: bool = False
    ) -> Dict[str, Any]:
        if not confirm:
            raise ValueError("Event deletion requires confirm=true")
        if dry_run:
            return {"status": "preview", "dry_run": True, "event_id": event_id}
        self._make_request("DELETE", f"/me/calendar/events/{event_id}")
        return {"status": "deleted", "event_id": event_id}
