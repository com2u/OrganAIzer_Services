from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import os
import tempfile
import logging
from services.video_text_service import transcribe_video

logger = logging.getLogger(__name__)

router = APIRouter()

class TranscribeResponse(BaseModel):
    text: str
    language: str
    segments: list = []

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(None),
    video_url: str = Form(None)
):
    temp_path = None
    try:
        if file:
            # Save uploaded file to temp
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
            temp_file.write(await file.read())
            temp_file.close()
            temp_path = temp_file.name
        elif video_url:
            # Use video_url directly
            pass
        else:
            raise HTTPException(status_code=400, detail="Either file or video_url must be provided")
        
        result = transcribe_video(video_path=temp_path, video_url=video_url)
        
        logger.info("Video transcription successful")
        
        return TranscribeResponse(
            text=result["text"],
            language=result["language"],
            segments=result["segments"]
        )
    except Exception as e:
        logger.error(f"Video transcription failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
