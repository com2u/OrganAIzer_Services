import whisper
import requests
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

# Load Whisper model (will be loaded on first use)
model = None

def get_whisper_model():
    """Lazy load Whisper model"""
    global model
    if model is None:
        logger.info("Loading Whisper model (this may take a moment on first use)...")
        model = whisper.load_model("base")  # Use base model for speed
        logger.info("Whisper model loaded successfully")
    return model

def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribes audio file using OpenAI Whisper.
    Returns transcription with text, language, and segments.
    """
    try:
        logger.info(f"Starting Whisper transcription for: {audio_path}")

        # Get Whisper model
        whisper_model = get_whisper_model()

        # Transcribe audio
        result = whisper_model.transcribe(audio_path)

        logger.info(f"Whisper transcription completed - Language: {result['language']}, Text length: {len(result['text'])}")

        # Format segments for response
        segments = []
        for segment in result.get('segments', []):
            segments.append({
                "start": segment.get('start', 0),
                "end": segment.get('end', 0),
                "text": segment.get('text', '').strip()
            })

        return {
            "text": result['text'].strip(),
            "language": result.get('language', 'unknown'),
            "segments": segments
        }

    except Exception as e:
        logger.error(f"Whisper transcription failed: {str(e)}")
        # Fallback to basic file info if Whisper fails
        try:
            file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
            file_ext = os.path.splitext(audio_path)[1].lower()
            fallback_text = f"Whisper transcription failed: {str(e)}. Audio file info: {file_ext}, {file_size} bytes."

            return {
                "text": fallback_text,
                "language": "unknown",
                "segments": []
            }
        except:
            raise Exception(f"Failed to transcribe audio: {str(e)}")

def download_audio_from_url(url: str) -> str:
    """
    Downloads audio from URL and returns temp file path.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.write(response.content)
        temp_file.close()
        
        logger.info(f"Downloaded audio from URL: {url}")
        return temp_file.name
    except Exception as e:
        logger.error(f"Failed to download audio: {str(e)}")
        raise Exception(f"Failed to download audio: {str(e)}")
