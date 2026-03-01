"""
Common pydantic models shared across the application.
Contains error response models used by all API endpoints.
"""

from typing import Dict, Any
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """
    Standardized error detail model.
    Used in all error responses to provide consistent error information.
    """
    code: str  # Short error code like "INVALID_INPUT", "INTERNAL_ERROR"
    message: str  # Human-readable error message
    details: Dict[str, Any] = {}  # Optional additional context


class ErrorResponse(BaseModel):
    """
    Wrapper for error responses.
    Ensures all errors follow the { "error": { ... } } format.
    """
    error: ErrorDetail
