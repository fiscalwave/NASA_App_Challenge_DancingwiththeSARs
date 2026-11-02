@echo off
REM Backend startup script for Windows

cd /d "%~dp0"

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Create logs directory
if not exist logs mkdir logs

REM Copy .env if it doesn't exist
if not exist ".env" (
    copy .env.example .env
    echo Created .env from .env.example - please configure as needed
)

REM Run the application
echo Starting FastAPI server...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
