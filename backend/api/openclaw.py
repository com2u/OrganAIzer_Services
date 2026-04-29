"""
OpenClaw API endpoints for OrganAIzer Services.
This module provides API endpoints for integrating with OpenClaw.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..services.openclaw_client import OpenClawClient
import os

router = APIRouter(tags=["openclaw"])

# Initialize OpenClaw client
openclaw_client = OpenClawClient(
    base_url=os.getenv("OPENCLAW_BASE_URL", "http://openclaw:18789"),
    token=os.getenv("OPENCLAW_GATEWAY_TOKEN", "")
)

@router.post("/cleanup")
async def cleanup_request(request_data: Dict[str, Any]):
    """
    Clean up and standardize a request text using OpenClaw.
    
    Args:
        request_data: Dictionary containing the request text to clean
        
    Returns:
        Dictionary with cleaned request data
    """
    try:
        cleaned_data = await openclaw_client.cleanup_request(request_data.get("text", ""))
        return cleaned_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clean request: {str(e)}")

@router.post("/summarize")
async def summarize_text(text_data: Dict[str, Any]):
    """
    Summarize text using OpenClaw.
    
    Args:
        text_data: Dictionary containing text to summarize
        
    Returns:
        Dictionary with summary data
    """
    try:
        summary = await openclaw_client.summarize_text(text_data.get("text", ""))
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to summarize text: {str(e)}")

