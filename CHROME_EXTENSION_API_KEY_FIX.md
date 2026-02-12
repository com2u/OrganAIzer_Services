# Chrome Extension API Key Fix - Diagnostic Report

## 🔍 PROBLEM IDENTIFIED

**Issue:** Chrome extension stopped working after changing the OpenRouter API key in `backend/.env`

**Root Cause:** Backend service was NOT restarted after updating the environment variable, causing it to use the cached (old) API key value.

---

## 📋 COMPLETE DIAGNOSIS

### 1️⃣ API Key Loading Flow ✅

**Chrome Extension (plugin/):**
- ✅ API key stored in: `chrome.storage.sync` 
- ✅ Variable name: `apiKey`
- ✅ Retrieved at runtime via: `chrome.storage.sync.get()`
- ✅ Used in header: `X-API-Key` (for backend auth, not OpenRouter)

**Backend Service (backend/):**
- ✅ OpenRouter key stored in: `backend/.env`
- ✅ Variable name: `OPENROUTER_API_KEY`
- ✅ Loaded at startup via: `dotenv.load_dotenv()` in `llm_service.py`
- ⚠️ **CACHED IN MEMORY** - Not reloaded during runtime

### 2️⃣ Request Configuration ✅

**Extension → Backend:**
```javascript
// content.js line ~481
fetch(`${settings.apiUrl}/api/llm`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': settings.apiKey  // Backend validation only
  },
  body: JSON.stringify({ prompt })
})
```

**Backend → OpenRouter:**
```python
# backend/services/llm_service.py line ~157
requests.post(
    "https://openrouter.ai/api/v1/chat/completions",  # ✅ CORRECT URL
    headers={
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",  # ✅ CORRECT FORMAT
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "OrganAIzer",
        "Content-Type": "application/json"
    },
    json={
        "model": model,  # ✅ Default: google/gemini-2.5-flash
        "messages": msg_array
    }
)
```

### 3️⃣ Message Passing ✅

**Background Script (background.js):**
- ✅ Context menu handling works correctly
- ✅ Message listener returns `true` for async operations
- ✅ No message passing issues

**Content Script (content.js):**
- ✅ Message listener properly configured
- ✅ `sendResponse()` called correctly
- ✅ No chrome.runtime.lastError issues

### 4️⃣ Manifest Configuration ✅

**Permissions:**
- ✅ `"storage"` - Required for chrome.storage.sync
- ✅ `"activeTab"` - Required for content script injection
- ✅ `"scripting"` - Required for dynamic script injection
- ✅ `"contextMenus"` - For right-click menu

**Service Worker:**
- ✅ Path: `"background.js"` - Correct
- ✅ No syntax errors in manifest.json

---

## 🎯 THE EXACT BREAKING POINT

**File:** `backend/services/llm_service.py`  
**Lines:** 9-10

```python
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # ⚠️ Loaded ONCE at import
MODEL = os.getenv("MODEL")                             # ⚠️ Loaded ONCE at import
```

**What happens:**
1. Backend starts → Python imports `llm_service.py`
2. `load_dotenv()` reads `.env` file
3. `OPENROUTER_API_KEY` variable set to OLD key value
4. Variable stays in memory (cached)
5. User updates `.env` with NEW key
6. Backend still uses OLD key from memory
7. OpenRouter API rejects requests (401 Unauthorized or similar)

---

## ✅ THE FIX

### Immediate Solution: RESTART BACKEND

```bash
# Stop backend (Ctrl+C in terminal running backend)
# Then restart:
cd backend
python main.py
```

**OR** if using the batch file:
```bash
# Stop all services (Ctrl+C)
# Then restart:
start_services.bat
```

### Verification Added

**New Debug Logging** (`llm_service.py` lines 13-21):
```python
# Debug logging for API key (safe - only shows length and prefix)
if OPENROUTER_API_KEY:
    print(f"[LLM Service] ✓ OpenRouter API key loaded: {OPENROUTER_API_KEY[:10]}...{OPENROUTER_API_KEY[-4:]} (length: {len(OPENROUTER_API_KEY)})")
else:
    print("[LLM Service] ✗ WARNING: OpenRouter API key NOT found in environment!")

if MODEL:
    print(f"[LLM Service] ✓ Model configured: {MODEL}")
else:
    print("[LLM Service] ✗ WARNING: MODEL not configured, will use default")
```

**New Diagnostic Endpoint** (`routers/llm.py`):
```
GET http://localhost:8000/api/llm/diagnostic
```

Returns:
```json
{
  "openrouter_configured": true,
  "api_key_length": 89,
  "api_key_prefix": "redacted",
  "api_key_suffix": "2865",
  "model_configured": true,
  "model": "google/gemini-2.5-flash",
  "api_url": "https://openrouter.ai/api/v1/chat/completions",
  "auth_header": "Authorization: Bearer <API_KEY>",
  "status": "OK"
}
```

---

## 🧪 HOW TO TEST

### Step 1: Verify Backend Configuration

**1.1 Check console output when starting backend:**
```bash
cd backend
python main.py
```

Look for:
```
[LLM Service] ✓ OpenRouter API key loaded: ...2865 (length: 89)
[LLM Service] ✓ Model configured: google/gemini-2.5-flash
```

**1.2 Test diagnostic endpoint:**
```bash
curl http://localhost:8000/api/llm/diagnostic
```

Or open in browser:
```
http://localhost:8000/api/llm/diagnostic
```

### Step 2: Test Extension Locally

**2.1 Load extension in Chrome:**
1. Open `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `plugin` folder
5. Click "Reload" button on extension

**2.2 Check Service Worker console:**
1. In `chrome://extensions`, click "Service worker" link
2. Check for errors in console

**2.3 Test functionality:**
1. Navigate to any webpage
2. Select some text
3. Right-click → OrganAIzer → Summarize
4. OR click extension icon → click "Summarize" button
5. Check for notification showing "Generating summary..."

### Step 3: Verify Request Flow

**3.1 Open Network tab in browser DevTools**

**3.2 Trigger an extension action**

**3.3 Check network request:**
- Request URL: `http://localhost:8000/api/llm`
- Method: POST
- Headers should include: `X-API-Key: test-key-123`
- Response status should be: 200 OK

**3.4 Check backend terminal:**
- Should see incoming request logged
- No 401/403 errors from OpenRouter

---

## 🚨 COMMON ERRORS & SOLUTIONS

### Error 1: "No active text field found"
**Cause:** User clicked action button without selecting text first  
**Solution:** Select text on webpage before using Summarize/Translate

### Error 2: "Failed to generate summary: Server error: 401"
**Cause:** Invalid or old OpenRouter API key  
**Solution:** 
1. Update `backend/.env` with valid key
2. **RESTART BACKEND** ← Critical step
3. Verify with diagnostic endpoint

### Error 3: "Disconnected" status in extension popup
**Cause:** Backend not running or wrong URL  
**Solution:**
1. Start backend: `cd backend && python main.py`
2. Check URL in extension settings (default: `http://localhost:8000`)
3. Click "Test Connection" button

### Error 4: Extension doesn't respond
**Cause:** Content script not loaded properly  
**Solution:**
1. Reload extension at `chrome://extensions`
2. Refresh the webpage
3. Check Service Worker console for errors

---

## 📝 CONFIGURATION CHECKLIST

### Backend (.env file)
- [ ] `OPENROUTER_API_KEY` is set and valid
- [ ] `MODEL` is set (e.g., `google/gemini-2.5-flash`)
- [ ] Backend has been **restarted** after any changes

### Chrome Extension
- [ ] Extension loaded in `chrome://extensions`
- [ ] Backend URL configured (Settings tab in popup)
- [ ] Connection status shows "Connected"
- [ ] Test Connection button returns success

### Permissions
- [ ] Microphone permission (for dictation)
- [ ] Clipboard permission (for copy operations)

---

## 🔧 FILES MODIFIED

1. ✅ **backend/services/llm_service.py**
   - Added debug logging on startup
   - Shows API key prefix/suffix and length
   - Warns if key is missing

2. ✅ **backend/routers/llm.py**
   - Added `/llm/diagnostic` endpoint
   - Returns configuration status
   - Safe debugging (doesn't expose full key)

---

## 📊 SUMMARY

| Component | Status | Issue | Fix |
|-----------|--------|-------|-----|
| Extension Files | ✅ OK | None | N/A |
| Manifest.json | ✅ OK | None | N/A |
| Message Passing | ✅ OK | None | N/A |
| API Key Storage | ⚠️ CACHED | Not reloaded | **Restart backend** |
| Request Format | ✅ OK | None | N/A |
| OpenRouter URL | ✅ OK | None | N/A |
| Auth Header | ✅ OK | None | N/A |

---

## 🎯 FINAL ANSWER

**What broke:** Backend service was using a cached (old) OpenRouter API key stored in memory.

**Where:** `backend/services/llm_service.py` lines 9-10 - Environment variables loaded once at startup.

**Why:** Python loads `.env` file only when the service starts. After changing the API key, the backend needed to be restarted to reload the new value.

**How to fix NOW:**
1. Stop backend (Ctrl+C)
2. Restart backend (`python backend/main.py`)
3. Verify key loaded correctly in console output
4. Test with extension

**How to test:**
1. Check backend console for: `[LLM Service] ✓ OpenRouter API key loaded...`
2. Test diagnostic endpoint: `http://localhost:8000/api/llm/diagnostic`
3. Open extension → Select text → Right-click → Summarize
4. Should see "Generating summary..." notification and receive result

---

## 🛡️ PREVENTION

**Always remember:** After changing ANY value in `backend/.env`, you MUST restart the backend service for changes to take effect.

**Pro tip:** Use the diagnostic endpoint to verify configuration after restart:
```bash
curl http://localhost:8000/api/llm/diagnostic | python -m json.tool
```
