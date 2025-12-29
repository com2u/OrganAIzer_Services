# OrganAIzer Browser Plugin

A Chrome browser extension that integrates AI-powered text and media processing directly into online documents (Confluence, Word Online, Google Docs, etc.). Process text, generate images, dictate content, and more without leaving your workflow.

## Features

### 🔊 Text to Speech
- Select any text and have it read aloud
- Uses backend TTS service for natural speech
- Keyboard shortcut: `Ctrl+Shift+R`

### 📝 Text to Summary
- Select text and generate a concise summary
- Customizable summary prompts
- Inserts summary at cursor position
- Keyboard shortcut: `Ctrl+Shift+S`

### 🎤 Dictation (Speech to Text)
- Dictate text and insert it at cursor position
- Uses browser's built-in speech recognition
- Works in any text field or contenteditable area
- Keyboard shortcut: `Ctrl+Shift+D`

### 🖼️ Text to Image
- Select text description and generate an image
- Automatically inserts image at cursor position
- Powered by backend AI image generation
- Keyboard shortcut: `Ctrl+Shift+I`

### 🌐 Translate
- Select text and translate it
- Customizable translation prompts (default: to English)
- Replaces selected text with translation
- Keyboard shortcut: `Ctrl+Shift+T`

## Prerequisites

- Chrome browser (or Chromium-based browser)
- OrganAIzer Service backend running (default: http://localhost:8000)
- See [Backend_README.md](Backend_README.md) for backend setup instructions

## Installation

### 1. Install the Backend Service

First, ensure the OrganAIzer Service backend is running. Refer to `Backend_README.md` for setup instructions.

### 2. Load the Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" using the toggle in the top right corner
3. Click "Load unpacked"
4. Select the `OgranAIzer_PlugIn` directory
5. The extension should now appear in your extensions list

### 3. Configure the Extension

1. Click the OrganAIzer extension icon in your browser toolbar
2. Set the Backend URL (default: `http://localhost:8000`)
3. (Optional) Enter an API key if your backend requires authentication
4. Customize the default prompts for Summary and Translation
5. Click "Save Settings"

## Usage

### Using the Popup

1. Click the OrganAIzer icon in your browser toolbar
2. Select text on the page (if required for the action)
3. Click one of the action buttons:
   - 🔊 Read Aloud
   - 📝 Summarize
   - 🎤 Dictation
   - 🖼️ Generate Image
   - 🌐 Translate

### Using Keyboard Shortcuts

- `Ctrl+Shift+R` - Read selected text aloud
- `Ctrl+Shift+S` - Summarize selected text
- `Ctrl+Shift+D` - Start dictation
- `Ctrl+Shift+I` - Generate image from selected text
- `Ctrl+Shift+T` - Translate selected text

### Using Context Menu

1. Select text on any webpage
2. Right-click to open the context menu
3. Navigate to "OrganAIzer" submenu
4. Choose your desired action

## Customization

### Summary Prompt

Default prompt:
```
Summarize the following text in a concise manner, highlighting the key points:

{text}
```

The `{text}` placeholder will be replaced with your selected text.

### Translation Prompt

Default prompt:
```
Translate the following text to English:

{text}
```

Change "English" to any target language you prefer.

## Supported Platforms

The plugin works best with:
- ✅ Google Docs
- ✅ Confluence
- ✅ Word Online
- ✅ GitHub
- ✅ Gmail
- ✅ Any contenteditable fields
- ✅ Standard textarea/input fields

## Troubleshooting

### Extension not working
- Ensure the backend service is running at the configured URL
- Check browser console for errors (F12 → Console tab)
- Verify the extension has permission for the current website

### Cannot insert text/images
- Make sure you have an active cursor in a text field
- For rich editors (Google Docs, Confluence), click in the editor first
- Some websites may block automatic insertion due to security policies

### Dictation not working
- Ensure you've granted microphone permissions to the browser
- Speech recognition requires an internet connection in most browsers
- Currently only supports English (en-US)

### API errors
- Verify backend URL is correct in settings
- Check that the backend service is running and accessible
- Review backend logs for error details

## Architecture

### Components

- **manifest.json** - Extension configuration and permissions
- **popup.html/css/js** - Extension popup interface
- **content.js** - Injected into web pages to interact with documents
- **background.js** - Service worker handling shortcuts and context menus

### Data Flow

1. User selects text and triggers action (popup/shortcut/context menu)
2. Content script extracts selected text or cursor position
3. Request sent to backend API
4. Content script inserts/replaces text or plays audio
5. User receives notification of success/failure

## Privacy & Security

- All processing happens on your backend server
- No data is sent to third parties (except via your backend's AI services)
- API key (if used) is stored locally in Chrome's sync storage
- Extension only activates when you explicitly trigger an action

## Development

### File Structure

```
OgranAIzer_PlugIn/
├── manifest.json          # Extension manifest
├── popup.html            # Popup UI
├── popup.css             # Popup styles
├── popup.js              # Popup logic
├── content.js            # Content script (page interaction)
├── background.js         # Background service worker
├── icons/                # Extension icons
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
├── Backend_README.md     # Backend documentation
├── openapi.json          # API specification
└── README.md            # This file
```

### Making Changes

1. Edit the relevant files
2. Go to `chrome://extensions/`
3. Click the refresh icon on the OrganAIzer extension
4. Test your changes

### Debugging

- Use Chrome DevTools for popup debugging (right-click popup → Inspect)
- Check content script errors in page console (F12)
- View background script logs at `chrome://extensions/` → Details → Inspect views: service worker

## API Endpoints Used

- `POST /api/tts/generate` - Text to Speech
- `GET /api/tts/audio/{id}` - Get audio file
- `POST /api/stt/transcribe` - Speech to Text (not currently used, browser API preferred)
- `POST /api/llm` - LLM requests (Summary, Translation)
- `POST /api/text-image/generate` - Image generation

See [openapi.json](openapi.json) for complete API specification.

## Future Enhancements

- [ ] Multi-language support for dictation
- [ ] Batch processing of multiple selections
- [ ] Custom keyboard shortcuts configuration
- [ ] Audio file upload for transcription
- [ ] More AI model options
- [ ] Firefox and Edge support
- [ ] Offline mode for basic features

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or feature requests, please refer to the project repository or contact the development team.

---

**Note:** This extension requires the OrganAIzer Service backend to be running. Ensure you have configured and started the backend service before using this extension.
