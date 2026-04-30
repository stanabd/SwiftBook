@echo off
REM SwiftBook — Quick Start (Windows)
cd /d "%~dp0"

echo ===================================================
echo   SwiftBook — Monetized Travel Search Engine
echo ===================================================
echo.

if exist .env (
    echo   .env loaded
) else (
    echo   No .env found — running with mock data
    echo   Copy .env.example to .env and add your Travelpayouts credentials
    echo.
)

if not exist venv (
    echo   Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo   Installing dependencies...
pip install -r requirements.txt -q

echo.
echo   SwiftBook is running!
echo      Open:     http://localhost:8000
echo      API docs: http://localhost:8000/docs
echo      Press Ctrl+C to stop
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
