from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uuid
import logging
from services.tts_service import generate_tts

logger = logging.getLogger(__name__)

router = APIRouter()
audio_router = APIRouter()

# Simple in-memory storage for demo
audio_files = {}

class GenerateRequest(BaseModel):
    text_md: str

class GenerateResponse(BaseModel):
    text_normalized: str
    language: str
    audio_url: str

@router.post("/generate", response_model=GenerateResponse)
async def generate_speech(request: GenerateRequest):
    try:
        result = generate_tts(request.text_md)
        
        audio_id = str(uuid.uuid4())
        audio_files[audio_id] = result["audio_path"]
        
        # Assuming the API base is known, but for demo, use relative
        audio_url = f"/api/tts/audio/{audio_id}"
        
        logger.info(f"TTS generated with ID: {audio_id}")
        
        return GenerateResponse(
            text_normalized=result["text_normalized"],
            language=result["language"],
            audio_url=audio_url
        )
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@audio_router.get("/audio/{audio_id}")
async def get_audio(audio_id: str):
    if audio_id not in audio_files:
        raise HTTPException(status_code=404, detail="Audio not found")
    
    file_path = audio_files[audio_id]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        path=file_path,
        media_type='audio/mpeg',
        filename=f"tts_{audio_id}.mp3"
    )
