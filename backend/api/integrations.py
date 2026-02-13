"""
API endpoints for external integrations (Google, Outlook).
"""

import logging
import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from typing import Optional
from datetime import datetime, timedelta
import secrets

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
        
        # Redirect to success page (you can customize this)
        return RedirectResponse(
            url=f"http://localhost:3000?auth=success&provider=google",
            status_code=302
        )
    
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        return RedirectResponse(
            url=f"http://localhost:3000?auth=error&message={str(e)}",
            status_code=302
        )


@router.get("/google/calendar/events", response_model=CalendarEventsResponse)
async def google_calendar_list_events(
    max_results: int = Query(10, description="Maximum number of events to return"),
    time_min: Optional[str] = Query(None, description="Lower bound for event start time (ISO 8601)")
):
    """
    List Google Calendar events.
    
    **Status: BETA/PLANNED**
    
    Retrieves events from the user's primary Google Calendar.
    Requires prior authentication via /google/auth/start.
    """
    # TODO: Implement Google Calendar event listing
    logger.warning("Google calendar list called - not yet implemented")
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Google Calendar integration is planned but not yet implemented",
            "details": {"status": "beta"}
        }
    )


@router.post("/google/calendar/events", response_model=CalendarEvent)
async def google_calendar_create_event(request: CalendarEventCreateRequest):
    """
    Create a new Google Calendar event.
    
    **Status: BETA/PLANNED**
    
    Creates an event in the user's primary Google Calendar.
    Requires prior authentication via /google/auth/start.
    """
    # TODO: Implement Google Calendar event creation
    logger.warning("Google calendar create called - not yet implemented")
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Google Calendar integration is planned but not yet implemented",
            "details": {"status": "beta"}
        }
    )


@router.post("/google/gmail/send", response_model=MailSendResponse)
async def google_gmail_send(request: MailSendRequest):
    """
    Send an email via Gmail.
    
    **Status: BETA/PLANNED**
    
    Sends an email using the authenticated user's Gmail account.
    Requires prior authentication via /google/auth/start.
    """
    # TODO: Implement Gmail send functionality
    logger.warning("Gmail send called - not yet implemented")
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Gmail integration is planned but not yet implemented",
            "details": {"status": "beta"}
        }
    )


# ============================================================================
# OUTLOOK INTEGRATIONS
# ============================================================================

@router.get("/outlook/auth/start", response_model=AuthStartResponse)
async def outlook_auth_start():
    """
    Start Outlook/Microsoft OAuth authentication flow.
    
    **Status: BETA/PLANNED**
    
    Returns OAuth URL to redirect user for Microsoft account authorization.
    This will grant access to Outlook Calendar and Mail.
    """
    # TODO: Implement Outlook OAuth flow
    logger.warning("Outlook auth start called - not yet implemented")
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Outlook authentication is planned but not yet implemented",
            "details": {"status": "beta"}
        }
    )


@router.post("/outlook/auth/callback", response_model=AuthCallbackResponse)
async def outlook_auth_callback(request: AuthCallbackRequest):
    """
    Handle Outlook/Microsoft OAuth callback.
    
    **Status: BETA/PLANNED**
    
    Processes the OAuth callback from Microsoft and stores access tokens.
    """
    # TODO: Implement Outlook OAuth callback handling
    logger.warning("Outlook auth callback called - not yet implemented")
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Outlook OAuth callback is planned but not yet implemented",
            "details": {"status": "beta"}
        }
    )


@router.get("/outlook/calendar/events", response_model=CalendarEventsResponse)
async def outlook_calendar_list_events(
    max_results: int = Query(10, description="Maximum number of events to return"),
    time_min: Optional[str] = Query(None, description="Lower bound for event start time (ISO 8601)")
):
    """
    List Outlook Calendar events.
    
    **Status: BETA/PLANNED**
    
    Retrieves events from the user's Outlook Calendar.
    Requires prior authentication via /outlook/auth/start.
    """
    # TODO: Implement Outlook Calendar event listing
    logger.warning("Outlook calendar list called - not yet implemented")
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Outlook Calendar integration is planned but not yet implemented",
            "details": {"status": "beta"}
        }
    )


@router.post("/outlook/calendar/events", response_model=CalendarEvent)
async def outlook_calendar_create_event(request: CalendarEventCreateRequest):
    """
    Create a new Outlook Calendar event.
    
    **Status: BETA/PLANNED**
    
    Creates an event in the user's Outlook Calendar.
    Requires prior authentication via /outlook/auth/start.
    """
    # TODO: Implement Outlook Calendar event creation
    logger.warning("Outlook calendar create called - not yet implemented")
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Outlook Calendar integration is planned but not yet implemented",
            "details": {"status": "beta"}
        }
    )


@router.post("/outlook/mail/send", response_model=MailSendResponse)
async def outlook_mail_send(request: MailSendRequest):
    """
    Send an email via Outlook.
    
    **Status: BETA/PLANNED**
    
    Sends an email using the authenticated user's Outlook account.
    Requires prior authentication via /outlook/auth/start.
    """
    # TODO: Implement Outlook mail send functionality
    logger.warning("Outlook mail send called - not yet implemented")
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Outlook Mail integration is planned but not yet implemented",
            "details": {"status": "beta"}
        }
    )
