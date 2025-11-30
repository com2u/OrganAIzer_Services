"""
Pydantic models package.
Contains request/response schemas for all API endpoints.
"""

from .common import ErrorDetail, ErrorResponse
from .tts import TTSGenerateRequest, TTSGenerateResponse
from .stt import STTTranscribeResponse

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "TTSGenerateRequest",
    "TTSGenerateResponse",
    "STTTranscribeResponse"
]
