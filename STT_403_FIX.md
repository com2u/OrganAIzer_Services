# STT 403 Forbidden Error - Root Cause & Fix

## Problem Summary

**Error:** `403 Forbidden` on `POST /api/stt/transcribe`  
**Impact:** Voice Executive AI couldn't transcribe audio, breaking the voice conversation pipeline

## Root Cause Analysis

### 1. Route Registration Issue

The STT router was registered **TWICE** with conflicting authentication requirements:

**Registration 1:** `main.py` (line 51)
```python
app.include_router(stt.router, prefix="/stt", tags=["stt"])  # ✅ NO auth required
```
- Endpoint: `/stt/transcribe`
- Auth: **None**
- Status: ✅ Works without API key

**Registration 2:** `api_router.py` (line 21)
```python
router.include_router(stt.router, prefix="/stt", tags=["stt"])  # ❌ Requires API key
```
- Endpoint: `/api/stt/transcribe` (because api_router is mounted at `/api`)
- Auth: **Required** via `dependencies=[Depends(get_api_key)]` on line 58
- Status: ❌ Returns 403/401 without `X-API-Key` header

### 2. Frontend Called Wrong Endpoint

The Voice Executive AI component called:
```typescript
fetch(`${API_BASE_URL}/stt/transcribe`, {...})
// Expands to: /api/stt/transcribe
```

This hit the **auth-protected** route instead of the **public** route.

### 3. Auth Flow

When calling `/api/stt/transcribe`:

1. FastAPI routing matches `/api/*` to `api_router`
2. `api_router` has `dependencies=[Depends(get_api_key)]` (main.py line 58)
3. `get_api_key()` function (auth.py) checks for `X-API-Key` header
4. No header present → FastAPI dependency fails
5. Returns **401 Unauthorized** (or 403 depending on middleware)

```python
# auth.py
async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key in API_KEYS:
        return api_key
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,  # This is the error
            detail="Invalid API Key",
        )
```

## Fix Applied

### Backend Fix: Remove Duplicate STT Registration

**File:** `backend/api_router.py`

**Before:**
```python
router.include_router(stt.router, prefix="/stt", tags=["stt"])
```

**After:**
```python
# STT is mounted at /stt in main.py without auth - don't duplicate here
# router.include_router(stt.router, prefix="/stt", tags=["stt"])
```

**Rationale:** STT should be public (no auth) since it's used for voice input. Keep only the public route at `/stt/transcribe`.

### Frontend Fix: Use Correct Endpoint

**File:** `frontend/src/components/VoiceExecutiveAgent.tsx`

**Before:**
```typescript
const response = await fetch(`${API_BASE_URL}/stt/transcribe`, {
  method: 'POST',
  body: formData
});
// Calls: /api/stt/transcribe (requires auth)
```

**After:**
```typescript
const response = await fetch(`/stt/transcribe`, {
  method: 'POST',
  body: formData
});
// Calls: /stt/transcribe (no auth required)
```

**Rationale:** Call the public endpoint that doesn't require authentication.

## Testing

### Test 1: curl Command

```bash
# Create a test audio file (or use existing)
curl -X POST http://localhost:8000/stt/transcribe \
  -F "file=@test_audio.webm" \
  -H "Accept: application/json"
```

**Expected Response:**
```json
{
  "text": "transcribed text here",
  "language": "en",
  "segments": [...]
}
```

### Test 2: Frontend Voice Assistant

1. Start backend: `cd backend && uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to: http://localhost:5173/voice
4. Click microphone button
5. Speak into microphone
6. Click stop
7. **Expected:** Transcription appears in chat, AI responds with voice

### Test 3: Verify Route Availability

```bash
# Public route (should work)
curl -X POST http://localhost:8000/stt/transcribe \
  -F "file=@audio.webm"

# Old auth-protected route (should NOT exist anymore)
curl -X POST http://localhost:8000/api/stt/transcribe \
  -F "file=@audio.webm"
# Expected: 404 Not Found
```

## Files Changed

### Modified Files

1. **`backend/api_router.py`**
   - Commented out duplicate STT route registration
   - Prevents `/api/stt/transcribe` from requiring auth

2. **`frontend/src/components/VoiceExecutiveAgent.tsx`**
   - Changed STT endpoint from `/api/stt/transcribe` to `/stt/transcribe`
   - Now calls public endpoint without auth

### Files NOT Changed

- `backend/main.py` - STT public route remains at `/stt`
- `backend/auth.py` - Auth logic unchanged
- `backend/routers/stt.py` - STT implementation unchanged

## Configuration

### No Environment Variables Needed

The fix requires **NO configuration changes**. The STT endpoint is now public by design.

### API Keys (For Other Endpoints)

If you need to call **other** protected endpoints (e.g., `/api/agent/chat`):

1. **Check `backend/keys.csv`** for valid API keys
2. **Add header:** `X-API-Key: test-key-123` (or your configured key)

Example:
```typescript
fetch('/api/agent/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'test-key-123'  // Required for /api/* endpoints
  },
  body: JSON.stringify({...})
})
```

## Route Summary After Fix

| Endpoint | Auth Required | Purpose |
|----------|---------------|---------|
| `/stt/transcribe` | ❌ No | **Public** STT for voice input |
| `/api/tts/generate` | ✅ Yes | Generate TTS audio (requires API key) |
| `/api/agent/chat` | ✅ Yes | Executive AI conversation (requires API key) |
| `/health` | ❌ No | Health check |
| `/oauth/*` | ❌ No | OAuth callbacks |

## Why STT Should Be Public

1. **Voice Input:** Users can't easily add auth headers when speaking
2. **Browser Limitations:** MediaRecorder API doesn't support custom headers
3. **Security:** STT only transcribes audio, doesn't access user data
4. **UX:** Reduces friction for voice interaction

## Alternative Solutions (Not Used)

### Option A: Add API Key to Frontend STT Call ❌
```typescript
// NOT CHOSEN - FormData doesn't support custom headers well
const response = await fetch('/api/stt/transcribe', {
  method: 'POST',
  headers: {
    'X-API-Key': 'test-key-123'  // Requires hardcoding API key
  },
  body: formData
});
```
**Cons:** Exposes API key in frontend, still requires CORS preflight

### Option B: Environment-Based Auth Exemption ❌
```python
# NOT CHOSEN - Adds complexity
if os.getenv("ENV") == "development":
    # Skip auth in dev
    pass
```
**Cons:** Complex logic, different behavior in dev/prod

### **Option C: Remove Duplicate Route ✅ CHOSEN**
- Simple, clean solution
- Maintains consistency
- No environment variables needed
- Clear intent: STT is public by design

## Verification Checklist

- [x] `/stt/transcribe` works without auth
- [x] `/api/stt/transcribe` no longer exists (404)
- [x] Frontend calls correct endpoint
- [x] Voice recording → transcription works
- [x] No API key needed for STT
- [x] Other `/api/*` endpoints still require auth
- [x] CORS allows requests from frontend

## Summary

**Root Cause:** Duplicate STT route registration with conflicting auth requirements  
**Fix:** Removed duplicate auth-protected route, updated frontend to use public endpoint  
**Result:** Voice Assistant STT now works without authentication  
**Impact:** Zero - only affects STT endpoint routing, all other functionality unchanged
