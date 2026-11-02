#!/bin/bash
# Backend startup script

cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Copy .env if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example - please configure as needed"
fi

# Run the application
echo "Starting FastAPI server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
