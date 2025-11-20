@echo off
echo ========================================
echo  Stopping OrganAIzer Services
echo ========================================
echo.

REM Stop backend (Python/FastAPI)
echo [1/2] Stopping Backend Service...
FOR /F "tokens=5" %%P IN ('netstat -ano ^| findstr :8000') DO (
    echo Killing process on port 8000 (PID: %%P)
    taskkill /F /PID %%P >nul 2>&1
)

REM Additional cleanup for Python processes
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" >nul 2>&1
echo Backend stopped.
echo.

REM Stop frontend (Node/Vite)
echo [2/2] Stopping Frontend Service...
FOR /F "tokens=5" %%P IN ('netstat -ano ^| findstr :5173') DO (
    echo Killing process on port 5173 (PID: %%P)
    taskkill /F /PID %%P >nul 2>&1
)

REM Additional cleanup for Node processes
taskkill /F /IM node.exe /FI "WINDOWTITLE eq *vite*" >nul 2>&1
echo Frontend stopped.
echo.

echo ========================================
echo  All Services Stopped
echo ========================================
pause
