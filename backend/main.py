"""
Main application entry point for the OrganAIzer Services backend.
Sets up FastAPI app, registers middleware, exception handlers, and API routes.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
from api import tts, stt, image_gen, youtube, video, chat, document, translation, knowledge_base, integrations, executive_agent

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for application startup and shutdown.
    Replaces deprecated @app.on_event decorators.
    """
    # Startup
    logger.info("Starting OrganAIzer Services API")
    
    # Ensure required directories exist
    config.ensure_directories()
    logger.info(f"TTS temporary directory: {config.TTS_TEMP_DIR}")
    logger.info(f"Image generation temporary directory: {config.IMAGE_GEN_TEMP_DIR}")
    
    # Note: Image generation now uses Google AI Studio (Gemini) via Node.js scripts
    # Vertex AI initialization removed
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down OrganAIzer Services API")


# Create FastAPI application with lifespan handler
app = FastAPI(
    title="OrganAIzer Services API",
    description="""
    **OrganAIzer Services** - Comprehensive AI-powered backend API
    
    ## Features
    
    * **Text-to-Speech (TTS)** - Convert text to natural speech using Google TTS
    * **Speech-to-Text (STT)** - Transcribe audio files to text
    * **Image Generation** - Create images from text prompts (Vertex AI Imagen & Gemini)
    * **Video Transcription** - Transcribe videos from YouTube, URLs, or uploads
    * **AI Chat** - LLM chat completions via OpenRouter (Gemini, Claude, GPT, etc.)
    * **Document Analysis** - Upload, summarize, and chat with documents (PDF, DOCX, TXT, MD)
    * **Translation** - Translate text, audio, and files between 30+ languages
    * **Knowledge Base (RAG)** - Semantic search and Q&A over your content
    * **Integrations** - Google and Outlook integration (Calendar, Mail) - BETA
    
    ## Technology Stack
    
    * FastAPI for high-performance API
    * Google AI (Gemini, Vertex AI) for advanced AI capabilities
    * OpenRouter for multi-model LLM access
    * TF-IDF vectorization for semantic search
    * FFmpeg for audio/video processing
    
    All services are designed for production use with comprehensive error handling,
    logging, and monitoring capabilities.
    """,
    version="1.0.0",
    contact={
        "name": "OrganAIzer Services",
        "url": "https://github.com/com2u/OrganAIzer_Services",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Health", "description": "API health and status endpoints"},
        {"name": "TTS", "description": "Text-to-Speech generation using Google TTS"},
        {"name": "STT", "description": "Speech-to-Text transcription using Google STT"},
        {"name": "Image Generation", "description": "Text-to-Image generation (Vertex AI Imagen & Gemini 2.5 Flash Image)"},
        {"name": "Video Transcription", "description": "Video transcription from YouTube, URLs, or file uploads"},
        {"name": "chat", "description": "LLM chat completions via OpenRouter"},
        {"name": "documents", "description": "Document upload, summarization, and Q&A"},
        {"name": "translation", "description": "Multi-language translation for text, audio, and files"},
        {"name": "knowledge-base", "description": "Knowledge base (RAG) for semantic search and Q&A"},
        {"name": "Integrations", "description": "External service integrations (Google, Outlook) - BETA/PLANNED"},
    ],
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=False,  # Must be False when using wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Mount static files directory for images
# This allows images to be accessed directly via /static/images/{filename}
app.mount("/static/images", StaticFiles(directory=config.IMAGE_GEN_TEMP_DIR), name="images")

# Register exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Include API routers
app.include_router(tts.router, prefix="/api/tts")
app.include_router(stt.router, prefix="/api/stt")
app.include_router(image_gen.router, prefix="/api")  # Includes both /image-gen and /nano-banana endpoints
app.include_router(youtube.router, prefix="/api")  # YouTube transcription endpoints (backwards compatible)
app.include_router(video.router, prefix="/api")  # Unified video transcription endpoints
app.include_router(chat.router, prefix="/api")  # LLM chat endpoints
app.include_router(document.router, prefix="/api")  # Document analysis endpoints
app.include_router(translation.router, prefix="/api")  # Translation endpoints
app.include_router(knowledge_base.router, prefix="/api")  # Knowledge base (RAG) endpoints
app.include_router(integrations.router, prefix="/api")  # External integrations (Google, Outlook) - BETA
app.include_router(executive_agent.router, prefix="/api/agent", tags=["executive-agent"])  # Executive Agent endpoints


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
