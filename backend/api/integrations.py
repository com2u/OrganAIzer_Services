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

# OAuth state storage (in production, use Redis or database)
_oauth_states = {}


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


@router.get("/google/calendar/events", response_model=CalendarEventsResponse)
async def google_calendar_list_events(
    user_id: str = Query("default_user", description="User ID"),
    max_results: int = Query(10, description="Maximum number of events to return"),
    time_min: Optional[str] = Query(None, description="Lower bound for event start time (ISO 8601)")
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
        
        # Call Calendar API
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
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
        
        # Build Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Create event body
        event_body = {
            'summary': request.summary,
            'start': {
                'dateTime': request.start,
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': request.end,
                'timeZone': 'UTC',
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
            attendees=[att.get('email') for att in created_event.get('attendees', [])] if created_event.get('attendees') else None
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

        service = build("gmail", "v1", credentials=credentials)
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()

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

MICROSOFT_SCOPES = [
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/User.Read",
    "offline_access",
]

GRAPH_API = "https://graph.microsoft.com/v1.0"


def _ms_get_token(user_id: str) -> str:
    """Load Microsoft access token for user, refreshing if expired."""
    token_storage = get_token_storage()
    tokens = token_storage.load_tokens(user_id, "microsoft")
    if not tokens:
        raise HTTPException(
            status_code=401,
            detail={"code": "NOT_AUTHENTICATED",
                    "message": "Microsoft account not connected. Please authenticate via /api/integrations/outlook/auth/start.",
                    "action": "CONNECT_MICROSOFT"}
        )
    expires_at = tokens.get("expires_at")
    if expires_at:
        try:
            if datetime.utcnow() >= datetime.fromisoformat(expires_at) - timedelta(minutes=5):
                client_id = os.getenv("MICROSOFT_CLIENT_ID")
                client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
                app = ConfidentialClientApplication(
                    client_id=client_id, client_credential=client_secret,
                    authority="https://login.microsoftonline.com/consumers"
                )
                result = app.acquire_token_by_refresh_token(
                    tokens.get("refresh_token"), scopes=["https://graph.microsoft.com/.default"]
                )
                if "error" not in result:
                    tokens.update({
                        "access_token": result["access_token"],
                        "refresh_token": result.get("refresh_token", tokens.get("refresh_token")),
                        "expires_at": (datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600))).isoformat(),
                    })
                    token_storage.save_tokens(user_id, "microsoft", tokens)
        except Exception as e:
            logger.warning(f"Microsoft token refresh warning: {e}")
    return tokens.get("access_token")


def _ms_request(method: str, endpoint: str, access_token: str, **kwargs):
    """Make authenticated Microsoft Graph request."""
    resp = http_requests.request(
        method, f"{GRAPH_API}{endpoint}",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        **kwargs
    )
    resp.raise_for_status()
    return {} if resp.status_code == 204 else resp.json()


@router.get("/outlook/auth/start")
async def outlook_auth_start(user_id: str = Query("default_user")):
    """
    Start Microsoft/Outlook OAuth authentication flow.

    Redirects user to Microsoft consent screen to grant Calendar and Mail access.
    After consent, Microsoft redirects to /outlook/auth/callback.
    """
    try:
        client_id = os.getenv("MICROSOFT_CLIENT_ID")
        client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise HTTPException(status_code=500, detail={
                "code": "CONFIGURATION_ERROR",
                "message": "MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET must be set in .env"
            })
        redirect_uri = (
            os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:8000")
            + "/api/integrations/outlook/auth/callback"
        )
        app = ConfidentialClientApplication(
            client_id=client_id, client_credential=client_secret,
            authority="https://login.microsoftonline.com/consumers"
        )
        auth_url = app.get_authorization_request_url(
            scopes=MICROSOFT_SCOPES,
            redirect_uri=redirect_uri,
            state=user_id,
            prompt="consent",
        )
        logger.info(f"Starting Microsoft OAuth for user {user_id}")
        return RedirectResponse(url=auth_url, status_code=302)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Microsoft OAuth start error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "OAUTH_START_FAILED", "message": str(e)})


@router.get("/outlook/auth/callback")
async def outlook_auth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...)
):
    """
    Handle Microsoft/Outlook OAuth callback.

    Exchanges the authorization code for tokens and stores them securely.
    The `state` parameter contains the user_id.
    """
    try:
        user_id = state
        client_id = os.getenv("MICROSOFT_CLIENT_ID")
        client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        redirect_uri = (
            os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:8000")
            + "/api/integrations/outlook/auth/callback"
        )
        app = ConfidentialClientApplication(
            client_id=client_id, client_credential=client_secret,
            authority="https://login.microsoftonline.com/consumers"
        )
        result = app.acquire_token_by_authorization_code(
            code=code, scopes=MICROSOFT_SCOPES, redirect_uri=redirect_uri
        )
        if "error" in result:
            raise Exception(f"Microsoft OAuth error: {result.get('error_description', result['error'])}")

        token_data = {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "token_type": result.get("token_type", "Bearer"),
            "scopes": result.get("scope", "").split(" "),
            "expires_in": result.get("expires_in", 3600),
            "expires_at": (datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600))).isoformat(),
            "client_id": client_id,
            "client_secret": client_secret,
        }
        get_token_storage().save_tokens(user_id, "microsoft", token_data)
        logger.info(f"✅ Microsoft OAuth successful for user {user_id}")

        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}?auth=success&provider=microsoft", status_code=302)
    except Exception as e:
        logger.error(f"Microsoft OAuth callback error: {e}", exc_info=True)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(url=f"{frontend_url}?auth=error&provider=microsoft&message={str(e)}", status_code=302)


@router.get("/outlook/status")
async def outlook_status(user_id: str = Query("default_user")):
    """Check whether Microsoft/Outlook tokens are stored for the user."""
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


@router.get("/outlook/calendar/events", response_model=CalendarEventsResponse)
async def outlook_calendar_list_events(
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

        data = _ms_request("GET", "/me/calendarView", access_token, params={
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


@router.post("/outlook/calendar/events", response_model=CalendarEvent)
async def outlook_calendar_create_event(
    request: CalendarEventCreateRequest,
    user_id: str = Query("default_user", description="User ID")
):
    """
    Create a new Outlook Calendar event via Microsoft Graph.

    Creates an event in the user's primary Outlook Calendar.
    Requires prior authentication via /outlook/auth/start.
    """
    try:
        access_token = _ms_get_token(user_id)
        body = {
            "subject": request.summary,
            "start": {"dateTime": request.start, "timeZone": "UTC"},
            "end": {"dateTime": request.end, "timeZone": "UTC"},
        }
        if request.description:
            body["body"] = {"contentType": "Text", "content": request.description}
        if request.location:
            body["location"] = {"displayName": request.location}
        if request.attendees:
            body["attendees"] = [{"emailAddress": {"address": e}, "type": "required"} for e in request.attendees]

        created = _ms_request("POST", "/me/calendar/events", access_token, json=body)
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


@router.post("/outlook/mail/send", response_model=MailSendResponse)
async def outlook_mail_send(
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

        message: dict = {
            "subject": request.subject,
            "body": {"contentType": content_type, "content": content},
            "toRecipients": [{"emailAddress": {"address": e}} for e in to_list],
        }
        if cc_list:
            message["ccRecipients"] = [{"emailAddress": {"address": e}} for e in cc_list]
        if bcc_list:
            message["bccRecipients"] = [{"emailAddress": {"address": e}} for e in bcc_list]

        _ms_request("POST", "/me/sendMail", access_token, json={"message": message, "saveToSentItems": True})

        logger.info(f"✅ Outlook email sent: user={user_id}, to={to_list}, subject='{request.subject}'")
        return MailSendResponse(
            success=True,
            message=f"Email sent successfully via Outlook to {', '.join(to_list)}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlook mail send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail={"code": "GRAPH_ERROR", "message": str(e)})
