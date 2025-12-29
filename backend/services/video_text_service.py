from moviepy.editor import VideoFileClip
import tempfile
import os
import logging
from services.stt_service import transcribe_audio
from services.youtube_service import download_youtube_video

logger = logging.getLogger(__name__)

def extract_audio_from_video(video_path: str) -> str:
    """
    Extracts audio from video file and returns audio file path.
    """
    try:
        video = VideoFileClip(video_path)
        audio = video.audio
        
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        audio.write_audiofile(temp_audio.name, verbose=False, logger=None)
        temp_audio.close()
        
        video.close()
        
        logger.info(f"Audio extracted: {temp_audio.name}")
        return temp_audio.name
    except Exception as e:
        logger.error(f"Audio extraction failed: {str(e)}")
        raise Exception(f"Failed to extract audio: {str(e)}")

def transcribe_video(video_path: str = None, video_url: str = None) -> dict:
    """
    Transcribes video from file or YouTube URL.
    """
    temp_video_path = None
    temp_audio_path = None
    try:
        if video_path:
            temp_audio_path = extract_audio_from_video(video_path)
        elif video_url:
            temp_video_path = download_youtube_video(video_url)
            temp_audio_path = extract_audio_from_video(temp_video_path)
        else:
            raise ValueError("Either video_path or video_url must be provided")
        
        result = transcribe_audio(temp_audio_path)
        
        return result
    except Exception as e:
        logger.error(f"Video transcription failed: {str(e)}")
        raise Exception(f"Failed to transcribe video: {str(e)}")
    finally:
        # Clean up temp files
        for path in [temp_video_path, temp_audio_path]:
            if path and os.path.exists(path):
                os.unlink(path)
