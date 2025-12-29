import yt_dlp
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

def download_youtube_video(url: str) -> str:
    """
    Downloads a YouTube video from the given URL and returns the file path.
    """
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        # Configure yt-dlp options with anti-detection measures
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'format': 'best[height<=720]',  # Best available up to 720p
            # Anti-detection options
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            # Additional options
            'geo_bypass': True,
            'extract_flat': False,
            'sleep_interval': 1,
            'max_sleep_interval': 5,
            # Disable some features that might trigger detection
            'no_check_certificate': True,
            'ignoreerrors': False,
            'quiet': False,
            'no_warnings': False,
        }

        logger.info(f"Starting download for URL: {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        logger.info(f"Download completed: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        raise Exception(f"Failed to download video: {str(e)}")
