#!/bin/bash

# =============================================================================
# OrganAIzer Services - Backend Startup Script
# =============================================================================
# This script installs all Python dependencies and starts the backend service.
# =============================================================================

set -e  # Exit on any error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "OrganAIzer Services - Backend Startup"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# Step 1: Check Python availability
# -----------------------------------------------------------------------------
echo "[1/4] Checking Python installation..."

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Found Python: $PYTHON_VERSION"

# -----------------------------------------------------------------------------
# Step 2: Create virtual environment if it doesn't exist
# -----------------------------------------------------------------------------
echo "[2/4] Setting up virtual environment..."

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
    echo "  Virtual environment created at: $SCRIPT_DIR/venv"
else
    echo "  Virtual environment already exists"
fi

# -----------------------------------------------------------------------------
# Step 3: Install dependencies
# -----------------------------------------------------------------------------
echo "[3/4] Installing dependencies..."

# Activate virtual environment
source venv/bin/activate

# Upgrade pip to latest version
echo "  Upgrading pip..."
pip install --upgrade pip --quiet

# Install requirements
echo "  Installing packages from requirements.txt..."
pip install -r requirements.txt

echo "  Dependencies installed successfully"

# -----------------------------------------------------------------------------
# Step 4: Start the backend service
# -----------------------------------------------------------------------------
echo "[4/4] Starting backend service..."
echo ""
echo "=============================================="
echo "Backend is starting..."
echo "=============================================="
echo ""
echo "  API Documentation: http://localhost:8000/docs"
echo "  ReDoc:             http://localhost:8000/redoc"
echo "  Health Check:      http://localhost:8000/health"
echo ""
echo "  Press Ctrl+C to stop the server"
echo ""

# Start uvicorn with the main app
# Using exec to replace the shell process (proper signal handling)
exec uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
