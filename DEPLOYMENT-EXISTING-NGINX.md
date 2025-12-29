# Organizer Service Deployment Guide (Existing Nginx)

This guide is for deploying the Organizer Service when you already have an nginx reverse proxy running.

## Prerequisites

- Docker and Docker Compose installed
- Existing nginx reverse proxy running
- Access to configure nginx for the required domains

## Quick Start

### 1. Setup Environment
```bash
chmod +x setup-deployment.sh
./setup-deployment.sh
```

### 2. Configure API Keys
```bash
nano .env
```

### 3. Deploy Services
```bash
chmod +x deploy.sh
./deploy.sh
```

## Architecture

### Services
- **Backend**: FastAPI on port 5263 (internal:8000)
- **Frontend**: React/Vite on port 5264 (internal:80)

### Network Flow
```
Client → Your Existing Nginx (80/443) → Backend (5263) or Frontend (5264)
```

## Nginx Configuration

You need to configure your existing nginx to proxy to these services:

### Backend Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name organaizer_backend.com2u.selfhost.eu;

    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5263;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers
        add_header 'Access-Control-Allow-Origin' 'https://organaizer.com2u.selfhost.eu http://localhost:5173 http://localhost:3000 http://192.168.0.95:5173 http://192.168.0.95:3000 http://100.107.41.75:5173 http://100.107.41.75:3000' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD' always;
        add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-Requested-With, Accept, Origin, X-Custom-Header' always;
        add_header 'Access-Control-Allow-Credentials' 'true' always;
        
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' 'https://organaizer.com2u.selfhost.eu http://localhost:5173 http://localhost:3000 http://192.168.0.95:5173 http://192.168.0.95:3000 http://100.107.41.75:5173 http://100.107.41.75:3000';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD';
            add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-Requested-With, Accept, Origin, X-Custom-Header';
            add_header 'Access-Control-Allow-Credentials' 'true';
            add_header 'Access-Control-Max-Age' 86400;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }

        # Timeouts for file processing
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:5263/health;
        access_log off;
    }
}
```

### Frontend Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name organaizer.com2u.selfhost.eu;

    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5264;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers for API calls
        add_header 'Access-Control-Allow-Origin' 'https://organaizer.com2u.selfhost.eu http://localhost:5173 http://localhost:3000 http://192.168.0.95:5173 http://192.168.0.95:3000 http://100.107.41.75:5173 http://100.107.41.75:3000' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD' always;
        add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-Requested-With, Accept, Origin, X-Custom-Header' always;
        add_header 'Access-Control-Allow-Credentials' 'true' always;
        
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' 'https://organaizer.com2u.selfhost.eu http://localhost:5173 http://localhost:3000 http://192.168.0.95:5173 http://192.168.0.95:3000 http://100.107.41.75:5173 http://100.107.41.75:3000';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD';
            add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-Requested-With, Accept, Origin, X-Custom-Header';
            add_header 'Access-Control-Allow-Credentials' 'true';
            add_header 'Access-Control-Max-Age' 86400;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }

        # Timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
    }
}
```

## Environment Variables (.env)

```bash
# Required
GOOGLE_API_KEY=your_google_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
MODEL=google/gemini-2.5-flash
AZURE_CLIENT_ID=your_azure_client_id
AZURE_TENANT_ID=your_azure_tenant_id
AZURE_CLIENT_SECRET=your_azure_client_secret
```

## CORS Configuration

The backend is configured to allow CORS from:
- `https://organaizer.com2u.selfhost.eu`
- `https://organaizer_backend.com2u.selfhost.eu`
- `http://localhost:5173`, `http://localhost:3000`
- `http://192.168.0.95:5173`, `http://192.168.0.95:3000`
- `http://100.107.41.75:5173`, `http://100.107.41.75:3000`

## Management Commands

### Deploy
```bash
./deploy.sh
```

### View Logs
```bash
docker-compose logs -f
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Update Services
```bash
git pull origin main
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Testing

```bash
# Test deployment
./test-deployment.sh

# Manual tests
curl http://localhost:5263/health
curl http://localhost:5264
```

## Troubleshooting

### Services not accessible
```bash
# Check if services are running
docker-compose ps

# Check logs
docker-compose logs -f
```

### CORS errors
```bash
# Verify nginx configuration
sudo nginx -t

# Check nginx logs
sudo tail -f /var/log/nginx/error.log
```

### API keys not working
```bash
# Verify .env file
cat .env

# Restart services after .env changes
docker-compose restart
```

## DNS Configuration

Ensure your DNS records point to your server:
- `organaizer.com2u.selfhost.eu` → YOUR_SERVER_IP
- `organaizer_backend.com2u.selfhost.eu` → YOUR_SERVER_IP

## SSL Certificates

Use your existing SSL certificates or obtain new ones:
```bash
# Using certbot (if needed)
sudo certbot --nginx -d organaizer.com2u.selfhost.eu
sudo certbot --nginx -d organaizer_backend.com2u.selfhost.eu