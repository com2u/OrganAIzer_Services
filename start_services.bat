@echo off
echo ========================================
echo  Starting OrganAIzer Services
echo ========================================
echo.

REM Start backend (Python/FastAPI)
echo [1/2] Starting Backend Service...
cd backend
start "OrganAIzer Backend" cmd /k "python main.py"
echo Backend starting on http://localhost:8000
cd ..
echo.

REM Wait a moment for backend to initialize
timeout /t 2 /nobreak >nul

REM Start frontend (Node/Vite)
echo [2/2] Starting Frontend Service...
cd frontend
start "OrganAIzer Frontend" cmd /k "npm run dev"
echo Frontend starting on http://localhost:5173
cd ..
echo.

echo ========================================
echo  All Services Started
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo Docs:     http://localhost:8000/docs
echo.
echo Press any key to close this window...
pause >nul
