# Image Generation Setup Guide

## Overview

This guide will help you set up the AI Image Generation feature using Google Vertex AI Imagen. The feature allows users to generate images from text descriptions (prompts).

## Prerequisites

- Python 3.8+ installed
- Node.js 16+ installed
- Google Cloud Platform account
- Google Cloud Project with Vertex AI API enabled

## Step 1: Google Cloud Setup

### 1.1 Create/Select a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your **Project ID** (you already have: `projects/1053209052640`)

### 1.2 Enable Vertex AI API

1. In Google Cloud Console, navigate to **APIs & Services** > **Library**
2. Search for "Vertex AI API"
3. Click **Enable**

### 1.3 Set Up Authentication

You have two options for authentication:

#### Option A: Application Default Credentials (Recommended for Development)

1. Install Google Cloud SDK (gcloud CLI):
   - Download from: https://cloud.google.com/sdk/docs/install
   - Run the installer

2. Authenticate with your Google Account:
   ```bash
   gcloud auth application-default login
   ```

3. Set your project:
   ```bash
   gcloud config set project 1053209052640
   ```

#### Option B: Service Account Key File (For Production)

1. In Google Cloud Console, go to **IAM & Admin** > **Service Accounts**
2. Click **Create Service Account**
3. Enter a name (e.g., "organizer-image-gen")
4. Grant the role: **Vertex AI User**
5. Click **Create and Continue**, then **Done**
6. Click on the created service account
7. Go to **Keys** tab
8. Click **Add Key** > **Create new key**
9. Choose **JSON** format and click **Create**
10. Save the downloaded JSON file securely (e.g., `credentials/service-account-key.json`)

11. Update `backend/.env`:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account-key.json
   ```

## Step 2: Backend Setup

### 2.1 Install Dependencies

The required packages are already installed:
- google-cloud-aiplatform==1.38.0
- Pillow (latest version)

If you need to reinstall:
```bash
pip install google-cloud-aiplatform Pillow
```

### 2.2 Verify Environment Configuration

Check that `backend/.env` has the correct settings:

```env
# Image Generation Configuration
IMAGE_GEN_TEMP_DIR=./data/images

# Google Cloud Vertex AI Configuration
GOOGLE_CLOUD_PROJECT=projects/1053209052640
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=
```

**Note:** If using Application Default Credentials (Option A above), leave `GOOGLE_APPLICATION_CREDENTIALS` empty.

### 2.3 Create Required Directories

The application will automatically create these directories on startup:
- `backend/data/images` - For storing generated images

## Step 3: Frontend Setup

No additional setup needed! The frontend code is already integrated.

## Step 4: Test the Setup

### 4.1 Start the Backend

```bash
# From project root
.\start_backend.bat

# Or manually
cd backend
python main.py
```

Check the console output for:
```
INFO:__main__:Vertex AI initialized: projects/1053209052640
```

### 4.2 Start the Frontend

```bash
# From project root
.\start_frontend.bat

# Or manually
cd frontend
npm run dev
```

### 4.3 Test Image Generation

1. Open your browser to http://localhost:5173
2. Click the **Text → Image** tab
3. Enter a test prompt, e.g., "A beautiful sunset over the ocean"
4. Click "Generate Images"
5. Wait for the image(s) to be generated
6. Images should display with download buttons

## Step 5: Troubleshooting

### Issue: "Failed to initialize Vertex AI"

**Cause:** Authentication not set up correctly

**Solutions:**
1. If using Application Default Credentials:
   ```bash
   gcloud auth application-default login
   gcloud config set project 1053209052640
   ```

2. If using Service Account Key:
   - Verify the JSON key file path in `.env` is correct
   - Ensure the service account has "Vertex AI User" role

### Issue: "Permission Denied" or "403 Forbidden"

**Cause:** Insufficient permissions

**Solution:**
1. Go to Google Cloud Console > IAM & Admin > IAM
2. Find your user/service account
3. Add role: **Vertex AI User** or **Vertex AI Administrator**

### Issue: "Quota Exceeded"

**Cause:** You've hit the API usage limits

**Solutions:**
1. Check your quotas in Google Cloud Console > IAM & Admin > Quotas
2. Request a quota increase if needed
3. Wait for the quota to reset (usually daily)

### Issue: Images not displaying in frontend

**Cause:** CORS or network issues

**Solutions:**
1. Check browser console for errors
2. Verify backend is running on http://localhost:8000
3. Check that the API is accessible: http://localhost:8000/docs

## API Endpoints

### Generate Images
```
POST /api/image-gen/generate
Content-Type: application/json

{
  "prompt": "A serene mountain landscape",
  "num_images": 1,
  "aspect_ratio": "1:1"
}
```

### Get Generated Image
```
GET /api/image-gen/image/{image_id}
```

## Advanced Configuration

### Supported Aspect Ratios
- `1:1` - Square (default)
- `16:9` - Landscape
- `9:16` - Portrait
- `4:3` - Traditional landscape
- `3:4` - Traditional portrait

### Number of Images
- Min: 1
- Max: 4

### Costs

Vertex AI Imagen pricing (as of 2024):
- Image generation: ~$0.02 - $0.04 per image
- Prices may vary by region and usage tier
- Check current pricing: https://cloud.google.com/vertex-ai/pricing#generative-ai-models

### Rate Limits

Default Vertex AI limits (may vary by project):
- Requests per minute: 60
- Images per minute: 60

## Security Best Practices

1. **Never commit** service account keys to version control
2. Add `credentials/` to `.gitignore`
3. Use environment variables for sensitive data
4. Rotate service account keys regularly
5. Use least-privilege IAM roles
6. Enable audit logging in production

## Next Steps

### Phase 2: Image-to-Image Generation (Future Enhancement)

The current implementation supports text-to-image. Future enhancements could include:
- Upload reference images
- Image-to-image transformation
- Style transfer
- Image inpainting

## Support

For issues:
1. Check the backend logs for detailed error messages
2. Refer to [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/image/overview)
3. Review Google Cloud Console for API status and quotas

## Quick Reference Commands

```bash
# Test authentication
gcloud auth application-default login

# Check current project
gcloud config get-value project

# List enabled APIs
gcloud services list --enabled

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Run both services
.\start_services.bat

# Run backend only
.\start_backend.bat

# Run frontend only
.\start_frontend.bat
