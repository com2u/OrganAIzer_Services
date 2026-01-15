"""
LLM Chat Service using OpenRouter API.
Handles chat completions with various AI models.
"""

import logging
import os
import requests
from typing import List, Optional
from core.config import config
from core.error_handling import AppError
from models.chat import ChatMessage, ChatRequest, ChatResponse, ModelInfo, AvailableModelsResponse

logger = logging.getLogger(__name__)


class ChatService:
    """Service for LLM chat completions using OpenRouter."""
    
    def __init__(self):
        """Initialize the chat service."""
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.models_url = "https://openrouter.ai/api/v1/models"
        self.default_model = os.getenv("MODEL", "google/gemini-2.5-flash")
        logger.info(f"ChatService initialized with default model: {self.default_model}")
    
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """
        Generate a chat completion using the specified or default model.
        
        Args:
            request: ChatRequest containing prompt and optional parameters
        
        Returns:
            ChatResponse with the AI's response
        
        Raises:
            AppError: If chat completion fails
        """
        try:
            # Check if API key is configured
            if not config.OPENROUTER_API_KEY:
                raise AppError(
                    code="API_KEY_MISSING",
                    message="OpenRouter API key not configured",
                    details={"hint": "Set OPENROUTER_API_KEY in .env file"}
                )
            
            # Use specified model or default
            model = request.model or self.default_model
            logger.info(f"Processing chat request with model: {model}")
            
            # Build messages array
            messages = []
            
            # Add conversation history if provided
            if request.conversation_history:
                messages.extend([
                    {"role": msg.role, "content": msg.content}
                    for msg in request.conversation_history
                ])
            
            # Add current user prompt
            messages.append({
                "role": "user",
                "content": request.prompt
            })
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",  # Optional
                "X-Title": "OrganAIzer Services"  # Optional
            }
            
            # Prepare payload
            payload = {
                "model": model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            }
            
            logger.info(f"Sending request to OpenRouter with {len(messages)} messages")
            
            # Make API request
            response = requests.post(self.api_url, headers=headers, json=payload)
            
            # Handle error responses
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"OpenRouter API error ({response.status_code}): {error_detail}")
                raise AppError(
                    code="API_REQUEST_FAILED",
                    message=f"OpenRouter API returned status {response.status_code}",
                    details={"error": error_detail}
                )
            
            result = response.json()
            
            # Extract response
            if not result.get("choices"):
                raise AppError(
                    code="NO_RESPONSE",
                    message="No response from AI model",
                    details={"result": result}
                )
            
            ai_response = result["choices"][0]["message"]["content"]
            usage = result.get("usage")
            
            logger.info(f"Successfully generated response ({len(ai_response)} chars)")
            
            return ChatResponse(
                response=ai_response,
                model=model,
                usage=usage
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}", exc_info=True)
            raise AppError(
                code="API_REQUEST_FAILED",
                message="Failed to communicate with OpenRouter API",
                details={"error": str(e)}
            )
        except AppError:
            # Re-raise AppErrors as-is
            raise
        except Exception as e:
            logger.error(f"Chat completion failed: {str(e)}", exc_info=True)
            raise AppError(
                code="CHAT_COMPLETION_FAILED",
                message="Failed to generate chat completion",
                details={"error": str(e)}
            )
    
    async def get_available_models(self) -> AvailableModelsResponse:
        """
        Get list of available models from OpenRouter.
        
        Returns:
            AvailableModelsResponse with current model and available models
        
        Raises:
            AppError: If fetching models fails
        """
        try:
            # Check if API key is configured
            if not config.OPENROUTER_API_KEY:
                raise AppError(
                    code="API_KEY_MISSING",
                    message="OpenRouter API key not configured",
                    details={"hint": "Set OPENROUTER_API_KEY in .env file"}
                )
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            
            logger.info("Fetching available models from OpenRouter")
            
            # Make API request
            response = requests.get(self.models_url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # Parse models
            models = []
            if result.get("data"):
                for model_data in result["data"]:
                    models.append(ModelInfo(
                        id=model_data["id"],
                        name=model_data.get("name", model_data["id"]),
                        description=model_data.get("description")
                    ))
            
            logger.info(f"Successfully fetched {len(models)} models")
            
            return AvailableModelsResponse(
                current_model=self.default_model,
                models=models
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch models: {str(e)}", exc_info=True)
            raise AppError(
                code="API_REQUEST_FAILED",
                message="Failed to fetch available models",
                details={"error": str(e)}
            )
        except Exception as e:
            logger.error(f"Error fetching models: {str(e)}", exc_info=True)
            raise AppError(
                code="FETCH_MODELS_FAILED",
                message="Failed to get available models",
                details={"error": str(e)}
            )


# Global service instance
_chat_service = None


def get_chat_service() -> ChatService:
    """Get or create the global ChatService instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
