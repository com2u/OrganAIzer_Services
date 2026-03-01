"""
Middleware module for request/response logging.
Logs all incoming requests and outgoing responses with structured context.
"""

import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all HTTP requests and responses.
    Captures method, path, client IP, status code, and processing time.
    Registered in main.py to log all API traffic.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Processes each request, logs it, calls the endpoint, and logs the response.
        Used by FastAPI to intercept all requests before and after processing.
        """
        # Record start time
        start_time = time.time()
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Log incoming request
        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "client_ip": client_ip
            }
        )
        
        # Process the request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log outgoing response
            logger.info(
                f"Response: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "client_ip": client_ip,
                    "process_time": f"{process_time:.3f}s"
                }
            )
            
            # Add processing time to response headers
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Log exceptions that occur during request processing
            logger.error(
                f"Exception during request: {request.method} {request.url.path} - {str(e)}",
                exc_info=True,
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "client_ip": client_ip
                }
            )
            raise
