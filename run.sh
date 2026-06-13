#!/bin/bash
# Startup script for Personal AI Commerce Assistant FastAPI Backend

# Check if venv directory exists, if not create it
if [ ! -d "venv" ]; then
    echo "📦 Creating python virtual environment (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment. Attempting install with --break-system-packages..."
        pip install -r requirements.txt --break-system-packages
        uvicorn main:app --host 0.0.0.0 --port 8000 --reload
        exit 0
    fi
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

echo "🚀 Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✨ Starting FastAPI Backend Server on port 8000..."
echo "Press Ctrl+C to stop the server."

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
