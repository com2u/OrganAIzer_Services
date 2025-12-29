from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from services.google_service import read_emails, send_email, read_calendar_events

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
        emails = read_emails(max_results)
        return {"emails": emails}
    except Exception as e:
        logger.error(f"Failed to read emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emails/send")
async def send_email_endpoint(request: SendEmailRequest):
    try:
        result = send_email(request.to, request.subject, request.body)
        return {"message": "Email sent successfully", "result": result}
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calendar/events")
async def get_calendar_events(max_results: int = 10):
    try:
        events = read_calendar_events(max_results)
        return {"events": events}
    except Exception as e:
        logger.error(f"Failed to read calendar events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))