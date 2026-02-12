"""
Correlation ID Middleware

Adds a unique correlation ID to each request for distributed tracing.
The correlation ID is:
- Generated as UUID4 for each request
- Added to request state for access in handlers
- Included in response headers
- Automatically logged with all log messages
"""

import uuid
import logging
from contextvars import ContextVar
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Context variable to store correlation ID for the current request
correlation_id_ctx: ContextVar[str] = ContextVar('correlation_id', default='')


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records."""
    
    def filter(self, record):
        correlation_id = correlation_id_ctx.get('')
        record.correlation_id = correlation_id if correlation_id else 'no-correlation-id'
        return True


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates and propagates correlation IDs.
    
    For each incoming request:
    1. Check if X-Correlation-ID header is present
    2. If not, generate a new UUID4
    3. Store in context variable for logging
    4. Add to request state for handler access
    5. Include in response headers
    """
    
    async def dispatch(self, request: Request, call_next):
        # Get or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Store in context for logging filter
        correlation_id_ctx.set(correlation_id)
        
        # Store in request state for handler access
        request.state.correlation_id = correlation_id
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers['X-Correlation-ID'] = correlation_id
        
        return response


def get_correlation_id() -> str:
    """Get the current request's correlation ID."""
    return correlation_id_ctx.get('')


def setup_correlation_logging():
    """
    Setup correlation ID logging for all loggers.
    
    Call this during application startup to add correlation IDs
    to all log messages.
    """
    # Create and add the filter to root logger
    correlation_filter = CorrelationIdFilter()
    root_logger = logging.getLogger()
    root_logger.addFilter(correlation_filter)
    
    #Update logging format to include correlation ID
    for handler in root_logger.handlers:
        if isinstance(handler.formatter, logging.Formatter):
            # Update format to include correlation_id
            current_format = handler.formatter._fmt
            if current_format and '[%(correlation_id)s]' not in current_format:
                new_format = current_format.replace(
                    '%(message)s',
                    '[%(correlation_id)s] %(message)s'
                )
                handler.setFormatter(logging.Formatter(new_format))
