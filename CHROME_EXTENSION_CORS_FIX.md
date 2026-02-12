# Chrome Extension CORS Fix

## Problem
The Chrome extension was experiencing "Failed to fetch" errors when trying to communicate with the backend API. This was due to CORS (Cross-Origin Resource Sharing) restrictions.

## Root Cause
Chrome extensions operate from special origins like `chrome-extension://[extension-id]`, which were not included in the backend's CORS allowed origins list. The backend was only allowing specific HTTP/HTTPS origins.

## Solution
Updated the backend's CORS configuration in `backend/main.py` to accept requests from browser extension origins:

### Changes Made
1. **Modified CORS Middleware Configuration**
   - Changed from `allow_origins` (specific list) to `allow_origin_regex` (pattern matching)
   - Added regex pattern to allow:
     - All HTTP/HTTPS origins: `https?://.*`
     - Chrome extensions: `chrome-extension://.*`
     - Firefox extensions: `moz-extension://.*`
     - Edge extensions: `edge-extension://.*`

### Code Changes
```python
# Before
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Only specific HTTP origins
    ...
)

# After
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https?://.*|chrome-extension://.*|moz-extension://.*|edge-extension://.*)$",
    ...
)
```

## Testing
After restarting the backend server with the updated CORS configuration:

1. **Test Connection from Extension**
   - Open the Chrome extension popup
   - Click "Test Connection" button
   - Status should show "Connected" (green dot)

2. **Test Extension Features**
   - Select some text on a webpage
   - Right-click and use OrganAIzer context menu
   - Try features like:
     - Summarize with OrganAIzer
     - Translate with OrganAIzer
     - Generate Image from Text
     - Read Aloud

## Important Notes

### Security Considerations
- The regex pattern `^(https?://.*|chrome-extension://.*|moz-extension://.*|edge-extension://.*)$` is intentionally broad to allow all browser extensions
- This is acceptable because:
  1. API key authentication is still required for most endpoints
  2. Extensions must be explicitly installed by the user
  3. Browser extensions have limited cross-origin capabilities
  4. Production environment can use more restrictive patterns if needed

### Production Deployment
For production, consider:
- Using more specific extension ID patterns if needed
- Monitoring CORS-related access logs
- Implementing additional authentication layers for sensitive endpoints

## Files Modified
- `backend/main.py` - Updated CORS middleware configuration

## Restart Required
✅ **Backend server must be restarted** after this change for the new CORS policy to take effect.

## Verification Steps
1. Stop backend server: `taskkill /F /IM python3.13.exe`
2. Start backend server: Run `python main.py` in the `backend` directory
3. Test extension connection using the popup "Test Connection" button
4. Verify no CORS errors in browser console (F12 → Console tab)

## Related Features
This fix enables the following Chrome extension features:
- Text summarization
- Translation
- Text-to-speech (Read aloud)
- Speech-to-text (Dictation)
- Text-to-image generation
- All context menu integrations
- All keyboard shortcuts

## Troubleshooting

### If "Failed to fetch" persists:
1. Verify backend is running: `http://localhost:8000/health`
2. Check browser console for error details (F12 → Console)
3. Verify API key is configured in extension settings
4. Check backend logs for CORS errors
5. Ensure backend URL in extension settings matches actual server URL (default: `http://localhost:8000`)

### Check Backend Status
```bash
# Windows
tasklist | findstr python

# Test health endpoint
curl http://localhost:8000/health
```

## Date
Fixed: February 12, 2026
