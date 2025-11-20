"""
Centralized error handling module.
Defines standardized error response models and exception handlers for the API.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import traceback

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    """
    Standardized error response model.
    Used across all API endpoints to return consistent error information.
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


class AppError(Exception):
    """
    Custom application exception class.
    Carries structured error information that can be converted to API responses.
    Used throughout the application to raise errors with consistent formatting.
    """
    
    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initializes an application error with structured information.
        
        Args:
            code: Short error code identifier
            message: Human-readable error message
            http_status: HTTP status code to return
            details: Optional additional context information
        """
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        super().__init__(self.message)
    
    def to_response(self) -> JSONResponse:
        """
        Converts the error to a FastAPI JSONResponse.
        Used by exception handlers to return standardized error responses.
        """
        return JSONResponse(
            status_code=self.http_status,
            content={
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "details": self.details
                }
            }
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """
    FastAPI exception handler for AppError instances.
    Converts AppError exceptions to standardized JSON responses.
    Registered in main.py to handle all AppError exceptions globally.
    """
    logger.warning(
        f"Application error: {exc.code} - {exc.message}",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown"
        }
    )
    return exc.to_response()


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    FastAPI exception handler for request validation errors.
    Converts Pydantic validation errors to standardized JSON responses.
    Registered in main.py to handle validation errors globally.
    """
    logger.warning(
        f"Validation error: {exc.errors()}",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown"
        }
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": {"errors": exc.errors()}
            }
        }
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    FastAPI exception handler for unexpected exceptions.
    Logs the full stack trace and returns a generic error response to the client.
    Registered in main.py to catch all unhandled exceptions.
    """
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown"
        }
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred. Please try again later.",
                "details": {}
            }
        }
    )
