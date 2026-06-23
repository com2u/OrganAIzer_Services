# Backend image for OrganAIzer Services (FastAPI).
# Referenced by docker-compose.yml service `backend` (build: ./backend).
#
# Python is pinned to 3.11 deliberately: requirements.txt depends on
# openai-whisper/torch (no Python 3.13 support) and pyVoIP==1.6.4 (uses the
# `audioop` module, which was removed in Python 3.13). Do NOT bump to 3.13.
FROM python:3.11-slim

# System dependencies:
#   ffmpeg        — required by voice mode (webm/opus → 16 kHz WAV for Whisper)
#   curl          — used by the docker-compose healthcheck (GET /health)
#   build-essential — lets pip build any source-only wheels on first build
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python deps first so the dependency layer is cached independently of
# application code changes.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy the application source. Secrets, virtualenvs, caches and runtime data are
# excluded via backend/.dockerignore so they never enter the image layers.
# NOTE: docker-compose also bind-mounts ./backend over /app at runtime; this COPY
# keeps the image self-contained for standalone runs (e.g. CI).
COPY . .

EXPOSE 8000

# Mirror backend/start.sh's run step (no reload — reload wipes in-memory session
# state and forces a slow Whisper reload; see backend/main.py).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
