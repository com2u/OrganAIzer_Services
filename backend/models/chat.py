"""
Data models for LLM chat functionality.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""
    role: str = Field(..., description="Role of the message sender (user, assistant, system)")
    content: str = Field(..., description="Content of the message")


class ChatRequest(BaseModel):
    """Request model for chat completion."""
    prompt: str = Field(..., description="User's prompt/message")
    model: Optional[str] = Field(None, description="Model to use (defaults to .env MODEL)")
    conversation_history: Optional[List[ChatMessage]] = Field(
        default=[],
        description="Previous conversation messages for context"
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0 to 2.0)"
    )
    max_tokens: Optional[int] = Field(
        default=1000,
        gt=0,
        description="Maximum tokens to generate"
    )


class ChatResponse(BaseModel):
    """Response model for chat completion."""
    response: str = Field(..., description="AI model's response")
    model: str = Field(..., description="Model that generated the response")
    usage: Optional[dict] = Field(None, description="Token usage information")


class ModelInfo(BaseModel):
    """Information about an available model."""
    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Display name of the model")
    description: Optional[str] = Field(None, description="Model description")


class AvailableModelsResponse(BaseModel):
    """Response model for available models list."""
    current_model: str = Field(..., description="Currently configured default model")
    models: List[ModelInfo] = Field(..., description="List of available models")
