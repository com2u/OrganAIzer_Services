"""
API endpoints for LLM chat functionality.
"""

import logging
from fastapi import APIRouter, HTTPException
from models.chat import ChatRequest, ChatResponse, AvailableModelsResponse
from services.chat_service import get_chat_service
from core.error_handling import AppError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Separate router for legacy /llm endpoint (Chrome Extension compatibility)
llm_router = APIRouter(tags=["chat"])


@router.post("/completion", response_model=ChatResponse)
async def chat_completion(request: ChatRequest):
    """
    Generate a chat completion using an LLM via OpenRouter.
    
    Args:
        request: ChatRequest with prompt and optional parameters
    
    Returns:
        ChatResponse with AI's response
    """
    try:
        logger.info(f"Chat completion request: prompt length={len(request.prompt)}, model={request.model}")
        
        service = get_chat_service()
        response = await service.chat_completion(request)
        
        logger.info(f"Chat completion successful: response length={len(response.response)}")
        return response
        
    except AppError as e:
        logger.error(f"Chat completion failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error in chat completion: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


@router.get("/models", response_model=AvailableModelsResponse)
async def get_available_models():
    """
    Get list of available LLM models from OpenRouter.
    
    Returns:
        AvailableModelsResponse with current model and available models
    """
    try:
        logger.info("Fetching available models")
        
        service = get_chat_service()
        response = await service.get_available_models()
        
        logger.info(f"Successfully fetched {len(response.models)} models")
        return response
        
    except AppError as e:
        logger.error(f"Failed to fetch models: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching models: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )


# Compatibility endpoint for Chrome Extension (on llm_router to avoid /chat prefix)
@llm_router.post("/llm", response_model=ChatResponse)
async def llm_compatibility_endpoint(request: ChatRequest):
    """
    Legacy LLM endpoint for backward compatibility with Chrome Extension.
    This endpoint is accessible at /api/llm (without /chat prefix).
    
    Args:
        request: ChatRequest with prompt and optional parameters
    
    Returns:
        ChatResponse with AI's response
    """
    try:
        logger.info(f"LLM compatibility endpoint called: prompt length={len(request.prompt)}, model={request.model}")
        
        service = get_chat_service()
        response = await service.chat_completion(request)
        
        logger.info(f"LLM compatibility - chat completion successful: response length={len(response.response)}")
        return response
        
    except AppError as e:
        logger.error(f"LLM compatibility - chat completion failed: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=e.http_status,
            detail={
                "code": e.code,
                "message": e.message,
                "details": e.details
            }
        )
    except Exception as e:
        logger.error(f"LLM compatibility - unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        )
