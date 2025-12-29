# Quick Installation Guide

## Step 1: Start the Backend Service

```bash
cd /path/to/OrganAIzer_Service
./start.sh
```

The backend should now be running at `http://localhost:8000`

## Step 2: Load Extension in Chrome

1. Open Chrome browser
2. Navigate to `chrome://extensions/`
3. Enable **Developer mode** (toggle in top-right corner)
4. Click **Load unpacked**
5. Navigate to and select the `OgranAIzer_PlugIn` folder
6. Click **Select Folder**

## Step 3: Verify Installation

You should see the OrganAIzer extension in your extensions list with a purple "AI" icon.

## Step 4: Configure (Optional)

1. Click the OrganAIzer extension icon in your browser toolbar
2. Verify the Backend URL is `http://localhost:8000`
3. Customize prompts if desired
4. Click **Save Settings**

## Step 5: Test the Extension

1. Open any webpage with text (e.g., Google Docs, Gmail, Wikipedia)
2. Select some text
3. Try one of these methods:
   - Click the extension icon and choose an action
   - Right-click → OrganAIzer → Choose an action
   - Use keyboard shortcuts:
     - `Ctrl+Shift+R` - Read Aloud
     - `Ctrl+Shift+S` - Summarize
     - `Ctrl+Shift+D` - Dictation
     - `Ctrl+Shift+I` - Generate Image
     - `Ctrl+Shift+T` - Translate

## Troubleshooting

### Extension doesn't load
- Make sure you selected the correct folder (should contain `manifest.json`)
- Check for errors in the extensions page
- Try reloading the extension

### Features don't work
- Verify backend is running: Open `http://localhost:8000/docs` in browser
- Check browser console for errors (F12 → Console)
- Ensure you granted necessary permissions (microphone for dictation)

### CORS errors
- The backend should allow localhost connections
- Check that `host_permissions` in `manifest.json` matches your backend URL

## Uninstalling

1. Go to `chrome://extensions/`
2. Find OrganAIzer Plugin
3. Click **Remove**
4. Confirm removal

---

**Need help?** See [README.md](README.md) for detailed documentation.
