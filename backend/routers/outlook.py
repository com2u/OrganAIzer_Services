from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from services.outlook_service import read_emails, send_email, read_calendar_events, get_device_code_info, get_graph_client

logger = logging.getLogger(__name__)

router = APIRouter()

class SendEmailRequest(BaseModel):
    to: str
    subject: str
    body: str

class ReadEmailsRequest(BaseModel):
    max_results: int = 10

class ReadCalendarRequest(BaseModel):
    max_results: int = 10

@router.get("/emails")
async def get_emails(max_results: int = 10):
    try:
        emails = await read_emails(max_results)
        return {"emails": emails}
    except Exception as e:
        logger.error(f"Failed to read emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emails/send")
async def send_email_endpoint(request: SendEmailRequest):
    try:
        result = await send_email(request.to, request.subject, request.body)
        return result
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calendar/events")
async def get_calendar_events(max_results: int = 10):
    try:
        events = await read_calendar_events(max_results)
        return {"events": events}
    except Exception as e:
        logger.error(f"Failed to read calendar events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth")
async def get_auth_info():
    try:
        # Reset client to force re-authentication
        from services.outlook_service import _graph_client, _cache, _device_code_info
        _graph_client = None
        _device_code_info = None
        # Trigger client creation to get device code
        get_graph_client()
        info = get_device_code_info()
        if info:
            return {
                "user_code": info.get("user_code"),
                "verification_uri": info.get("verification_uri"),
                "message": info.get("message")
            }
        return {"message": "Authentication initiated"}
    except Exception as e:
        logger.error(f"Failed to get auth info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))