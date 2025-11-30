# OrganAIzer Services - Quick Start Guide

## Running Services

### Option 1: Run Both Services Together (Recommended)
```bash
start_services.bat
```
This will start both backend and frontend in separate terminal windows.

---

## Manual Service Startup

### Backend Only

**Navigate to backend and run:**
```bash
cd backend
python main.py
```

**Or run from root directory:**
```bash
cd backend && python main.py
```

**Backend will be available at:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

---

### Frontend Only

**Navigate to frontend and run:**
```bash
cd frontend
npm run dev
```

**Or run from root directory:**
```bash
cd frontend && npm run dev
```

**Frontend will be available at:**
- App: http://localhost:5173

---

## Service Management

### Start Services
```bash
start_services.bat
```

### Stop Services
```bash
stop_services.bat
```

### Restart Services
```bash
restart_services.bat
```

---

## Prerequisites

### Backend Requirements
- Python 3.8+
- Install dependencies: `cd backend && pip install -r requirements.txt`
- Configure environment: Copy `.env.example` to `.env` and add your API keys

### Frontend Requirements
- Node.js 16+
- Install dependencies: `cd frontend && npm install`
- Configure environment: Copy `.env.example` to `.env`

---

## First Time Setup

### 1. Setup Backend
```bash
cd backend
pip install -r requirements.txt
copy .env.example .env
# Edit .env and add your API keys
cd ..
```

### 2. Setup Frontend
```bash
cd frontend
npm install
copy .env.example .env
# Edit .env if needed
cd ..
```

### 3. Run Services
```bash
start_services.bat
```

---

## Development Commands

### Backend
- **Run with auto-reload:** `cd backend && python main.py` (uvicorn reload enabled)
- **Run tests:** `cd backend && pytest`
- **Check logs:** Check the terminal output

### Frontend
- **Development server:** `cd frontend && npm run dev`
- **Build for production:** `cd frontend && npm run build`
- **Preview build:** `cd frontend && npm run preview`
- **Lint code:** `cd frontend && npm run lint`

---

## Troubleshooting

### Port Already in Use
- Backend (8000): Another process is using port 8000
- Frontend (5173): Another process is using port 5173
- Solution: Stop the other process or use `stop_services.bat`

### Backend Not Starting
- Check Python is installed: `python --version`
- Check dependencies: `cd backend && pip install -r requirements.txt`
- Check `.env` file exists and has required keys

### Frontend Not Starting
- Check Node is installed: `node --version`
- Check dependencies: `cd frontend && npm install`
- Clear cache: `cd frontend && npm clean-install`

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start both | `start_services.bat` |
| Stop both | `stop_services.bat` |
| Restart both | `restart_services.bat` |
| Backend only | `cd backend && python main.py` |
| Frontend only | `cd frontend && npm run dev` |
| Backend docs | http://localhost:8000/docs |
| Frontend app | http://localhost:5173 |
