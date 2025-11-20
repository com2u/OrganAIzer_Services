"""
Centralized logging configuration module.
Sets up structured JSON logging for the entire application with console and optional file output.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path
from .config import config


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs log records as JSON.
    Includes timestamp, level, message, and additional context fields.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Formats a log record as a JSON string.
        Used by logging handlers to structure log output.
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        
        # Add optional fields if they exist
        if hasattr(record, 'path'):
            log_data['path'] = record.path
        if hasattr(record, 'method'):
            log_data['method'] = record.method
        if hasattr(record, 'client_ip'):
            log_data['client_ip'] = record.client_ip
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code
        
        # Include exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging() -> logging.Logger:
    """
    Configures and returns the root logger with JSON formatting.
    Sets up console and optional file handlers based on configuration.
    Called once during application startup to initialize logging.
    """
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # Optional file handler
    if config.LOG_FILE_PATH:
        try:
            # Ensure log directory exists
            log_path = Path(config.LOG_FILE_PATH)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(config.LOG_FILE_PATH)
            file_handler.setFormatter(JSONFormatter())
            logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Failed to set up file logging: {e}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance for the specified module name.
    Used throughout the application to get module-specific loggers.
    """
    return logging.getLogger(name)
