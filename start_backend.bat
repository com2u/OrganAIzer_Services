@echo off
echo ========================================
echo  Starting Backend Service Only
echo ========================================
echo.

cd backend
echo Starting FastAPI backend...
python main.py

echo.
echo Backend stopped.
pause
