from fastapi import APIRouter, Depends
from auth import get_api_key
from routers import youtube, tts, stt, video_text, text_image, llm, google, outlook

router = APIRouter()

router.include_router(youtube.router, prefix="/youtube", tags=["youtube"])
router.include_router(tts.router, prefix="/tts", tags=["tts"])
router.include_router(stt.router, prefix="/stt", tags=["stt"])
router.include_router(video_text.router, prefix="/video-text", tags=["video-text"])
router.include_router(text_image.router, prefix="/text-image", tags=["text-image"])
router.include_router(llm.router, tags=["llm"])
router.include_router(google.router, prefix="/google", tags=["google"])
router.include_router(outlook.router, prefix="/outlook", tags=["outlook"])
