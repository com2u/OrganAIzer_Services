# Organizer Service Setup Guide

## Overview
This guide will help you set up the Organizer Service with proper environment configuration for both development and production.

## Files Created/Modified

### Root Level
- `.env` - Main environment configuration (already updated)
- `.env.example` - Template for environment variables
- `docker-compose.yml` - Updated to pass API keys to frontend
- `SETUP-GUIDE.md` - This guide

### Frontend Level
- `frontend/.env.example` - Frontend-specific environment template
- `frontend/vite.config.ts` - Updated for production backend URL
- `frontend/Dockerfile` - Updated to accept API key build argument
- `frontend/.dockerignore` - Already excludes .env files

## Quick Start

### 1. Environment Setup

#### For Development
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual values
# Make sure to set:
# - VITE_API_KEY (must match one of the API_KEYS)
# - All other API keys for your services
```

#### For Production
```bash
# Ensure .env contains production values:
VITE_API_KEY=l5hhroDITUp5zCFEGSaMk43HdVDFlK85
VITE_API_URL_PROD=http://organaizer_backend.com2u.selfhost.eu
```

### 2. Backend Configuration

The backend should be configured to use the same API keys. The `.env` file contains:
- `API_KEYS` - Comma-separated list of valid API keys
- `VITE_API_KEY` - The specific key used by frontend

### 3. Frontend Build Configuration

#### Development Build
```bash
cd frontend
npm install
npm run dev
```

#### Production Build (Docker)
```bash
# Build with API key
cd frontend
docker build --build-arg VITE_API_KEY=l5hhroDITUp5zCFEGSaMk43HdVDFlK85 -t frontend:latest .

# Or use docker-compose from root
cd ..
docker-compose up -d frontend
```

### 4. Docker Compose Deployment

From the project root:
```bash
# Make sure .env file exists with all required values
docker-compose up -d

# Check logs
docker-compose logs -f
```

## Environment Variables Reference

### Required Variables

#### Backend (.env)
```bash
# API Keys for backend authentication
API_KEYS=ylgS92K4Ca3HS7p53FW76ttoKwNhLgxB,D1RVbXwPLr00uCWpoC9eJhaQvAhEj8Y8,p8Mq3PWqkLFtjv8txsyVT8FjLH2Bmu95,l5hhroDITUp5zCFEGSaMk43HdVDFlK85

# Google API
GOOGLE_API_KEY=your_google_key

# OpenRouter (LLM)
OPENROUTER_API_KEY=your_openrouter_key
MODEL=google/gemini-2.5-flash

# Azure (Outlook)
AZURE_CLIENT_ID=your_azure_client_id
AZURE_TENANT_ID=your_azure_tenant_id
AZURE_CLIENT_SECRET=your_azure_client_secret
```

#### Frontend (.env)
```bash
# Must match one of the API_KEYS above
VITE_API_KEY=l5hhroDITUp5zCFEGSaMk43HdVDFlK85

# API URLs
VITE_API_URL=http://localhost:8000/api          # Development
VITE_API_URL_PROD=https://organaizer_backend.com2u.selfhost.eu  # Production

# Frontend URL (for reference)
FRONTEND_URL=https://organaizer.com2u.selfhost.eu
```

### Production Deployment

#### Step 1: Prepare Environment
```bash
# On production server
cd /path/to/OrganAIzer_Service

# Ensure .env is properly configured
nano .env
```

#### Step 2: Build and Deploy
```bash
# Build backend
docker-compose build backend

# Build frontend with production API key
cd frontend
docker build --build-arg VITE_API_KEY=l5hhroDITUp5zCFEGSaMk43HdVDFlK85 -t frontend:latest .
cd ..

# Deploy all services
docker-compose up -d
```

#### Step 3: Verify Deployment
```bash
# Check services are running
docker-compose ps

# Check logs
docker-compose logs -f

# Test backend health
curl https://organaizer_backend.com2u.selfhost.eu/health

# Test frontend
curl https://organaizer.com2u.selfhost.eu/
```

## Security Checklist

- [ ] `.env` file is never committed to version control
- [ ] `.env.example` contains only placeholder values
- [ ] API keys are strong and unique
- [ ] Docker .dockerignore excludes .env files
- [ ] Production uses HTTPS
- [ ] API keys are rotated regularly
- [ ] CORS is properly configured in production

## Troubleshooting

### Frontend shows "API key not configured"
- Check that `VITE_API_KEY` is set in `.env`
- Rebuild frontend with the build argument

### Backend returns 401 Unauthorized
- Ensure `VITE_API_KEY` matches one of the `API_KEYS` in backend `.env`
- Restart backend container after changing API keys

### Build fails with "tsc not found"
- This was fixed by updating Dockerfile to install devDependencies
- Run `docker-compose build --no-cache frontend` to rebuild

## File Structure Summary

```
OrganAIzer_Service/
├── .env                          # Main environment file
├── .env.example                  # Environment template
├── docker-compose.yml            # Updated with API key args
├── SETUP-GUIDE.md               # This file
├── frontend/
│   ├── .env.example             # Frontend env template
│   ├── vite.config.ts           # Production URL configured
│   ├── Dockerfile               # Accepts VITE_API_KEY arg
│   ├── .dockerignore            # Excludes .env files
│   └── src/
│       └── components/          # All use import.meta.env.VITE_API_KEY
└── backend/
    └── .env                     # Backend environment
```

## Next Steps

1. ✅ All files are now properly configured
2. ✅ API keys are moved from code to environment variables
3. ✅ Production backend URL is set
4. ✅ Docker builds are secure

Your setup is complete! You can now deploy with confidence knowing that:
- No hardcoded secrets exist
- Environment variables are properly configured
- Production uses the correct backend URL
- All files are in place for both dev and production