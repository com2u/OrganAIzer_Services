from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from dotenv import load_dotenv
from auth import get_api_key

# Load environment variables
load_dotenv()

from middleware import log_middleware

app = FastAPI(title="OrganAIzer Service", version="1.0.0")

# Logging middleware
app.middleware("http")(log_middleware)

# CORS middleware
# Allowed origins for production and testing
ALLOWED_ORIGINS = [
    "https://organaizer.com2u.selfhost.eu",
    "https://organaizer_backend.com2u.selfhost.eu",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://192.168.0.95:5173",
    "http://192.168.0.95:3000",
    "http://100.107.41.75:5173",
    "http://100.107.41.75:3000",
    "http://192.168.0.95",
    "http://100.107.41.75",
    "http://localhost"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin", "X-Custom-Header"],
    expose_headers=["Content-Length", "Content-Range", "X-Error-Message"],
)

from api import router as api_router
from routers import root, tts
from fastapi.responses import JSONResponse

app.include_router(root.router, tags=["root"])
app.include_router(api_router, prefix="/api", dependencies=[Depends(get_api_key)])
app.include_router(tts.audio_router, prefix="/api/tts", tags=["tts"])

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "OrganAIzer Backend",
            "version": "1.0.0",
            "timestamp": "2025-12-29T14:42:51.147Z"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
