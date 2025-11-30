"""
Configuration module for the backend application.
Reads environment variables and provides configuration settings to other modules.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()


class Config:
    """
    Application configuration class.
    Centralizes all configuration settings read from environment variables.
    """
    
    # TTS Configuration - directory for storing temporary audio files
    TTS_TEMP_DIR: str = os.getenv("TTS_TEMP_DIR", "./data/tts")
    
    # Image Generation Configuration
    IMAGE_GEN_TEMP_DIR: str = os.getenv("IMAGE_GEN_TEMP_DIR", "./data/images")
    
    # Google Cloud Vertex AI Configuration
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "projects/1053209052640")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "")  # Empty string means no file logging
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    @classmethod
    def ensure_directories(cls):
        """
        Ensures that all required directories exist.
        Creates them if they don't exist.
        Used during application startup to prepare the environment.
        """
        Path(cls.TTS_TEMP_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.IMAGE_GEN_TEMP_DIR).mkdir(parents=True, exist_ok=True)


# Create a singleton instance for easy import
config = Config()
