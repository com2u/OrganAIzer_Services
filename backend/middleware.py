from fastapi import Request
import time
import logging
import json
from fastapi import Request
import time

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage()
        }
        return json.dumps(log_record)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler("backend.log")
file_handler.setFormatter(JsonFormatter())
logger.addHandler(file_handler)

# Stream handler
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(JsonFormatter())
logger.addHandler(stream_handler)

async def log_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    log_message = {
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_s": f"{process_time:.4f}"
    }
    logger.info(json.dumps(log_message))
    
    return response
