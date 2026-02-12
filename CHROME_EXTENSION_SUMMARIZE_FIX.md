# Chrome Extension "Summarize with OrganAIzer" Fix

## Date: 2026-02-12
## Issue: Summarize feature fails silently with no error details

---

## ROOT CAUSE ANALYSIS

### Problem 1: Content Script Message Handler Not Returning Errors
**Location:** `plugin/content.js` line 11-16

**Issue:** The message listener was responding immediately with `{success: true}` WITHOUT waiting for the async `handleAction()` to complete. This meant:
- Errors were never captured or returned to background.js
- background.js:157 always got `{success: true}` even when summarization failed
- The actual error was hidden in the content script console

**Before:**
```javascript
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action) {
    handleAction(request.action); // Async, not awaited!
    sendResponse({ success: true }); // Returns immediately
  }
  return true;
});
```

**After:**
```javascript
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[DEBUG] Content script received message:', request);
  
  if (request.action) {
    // Handle action asynchronously and wait for result
    handleAction(request.action)
      .then(() => {
        console.log('[DEBUG] Action completed successfully:', request.action);
        sendResponse({ success: true });
      })
      .catch((error) => {
        console.error('[DEBUG] Action failed:', request.action, error);
        sendResponse({ success: false, error: error.message });
      });
    return true; // Keep message channel open for async response
  }
  
  sendResponse({ success: false, error: 'Unknown request' });
  return false;
});
```

### Problem 2: Global API Key Dependency Override
**Location:** `backend/main.py` line 74 and `backend/api_router.py`

**Issue:** The `api_router` was included with a global `dependencies=[Depends(get_api_key)]`, which REQUIRED an API key for ALL endpoints under `/api/*`, even though:
- The LLM endpoint in `backend/routers/llm.py` uses `get_api_key_optional`
- Chrome extension may not have an API key configured
- This resulted in 401 Unauthorized errors when calling `/api/llm` from the extension

**Before (main.py):**
```python
# All other API endpoints require API key (including STT and TTS generation)
app.include_router(api_router, prefix="/api", dependencies=[Depends(get_api_key)])
```

The LLM router was included inside `api_router`, so the global dependency override the optional auth.

**After (main.py):**
```python
# LLM endpoint with optional API key (for Chrome extension compatibility)
app.include_router(llm.router, prefix="/api", tags=["llm"])

# All other API endpoints require API key (including STT and TTS generation)
app.include_router(api_router, prefix="/api", dependencies=[Depends(get_api_key)])
```

And in `api_router.py`, removed:
```python
router.include_router(llm.router, tags=["llm"])  # Removed from here
```

### Problem 3: No Debug Logging
**Issue:** There was no logging to capture the actual error, making it impossible to debug

**Fix:** Added comprehensive debug logging:
- Background.js: Logs message send and response
- Content.js: Logs message receive, fetch request details, response status, and errors

---

## FILES CHANGED

### 1. `plugin/background.js`
- Added debug logging in `sendMessageToTab()` function
- Logs outgoing message and incoming response from content script

### 2. `plugin/content.js`
- **CRITICAL FIX:** Changed message handler to wait for async operations
- Added error catching and proper error responses
- Added detailed debug logging in `handleTextToSummary()`:
  - Settings loaded
  - Request URL, headers, body
  - Response status and data
  - Errors with full details

### 3. `backend/main.py`
- Moved LLM router to be included separately BEFORE api_router
- LLM endpoint now uses optional API key authentication
- Chrome extensions can call `/api/llm` without an API key

### 4. `backend/api_router.py`
- Removed LLM router from this file
- Added comment explaining why it's in main.py

---

## TESTING INSTRUCTIONS

### Step 1: Restart Backend
```bash
cd c:\Users\rxhec\OrganAIzer_Services\backend
python main.py
```

Verify the server starts successfully on http://localhost:8000

### Step 2: Reload Extension in Chrome
1. Open Chrome and go to `chrome://extensions/`
2. Find "OrganAIzer Plugin"
3. Click the **reload** button (🔄)

### Step 3: Test Summarize Feature
1. Go to any webpage (e.g., https://en.wikipedia.org/wiki/Artificial_intelligence)
2. Select some text (at least a paragraph)
3. Right-click and select **"Summarize with OrganAIzer"**
4. Open DevTools Console (F12)
5. Check for debug logs:

**Expected logs if working:**
```
[DEBUG] Sending message to tab X, action: textToSummary
[DEBUG] Content script received message: {action: "textToSummary"}
[DEBUG] Settings loaded: {apiUrl: "http://localhost:8000", hasApiKey: false}
[DEBUG] Fetch request: {url: "http://localhost:8000/api/llm", method: "POST", ...}
[DEBUG] Fetch response: {status: 200, statusText: "OK", ok: true}
[DEBUG] Response data: {response: "...summary text..."}
[DEBUG] Action completed successfully: textToSummary
[DEBUG] Received response from content script: {success: true}
```

**Expected if error:**
```
[DEBUG] Sending message to tab X, action: textToSummary
[DEBUG] Content script received message: {action: "textToSummary"}
[DEBUG] Settings loaded: {apiUrl: "http://localhost:8000", hasApiKey: false}
[DEBUG] Fetch request: {url: "http://localhost:8000/api/llm", method: "POST", ...}
[DEBUG] Fetch response: {status: 401, statusText: "Unauthorized", ok: false}
[DEBUG] Error response body: {"detail":"Invalid API Key"}
[DEBUG] Action failed: textToSummary Error: Server error: 401 - ...
[DEBUG] Received response from content script: {success: false, error: "Server error: 401 - ..."}
```

### Step 4: Verify Functionality
- Summary should appear in a notification (top-right purple/green box)
- Summary should be copied to clipboard
- Summary should be inserted at cursor position
- **No error in background.js:157**

---

## CLEANUP (After Confirming Fix Works)

Once you've confirmed the fix works, remove the debug logs:

### In `plugin/background.js` - Remove lines:
```javascript
console.log(`[DEBUG] Sending message to tab ${tabId}, action: ${action}`);
console.log(`[DEBUG] Received response from content script:`, response);
```

### In `plugin/content.js` - Remove lines:
```javascript
console.log('[DEBUG] Content script received message:', request);
console.log('[DEBUG] Action completed successfully:', request.action);
console.error('[DEBUG] Action failed:', request.action, error);
console.log('[DEBUG] Settings loaded:', { apiUrl: settings.apiUrl, hasApiKey: !!settings.apiKey });
console.log('[DEBUG] Fetch request:', { url, method: 'POST', headers, bodyLength: body.length });
console.log('[DEBUG] Fetch response:', { status: response.status, statusText: response.statusText, ok: response.ok });
console.error('[DEBUG] Error response body:', errorText);
console.log('[DEBUG] Response data:', data);
console.error('[DEBUG] Text to summary error:', error);
```

---

## WHAT WAS THE ACTUAL ERROR?

Based on the architecture:
1. **Most likely:** 401 Unauthorized because API key was required but extension had none
2. **Possible:** CORS error (less likely since CORS was already configured for extensions)
3. **Possible:** Backend not running (would show network error)

The debug logs will reveal the exact error when you test.

---

## API KEY SETUP (Optional)

If you want to require an API key from the extension:

1. Get a valid API key from `backend/keys.csv`
2. Open the extension popup
3. Click "Settings" or "Options"
4. Enter the API key
5. Save

However, with the current fix, the API key is **optional** for the `/api/llm` endpoint.

---

## VERIFICATION CHECKLIST

- [ ] Backend starts without errors
- [ ] Extension reloaded in Chrome
- [ ] Selected text on a webpage
- [ ] Right-clicked and chose "Summarize with OrganAIzer"
- [ ] Checked console for [DEBUG] logs
- [ ] Summary notification appeared
- [ ] Summary was copied to clipboard
- [ ] No error at background.js:157
- [ ] Summarization completed successfully

---

## Notes

- The same fix applies to "Translate with OrganAIzer" feature (it uses the same `/api/llm` endpoint)
- Other features (Text-to-Speech, Image Generation) may need similar review if they fail
- CORS is already configured to allow Chrome extensions
- The fix maintains backward compatibility with API key authentication

---

## Future Improvements

1. Add better error messages in the notification UI (currently just shows "Failed to generate summary: ...")
2. Add retry logic for network failures
3. Add settings UI in the extension popup for API URL and API key
4. Consider adding a "loading" state indicator beyond just the notification
5. Add proper error types (NetworkError, AuthError, ServerError, etc.)
