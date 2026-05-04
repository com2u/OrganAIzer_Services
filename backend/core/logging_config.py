"""
Centralized logging configuration module.
Sets up structured JSON logging for the entire application with console and optional file output.
"""

import logging
import json
import re
import sys
from datetime import datetime
from typing import Any, Optional
from pathlib import Path
from .config import config


_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:api[_-]?key|x-api-key|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|client[_-]?secret|token_encryption_key)\b[\"']?\s*[:=]\s*[\"']?)"
    r"([^\"'\s,}]+)"
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)
_API_KEY_VALUE_RE = re.compile(
    r"\b(?:sk-or-v1-[A-Za-z0-9_-]+|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{20,})\b"
)
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?<![\w])(?:\+\d{1,3}|00\d{1,3}|0\d)(?:[\s()./-]*\d){5,}(?![\w])"
)


def _mask_phone_number(match: re.Match[str]) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7:
        return raw

    stripped = raw.strip()
    if stripped.startswith("+"):
        prefix = f"+{digits[:2]}"
    elif digits.startswith("00"):
        prefix = digits[:4]
    elif digits.startswith("0"):
        prefix = digits[:3]
    else:
        prefix = digits[:2]

    return f"{prefix}******{digits[-4:]}"


def redact_text(value: str) -> str:
    """Redact sensitive values before they are written to logs."""
    value = _BEARER_TOKEN_RE.sub("Bearer [REDACTED]", value)
    value = _SENSITIVE_ASSIGNMENT_RE.sub(r"\1[REDACTED]", value)
    value = _JWT_RE.sub("[REDACTED_TOKEN]", value)
    value = _API_KEY_VALUE_RE.sub("[REDACTED_API_KEY]", value)
    value = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    value = _PHONE_RE.sub(_mask_phone_number, value)
    return value


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


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
            "message": redact_text(record.getMessage()),
            "logger": record.name,
        }
        
        # Add optional fields if they exist
        if hasattr(record, 'path'):
            log_data['path'] = _redact_value(record.path)
        if hasattr(record, 'method'):
            log_data['method'] = _redact_value(record.method)
        if hasattr(record, 'client_ip'):
            log_data['client_ip'] = _redact_value(record.client_ip)
        if hasattr(record, 'status_code'):
            log_data['status_code'] = _redact_value(record.status_code)
        
        # Include exception info if present
        if record.exc_info:
            log_data['exception'] = redact_text(self.formatException(record.exc_info))
        
        return json.dumps(_redact_value(log_data))


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
