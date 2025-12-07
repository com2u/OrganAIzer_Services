# OpenRouter Image Generation Setup

This document describes the OpenRouter integration for image generation using Google Gemini 2.5 Flash Image Preview.

## Overview

The image generation service has been migrated from Google Vertex AI to OpenRouter API, which provides access to Google's Gemini 2.5 Flash Image Preview model for generating high-quality images from text prompts.

## Configuration

### Environment Variables

Add the following to your `backend/.env` file:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

Get your API key from: https://openrouter.ai/

### Dependencies

The service requires the `requests` library, which is included in `backend/requirements.txt`:

```
requests==2.31.0
```

## Supported Features

### Aspect Ratios

The following aspect ratios are supported:

- `1:1` → 1024×1024 (default)
- `2:3` → 832×1248
- `3:2` → 1248×832
- `3:4` → 864×1184
- `4:3` → 1184×864
- `4:5` → 896×1152
- `5:4` → 1152×896
- `9:16` → 768×1344
- `16:9` → 1344×768
- `21:9` → 1536×672

### API Parameters

- `prompt` (required): Text description of the image to generate
- `num_images` (optional, default: 1): Number of images to generate (1-4)
- `aspect_ratio` (optional, default: "1:1"): Image aspect ratio (see above)

## API Endpoint

### Generate Images

**POST** `/api/image-gen/generate`

**Request Body:**
```json
{
  "prompt": "A beautiful sunset over mountains",
  "num_images": 1,
  "aspect_ratio": "16:9"
}
```

**Response:**
```json
{
  "images": [
    {
      "image_id": "6fe5fb39-007a-4009-84b0-ce09de78ec55",
      "url": "/api/image-gen/images/6fe5fb39-007a-4009-84b0-ce09de78ec55"
    }
  ]
}
```

### Retrieve Generated Image

**GET** `/api/image-gen/images/{image_id}`

Returns the generated image as a PNG file.

## Testing

Use the provided test script to verify the setup:

```bash
python test-openrouter-image-gen.py
```

This will:
1. Initialize the image generation service
2. Generate a test image
3. Save it to the `data/images/` directory
4. Display the image path and file information

## Implementation Details

### Service Architecture

- **Service**: `backend/services/image_gen_service.py`
  - Uses OpenRouter API to generate images
  - Handles base64 decoding of received images
  - Saves images to local storage
  - Provides cleanup functionality for old images

- **API Endpoint**: `backend/api/image_gen.py`
  - FastAPI routes for image generation and retrieval
  - Handles request validation
  - Returns generated images

- **Configuration**: `backend/core/config.py`
  - Manages OpenRouter API key
  - Provides application-wide settings

### Image Storage

Generated images are stored in:
```
backend/data/images/image_{uuid}.png
```

Images are automatically cleaned up after 24 hours (configurable).

## Migration from Vertex AI

The service was previously using Google Vertex AI Imagen. Key changes:

1. **API Provider**: Changed from Vertex AI to OpenRouter
2. **Authentication**: API key-based instead of service account
3. **Dependencies**: Replaced `google-cloud-aiplatform` with `requests`
4. **Response Format**: Base64-encoded images instead of PIL Image objects

## Troubleshooting

### API Key Not Found

Error: `OpenRouter API key not configured`

**Solution**: Ensure `OPENROUTER_API_KEY` is set in `backend/.env`

### API Request Failed

Error: `Failed to communicate with OpenRouter API`

**Possible Causes**:
- Invalid API key
- Network connectivity issues
- API rate limits exceeded

**Solution**: Check API key validity and network connection

### No Images Generated

Error: `No images were generated from the API response`

**Possible Causes**:
- Prompt may violate content policy
- API returned unexpected response format

**Solution**: Review prompt content and check API response logs

## Example Usage

### Python (Direct Service Call)

```python
from services.image_gen_service import get_image_gen_service
import asyncio

async def generate():
    service = get_image_gen_service()
    image_ids = await service.generate_images(
        prompt="A serene lake at sunset",
        num_images=1,
        aspect_ratio="16:9"
    )
    print(f"Generated image IDs: {image_ids}")

asyncio.run(generate())
```

### Via API (PowerShell)

```powershell
$body = @{
    prompt = "A cute cat sitting on a windowsill"
    num_images = 1
    aspect_ratio = "1:1"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/image-gen/generate" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

### Frontend (TypeScript/React)

```typescript
import { api } from '@/lib/api';

const response = await api.generateImage({
  prompt: "A futuristic cityscape",
  numImages: 1,
  aspectRatio: "16:9"
});

console.log(response.images);
```

## Resources

- OpenRouter Documentation: https://openrouter.ai/docs
- Gemini Image Generation: https://ai.google.dev/gemini-api/docs/image-generation
- API Reference: http://localhost:8000/docs (when backend is running)
