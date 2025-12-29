# Organizer Service - Docker Deployment (Existing Nginx)

## 🚀 Quick Start

```bash
# 1. Setup environment
./setup-deployment.sh

# 2. Configure your API keys in .env
nano .env

# 3. Deploy
./deploy.sh
```

## 📁 Project Structure

```
OrganAIzer_Service/
├── backend/
│   ├── Dockerfile              # Backend container definition
│   ├── main.py                 # FastAPI application with CORS
│   ├── requirements.txt        # Python dependencies
│   └── .dockerignore          # Docker ignore patterns
├── frontend/
│   ├── Dockerfile              # Frontend container definition
│   ├── package.json            # Node dependencies
│   ├── vite.config.ts          # Build configuration
│   └── .dockerignore          # Docker ignore patterns
├── docker-compose.yml          # Backend & Frontend containers
├── deploy.sh                   # Deployment script
├── setup-deployment.sh         # Environment setup script
├── DEPLOYMENT-EXISTING-NGINX.md # Nginx configuration guide
└── .env                        # Environment variables (create this)
```

## 🏗️ Architecture

### Services
- **Backend**: FastAPI on port 5263 (internal:8000)
- **Frontend**: React/Vite on port 5264 (internal:80)

### Network Flow
```
Client → Your Existing Nginx (80/443) → Backend (5263) or Frontend (5264)
```

## 🔧 Configuration

### Required Environment Variables (.env)
```bash
GOOGLE_API_KEY=your_key
OPENROUTER_API_KEY=your_key
MODEL=google/gemini-2.5-flash
AZURE_CLIENT_ID=your_id
AZURE_TENANT_ID=your_id
AZURE_CLIENT_SECRET=your_secret
```

### CORS Domains Supported
- Production: `https://organaizer.com2u.selfhost.eu`, `https://organaizer_backend.com2u.selfhost.eu`
- Development: `localhost`, `192.168.0.95`, `100.107.41.75`

## 🚀 Deployment Commands

### Deploy
```bash
./deploy.sh
```

### Check Status
```bash
docker-compose ps
curl http://localhost:5263/health
```

### View Logs
```bash
docker-compose logs -f
```

### Stop
```bash
docker-compose down
```

### Update
```bash
./deploy.sh  # Rebuilds and restarts
```

## 🌐 URLs

### Direct Access
- Backend: http://localhost:5263
- Frontend: http://localhost:5264

### Via Your Existing Nginx
- Frontend: https://organaizer.com2u.selfhost.eu
- Backend API: https://organaizer_backend.com2u.selfhost.eu

## 📋 Checklist

Before deployment:
- [ ] Run `./setup-deployment.sh`
- [ ] Update `.env` with real API keys
- [ ] Configure your nginx to proxy to localhost:5263 and localhost:5264
- [ ] Ensure DNS records point to your server

## 🆘 Troubleshooting

### Services won't start
```bash
docker-compose logs -f  # Check error messages
```

### CORS errors
```bash
# Check backend CORS configuration
docker-compose exec backend cat /app/main.py | grep -A 20 "CORS"
```

### Nginx issues
```bash
# Test nginx configuration
sudo nginx -t

# Check nginx logs
sudo tail -f /var/log/nginx/error.log
```

## 📚 More Info
See `DEPLOYMENT-EXISTING-NGINX.md` for detailed nginx configuration guide.