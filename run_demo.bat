@echo off
title SHIELD-LLM Launcher
echo ======================================================================
echo                  SHIELD-LLM LIVE DEMONSTRATION LAUNCHER
echo ======================================================================
echo.
echo [1/2] Launching FastAPI Backend on http://localhost:8000 ...
start "SHIELD-LLM Backend (FastAPI)" cmd /k "cd /d "%~dp0" && ml\venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] Waiting for backend to initialize before starting UI...
timeout /t 6 /nobreak >nul

echo Launching React Frontend on http://localhost:5173 ...
start "SHIELD-LLM Frontend (Vite)" cmd /k "cd /d "%~dp0" && npm run dev"

echo.
echo ======================================================================
echo SHIELD-LLM is now running!
echo   * Security Console and Dashboard: http://localhost:5173
echo   * FastAPI OpenAPI Documentation: http://localhost:8000/docs
echo ======================================================================
pause
