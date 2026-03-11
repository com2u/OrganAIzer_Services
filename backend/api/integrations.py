"""
API endpoints for external integrations (Google, Outlook).
"""

import logging
import os
import json
import base64
import re
import secrets
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from datetime import datetime, timedelta

import requests as http_requests
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from msal import ConfidentialClientApplication

from utils.ms_token import get_valid_ms_token, _refresh_ms_token, _ms_authority as _ms_auth_from_helper

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models.integrations import (
    AuthStartResponse,
    AuthCallbackRequest,
    AuthCallbackResponse,
    CalendarEvent,
    CalendarEventsResponse,
    CalendarEventCreateRequest,
    MailSendRequest,
    MailSendResponse
)
from config.google_scopes import GOOGLE_SCOPES, CURRENT_SCOPE_HASH
from utils.token_storage import get_token_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ---------------------------------------------------------------------------
# Calendar helpers (shared by Google + Microsoft endpoints)
# ---------------------------------------------------------------------------

def _calendar_timezone() -> str:
    """Return the configured timezone name (defaults to 'Europe/Berlin').
    Used in every calendar create/update payload so events are created in the
    user's local time zone rather than UTC."""
    return os.getenv("TIMEZONE", "Europe/Berlin")


def _validate_calendar_times(start: str, end: str) -> None:
    """Raise HTTP 400 if end <= start or if either datetime cannot be parsed.

    Accepts ISO 8601 strings with or without a timezone offset.
    This guard prevents invalid payloads from ever reaching the provider APIs.
    """
    try:
        # Strip trailing 'Z' and normalise offset so fromisoformat works in 3.10
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt   = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_DATETIME",
                "message": f"Cannot parse start/end datetime: {exc}",
                "start": start,
                "end": end,
            },
        )
    if end_dt <= start_dt:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_TIME_RANGE",
                "message": "Event end time must be after start time.",
                "start": start,
                "end": end,
            },
        )

# OAuth state storage (in production, use Redis or database)
# Each entry: { "user_id": str, "timestamp": datetime }
_oauth_states: dict = {}
_OAUTH_STATE_TTL_SECONDS = 600  # 10-minute window to complete the OAuth flow


def _cleanup_expired_oauth_states() -> None:
    """Remove OAuth state entries older than _OAUTH_STATE_TTL_SECONDS."""
    cutoff = datetime.now() - timedelta(seconds=_OAUTH_STATE_TTL_SECONDS)
    expired = [k for k, v in _oauth_states.items() if v.get("timestamp", datetime.now()) < cutoff]
    for k in expired:
        _oauth_states.pop(k, None)
    if expired:
        logger.debug("[OAUTH] Cleaned up %d expired state entries", len(expired))


def get_credentials_json_path() -> Path:
    """Get or create credentials.json from environment variables."""
    creds_path = Path(__file__).resolve().parent.parent / "credentials.json"
    
    # Create credentials.json from environment if it doesn't exist
    if not creds_path.exists():
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env file"
            )
        
        credentials_data = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": ["http://localhost:8000/api/integrations/google/auth/callback"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }
        
        creds_path.write_text(json.dumps(credentials_data, indent=2))
        logger.info(f"✅ Created credentials.json at {creds_path}")
    
    return creds_path


# ============================================================================
# GOOGLE INTEGRATIONS
# ============================================================================

@router.get("/google/auth/start", response_model=AuthStartResponse)
async def google_auth_start(user_id: str = Query("default_user")):
    """
    Start Google OAuth authentication flow.
    
    Returns OAuth URL to redirect user for Google account authorization.
    This will grant access to Google Calendar and Gmail.
    """
    try:
        _cleanup_expired_oauth_states()
        # Get credentials file path
        credentials_path = get_credentials_json_path()
        logger.info(f"🔑 Using credentials from: {credentials_path}")
        
        # Create OAuth flow
        flow = Flow.from_client_secrets_file(
            str(credentials_path),
            scopes=GOOGLE_SCOPES,
            redirect_uri="http://localhost:8000/api/integrations/google/auth/callback"
        )
        
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)
        _oauth_states[state] = {"user_id": user_id, "timestamp": datetime.now()}
        
        # Get authorization URL
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # Force consent to get refresh token
        )
        
        logger.info(f"✅ Generated OAuth URL for user {user_id}")
        logger.info(f"📋 Requesting scopes: {GOOGLE_SCOPES}")
        
        return AuthStartResponse(
            auth_url=authorization_url,
            state=state
        )
    
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CONFIGURATION_ERROR",
                "message": str(e),
                "details": {"status": "error"}
            }
        )
    except Exception as e:
        logger.error(f"Failed to start Google OAuth: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "OAUTH_START_FAILED",
                "message": f"Failed to start OAuth flow: {str(e)}",
                "details": {"status": "error"}
            }
        )


@router.get("/google/auth/callback")
async def google_auth_callback(code: str = Query(...), state: str = Query(...)):
    """
    Handle Google OAuth callback.
    
    Processes the OAuth callback from Google and stores access tokens.
    """
    try:
        # Validate state
        if state not in _oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        user_data = _oauth_states.pop(state)
        user_id = user_data["user_id"]
        
        # Get credentials file path
        credentials_path = get_credentials_json_path()
        logger.info(f"📄 Loading OAuth config from: {credentials_path}")
        
        # Create OAuth flow
        flow = Flow.from_client_secrets_file(
            str(credentials_path),
            scopes=GOOGLE_SCOPES,
            redirect_uri="http://localhost:8000/api/integrations/google/auth/callback",
            state=state
        )
        
        # Exchange authorization code for tokens
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        # Extract token information
        token_data = {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "scope_hash": CURRENT_SCOPE_HASH,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }
        
        # Store tokens securely
        token_storage = get_token_storage()
        token_storage.save_tokens(user_id, "google", token_data)
        
        logger.info(f"✅ Google OAuth successful for user {user_id}")
        logger.info(f"📋 Granted scopes: {credentials.scopes}")
        logger.info(f"🔄 Has refresh token: {credentials.refresh_token is not None}")
        
        # Read frontend URL from env (default: http://localhost:5173 for Vite dev server)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        logger.info(f"🔀 Redirecting to frontend: {frontend_url}?auth=success&provider=google")
        return RedirectResponse(
            url=f"{frontend_url}?auth=success&provider=google",
            status_code=302
        )
    
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(
            url=f"{frontend_url}?auth=error&message={str(e)}",
            status_code=302
        )


@router.get("/google/status")
async def google_status(user_id: str = Query("default_user")):
    """
    Check whether Google OAuth tokens are stored for the user.
    Returns connected=True if tokens exist and have a valid access_token.
    """
    try:
        token_storage = get_token_storage()
        token_data = token_storage.load_tokens(user_id, "google")
        
        if not token_data or not token_data.get("access_token"):
            return {"connected": False}
        
        # Optionally surface the scopes so the frontend can verify
        scopes = token_data.get("scopes", [])
        return {
            "connected": True,
            "scopes": list(scopes) if scopes else [],
            "has_refresh_token": bool(token_data.get("refresh_token")),
        }
    except Exception as e:
        logger.error(f"Error checking Google status for user {user_id}: {e}")
        return {"connected": False}


@router.delete("/google/disconnect")
async def google_disconnect(user_id: str = Query("default_user")):
    """
    Disconnect Google integration by deleting stored OAuth tokens.

    Removes all stored Google tokens for the user. The user will need to
    re-authenticate via /google/auth/start to use Google features again.
    """
    try:
        token_storage = get_token_storage()
        deleted = token_storage.delete_tokens(user_id, "google")
        logger.info(f"Google tokens deleted for user {user_id}: {deleted}")
        return {"success": True, "disconnected": True}
    except Exception as e:
        logger.error(f"Error disconnecting Google for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"code": "DISCONNECT_ERROR", "message": str(e)})


@router.get("/google/calendar/events", response_model=CalendarEventsResponse)
async def google_calendar_list_events(
    user_id: str = Query("default_user", description="User ID"),
    max_results: int = Query(10, description="Maximum number of events to return"),
    time_min: Optional[str] = Query(None, description="Lower bound for event start time (ISO 8601)"),
    time_max: Optional[str] = Query(None, description="Upper bound for event end time (ISO 8601)"),
):
    """
    List Google Calendar events.
    
    Retrieves events from the user's primary Google Calendar.
    Requires prior authentication via /google/auth/start.
    """
    try:
        # Get stored tokens
        token_storage = get_token_storage()
        token_data = token_storage.load_tokens(user_id, "google")
        
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "NOT_AUTHENTICATED",
                    "message": "Google account not connected. Please connect your Google account first.",
                    "action": "CONNECT_GOOGLE"
                }
            )
        
        # Build credentials from stored tokens
        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes")
        )
        
        # Build Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Set default time_min to now if not provided
        if not time_min:
            time_min = datetime.utcnow().isoformat() + 'Z'
        
        # Build list() kwargs — only pass timeMax when provided
        list_kwargs: dict = {
            "calendarId": "primary",
            "timeMin": time_min,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_max:
            list_kwargs["timeMax"] = time_max

        # Call Calendar API
        events_result = service.events().list(**list_kwargs).execute()
        
        events = events_result.get('items', [])
        
        # Convert to our event model
        calendar_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            calendar_events.append(CalendarEvent(
                id=event.get('id'),
                summary=event.get('summary', 'No Title'),
                description=event.get('description'),
                start=start,
                end=end,
                location=event.get('location'),
                attendees=[att.get('email') for att in event.get('attendees', [])] if event.get('attendees') else None
            ))
        
        logger.info(f"✅ Retrieved {len(calendar_events)} calendar events for user {user_id}")
        
        return CalendarEventsResponse(
            events=calendar_events,
            total=len(calendar_events)
        )
        
    except HttpError as e:
        logger.error(f"Google Calendar API error: {e}")
        if e.resp.status in [401, 403]:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Google Calendar access expired or invalid. Please reconnect your Google account.",
                    "action": "RECONNECT_GOOGLE"
                }
            )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CALENDAR_API_ERROR",
                "message": f"Failed to retrieve calendar events: {str(e)}",
                "details": {"status": "error"}
            }
        )
    except Exception as e:
        logger.error(f"Error listing calendar events: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"Failed to list calendar events: {str(e)}",
                "details": {"status": "error"}
            }
        )


@router.post("/google/calendar/events", response_model=CalendarEvent)
async def google_calendar_create_event(
    request: CalendarEventCreateRequest,
    user_id: str = Query("default_user", description="User ID")
):
    """
    Create a new Google Calendar event.
    
    Creates an event in the user's primary Google Calendar.
    Requires prior authentication via /google/auth/start.
    """
    try:
        # Get stored tokens
        token_storage = get_token_storage()
        token_data = token_storage.load_tokens(user_id, "google")
        
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "NOT_AUTHENTICATED",
                    "message": "Google account not connected. Please connect your Google account first.",
                    "action": "CONNECT_GOOGLE"
                }
            )
        
        # Build credentials from stored tokens
        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes")
        )
        
        # Validate: end must be after start
        _validate_calendar_times(request.start, request.end)

        tz_name = _calendar_timezone()

        # Build Calendar API service
        service = build('calendar', 'v3', credentials=credentials)

        # Create event body — use configured timezone, never hardcode UTC
        event_body = {
            'summary': request.summary,
            'start': {
                'dateTime': request.start,
                'timeZone': tz_name,
            },
            'end': {
                'dateTime': request.end,
                'timeZone': tz_name,
            },
        }

        # Add optional fields
        if request.description:
            event_body['description'] = request.description
        if request.location:
            event_body['location'] = request.location
        if request.attendees:
            event_body['attendees'] = [{'email': email} for email in request.attendees]

        # Create the event
        created_event = service.events().insert(
            calendarId='primary',
            body=event_body
        ).execute()
        
        logger.info(f"✅ Created calendar event '{request.summary}' for user {user_id}")
        logger.info(f"📋 Event ID: {created_event.get('id')}")
        
        # Convert to our event model
        start_time = created_event['start'].get('dateTime', created_event['start'].get('date'))
        end_time = created_event['end'].get('dateTime', created_event['end'].get('date'))
        
        return CalendarEvent(
            id=created_event.get('id'),
            summary=created_event.get('summary'),
            description=created_event.get('description'),
            start=start_time,
            end=end_time,
            location=created_event.get('location'),
            attendees=[att.get('email') for att in created_event.get('attendees', [])] if created_event.get('attendees') else None,
            htmlLink=created_event.get('htmlLink'),
        )

    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Google Calendar API error: {e}")
        if e.resp.status in [401, 403]:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Google Calendar access expired or invalid. Please reconnect your Google account.",
                    "action": "RECONNECT_GOOGLE"
                }
            )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CALENDAR_API_ERROR",
                "message": f"Failed to create calendar event: {str(e)}",
                "details": {"status": "error"}
            }
        )
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"Failed to create calendar event: {str(e)}",
                "details": {"status": "error"}
            }
        )


@router.patch("/google/calendar/events/{event_id}", response_model=CalendarEvent)
async def google_calendar_update_event(
    event_id: str,
    request: CalendarEventCreateRequest,
    user_id: str = Query("default_user", description="User ID"),
):
    """
    Update an existing Google Calendar event (PATCH — partial update).

    Only fields present in the request body are changed.
    Requires prior Google OAuth (calendar scope).
    """
    try:
        token_storage = get_token_storage()
        token_data = token_storage.load_tokens(user_id, "google")
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "NOT_AUTHENTICATED",
                    "message": "Google account not connected. Please connect your Google account first.",
                    "action": "CONNECT_GOOGLE",
                },
            )

        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )
        service = build("calendar", "v3", credentials=credentials)

        patch_body: dict = {}
        tz_name = _calendar_timezone()

        if request.summary:
            patch_body["summary"] = request.summary
        if request.start and request.end:
            _validate_calendar_times(request.start, request.end)
            patch_body["start"] = {"dateTime": request.start, "timeZone": tz_name}
            patch_body["end"]   = {"dateTime": request.end,   "timeZone": tz_name}
        elif request.start:
            patch_body["start"] = {"dateTime": request.start, "timeZone": tz_name}
        elif request.end:
            patch_body["end"]   = {"dateTime": request.end,   "timeZone": tz_name}
        if request.description is not None:
            patch_body["description"] = request.description
        if request.location is not None:
            patch_body["location"] = request.location
        if request.attendees is not None:
            patch_body["attendees"] = [{"email": e} for e in request.attendees]

        updated_event = service.events().patch(
            calendarId="primary", eventId=event_id, body=patch_body
        ).execute()

        logger.info(f"✅ Updated Google Calendar event {event_id} for user {user_id}")
        start_time = updated_event["start"].get("dateTime", updated_event["start"].get("date"))
        end_time   = updated_event["end"].get("dateTime", updated_event["end"].get("date"))
        return CalendarEvent(
            id=updated_event.get("id"),
            summary=updated_event.get("summary"),
            description=updated_event.get("description"),
            start=start_time,
            end=end_time,
            location=updated_event.get("location"),
            attendees=[a.get("email") for a in updated_event.get("attendees", [])] or None,
        )

    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Google Calendar update error: {e}")
        if e.resp.status in (401, 403):
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Google Calendar access expired. Please reconnect your Google account.",
                    "action": "RECONNECT_GOOGLE",
                },
            )
        raise HTTPException(
            status_code=500,
            detail={"code": "CALENDAR_API_ERROR", "message": f"Failed to update event: {str(e)}"},
        )
    except Exception as e:
        logger.error(f"Error updating Google Calendar event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": f"Failed to update calendar event: {str(e)}"},
        )


@router.delete("/google/calendar/events/{event_id}")
async def google_calendar_delete_event(
    event_id: str,
    user_id: str = Query("default_user", description="User ID"),
):
    """
    Delete a Google Calendar event (DELETE).

    Returns 200 with {"status": "deleted", "event_id": event_id} on success.
    Requires prior Google OAuth (calendar scope).
    """
    try:
        token_storage = get_token_storage()
        token_data = token_storage.load_tokens(user_id, "google")
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "NOT_AUTHENTICATED",
                    "message": "Google account not connected. Please connect your Google account first.",
                    "action": "CONNECT_GOOGLE",
                },
            )

        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )
        service = build("calendar", "v3", credentials=credentials)

        service.events().delete(calendarId="primary", eventId=event_id).execute()
        logger.info(f"✅ Deleted Google Calendar event {event_id} for user {user_id}")
        return {"status": "deleted", "event_id": event_id}

    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Google Calendar delete error: {e}")
        if e.resp.status in (401, 403):
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Google Calendar access expired. Please reconnect your Google account.",
                    "action": "RECONNECT_GOOGLE",
                },
            )
        if e.resp.status == 404:
            raise HTTPException(
                status_code=404,
                detail={"code": "EVENT_NOT_FOUND", "message": f"Calendar event {event_id} not found."},
            )
        raise HTTPException(
            status_code=500,
            detail={"code": "CALENDAR_API_ERROR", "message": f"Failed to delete event: {str(e)}"},
        )
    except Exception as e:
        logger.error(f"Error deleting Google Calendar event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": f"Failed to delete calendar event: {str(e)}"},
        )


@router.get("/google/gmail/messages")
async def google_gmail_list_messages(
    user_id: str = Query("default_user", description="User ID"),
    max_results: int = Query(5, description="Max emails to return"),
    unread_only: bool = Query(False, description="Filter to unread only"),
    sender: Optional[str] = Query(None, description="Filter by sender name or email"),
    date_after: Optional[str] = Query(None, description="Filter emails after this date (YYYY-MM-DD)"),
    date_before: Optional[str] = Query(None, description="Filter emails before this date (YYYY-MM-DD)"),
):
    """
    List Gmail messages via Gmail API (users.messages.list → users.messages.get).

    Returns a structured list: from, subject, received time, short preview.
    Requires prior Google OAuth via /google/auth/start (gmail.readonly or gmail.modify scope).
    """
    try:
        token_storage = get_token_storage()
        token_data = token_storage.load_tokens(user_id, "google")
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail={"code": "NOT_AUTHENTICATED",
                        "message": "Google account not connected. Please authenticate via /api/integrations/google/auth/start.",
                        "action": "CONNECT_GOOGLE"}
            )

        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )

        service = build("gmail", "v1", credentials=credentials)

        # Build Gmail query string
        query_parts = []
        if unread_only:
            query_parts.append("is:unread")
        if sender:
            query_parts.append(f"from:{sender}")
        if date_after:
            query_parts.append(f"after:{date_after.replace('-', '/')}")
        if date_before:
            query_parts.append(f"before:{date_before.replace('-', '/')}")
        query = " ".join(query_parts) if query_parts else None

        list_params = {"userId": "me", "maxResults": min(max_results, 20)}
        if query:
            list_params["q"] = query

        list_result = service.users().messages().list(**list_params).execute()
        messages_meta = list_result.get("messages", [])

        emails = []
        for meta in messages_meta[:max_results]:
            msg = service.users().messages().get(
                userId="me", id=meta["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            snippet = msg.get("snippet", "")[:200]
            label_ids = msg.get("labelIds", [])

            emails.append({
                "id": msg["id"],
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "(No Subject)"),
                "received": headers.get("Date", ""),
                "preview": snippet,
                "unread": "UNREAD" in label_ids,
            })

        logger.info(f"✅ Gmail list: user={user_id}, count={len(emails)}, query={query!r}")
        return {"emails": emails, "total": len(emails)}

    except HttpError as e:
        logger.error(f"Gmail list error: {e}")
        status = e.resp.status if hasattr(e, "resp") else 500
        if status in (401, 403):
            raise HTTPException(status_code=401, detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Gmail access expired or missing scope. Please reconnect your Google account.",
                "action": "RECONNECT_GOOGLE"
            })
        raise HTTPException(status_code=500, detail={"code": "GMAIL_API_ERROR", "message": str(e)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.post("/google/gmail/send", response_model=MailSendResponse)
async def google_gmail_send(
    request: MailSendRequest,
    user_id: str = Query("default_user", description="User ID")
):
    """
    Send an email via Gmail API (users.messages.send).

    Accepts plain text and optional HTML body. Constructs an RFC 2822 message,
    base64url-encodes it, and sends via the Gmail API.
    Requires prior Google OAuth via /google/auth/start (gmail.send scope).
    """
    try:
        token_storage = get_token_storage()
        token_data = token_storage.load_tokens(user_id, "google")
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail={"code": "NOT_AUTHENTICATED",
                        "message": "Google account not connected. Please authenticate via /api/integrations/google/auth/start.",
                        "action": "CONNECT_GOOGLE"}
            )

        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )

        to_list = request.to_list()
        cc_list = request.cc_list()
        bcc_list = request.bcc_list()

        # Build RFC 2822 email
        if request.html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(request.body, "plain"))
            msg.attach(MIMEText(request.html, "html"))
        else:
            msg = MIMEText(request.body, "plain")

        msg["To"] = ", ".join(to_list)
        msg["Subject"] = request.subject
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)
        if bcc_list:
            msg["Bcc"] = ", ".join(bcc_list)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        send_body: dict = {"raw": raw}
        if request.thread_id:
            # Keep the reply inside the same Gmail thread
            send_body["threadId"] = request.thread_id

        service = build("gmail", "v1", credentials=credentials)
        sent = service.users().messages().send(userId="me", body=send_body).execute()

        logger.info(f"✅ Gmail sent: user={user_id}, to={to_list}, msg_id={sent.get('id')}")
        return MailSendResponse(
            success=True,
            message=f"Email sent successfully to {', '.join(to_list)}",
            message_id=sent.get("id"),
        )

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        status = e.resp.status if hasattr(e, "resp") else 500
        if status in (401, 403):
            raise HTTPException(status_code=401, detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Gmail access expired or missing gmail.send scope. Please reconnect your Google account.",
                "action": "RECONNECT_GOOGLE"
            })
        raise HTTPException(status_code=500, detail={"code": "GMAIL_API_ERROR", "message": str(e)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gmail send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


# ============================================================================
# OUTLOOK / MICROSOFT INTEGRATIONS
# Microsoft OAuth scopes for personal & work accounts
# ============================================================================

# NOTE: Do NOT include 'offline_access', 'openid', or 'profile' here.
# MSAL adds these automatically; passing them explicitly causes a "reserved scope" ValueError.
MICROSOFT_SCOPES = [
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/User.Read",
]

GRAPH_API = "https://graph.microsoft.com/v1.0"


def _ms_authority() -> str:
    """Return MSAL authority URL from MICROSOFT_TENANT_ID env var.

    Defaults to 'common' so the app works for BOTH personal Microsoft accounts
    (@outlook.com, @hotmail.com, @live.com) AND work/school accounts (Entra ID).

    IMPORTANT: Must match the authority used for initial auth AND token refresh.
    Since ms_token._ms_authority() also defaults to 'common', they stay in sync.
    """
    tenant = os.getenv("MICROSOFT_TENANT_ID", "common")
    return f"https://login.microsoftonline.com/{tenant}"


def _ms_redirect_uri() -> str:
    """Return Microsoft OAuth redirect URI from env (must match Azure app registration exactly)."""
    return os.getenv(
        "MICROSOFT_REDIRECT_URI",
        os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:8000")
        + "/api/integrations/microsoft/auth/callback",
    )


def _ms_get_token(user_id: str) -> str:
    """
    Get a valid Microsoft access token.
    Delegates to the centralized get_valid_ms_token() helper which handles
    structured logging and auto-refresh.
    """
    return get_valid_ms_token(user_id)


def _ms_request(
    method: str,
    endpoint: str,
    access_token: str,
    user_id: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Make an authenticated Microsoft Graph request.

    Improvements over original:
    - Structured logging: endpoint, method, response status, error body
    - 401 → one-shot token refresh + retry (when user_id provided)
    - 401 → HTTPException(401, MICROSOFT_UNAUTHORIZED)  [no longer wrapped as 500]
    - 403 → HTTPException(403, MICROSOFT_FORBIDDEN)
    - other errors → HTTPException(502, GRAPH_ERROR)
    """
    url = f"{GRAPH_API}{endpoint}"
    # Only send Content-Type on requests that have a body (POST/PATCH/PUT).
    # Sending Content-Type on GET/DELETE can cause 400/401 with some Graph versions.
    m = method.upper()
    headers: dict = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if m in ("POST", "PATCH", "PUT"):
        headers["Content-Type"] = "application/json"

    auth_prefix = f"Bearer {access_token[:16]}..." if access_token else "Bearer (EMPTY!)"
    logger.info(
        "[MS_GRAPH] → %s %s  auth_prefix=%s",
        m, url, auth_prefix,
    )
    resp = http_requests.request(method=m, url=url, headers=headers, **kwargs)
    logger.info("[MS_GRAPH] ← %s %s  status=%s", method.upper(), url, resp.status_code)

    # ── 401: try one token refresh + retry ───────────────────────────────────
    if resp.status_code == 401:
        # Eagerly read the response body so it's not lost if stream is consumed
        resp_body_401 = resp.text
        www_auth_401 = resp.headers.get("WWW-Authenticate", "(not present)")
        req_id_401 = resp.headers.get(
            "request-id",
            resp.headers.get("x-ms-request-id", resp.headers.get("client-request-id", "(not present)"))
        )
        logger.error(
            "[MS_GRAPH] 401 Unauthorized.\n"
            "  endpoint        = %s\n"
            "  status          = 401\n"
            "  body            = %.500s\n"
            "  WWW-Authenticate= %s\n"
            "  request-id      = %s",
            url, resp_body_401, www_auth_401, req_id_401,
        )
        if user_id:
            try:
                tokens = get_token_storage().load_tokens(user_id, "microsoft")
                if tokens:
                    logger.info("[MS_GRAPH] Retrying with fresh token for user=%s", user_id)
                    new_token = _refresh_ms_token(user_id, tokens)
                    # Rebuild headers from scratch — do NOT reuse the old headers object
                    retry_headers: dict = {
                        "Authorization": f"Bearer {new_token}",
                        "Accept": "application/json",
                    }
                    if m in ("POST", "PATCH", "PUT"):
                        retry_headers["Content-Type"] = "application/json"
                    retry_resp = http_requests.request(
                        method=m, url=url, headers=retry_headers, **kwargs
                    )
                    logger.info(
                        "[MS_GRAPH] Retry ← %s  status=%s", url, retry_resp.status_code
                    )
                    if retry_resp.ok:
                        return {} if retry_resp.status_code == 204 else retry_resp.json()
                    # Retry also failed — log with full headers
                    retry_www = retry_resp.headers.get("WWW-Authenticate", "(not present)")
                    retry_req_id = retry_resp.headers.get(
                        "request-id",
                        retry_resp.headers.get("x-ms-request-id", "(not present)")
                    )
                    logger.error(
                        "[MS_GRAPH] Retry also failed.\n"
                        "  status          = %s\n"
                        "  body            = %.300s\n"
                        "  WWW-Authenticate= %s\n"
                        "  request-id      = %s",
                        retry_resp.status_code, retry_resp.text, retry_www, retry_req_id,
                    )
            except HTTPException:
                pass  # refresh failed; fall through to 401
            except Exception as retry_err:
                logger.warning("[MS_GRAPH] Token refresh attempt failed: %s", retry_err)

        raise HTTPException(
            status_code=401,
            detail={
                "code": "MICROSOFT_UNAUTHORIZED",
                "message": (
                    "Microsoft Graph returned 401 Unauthorized. "
                    "Your session may have expired. "
                    "Please reconnect your Microsoft account via the Integrations page."
                ),
                "action": "RECONNECT_MICROSOFT",
                "graph_endpoint": url,
                "graph_detail": resp_body_401[:400],
                "www_authenticate": www_auth_401,
                "ms_request_id": req_id_401,
            },
        )

    # ── 403: permission / admin consent missing ───────────────────────────────
    if resp.status_code == 403:
        resp_body_403 = resp.text
        www_auth_403 = resp.headers.get("WWW-Authenticate", "(not present)")
        req_id_403 = resp.headers.get(
            "request-id",
            resp.headers.get("x-ms-request-id", resp.headers.get("client-request-id", "(not present)"))
        )
        logger.error(
            "[MS_GRAPH] 403 Forbidden.\n"
            "  endpoint        = %s\n"
            "  body            = %.500s\n"
            "  WWW-Authenticate= %s\n"
            "  request-id      = %s",
            url, resp_body_403, www_auth_403, req_id_403,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "MICROSOFT_FORBIDDEN",
                "message": (
                    "Microsoft Graph returned 403 Forbidden. "
                    "The application is missing a required permission or admin consent. "
                    "Check your Azure app registration API permissions "
                    "(Mail.Read, Mail.Send, Calendars.ReadWrite, User.Read)."
                ),
                "action": "CHECK_MS_APP_PERMISSIONS",
                "graph_endpoint": url,
                "graph_detail": resp_body_403[:400],
                "www_authenticate": www_auth_403,
                "ms_request_id": req_id_403,
            },
        )

    # ── other non-2xx ─────────────────────────────────────────────────────────
    if not resp.ok:
        resp_body_err = resp.text
        www_auth_err = resp.headers.get("WWW-Authenticate", "(not present)")
        req_id_err = resp.headers.get(
            "request-id",
            resp.headers.get("x-ms-request-id", resp.headers.get("client-request-id", "(not present)"))
        )
        logger.error(
            "[MS_GRAPH] Non-2xx error.\n"
            "  endpoint        = %s\n"
            "  status          = %s\n"
            "  body            = %.500s\n"
            "  WWW-Authenticate= %s\n"
            "  request-id      = %s",
            url, resp.status_code, resp_body_err, www_auth_err, req_id_err,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "GRAPH_ERROR",
                "message": f"Microsoft Graph returned {resp.status_code}: {resp_body_err[:400]}",
                "graph_endpoint": url,
                "www_authenticate": www_auth_err,
                "ms_request_id": req_id_err,
            },
        )

    if resp.status_code == 204 or not resp.content:
        return {}
    return resp.json()


@router.get("/microsoft/auth/start")
async def microsoft_auth_start(user_id: str = Query("default_user")):
    """
    Start Microsoft OAuth authentication flow.

    Returns the Microsoft consent URL. Frontend must redirect to auth_url.
    After consent, Microsoft redirects to /microsoft/auth/callback.
    """
    try:
        _cleanup_expired_oauth_states()
        client_id = os.getenv("MICROSOFT_CLIENT_ID")
        client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise HTTPException(status_code=500, detail={
                "code": "CONFIGURATION_ERROR",
                "message": "MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET must be set in .env"
            })
        redirect_uri = _ms_redirect_uri()
        app = ConfidentialClientApplication(
            client_id=client_id, client_credential=client_secret,
            authority=_ms_authority()
        )
        auth_url = app.get_authorization_request_url(
            scopes=MICROSOFT_SCOPES,
            redirect_uri=redirect_uri,
            state=user_id,
            prompt="consent",
        )
        logger.info(f"Starting Microsoft OAuth for user {user_id}, redirect_uri={redirect_uri}")
        return {"auth_url": auth_url, "state": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Microsoft OAuth start error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "OAUTH_START_FAILED", "message": str(e)})


async def _ms_handle_callback(code: str, state: str) -> RedirectResponse:
    """
    Internal Microsoft OAuth callback logic.

    Exchanges the authorization code for tokens and stores them securely.
    Called by the /microsoft/auth/callback route (the only registered callback route).
    The `state` parameter contains the user_id passed at auth/start.
    """
    try:
        user_id = state
        client_id = os.getenv("MICROSOFT_CLIENT_ID")
        client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        redirect_uri = _ms_redirect_uri()
        app = ConfidentialClientApplication(
            client_id=client_id, client_credential=client_secret,
            authority=_ms_authority()
        )
        result = app.acquire_token_by_authorization_code(
            code=code, scopes=MICROSOFT_SCOPES, redirect_uri=redirect_uri
        )
        if "error" in result:
            raise Exception(f"Microsoft OAuth error: {result.get('error_description', result['error'])}")

        # SECURITY: client_id and client_secret are intentionally NOT stored here.
        # They are always read from environment variables (MICROSOFT_CLIENT_ID /
        # MICROSOFT_CLIENT_SECRET) by _refresh_ms_token when a refresh is needed.
        token_data = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "token_type": result.get("token_type", "Bearer"),
            "scopes": result.get("scope", "").split(" "),
            "expires_in": result.get("expires_in", 3600),
            "expires_at": (datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600))).isoformat(),
        }
        get_token_storage().save_tokens(user_id, "microsoft", token_data)
        logger.info(f"✅ Microsoft OAuth successful for user {user_id}")

        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}?auth=success&provider=microsoft", status_code=302)
    except Exception as e:
        logger.error(f"Microsoft OAuth callback error: {e}", exc_info=True)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}?auth=error&provider=microsoft&message={str(e)}", status_code=302)


@router.get("/microsoft/auth/callback")
async def microsoft_auth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...)
):
    """
    Microsoft OAuth callback — the single canonical callback route.

    This path must match MICROSOFT_REDIRECT_URI in .env AND the Redirect URI
    registered in Azure Portal > App Registration > Authentication.
    Azure posts the authorization code here after user consent.
    """
    return await _ms_handle_callback(code=code, state=state)


@router.get("/microsoft/status")
async def microsoft_status(user_id: str = Query("default_user")):
    """Check whether Microsoft tokens are stored for the user."""
    try:
        token_data = get_token_storage().load_tokens(user_id, "microsoft")
        if not token_data or not token_data.get("access_token"):
            return {"connected": False}
        return {
            "connected": True,
            "scopes": token_data.get("scopes", []),
            "has_refresh_token": bool(token_data.get("refresh_token")),
        }
    except Exception as e:
        logger.error(f"Microsoft status error: {e}")
        return {"connected": False}


@router.delete("/microsoft/disconnect")
async def microsoft_disconnect(user_id: str = Query("default_user")):
    """
    Disconnect Microsoft integration by deleting stored OAuth tokens.

    Removes all stored Microsoft tokens for the user. The user will need to
    re-authenticate via /microsoft/auth/start to use Microsoft features again.
    """
    try:
        token_storage = get_token_storage()
        deleted = token_storage.delete_tokens(user_id, "microsoft")
        logger.info(f"Microsoft tokens deleted for user {user_id}: {deleted}")
        return {"success": True, "disconnected": True}
    except Exception as e:
        logger.error(f"Error disconnecting Microsoft for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail={"code": "DISCONNECT_ERROR", "message": str(e)})


@router.get("/microsoft/calendar/events", response_model=CalendarEventsResponse)
async def microsoft_calendar_list_events(
    user_id: str = Query("default_user", description="User ID"),
    max_results: int = Query(10, description="Maximum number of events to return"),
    time_min: Optional[str] = Query(None, description="Lower bound for event start time (ISO 8601)")
):
    """
    List Outlook Calendar events via Microsoft Graph.

    Retrieves upcoming events from the user's Outlook Calendar.
    Requires prior authentication via /outlook/auth/start.
    """
    try:
        access_token = _ms_get_token(user_id)
        now = datetime.utcnow()
        start = time_min or (now.isoformat() + "Z")
        end = (now + timedelta(days=30)).isoformat() + "Z"

        data = _ms_request("GET", "/me/calendarView", access_token, user_id=user_id, params={
            "startDateTime": start, "endDateTime": end,
            "$top": max_results, "$orderby": "start/dateTime",
            "$select": "id,subject,bodyPreview,location,start,end,attendees,isAllDay",
        })
        events = []
        for e in data.get("value", []):
            attendees = [a.get("emailAddress", {}).get("address", "") for a in e.get("attendees", [])]
            events.append(CalendarEvent(
                id=e["id"],
                summary=e.get("subject", "(No title)"),
                description=e.get("bodyPreview"),
                start=e["start"]["dateTime"],
                end=e["end"]["dateTime"],
                location=e.get("location", {}).get("displayName"),
                attendees=attendees or None,
            ))
        logger.info(f"✅ Retrieved {len(events)} Outlook calendar events for user {user_id}")
        return CalendarEventsResponse(events=events, total=len(events))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook calendar list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "GRAPH_ERROR", "message": str(e)})


@router.post("/microsoft/calendar/events", response_model=CalendarEvent)
async def microsoft_calendar_create_event(
    request: CalendarEventCreateRequest,
    user_id: str = Query("default_user", description="User ID")
):
    """
    Create a new Outlook Calendar event via Microsoft Graph.

    Creates an event in the user's primary Outlook Calendar.
    Requires prior authentication via /outlook/auth/start.
    """
    try:
        _validate_calendar_times(request.start, request.end)
        access_token = _ms_get_token(user_id)
        tz_name = _calendar_timezone()
        body = {
            "subject": request.summary,
            "start": {"dateTime": request.start, "timeZone": tz_name},
            "end": {"dateTime": request.end, "timeZone": tz_name},
        }
        if request.description:
            body["body"] = {"contentType": "Text", "content": request.description}
        if request.location:
            body["location"] = {"displayName": request.location}
        if request.attendees:
            body["attendees"] = [{"emailAddress": {"address": e}, "type": "required"} for e in request.attendees]

        created = _ms_request("POST", "/me/calendar/events", access_token, user_id=user_id, json=body)
        logger.info(f"✅ Created Outlook calendar event '{request.summary}' for user {user_id}")
        return CalendarEvent(
            id=created["id"],
            summary=created.get("subject", request.summary),
            description=created.get("bodyPreview"),
            start=created["start"]["dateTime"],
            end=created["end"]["dateTime"],
            location=created.get("location", {}).get("displayName"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook calendar create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "GRAPH_ERROR", "message": str(e)})


@router.patch("/microsoft/calendar/events/{event_id}", response_model=CalendarEvent)
async def microsoft_calendar_update_event(
    event_id: str,
    request: CalendarEventCreateRequest,
    user_id: str = Query("default_user", description="User ID"),
):
    """
    Update an existing Outlook Calendar event via Microsoft Graph (PATCH).

    Partial update: only fields provided in the request body are changed.
    Requires prior Microsoft OAuth (Calendars.ReadWrite scope).
    """
    try:
        access_token = _ms_get_token(user_id)
        tz_name = _calendar_timezone()
        body: dict = {}
        if request.summary:
            body["subject"] = request.summary
        if request.start and request.end:
            _validate_calendar_times(request.start, request.end)
            body["start"] = {"dateTime": request.start, "timeZone": tz_name}
            body["end"]   = {"dateTime": request.end,   "timeZone": tz_name}
        elif request.start:
            body["start"] = {"dateTime": request.start, "timeZone": tz_name}
        elif request.end:
            body["end"]   = {"dateTime": request.end,   "timeZone": tz_name}
        if request.description is not None:
            body["body"] = {"contentType": "Text", "content": request.description}
        if request.location is not None:
            body["location"] = {"displayName": request.location}
        if request.attendees is not None:
            body["attendees"] = [
                {"emailAddress": {"address": e}, "type": "required"}
                for e in request.attendees
            ]

        updated = _ms_request(
            "PATCH", f"/me/calendar/events/{event_id}", access_token, user_id=user_id, json=body
        )
        logger.info(f"✅ Updated Outlook calendar event {event_id} for user {user_id}")
        return CalendarEvent(
            id=updated.get("id", event_id),
            summary=updated.get("subject", request.summary),
            description=updated.get("bodyPreview"),
            start=updated.get("start", {}).get("dateTime", request.start),
            end=updated.get("end", {}).get("dateTime", request.end),
            location=updated.get("location", {}).get("displayName"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook calendar update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "GRAPH_ERROR", "message": str(e)})


@router.delete("/microsoft/calendar/events/{event_id}")
async def microsoft_calendar_delete_event(
    event_id: str,
    user_id: str = Query("default_user", description="User ID"),
):
    """
    Delete an Outlook Calendar event via Microsoft Graph (DELETE).

    Returns 204 / success dict.
    Requires prior Microsoft OAuth (Calendars.ReadWrite scope).
    """
    try:
        access_token = _ms_get_token(user_id)
        _ms_request("DELETE", f"/me/calendar/events/{event_id}", access_token, user_id=user_id)
        logger.info(f"✅ Deleted Outlook calendar event {event_id} for user {user_id}")
        return {"status": "deleted", "event_id": event_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook calendar delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "GRAPH_ERROR", "message": str(e)})


@router.get("/microsoft/mail/messages")
async def microsoft_mail_list_messages(
    user_id: str = Query("default_user", description="User ID"),
    max_results: int = Query(5, description="Max emails to return"),
    unread_only: bool = Query(False, description="Filter to unread only"),
    sender: Optional[str] = Query(None, description="Filter by sender name or email"),
    date_after: Optional[str] = Query(None, description="Filter emails after this date (YYYY-MM-DD)"),
    date_before: Optional[str] = Query(None, description="Filter emails before this date (YYYY-MM-DD)"),
):
    """
    List Outlook messages via Microsoft Graph /me/messages.

    Returns structured list: from, subject, received time, preview.
    Requires prior Microsoft OAuth via /microsoft/auth/start (Mail.Read scope).
    """
    try:
        access_token = _ms_get_token(user_id)

        # Build OData filter
        filters = []
        if unread_only:
            filters.append("isRead eq false")
        if date_after:
            filters.append(f"receivedDateTime ge {date_after}T00:00:00Z")
        if date_before:
            filters.append(f"receivedDateTime le {date_before}T23:59:59Z")

        params: dict = {
            "$top": min(max_results, 20),
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead",
        }
        if filters:
            params["$filter"] = " and ".join(filters)
        if sender:
            # Use $search for sender (Graph doesn't support 'from/emailAddress/address' contains in $filter easily)
            params["$search"] = f'"{sender}"'

        data = _ms_request("GET", "/me/messages", access_token, user_id=user_id, params=params)

        emails = []
        for m in data.get("value", []):
            from_addr = m.get("from", {}).get("emailAddress", {})
            emails.append({
                "id": m["id"],
                "from": f"{from_addr.get('name', '')} <{from_addr.get('address', '')}>".strip(" <>"),
                "subject": m.get("subject", "(No Subject)"),
                "received": m.get("receivedDateTime", ""),
                "preview": m.get("bodyPreview", "")[:200],
                "unread": not m.get("isRead", True),
            })

        logger.info(f"✅ Outlook mail list: user={user_id}, count={len(emails)}")
        return {"emails": emails, "total": len(emails)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook mail list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "GRAPH_ERROR", "message": str(e)})


@router.post("/microsoft/mail/send", response_model=MailSendResponse)
async def microsoft_mail_send(
    request: MailSendRequest,
    user_id: str = Query("default_user", description="User ID")
):
    """
    Send an email via Outlook using Microsoft Graph /me/sendMail.

    Accepts plain text and optional HTML body.
    Requires prior authentication via /outlook/auth/start (Mail.Send scope).
    """
    try:
        access_token = _ms_get_token(user_id)
        to_list = request.to_list()
        cc_list = request.cc_list()
        bcc_list = request.bcc_list()

        content_type = "HTML" if request.html else "Text"
        content = request.html if request.html else request.body

        if request.reply_to_id:
            # Use the Graph /reply endpoint — preserves conversation thread
            _ms_request(
                "POST",
                f"/me/messages/{request.reply_to_id}/reply",
                access_token,
                user_id=user_id,
                json={"comment": content},
            )
        else:
            message: dict = {
                "subject": request.subject,
                "body": {"contentType": content_type, "content": content},
                "toRecipients": [{"emailAddress": {"address": e}} for e in to_list],
            }
            if cc_list:
                message["ccRecipients"] = [{"emailAddress": {"address": e}} for e in cc_list]
            if bcc_list:
                message["bccRecipients"] = [{"emailAddress": {"address": e}} for e in bcc_list]
            _ms_request("POST", "/me/sendMail", access_token, user_id=user_id, json={"message": message, "saveToSentItems": True})

        logger.info(f"✅ Outlook email sent: user={user_id}, to={to_list}, subject='{request.subject}', reply_to_id={request.reply_to_id}")
        return MailSendResponse(
            success=True,
            message=f"Email sent successfully via Outlook to {', '.join(to_list)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook mail send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "GRAPH_ERROR", "message": str(e)})


@router.get("/microsoft/mail/messages/{message_id}")
async def microsoft_mail_get_message(
    message_id: str,
    user_id: str = Query("default_user", description="User ID"),
):
    """
    Read a specific Outlook message by ID via Microsoft Graph.

    Returns the full message body plus headers.
    Requires prior Microsoft OAuth (Mail.Read scope).
    """
    try:
        access_token = _ms_get_token(user_id)
        msg = _ms_request(
            "GET",
            f"/me/messages/{message_id}",
            access_token,
            user_id=user_id,
            params={
                "$select": (
                    "id,subject,from,toRecipients,ccRecipients,"
                    "receivedDateTime,isRead,hasAttachments,body,bodyPreview"
                )
            },
        )
        from_addr = msg.get("from", {}).get("emailAddress", {})
        logger.info(f"✅ Outlook mail get: user={user_id}, message_id={message_id}")
        return {
            "id": msg["id"],
            "subject": msg.get("subject", "(No Subject)"),
            "from": f"{from_addr.get('name', '')} <{from_addr.get('address', '')}>".strip(" <>"),
            "to": [
                r.get("emailAddress", {}).get("address", "")
                for r in msg.get("toRecipients", [])
            ],
            "cc": [
                r.get("emailAddress", {}).get("address", "")
                for r in msg.get("ccRecipients", [])
            ] or None,
            "received": msg.get("receivedDateTime", ""),
            "unread": not msg.get("isRead", True),
            "has_attachments": msg.get("hasAttachments", False),
            "body": msg.get("body", {}).get("content", ""),
            "body_type": msg.get("body", {}).get("contentType", "text"),
            "preview": msg.get("bodyPreview", "")[:300],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook mail get error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "GRAPH_ERROR", "message": str(e)})


# ============================================================================
# MICROSOFT DIAGNOSTIC ENDPOINTS
# ============================================================================

@router.get("/microsoft/token-debug")
async def microsoft_token_debug(user_id: str = Query("default_user")):
    """
    Safe token diagnostic endpoint — returns decoded JWT payload fields only.

    NEVER returns the full token.
    Returns: aud, scp, exp, token_prefix (16 chars), has_refresh_token,
             expires_at, expired_or_expiring_soon, MICROSOFT_TENANT_ID,
             authority that would be used, stored_scopes.

    This is the primary tool to diagnose "wrong token audience" (id_token
    stored instead of Graph access_token).
    """
    from utils.ms_token import _decode_jwt_payload

    tokens = get_token_storage().load_tokens(user_id, "microsoft")
    if not tokens:
        return {
            "connected": False,
            "reason": f"No tokens found for user_id={user_id!r}",
            "hint": "Call /microsoft/auth/start to authenticate.",
        }

    access_token: str = tokens.get("access_token", "")
    refresh_token: str = tokens.get("refresh_token", "")
    expires_at: str = tokens.get("expires_at", "")

    # Safe prefix only
    token_prefix = (access_token[:16] + "...") if len(access_token) > 16 else "(short/empty)"

    # Decode JWT for diagnostics
    payload = _decode_jwt_payload(access_token) if access_token else {}
    aud = payload.get("aud", "(not decodable — may be opaque token)")
    scp = payload.get("scp", payload.get("roles", "(not found in jwt)"))
    exp_claim = payload.get("exp")
    exp_claim_str = None
    if exp_claim:
        try:
            exp_claim_str = datetime.utcfromtimestamp(exp_claim).isoformat()
        except Exception:
            pass

    # Expiry check
    expired = None
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at)
            expired = datetime.utcnow() >= exp_dt - timedelta(minutes=5)
        except Exception:
            expired = "parse_error"

    # Audience diagnosis
    aud_str = str(aud).lower()
    aud_ok = "graph.microsoft.com" in aud_str or "00000003-0000-0000-c000-000000000000" in aud_str
    aud_diagnosis = "✅ Correct Graph audience" if aud_ok else (
        f"❌ WRONG AUDIENCE — token is not for Graph. "
        f"Expected 'https://graph.microsoft.com' or '00000003-0000-0000-c000-000000000000', got: {aud}. "
        "This will cause 401 from Graph. Delete token file and re-authenticate."
    )

    tenant_id = os.getenv("MICROSOFT_TENANT_ID", "consumers")
    authority = f"https://login.microsoftonline.com/{tenant_id}"

    return {
        "connected": True,
        "token_prefix": token_prefix,
        "has_refresh_token": bool(refresh_token),
        "stored_scopes": tokens.get("scopes", []),
        "expires_at": expires_at,
        "expired_or_expiring_soon": expired,
        "jwt": {
            "aud": aud,
            "scp": scp,
            "exp": exp_claim_str,
            "aud_ok_for_graph": aud_ok,
            "aud_diagnosis": aud_diagnosis,
        },
        "config": {
            "MICROSOFT_TENANT_ID": tenant_id,
            "authority": authority,
            "MICROSOFT_CLIENT_ID": os.getenv("MICROSOFT_CLIENT_ID", "(not set)"),
            "note": (
                "For personal accounts (@outlook.com, @hotmail.com): use MICROSOFT_TENANT_ID=consumers. "
                "For work accounts: use your tenant GUID or 'common'."
            ),
        },
    }


@router.get("/microsoft/debug/me")
async def microsoft_debug_me(user_id: str = Query("default_user")):
    """
    Smoke test endpoint — loads stored token and calls GET /me on Microsoft Graph.

    Returns:
      - status: HTTP status from Graph
      - ok: True if 2xx
      - body_snippet: first 500 chars of the Graph response body
      - www_authenticate: WWW-Authenticate header from error responses
      - request_id: Microsoft request-id for support tracing
      - token_info: safe diagnostics (len, prefix, aud, iss, scp, tid) — NO full token

    Diagnostic logic:
      - If /me FAILS → auth is fundamentally broken (wrong authority, wrong audience, etc.)
      - If /me WORKS but calendar/mail fail → issue is scope-specific (missing Calendars.ReadWrite etc.)

    Use this as the FIRST diagnostic step for any Microsoft Graph 401 error.
    """
    from utils.ms_token import _decode_jwt_payload

    # Step 1: load token (will attempt refresh if expired)
    try:
        access_token = _ms_get_token(user_id)
    except HTTPException as e:
        return {
            "status": e.status_code,
            "ok": False,
            "body_snippet": None,
            "www_authenticate": None,
            "request_id": None,
            "token_info": None,
            "error": e.detail,
            "hint": "Token load failed. Check /microsoft/token-debug for details.",
        }

    # Step 2: safe token diagnostics
    token_len = len(access_token)
    token_prefix = (access_token[:20] + "...") if token_len > 20 else "(short)"
    payload = _decode_jwt_payload(access_token)

    token_info = {
        "len": token_len,
        "prefix": token_prefix,
        "aud": payload.get("aud", "(not decodable)"),
        "iss": payload.get("iss", "(not found)"),
        "scp": payload.get("scp", payload.get("roles", "(not found)")),
        "tid": payload.get("tid", "(not found)"),
    }

    logger.info(
        "[DEBUG_ME] user=%s  token_len=%d  token_prefix=%s  "
        "jwt.aud=%s  jwt.iss=%s  jwt.scp=%s  jwt.tid=%s",
        user_id, token_len, token_prefix,
        token_info["aud"], token_info["iss"], token_info["scp"], token_info["tid"],
    )

    # Step 3: call GET /me — fresh headers built from scratch
    me_headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    me_resp = http_requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers=me_headers,
        timeout=10,
    )

    resp_status = me_resp.status_code
    www_auth = me_resp.headers.get("WWW-Authenticate", None)
    ms_request_id = me_resp.headers.get(
        "request-id",
        me_resp.headers.get("x-ms-request-id", me_resp.headers.get("client-request-id", None))
    )

    try:
        body_json = me_resp.json()
        body_snippet = str(body_json)[:500]
    except Exception:
        body_snippet = me_resp.text[:500]

    logger.info(
        "[DEBUG_ME] user=%s  GET /me → status=%s  www_authenticate=%s  request_id=%s  body=%.300s",
        user_id, resp_status, www_auth, ms_request_id, body_snippet,
    )

    if me_resp.ok:
        hint = (
            "✅ /me succeeded — token is valid for Microsoft Graph. "
            "If calendar or mail calls still fail with 401/403, the issue is scope-specific "
            "(missing Calendars.ReadWrite, Mail.Read, or Mail.Send consent). "
            "Reconnect Microsoft account to re-consent all scopes."
        )
    else:
        hint = (
            "❌ /me failed — auth is fundamentally broken. Most common causes:\n"
            "1. Wrong authority (was 'consumers' or tenant-specific, now fixed to 'common')\n"
            "2. Wrong token audience (id_token stored instead of access_token)\n"
            "3. Token genuinely expired and refresh failed\n"
            "4. Azure app not configured for 'common' (All Entra ID + personal accounts)\n"
            "Check www_authenticate and token_info.aud. "
            "If aud != 'https://graph.microsoft.com', disconnect and reconnect your account."
        )

    return {
        "endpoint": "GET https://graph.microsoft.com/v1.0/me",
        "status": resp_status,
        "ok": me_resp.ok,
        "body_snippet": body_snippet,
        "www_authenticate": www_auth,
        "request_id": ms_request_id,
        "token_info": token_info,
        "hint": hint,
    }


@router.get("/microsoft/test-connection")
async def microsoft_test_connection(user_id: str = Query("default_user")):
    """
    Live connectivity test — calls GET /me on Microsoft Graph.

    Returns the raw Graph response (or error). Use this to confirm:
    - Token is valid for Graph
    - Scopes are granted
    - User identity (displayName, mail, userPrincipalName)

    If this returns 200 but calendar/mail calls return 401, the issue is
    scope-specific (e.g., Calendars.ReadWrite not granted).
    """
    try:
        access_token = _ms_get_token(user_id)
        me_resp = http_requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10,
        )
        status = me_resp.status_code
        try:
            body = me_resp.json()
        except Exception:
            body = me_resp.text[:500]

        if status == 200:
            return {
                "graph_reachable": True,
                "status": status,
                "user": {
                    "displayName": body.get("displayName"),
                    "mail": body.get("mail"),
                    "userPrincipalName": body.get("userPrincipalName"),
                    "id": body.get("id"),
                },
                "hint": (
                    "Token is valid for Graph. If specific APIs still fail "
                    "with 401/403, check that the required scopes were granted "
                    "(Calendars.ReadWrite, Mail.Read, Mail.Send)."
                ),
            }
        else:
            return {
                "graph_reachable": False,
                "status": status,
                "graph_response": body,
                "hint": (
                    "Graph rejected the token. Check /microsoft/token-debug for aud/scp details. "
                    "Most common cause: wrong MICROSOFT_TENANT_ID or missing admin consent."
                    if status == 401
                    else f"Unexpected Graph error: {status}"
                ),
            }
    except HTTPException as e:
        return {
            "graph_reachable": False,
            "error_code": e.detail.get("code") if isinstance(e.detail, dict) else str(e.detail),
            "error_message": e.detail.get("message") if isinstance(e.detail, dict) else str(e.detail),
            "status": e.status_code,
        }
    except Exception as e:
        logger.error(f"Microsoft test-connection error: {e}", exc_info=True)
        return {"graph_reachable": False, "error": str(e)}
