# Organizer Service Deployment Guide

This guide will help you deploy the Organizer Service using Docker Compose with Nginx reverse proxy and proper CORS configuration.

## Prerequisites

- Docker and Docker Compose installed on your server
- Access to the server where you want to deploy
- API keys for the services you plan to use (Google, Azure, etc.)

## Quick Start

### 1. Setup Environment

```bash
# Make setup script executable
chmod +x setup-deployment.sh

# Run setup
./setup-deployment.sh
```

This will:
- Install Docker and Docker Compose (if not already installed)
- Create necessary directory structure
- Generate self-signed SSL certificates for testing
- Create .env template file

### 2. Configure Environment Variables

Edit the `.env` file with your actual API keys:

```bash
nano .env
```

**Required variables:**
```bash
GOOGLE_API_KEY=your_google_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
MODEL=google/gemini-2.5-flash
AZURE_CLIENT_ID=your_azure_client_id
AZURE_TENANT_ID=your_azure_tenant_id
AZURE_CLIENT_SECRET=your_azure_client_secret
```

### 3. Deploy Services

```bash
# Make deploy script executable
chmod +x deploy.sh

# Deploy
./deploy.sh
```

## Architecture

### Services Overview

1. **Backend (FastAPI)** - Port 5263
   - REST API for all organizer services
   - Health check at `/health`
   - CORS configured for production and testing domains

2. **Frontend (React/Vite)** - Port 5264
   - React single-page application
   - Served via Nginx in production

3. **Nginx Reverse Proxy** - Ports 80/443
   - Handles SSL termination
   - Routes traffic to backend and frontend
   - Manages CORS headers
   - Supports multiple domains

### Network Architecture

```
┌─────────────────┐
│   Client        │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Nginx Reverse Proxy    │
│  Ports: 80, 443         │
│                         │
│  - organaizer.com2u...  │
│  - organaizer_backend   │
│  - Direct IP access     │
└────────┬────────────────┘
         │
    ┌────┴─────┬──────────┐
    ▼          ▼          ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Backend │ │ Frontend│ │ Testing │
│ :5263   │ │ :5264   │ │ :80/443 │
└─────────┘ └─────────┘ └─────────┘
```

## CORS Configuration

The system supports CORS for the following domains:

### Production Domains
- `https://organaizer.com2u.selfhost.eu` (Frontend)
- `https://organaizer_backend.com2u.selfhost.eu` (Backend)

### Development/Testing Domains
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000` (Alternative dev port)
- `http://192.168.0.95:5173` (Local network)
- `http://192.168.0.95:3000` (Local network)
- `http://100.107.41.75:5173` (Alternative network)
- `http://100.107.41.75:3000` (Alternative network)

## Domain Setup

### DNS Configuration

For production use, you need to configure DNS records:

1. **Frontend Domain:**
   ```
   organaizer.com2u.selfhost.eu → YOUR_SERVER_IP
   ```

2. **Backend Domain:**
   ```
   organaizer_backend.com2u.selfhost.eu → YOUR_SERVER_IP
   ```

### SSL Certificates

#### For Testing (Self-signed)
The deployment script automatically generates self-signed certificates. You'll get browser warnings, but it's fine for testing.

#### For Production (Let's Encrypt)
```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificates
sudo certbot --nginx -d organaizer.com2u.selfhost.eu
sudo certbot --nginx -d organaizer_backend.com2u.selfhost.eu

# Update nginx configuration to use real certificates
# Remove the self-signed certificate generation from docker-compose.yml
```

## API Endpoints

### Backend API
```
GET  /health                          - Health check
POST /api/youtube/download            - Download YouTube videos
POST /api/tts                         - Text to Speech
POST /api/stt                         - Speech to Text
POST /api/video-text                  - Video to Text
POST /api/text-image                  - Text to Image
POST /api/llm                         - LLM Interaction
POST /api/google                      - Google Integration
POST /api/outlook                     - Outlook Integration
```

### Frontend
```
GET  /                               - Main application
GET  /youtube                        - YouTube downloader
GET  /tts                            - Text to Speech
GET  /stt                            - Speech to Text
GET  /video-text                     - Video to Text
GET  /text-image                     - Text to Image
GET  /llm-interaction                - LLM Interaction
GET  /google                         - Google Integration
GET  /outlook                        - Outlook Integration
```

## Management Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f nginx-proxy
```

### Service Management
```bash
# Stop services
docker-compose down

# Restart services
docker-compose restart

# Restart specific service
docker-compose restart backend

# View service status
docker-compose ps

# Build without cache
docker-compose build --no-cache
```

### Update Services
```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Troubleshooting

### Common Issues

1. **CORS Errors**
   - Check that all domains are listed in the CORS configuration
   - Verify nginx configuration is loaded correctly
   - Check browser console for specific error messages

2. **SSL Certificate Warnings**
   - For production, use real SSL certificates
   - For testing, accept the self-signed certificate in your browser

3. **Service Not Starting**
   - Check logs: `docker-compose logs <service>`
   - Verify .env file has all required variables
   - Ensure ports 80, 443, 5263, 5264 are available

4. **API Keys Not Working**
   - Verify .env file is correctly formatted
   - Check that keys have necessary permissions
   - Restart services after updating .env: `docker-compose restart`

5. **File Upload/Download Issues**
   - Check disk space: `df -h`
   - Verify permissions on mounted volumes
   - Check nginx timeout settings

### Health Checks

```bash
# Backend health
curl http://localhost:5263/health

# Frontend accessibility
curl http://localhost:5264

# Nginx proxy
curl http://localhost/health

# CORS headers
curl -I http://localhost:5263/health
```

## Security Considerations

### Production Checklist
- [ ] Use real SSL certificates (not self-signed)
- [ ] Update CORS to only allow specific domains
- [ ] Set strong API keys
- [ ] Enable firewall (UFW/iptables)
- [ ] Regular security updates
- [ ] Monitor logs for suspicious activity
- [ ] Use environment variables for secrets
- [ ] Regular backups of .env and data volumes

### Firewall Configuration
```bash
# Allow only necessary ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp  # SSH
sudo ufw enable
```

## Performance Optimization

### Nginx Optimization
- Gzip compression is enabled
- Static file caching
- Connection keep-alive

### Docker Optimization
- Multi-stage builds for smaller images
- Layer caching
- Health checks for auto-recovery

## Monitoring

### Container Health
```bash
# Check container status
docker-compose ps

# View resource usage
docker stats
```

### Application Logs
```bash
# Real-time monitoring
docker-compose logs -f --tail=100

# Check for errors
docker-compose logs | grep -i error
```

## Backup and Recovery

### Backup Important Data
```bash
# Backup .env file
cp .env .env.backup

# Backup nginx configuration
tar -czf nginx-backup.tar.gz nginx/

# Backup any persistent data
docker-compose down
tar -czf data-backup.tar.gz backend-data/ frontend-data/
docker-compose up -d
```

### Recovery
```bash
# Restore from backup
tar -xzf data-backup.tar.gz
cp .env.backup .env
docker-compose up -d
```

## Support

For issues or questions:
1. Check the logs first: `docker-compose logs -f`
2. Verify environment variables are set correctly
3. Ensure all required ports are available
4. Check the health endpoints

## Production Deployment Checklist

- [ ] All API keys configured in .env
- [ ] DNS records pointing to server
- [ ] SSL certificates obtained and configured
- [ ] Firewall configured and enabled
- [ ] CORS updated for production domains only
- [ ] Services tested and running
- [ ] Monitoring and logging set up
- [ ] Backup strategy in place
- [ ] Security hardening completed
- [ ] Documentation updated for production URLs