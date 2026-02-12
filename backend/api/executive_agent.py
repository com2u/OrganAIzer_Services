"""
Executive Agent API endpoints.

Provides conversational interface to the OrganAIzer Executive Agent.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.executive_agent_service import ExecutiveAgent

logger = logging.getLogger(__name__)

router = APIRouter()


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class ChatRequest(BaseModel):
    """Request to chat with the Executive Agent."""
    message: str
    session_id: Optional[str] = "default"
    user_id: Optional[str] = "default_user"
    provider: Optional[str] = "gmail"


class ChatResponse(BaseModel):
    """Executive Agent chat response."""
    message: str
    success: bool
    type: Optional[str] = None
    data: Optional[dict] = None
    action_needed: Optional[str] = None
    error: Optional[str] = None
    # State Machine Information
    agent_state: Optional[str] = None  # IDLE, EMAIL_FLOW, CALENDAR_FLOW, etc.
    active_task: Optional[dict] = None  # Current active task details
    pending_action: Optional[dict] = None  # Pending action awaiting confirmation
    last_action: Optional[dict] = None  # Last completed action from history


class SessionInfoResponse(BaseModel):
    """Session information response."""
    session_id: str
    message_count: int
    context: dict
    last_activity: str


# ==============================================================================
# EXECUTIVE AGENT ENDPOINTS
# ==============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """
    Chat with the OrganAIzer Executive Agent.
    
    The Executive Agent is your intelligent companion that can:
    - Read, summarize, and draft emails (Gmail & Outlook)
    - Manage calendar events (Google Calendar & Outlook)
    - Answer knowledge queries (history, geography, facts)
    - Generate images and convert text to speech
    - Remember conversation context within the session
    
    Communication Style:
    - Professional for email operations
    - Conversational and witty for general chat
    
    Safety Protocols:
    - NEVER sends emails without explicit user approval
    - Requires confirmation for delete operations
    - Always summarizes emails before suggesting replies
    
    Args:
        request: Chat request with user message and session info
    
    Returns:
        Agent's response with message and any data/actions
    
    Examples:
        - "Show me my recent emails"
        - "Summarize the first email"
        - "What's on my calendar today?"
        - "Tell me about the history of Rome"
        - "Generate an image of a sunset"
    """
    try:
        # Initialize Executive Agent with session
        agent = ExecutiveAgent(session_id=request.session_id)
        
        # Process message
        response = await agent.process_message(
            user_message=request.message,
            user_id=request.user_id,
            provider=request.provider
        )
        
        # CRITICAL: Add state machine information to response
        active_task = agent.memory.get_active_task()
        pending_action = agent.memory.get_pending_action()
        last_action = agent.memory.get_last_action()
        
        # Determine agent state
        agent_state = "IDLE"
        if active_task and agent.memory.is_task_locked():
            task_type = active_task.get("type", "")
            task_status = active_task.get("status", "")
            
            if task_type in ["draft_email", "send_email"]:
                if task_status == "collecting":
                    agent_state = "EMAIL_COLLECTING"
                elif task_status == "awaiting_confirmation":
                    agent_state = "EMAIL_DRAFT_READY"
                else:
                    agent_state = f"EMAIL_FLOW_{task_status.upper()}"
            elif task_type == "calendar_event":
                if task_status == "collecting":
                    agent_state = "CALENDAR_COLLECTING"
                elif task_status == "awaiting_confirmation":
                    agent_state = "CALENDAR_CONFIRM"
                else:
                    agent_state = f"CALENDAR_FLOW_{task_status.upper()}"
            else:
                agent_state = f"{task_type.upper()}_{task_status.upper()}"
        
        # Add state to response
        response["agent_state"] = agent_state
        response["active_task"] = active_task
        response["pending_action"] = pending_action
        response["last_action"] = last_action
        
        return ChatResponse(**response)
        
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Executive Agent error: {str(e)}"
        )


@router.get("/session/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(session_id: str):
    """
    Get information about a conversation session.
    
    Retrieves session details including:
    - Number of messages exchanged
    - Current conversation context
    - Last activity timestamp
    
    Args:
        session_id: Session identifier
    
    Returns:
        Session information
    """
    try:
        # Get session from ExecutiveAgent
        if session_id not in ExecutiveAgent.sessions:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        session = ExecutiveAgent.sessions[session_id]
        
        return SessionInfoResponse(
            session_id=session.session_id,
            message_count=len(session.history),
            context=session.context,
            last_activity=session.last_activity.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear a conversation session.
    
    Removes all conversation history and context for the specified session.
    Use this to start a fresh conversation.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Confirmation of session deletion
    """
    try:
        if session_id in ExecutiveAgent.sessions:
            del ExecutiveAgent.sessions[session_id]
            return {
                "message": f"Session {session_id} cleared successfully",
                "success": True
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions():
    """
    List all active conversation sessions.
    
    Returns:
        List of active sessions with basic info
    """
    try:
        sessions_info = []
        for session_id, session in ExecutiveAgent.sessions.items():
            sessions_info.append({
                "session_id": session_id,
                "message_count": len(session.history),
                "last_activity": session.last_activity.isoformat(),
                "created_at": session.created_at.isoformat()
            })
        
        return {
            "sessions": sessions_info,
            "count": len(sessions_info)
        }
        
    except Exception as e:
        logger.error(f"List sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities")
async def get_capabilities():
    """
    Get information about Executive Agent capabilities.
    
    Returns:
        List of agent capabilities and features
    """
    return {
        "agent_name": "OrganAIzer Executive Agent",
        "version": "1.0.0",
        "capabilities": {
            "email_management": {
                "description": "Read, summarize, draft, and send emails",
                "providers": ["gmail", "outlook"],
                "features": [
                    "List recent emails",
                    "Summarize email content with AI",
                    "Draft replies with context awareness",
                    "Send emails (requires user approval)",
                    "Search emails"
                ]
            },
            "calendar_management": {
                "description": "View and manage calendar events",
                "providers": ["google", "outlook"],
                "features": [
                    "List upcoming events",
                    "Create new events",
                    "Update existing events",
                    "Delete events (requires confirmation)",
                    "Parse natural language into events",
                    "Suggest meeting times"
                ]
            },
            "knowledge_companion": {
                "description": "Answer questions about history, geography, and general facts",
                "features": [
                    "Historical facts and context",
                    "Geographic information",
                    "Session memory for contextual follow-ups",
                    "Concise, witty responses"
                ]
            },
            "multimodal_tools": {
                "description": "AI-powered media generation",
                "features": [
                    "Text-to-Speech (TTS)",
                    "Speech-to-Text (STT)",
                    "Image Generation"
                ]
            },
            "productivity_assistant": {
                "description": "High-value productivity features",
                "features": [
                    "Daily digest generation",
                    "Follow-up reminders",
                    "Email-to-calendar conversion"
                ]
            }
        },
        "safety_protocols": [
            "All email sends require explicit user approval",
            "Delete operations require second confirmation",
            "Emails are always summarized before reply suggestions",
            "Dry-run mode for previewing actions"
        ],
        "communication_style": {
            "email_operations": "Professional and clear",
            "general_chat": "Conversational and buddy-like",
            "knowledge_queries": "Concise but witty"
        }
    }
