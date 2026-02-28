# OrganAIzer Services – Developer Guide

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend build toolchain |
| npm | 9+ | Package management |
| FFmpeg | Any recent | Audio/video processing (STT, transcription) |
| git | Any | Source control |

---

## Running the Backend

### First-Time Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment — copy the example and fill in your values
copy backend\.env.example backend\.env   # Windows
cp backend/.env.example backend/.env     # Linux / macOS
# Edit backend/.env — minimum: OPENROUTER_API_KEY + TOKEN_ENCRYPTION_KEY
# Full variable reference: see DEPLOYMENT.md
```

### Starting the Backend

```bash
# From repo root (Windows, recommended)
start_backend_venv.bat

# Or manually
cd backend
venv\Scripts\activate
python main.py
```

The API is available at: **http://localhost:8000**  
Interactive docs: **http://localhost:8000/docs**

---

## Running the Frontend

### First-Time Setup

```bash
cd frontend
npm install

# Configure environment
echo VITE_API_BASE_URL=http://localhost:8000 > .env
```

### Starting the Frontend

```bash
# From repo root (Windows)
start_frontend.bat

# Or manually
cd frontend
npm run dev
```

Frontend available at: **http://localhost:5173**

### Both Services Together (Windows)

```bash
start_services.bat
```

---

## Running Tests

Test files are located in the repo root (named `test_*.py`) and in `scripts/`.

```bash
# Activate venv first
cd backend && venv\Scripts\activate

# Run all tests
cd ..
python test_all_features.py

# Run specific tests
python test_intent_router.py
python test_email_state_machine.py
python test_executive_agent.py
python test_agent_calendar_e2e.py

# Backend import check
cd backend && python test_import.py
```

PowerShell test runner:
```powershell
.\test_agent_live.ps1
.\check_backend.ps1
```

---

## Project Structure

```
OrganAIzer_Services/
├── backend/                   # Python FastAPI backend
│   ├── main.py                # Application entry point
│   ├── api/                   # HTTP endpoint handlers (thin layer)
│   ├── services/              # Business logic
│   ├── utils/                 # Shared utilities (intent router, slot extraction, tokens)
│   ├── models/                # Pydantic schemas (request/response)
│   ├── core/                  # Config, logging, error handling, middleware
│   ├── config/                # Google OAuth scopes definition
│   ├── middleware/            # Correlation ID middleware
│   ├── routers/               # Additional routers (e.g., Outlook health)
│   ├── data/                  # Runtime data (tts audio, images, tokens) — gitignored
│   ├── requirements.txt       # Python dependencies
│   └── .env                   # Environment variables (gitignored)
├── frontend/                  # React/Vite SPA
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Page-level components
│   │   ├── lib/api.ts         # Typed API client
│   │   └── App.tsx            # Root application
│   ├── package.json
│   └── .env                   # Frontend env (gitignored)
├── docs/                      # Additional documentation assets
├── scripts/                   # Standalone test/utility scripts
├── ARCHITECTURE.md            # System architecture documentation
├── DEPLOYMENT.md              # Deployment & environment guide
├── DEVELOPER_GUIDE.md         # This file
├── API_OVERVIEW.md            # API endpoint reference
├── README.md                  # Project overview and quick start
└── LICENSE
```

---

## How to Extend the Executive AI

The Executive AI lives in `backend/services/executive_agent_service.py`. Adding new capabilities involves:

### 1. Add a new tool function

Inside `ExecutiveAgent`, add a new async method. Follow the existing pattern:

```python
async def _tool_my_new_tool(self, user_id: str, param: str) -> dict:
    """Description of what this tool does."""
    # Implementation here
    return {"result": "...", "success": True}
```

### 2. Register the tool in the system prompt

The system prompt defines which tools the LLM can call. Update the tools list in `executive_agent_service.py` to include your new tool description.

### 3. Handle the tool call in the dispatch logic

The agent's `process_message` method dispatches tool calls. Add a case for your new tool:

```python
elif tool_name == "my_new_tool":
    result = await self._tool_my_new_tool(
        user_id=user_id,
        param=tool_args.get("param")
    )
```

### 4. Write a test

Add a test in the repo root:

```python
# test_my_new_tool.py
import asyncio
from backend.services.executive_agent_service import ExecutiveAgent

async def test():
    agent = ExecutiveAgent(session_id="test")
    response = await agent.process_message("use my new tool with X", user_id="test")
    print(response)

asyncio.run(test())
```

---

## How to Add New API Endpoints

### 1. Create a router module in `backend/api/`

```python
# backend/api/my_feature.py
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class MyRequest(BaseModel):
    input: str

class MyResponse(BaseModel):
    output: str
    success: bool

@router.post("/my-endpoint")
async def my_endpoint(request: MyRequest) -> MyResponse:
    # Implementation
    return MyResponse(output="result", success=True)
```

### 2. Register the router in `backend/main.py`

```python
from api import my_feature

# Add with the other router registrations:
app.include_router(my_feature.router, prefix="/api")
```

### 3. Create a service (if needed)

Keep API handlers thin. Put business logic in `backend/services/my_feature_service.py`.

### 4. Add a Pydantic model (if needed)

Define request/response schemas in `backend/models/my_feature.py`.

---

## How to Modify Intent Routing

The Intent Router (`backend/utils/intent_router.py`) is intentionally **separate from the LLM**. It runs deterministically before any AI inference.

### Add new keyword patterns

```python
# Example: Add new confirmation keywords
CONFIRM_KEYWORDS = [
    "yes", "y", "yep",  # existing
    "affirmative",       # new
]
```

### Add a new intent type

```python
class IntentType:
    # ... existing types ...
    MY_NEW_INTENT = "MY_NEW_INTENT"
```

Then add detection logic in `route_message()` at the appropriate priority level.

### Add calendar/email patterns

```python
# In IntentRouter class:
CALENDAR_CREATE_PATTERNS = [
    # ... existing ...
    "book a room",   # new pattern
]
```

---

## How to Add a New Integration Provider

The integration system supports Google and Microsoft. To add a third provider (e.g., Apple Calendar):

1. Create `backend/services/providers/apple_provider.py` implementing the interface in `backend/services/providers/base.py`
2. Add OAuth endpoints in `backend/api/integrations.py` following the Google/Outlook pattern
3. Update `backend/utils/token_storage.py` to handle the new provider key
4. Add provider detection in `backend/utils/intent_router.py` (`SENDER_ACCOUNT_KEYWORDS`, `CALENDAR_PROVIDER_KEYWORDS`)
5. Handle the new provider in `executive_agent_service.py` tool dispatch

---

## Code Style & Conventions

| Convention | Details |
|---|---|
| Python style | PEP 8; type hints on all function signatures |
| Async | All API handlers and service methods are `async` |
| Error handling | Raise `AppError` for business logic errors; let `HTTPException` propagate |
| Logging | Use `logger = logging.getLogger(__name__)` in each module |
| Pydantic | All request/response models use Pydantic v2 syntax |
| Router tags | Always set `tags=[...]` on routers for Swagger grouping |

### Logging Pattern

```python
import logging
logger = logging.getLogger(__name__)

# In functions:
logger.info(f"[FEATURE] Action description: {variable}")
logger.error(f"[FEATURE] Error description: {e}", exc_info=True)
```

### Error Response Format

All errors follow this structure:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {}
  }
}
```

---

## Regenerating the OpenAPI Spec

After adding or modifying endpoints:

```bash
# From the repo root
python backend/export_openapi.py
```

This regenerates both `openapi.yaml` and `openapi.json` in the repo root.

---

## Useful Development Commands

```bash
# Check all backend imports are working
cd backend && python test_import.py

# Verify OpenAPI spec is valid
python verify_openapi.py

# Run the backend in debug mode
cd backend && LOG_LEVEL=DEBUG python main.py

# Check backend health
curl http://localhost:8000/health

# View active sessions
curl http://localhost:8000/api/agent/sessions
```
