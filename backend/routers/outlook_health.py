"""
Outlook Health & Debug Endpoint

Provides diagnostic information about Outlook OAuth integration status
without exposing sensitive credentials.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query

from utils.token_storage import get_token_storage
from services.providers.microsoft_provider import MicrosoftEmailProvider, MicrosoftCalendarProvider

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status")
async def get_outlook_status(
    user_id: str = Query("default_user", description="User identifier")
) -> Dict[str, Any]:
    """
    Get Outlook OAuth and API status for debugging.
    
    Returns:
        - Token status (exists, expiry)
        - Scopes present
        - API connectivity test
        - No sensitive data (tokens, secrets)
    
    Args:
        user_id: User identifier
    
    Returns:
        Status information dict
    """
    try:
        token_storage = get_token_storage()
        tokens = token_storage.load_tokens(user_id, "microsoft")
        
        if not tokens:
            return {
                "status": "not_connected",
                "message": "No Microsoft/Outlook tokens found for this user",
                "user_id": user_id,
                "oauth_required": True,
                "oauth_url": "/oauth/outlook/authorize"
            }
        
        # Check token expiry
        expires_at = tokens.get("expires_at")
        is_expired = False
        expires_in_minutes = None
        
        if expires_at:
            try:
                expiry_time = datetime.fromisoformat(expires_at)
                now = datetime.utcnow()
                is_expired = now >= expiry_time
                
                if not is_expired:
                    time_diff = expiry_time - now
                    expires_in_minutes = int(time_diff.total_seconds() / 60)
            except Exception as e:
                logger.warning(f"Error parsing expiry time: {e}")
        
        # Get scopes (sanitized)
        scopes = tokens.get("scopes", [])
        
        # Test API connectivity
        api_test_result = {"email": "unknown", "status": "not_tested"}
        try:
            email_provider = MicrosoftEmailProvider(user_id)
            user_email = await email_provider.get_user_email()
            api_test_result = {
                "email": user_email,
                "status": "success"
            }
        except Exception as e:
            api_test_result = {
                "email": None,
                "status": "error",
                "error": str(e)
            }
        
        # Check if required scopes are present
        required_email_scopes = ["Mail.Send", "Mail.Read"]
        required_calendar_scopes = ["Calendars.ReadWrite"]
        
        has_email_scopes = any(
            scope for scope in scopes 
            if any(req in scope for req in required_email_scopes) or ".default" in scope
        )
        
        has_calendar_scopes = any(
            scope for scope in scopes 
            if any(req in scope for req in required_calendar_scopes) or ".default" in scope
        )
        
        # Build status response
        status_response = {
            "status": "connected",
            "user_id": user_id,
            "token_info": {
                "exists": True,
                "is_expired": is_expired,
                "expires_in_minutes": expires_in_minutes,
                "has_refresh_token": bool(tokens.get("refresh_token"))
            },
            "scopes": {
                "present": scopes if scopes else ["(using .default - all permissions)"],
                "has_email_scopes": has_email_scopes,
                "has_calendar_scopes": has_calendar_scopes
            },
            "api_connectivity": api_test_result,
            "capabilities": {
                "can_send_email": has_email_scopes and api_test_result["status"] == "success",
                "can_read_email": has_email_scopes and api_test_result["status"] == "success",
                "can_manage_calendar": has_calendar_scopes and api_test_result["status"] == "success"
            },
            "config_status": {
                "client_id_configured": bool(os.getenv("MICROSOFT_CLIENT_ID")),
                "client_secret_configured": bool(os.getenv("MICROSOFT_CLIENT_SECRET")),
                "redirect_uri_configured": bool(os.getenv("OUTLOOK_REDIRECT_URI"))
            }
        }
        
        # Add warnings
        warnings = []
        if is_expired:
            warnings.append("Token is expired - will attempt auto-refresh on next API call")
        if not has_email_scopes:
            warnings.append("Email scopes may be missing - email operations may fail")
        if not has_calendar_scopes:
            warnings.append("Calendar scopes may be missing - calendar operations may fail")
        if api_test_result["status"] == "error":
            warnings.append(f"API connectivity test failed: {api_test_result.get('error')}")
        
        if warnings:
            status_response["warnings"] = warnings
        
        return status_response
        
    except Exception as e:
        logger.error(f"Outlook status check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check Outlook status: {str(e)}"
        )


@router.post("/test-send")
async def test_outlook_send(
    user_id: str = Query("default_user", description="User identifier"),
    to_email: str = Query(..., description="Test recipient email")
) -> Dict[str, Any]:
    """
    Test Outlook email sending with a simple test email.
    
    SAFETY: This is a DRY RUN by default - no email is actually sent.
    To actually send, API would need to be modified.
    
    Args:
        user_id: User identifier
        to_email: Test recipient
    
    Returns:
        Test result
    """
    try:
        from services.providers.base import EmailSendRequest
        
        email_provider = MicrosoftEmailProvider(user_id)
        
        # DRY RUN TEST - does not actually send
        request = EmailSendRequest(
            to=[to_email],
            subject="OrganAIzer Outlook Test",
            body="This is a test email from OrganAIzer to verify Outlook integration.",
            dry_run=True,  # SAFETY: Dry run only
            confirm=True
        )
        
        result = await email_provider.send_email(request)
        
        return {
            "test_type": "dry_run",
            "status": "success",
            "message": "Outlook send test completed (dry run - no email sent)",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Outlook send test error: {e}", exc_info=True)
        return {
            "test_type": "dry_run",
            "status": "error",
            "message": f"Outlook send test failed: {str(e)}",
            "error": str(e)
        }


@router.post("/test-calendar")
async def test_outlook_calendar(
    user_id: str = Query("default_user", description="User identifier")
) -> Dict[str, Any]:
    """
    Test Outlook Calendar access.
    
    Lists upcoming events to verify calendar connectivity.
    
    Args:
        user_id: User identifier
    
    Returns:
        Test result with event count
    """
    try:
        calendar_provider = MicrosoftCalendarProvider(user_id)
        
        # Try to list events (safe read operation)
        events = await calendar_provider.list_events(limit=5)
        
        return {
            "status": "success",
            "message": "Outlook Calendar access verified",
            "event_count": len(events),
            "sample_events": [
                {
                    "id": event.id,
                    "summary": event.summary,
                    "start": event.start
                }
                for event in events[:3]
            ] if events else []
        }
        
    except Exception as e:
        logger.error(f"Outlook calendar test error: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Outlook Calendar test failed: {str(e)}",
            "error": str(e)
        }
