"""
Audio utility functions for chunking, processing, and manipulation.
"""

import logging
import subprocess
import tempfile
import os
from pathlib import Path
from typing import List, Tuple
import json

logger = logging.getLogger(__name__)


def get_audio_duration(filepath: str) -> float:
    """
    Get the duration of an audio file in seconds using ffprobe.
    
    Args:
        filepath: Path to the audio file
        
    Returns:
        Duration in seconds
        
    Raises:
        Exception: If ffprobe fails to get duration
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            filepath
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        
        logger.info(f"Audio duration: {duration:.2f}s for {filepath}")
        return duration
        
    except Exception as e:
        logger.error(f"Failed to get audio duration: {e}")
        raise


def split_audio(
    filepath: str,
    chunk_duration_minutes: int = 5,
    output_dir: str = None
) -> List[str]:
    """
    Split an audio file into chunks of specified duration using ffmpeg.
    
    Args:
        filepath: Path to the input audio file
        chunk_duration_minutes: Duration of each chunk in minutes (default: 5min)
        output_dir: Directory to save chunks (default: temp directory)
        
    Returns:
        List of paths to the generated audio chunks
        
    Raises:
        Exception: If ffmpeg fails to split the audio
    """
    try:
        # Get total duration
        total_duration = get_audio_duration(filepath)
        chunk_duration_seconds = chunk_duration_minutes * 60
        
        # Calculate number of chunks
        num_chunks = int(total_duration / chunk_duration_seconds) + 1
        logger.info(f"Splitting audio into {num_chunks} chunks of {chunk_duration_minutes}min each")
        
        # Create output directory if not provided
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="audio_chunks_")
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        chunk_paths = []
        
        # Split audio into chunks
        for i in range(num_chunks):
            start_time = i * chunk_duration_seconds
            chunk_path = os.path.join(output_dir, f"chunk_{i:03d}.mp3")
            
            cmd = [
                'ffmpeg',
                '-i', filepath,
                '-ss', str(start_time),
                '-t', str(chunk_duration_seconds),
                '-acodec', 'libmp3lame',
                '-ar', '16000',  # 16kHz sample rate (optimal for Whisper)
                '-ac', '1',      # Mono audio
                '-b:a', '64k',   # 64kbps bitrate
                '-y',            # Overwrite output file
                chunk_path
            ]
            
            logger.info(f"Creating chunk {i+1}/{num_chunks}: {chunk_path}")
            subprocess.run(cmd, capture_output=True, check=True)
            
            # Verify chunk was created and has content
            if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
                chunk_paths.append(chunk_path)
                logger.info(f"Chunk {i+1} created successfully: {os.path.getsize(chunk_path)} bytes")
            else:
                logger.warning(f"Chunk {i+1} was not created or is empty")
        
        logger.info(f"Successfully split audio into {len(chunk_paths)} chunks")
        return chunk_paths
        
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg failed to split audio: {e.stderr}")
        raise Exception(f"Failed to split audio: {e.stderr}")
    except Exception as e:
        logger.error(f"Error splitting audio: {e}", exc_info=True)
        raise


def merge_transcripts(transcripts: List[Tuple[int, str]]) -> str:
    """
    Merge multiple transcript chunks into a single transcript.
    Ensures proper ordering and spacing.
    
    Args:
        transcripts: List of tuples (chunk_index, transcript_text)
        
    Returns:
        Merged transcript text
    """
    # Sort by chunk index to ensure correct order
    sorted_transcripts = sorted(transcripts, key=lambda x: x[0])
    
    # Join transcripts with space
    merged = ' '.join(text.strip() for _, text in sorted_transcripts if text.strip())
    
    logger.info(f"Merged {len(sorted_transcripts)} transcript chunks into {len(merged)} characters")
    return merged


def cleanup_chunks(chunk_paths: List[str]) -> None:
    """
    Clean up temporary audio chunk files.
    
    Args:
        chunk_paths: List of paths to chunk files to delete
    """
    for chunk_path in chunk_paths:
        try:
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
                logger.debug(f"Deleted chunk: {chunk_path}")
        except Exception as e:
            logger.warning(f"Failed to delete chunk {chunk_path}: {e}")
    
    # Try to remove the directory if empty
    if chunk_paths:
        try:
            chunk_dir = os.path.dirname(chunk_paths[0])
            if os.path.exists(chunk_dir) and not os.listdir(chunk_dir):
                os.rmdir(chunk_dir)
                logger.debug(f"Deleted empty chunk directory: {chunk_dir}")
        except Exception as e:
            logger.warning(f"Failed to delete chunk directory: {e}")


def convert_to_whisper_format(input_path: str, output_path: str = None) -> str:
    """
    Convert audio to Whisper-optimized format (16kHz, mono, MP3).
    
    Args:
        input_path: Path to the input audio file
        output_path: Path for the output file (optional)
        
    Returns:
        Path to the converted audio file
    """
    try:
        if output_path is None:
            # Create temp file with same extension
            suffix = Path(input_path).suffix
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            output_path = temp_file.name
            temp_file.close()
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',      # Mono
            '-acodec', 'libmp3lame',
            '-b:a', '64k',   # 64kbps bitrate
            '-y',
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        logger.info(f"Converted audio to Whisper format: {output_path}")
        
        return output_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg conversion failed: {e.stderr}")
        raise Exception(f"Failed to convert audio: {e.stderr}")
