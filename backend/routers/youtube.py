from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import logging
from services.youtube_service import download_youtube_video

logger = logging.getLogger(__name__)

router = APIRouter()

class DownloadRequest(BaseModel):
    url: str

@router.post("/download")
async def download_video(request: DownloadRequest):
    try:
        file_path = download_youtube_video(request.url)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=500, detail="File not found after download")
        
        logger.info(f"Serving file: {file_path}")
        return FileResponse(
            path=file_path,
            media_type='video/mp4',
            filename=os.path.basename(file_path)
        )
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
