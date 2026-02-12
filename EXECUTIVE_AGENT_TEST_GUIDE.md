# Executive Agent Test Guide

## Overview
This guide explains how to run the Executive Agent tests locally on Windows.

## Prerequisites
1. Python 3.8+ installed
2. All dependencies installed: `pip install -r backend/requirements.txt`
3. API key configured in `backend/.env` (default: `test-key-123`)

## Quick Start

### Terminal A: Start the Backend
```bash
# From the project root directory
python backend/main.py
```

You should see:
```
======================================================================
🚀 OrganAIzer Backend Server Starting
======================================================================
✅ Server URL: http://localhost:8000
✅ API Docs: http://localhost:8000/docs
✅ Health Check: http://localhost:8000/health
✅ Executive Agent: http://localhost:8000/api/agent/capabilities
======================================================================
```

### Terminal B: Run the Tests
```bash
# Quick verification test
python test_quick.py

# Full interactive test suite
python test_executive_agent.py
```

## What Was Fixed

### 1. **.env File Syntax Errors** (Lines 38-39)
**Problem:** Invalid syntax causing dotenv parsing errors
```bash
# BEFORE (BROKEN):
api_key test-key-123
l5hhroDITUp5zCFEGSaMk43HdVDFlK85
```

✅ **Fixed:**
```bash
# API Key for development/testing
API_KEY=test-key-123
```

### 2. **Executive Agent Router Not Registered**
**Problem:** The executive agent endpoints were defined but never registered in `api_router.py`

✅ **Fixed:** Added to `backend/api_router.py`:
```python
import api.executive_agent as executive_agent_api

# Executive Agent - The Core Intelligence
router.include_router(executive_agent_api.router, prefix="/agent", tags=["executive-agent"])
```

### 3. **Missing API Key Authentication**
**Problem:** Test script didn't send the required API key header

✅ **Fixed:** Updated `test_executive_agent.py` to:
- Load API key from `.env` file or use default
- Send `X-API-Key` header with all requests
- Support `BACKEND_URL` and `API_KEY` environment variables

### 4. **Backend Startup Logging**
**Problem:** No clear indication of which URL the server is running on

✅ **Fixed:** Added informative startup banner showing:
- Server URL
- API documentation URL
- Health check endpoint
- Executive agent capabilities endpoint

## Configuration

### Environment Variables
The test script supports these optional environment variables:

```bash
# Backend URL (default: http://localhost:8000)
BACKEND_URL=http://localhost:8000

# API Key for authentication (default: test-key-123)
API_KEY=test-key-123
```

### Using Custom Configuration
```bash
# Set environment variables before running tests
set BACKEND_URL=http://localhost:9000
set API_KEY=my-custom-key
python test_executive_agent.py
```

## Test Script Features

### test_quick.py
Quick verification that all endpoints are working:
- ✅ Health check
- ✅ Agent capabilities
- ✅ Chat endpoint

### test_executive_agent.py
Full interactive test suite with menu:
1. **Conversation Test** - Automated test with sample messages
2. **Email Workflow Test** - Test email-related features
3. **Calendar Workflow Test** - Test calendar operations
4. **Interactive Chat Mode** - Chat directly with the agent
5. **Get Agent Capabilities** - View what the agent can do
6. **Get Session Info** - View current session details
7. **Clear Session** - Start fresh conversation

## Available Endpoints

### GET /api/agent/capabilities
Get information about what the agent can do.
- **Auth:** Requires `X-API-Key` header
- **Returns:** Agent capabilities and features

### POST /api/agent/chat
Send a message to the executive agent.
- **Auth:** Requires `X-API-Key` header
- **Body:**
  ```json
  {
    "message": "Show me my recent emails",
    "session_id": "my_session",
    "user_id": "user123",
    "provider": "gmail"
  }
  ```

### GET /api/agent/session/{session_id}
Get information about a conversation session.
- **Auth:** Requires `X-API-Key` header
- **Returns:** Session details, message count, context

### DELETE /api/agent/session/{session_id}
Clear a conversation session.
- **Auth:** Requires `X-API-Key` header
- **Returns:** Confirmation message

## Troubleshooting

### Error: "Backend server is not running!"
**Solution:** Start the backend in a separate terminal:
```bash
python backend/main.py
```

### Error: 404 Not Found on /api/agent/*
**Solution:** The backend server was started before the code changes. Restart it:
1. Press `Ctrl+C` in the backend terminal
2. Run `python backend/main.py` again
3. Run the tests again

### Error: 403 Forbidden / API Key Invalid
**Solution:** Check that:
1. `backend/.env` contains `API_KEY=test-key-123`
2. The test is using the correct API key
3. Try setting it explicitly: `set API_KEY=test-key-123`

### Error: "Python-dotenv could not parse statement"
**Solution:** This was fixed - the `.env` file had invalid syntax on lines 38-39. The fix is already applied.

## Example Usage

```python
# Simple example of using the executive agent
import requests

headers = {"X-API-Key": "test-key-123"}
payload = {
    "message": "What's on my calendar today?",
    "session_id": "demo_session",
    "user_id": "demo_user",
    "provider": "gmail"
}

response = requests.post(
    "http://localhost:8000/api/agent/chat",
    json=payload,
    headers=headers
)

data = response.json()
print(data["message"])
```

## Next Steps

1. **Explore Interactive Mode:** Run `python test_executive_agent.py` and select option 4
2. **Check API Docs:** Visit http://localhost:8000/docs for full API documentation
3. **Read the Guide:** See `EXECUTIVE_AGENT_GUIDE.md` for detailed agent capabilities

## Success Criteria

✅ Backend starts without errors  
✅ `python test_quick.py` shows all green checkmarks  
✅ `python test_executive_agent.py` connects to backend  
✅ Chat with the agent works in interactive mode  

---

**Last Updated:** 2026-02-03  
**Tested On:** Windows 11, Python 3.x
