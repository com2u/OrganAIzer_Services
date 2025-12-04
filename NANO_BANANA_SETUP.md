# Nano Banana (Gemini 2.5 Flash Image) Integration

## Overview

"Nano Banana" is your nickname for **Gemini 2.5 Flash Image** - Google's image generation model accessible via the Gemini API.

## What Has Been Set Up

### 1. Node.js Script (`backend/generate-nano-banana.js`)
- **Purpose**: Generates images using Gemini 2.5 Flash Image
- **Model**: `gemini-2.5-flash-image`
- **Authentication**: Uses `GEMINI_API_KEY` from backend/.env
- **Features**:
  - Generate 1-4 images per request
  - Saves images to `backend/data/images/`
  - Returns base64 data URLs
  - Exports functions for use as a module

**Usage**:
```bash
node backend/generate-nano-banana.js "your prompt here" [numImages]
```

### 2. Python Service (`backend/services/nano_banana_service.py`)
- **Purpose**: Wraps the Node.js script for Python backend integration
- **Class**: `NanoBananaService`
- **Methods**:
  - `generate_images(prompt, num_images)`: Generate images
  - `get_image_path(image_id)`: Retrieve saved image path

### 3. API Endpoints (`backend/api/image_gen.py`)

#### Generate Images
```http
POST /api/nano-banana/generate
Content-Type: application/json

{
  "prompt": "your image description",
  "num_images": 2
}
```

**Response**:
```json
{
  "success": true,
  "model": "gemini-2.5-flash-image",
  "prompt": "your image description",
  "images": [
    {
      "image_id": "uuid-here",
      "url": "/api/nano-banana/image/uuid-here",
      "dataUrl": "data:image/png;base64,..."
    }
  ]
}
```

#### Retrieve Image
```http
GET /api/nano-banana/image/{image_id}
```

Returns the PNG image file.

## Configuration

### API Key
The Gemini API key is stored in `backend/.env`:
```env
GEMINI_API_KEY=AIzaSyAZguzHqpQgqUsc2LzMsohJ82OnKRq9osw
```

**Important**: This is Patrick's API key. Do not replace or remove it.

### Package Configuration
Updated `package.json` to use ES modules:
```json
{
  "type": "module",
  ...
}
```

## Testing

### Test the Node.js Script Directly
```bash
node backend/generate-nano-banana.js "a cute robot" 1
```

### Test via Python
```bash
python test-nano-banana.py
```

### Test via API
1. Start the backend:
   ```bash
   .\start_backend.bat
   ```

2. Make a POST request:
   ```bash
   curl -X POST http://localhost:8000/api/nano-banana/generate \
     -H "Content-Type: application/json" \
     -d "{\"prompt\": \"a cute robot\", \"num_images\": 1}"
   ```

## Current Status

✅ **Completed**:
- Node.js script created with Gemini 2.5 Flash Image integration
- Python service wrapper implemented
- API endpoints added to backend
- ES module configuration in package.json
- Test script created

⚠️ **Pending Verification**:
- The Node.js script execution needs debugging
- Image generation hasn't been confirmed yet
- May need to verify API key permissions for image generation

## Troubleshooting

### If images aren't generating:

1. **Check API Key Permissions**:
   - Verify the API key has access to Gemini 2.5 Flash Image
   - Visit: https://aistudio.google.com

2. **Check Node.js Version**:
   ```bash
   node --version
   ```
   Should be v16 or higher

3. **Check Dependencies**:
   ```bash
   npm list @google/genai
   ```

4. **Enable Detailed Logging**:
   Add debugging to `backend/generate-nano-banana.js`:
   ```javascript
   console.log("Starting generation...");
   console.log("API Key present:", !!process.env.GEMINI_API_KEY);
   ```

5. **Test with Simple Gemini Call First**:
   ```bash
   node generate-image-test.js
   ```
   This tests if basic Gemini API access works.

## Next Steps

1. **Debug the Node.js script** to understand why it's not producing output
2. **Verify API key** has image generation permissions
3. **Test end-to-end** once Node.js script works
4. **Update frontend** to use the new nano banana endpoint (optional)

## API Documentation

- Gemini API Docs: https://ai.google.dev/gemini-api/docs
- Imagen Guide: https://ai.google.dev/gemini-api/docs/imagen
- AI Studio: https://aistudio.google.com/models/gemini-2-5-flash-image

## File Structure

```
OrganAIzer_Services/
├── backend/
│   ├── generate-nano-banana.js     # Node.js image generation script
│   ├── services/
│   │   └── nano_banana_service.py  # Python wrapper service
│   ├── api/
│   │   └── image_gen.py            # API endpoints (includes nano banana)
│   └── .env                        # Contains GEMINI_API_KEY
├── package.json                    # Updated with "type": "module"
└── test-nano-banana.py            # Python test script
