@echo off
echo ========================================
echo  Restarting OrganAIzer Services
echo ========================================
echo.

REM Stop all services first
echo Stopping existing services...
call stop_services.bat

REM Wait a moment to ensure all processes are terminated
timeout /t 2 /nobreak >nul
echo.

REM Start all services
echo Starting services...
call start_services.bat
