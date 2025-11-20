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


# Create a singleton instance for easy import
config = Config()
