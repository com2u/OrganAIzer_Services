@echo off
cd /d c:\Users\rxhec\OrganAIzer_Services\backend
c:\Users\rxhec\OrganAIzer_Services\venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000
