"""
Main application entry point for the OrganAIzer Services backend.
Sets up FastAPI app, registers middleware, exception handlers, and API routes.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from core.config import config
from core.logging_config import setup_logging
from core.middleware import LoggingMiddleware
from core.error_handling import (
    AppError,
    app_error_handler,
    validation_error_handler,
    generic_error_handler
)
from api import tts, stt, image_gen

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="OrganAIzer Services API",
    description="Backend API for AI-powered utilities including Text-to-Speech",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Register exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Include API routers
app.include_router(tts.router, prefix="/api/tts")
app.include_router(stt.router, prefix="/api/stt")
app.include_router(image_gen.router, prefix="/api")  # Includes both /image-gen and /nano-banana endpoints



@app.on_event("startup")
async def startup_event():
    """
    Runs on application startup.
    Ensures required directories exist and logs startup information.
    """
    logger.info("Starting OrganAIzer Services API")
    
    # Ensure required directories exist
    config.ensure_directories()
    logger.info(f"TTS temporary directory: {config.TTS_TEMP_DIR}")
    logger.info(f"Image generation temporary directory: {config.IMAGE_GEN_TEMP_DIR}")
    
    # Note: Image generation now uses Google AI Studio (Gemini) via Node.js scripts
    # Vertex AI initialization removed
    
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Runs on application shutdown.
    Performs cleanup tasks if needed.
    """
    logger.info("Shutting down OrganAIzer Services API")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns a simple status indicating the API is running.
    Used for monitoring and load balancer health checks.
    """
    return {"status": "ok"}


@app.get("/")
async def root():
    """
    Root endpoint.
    Provides basic API information and links to documentation.
    """
    return {
        "message": "OrganAIzer Services API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    # Run the application with uvicorn
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True,
        log_level=config.LOG_LEVEL.lower()
    )
