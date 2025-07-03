#!/bin/bash

# Launch script for the Student Data Collection App

echo "📦 Starting Student Data Collection Application..."

# Get directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if virtualenv exists
if [ ! -d "../venv" ]; then
    echo "❌ Error: Virtual environment not found at ../venv"
    echo "ℹ️ Please run setup-production.sh first"
    exit 1
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source ../venv/bin/activate

# Verify activation
if [[ "$VIRTUAL_ENV" != *"venv" ]]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
fi
echo "✅ Virtual environment activated"

# Ensure data dir exists
mkdir -p "../data/student_data"

# Load .env variables
if [ -f "../../.env" ]; then
    echo "🔧 Loading environment from .env"
    source "../../.env"
fi

# Default values
HOST=${DATA_COLLECTION_HOST:-0.0.0.0}
PORT=${DATA_COLLECTION_PORT:-5001}
WORKERS=${DATA_COLLECTION_WORKERS:-1}

# Locate PM2
if [ -n "$PM2_EXECUTABLE" ]; then
    PM2_CMD="$PM2_EXECUTABLE"
else
    PM2_LOCATIONS=("pm2" "/usr/local/bin/pm2" "/usr/bin/pm2" "$HOME/.npm-global/bin/pm2")
    for path in "${PM2_LOCATIONS[@]}"; do
        if command -v "$path" &> /dev/null; then
            PM2_CMD="$path"
            break
        fi
    done
fi

if [ -z "$PM2_CMD" ]; then
    echo "❌ PM2 not found. Please install it with: npm install -g pm2"
    exit 1
fi

# Stop previous instance
$PM2_CMD delete "data-collection-app" 2>/dev/null || true
sleep 2

# Check if port is free
MAX_RETRIES=10
RETRY_COUNT=0
while nc -z $HOST $PORT 2>/dev/null && [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "⏳ Port $PORT still in use... attempt $((RETRY_COUNT+1))/$MAX_RETRIES"
    sleep 1
    ((RETRY_COUNT++))
done

if nc -z $HOST $PORT 2>/dev/null; then
    echo "❌ Port $PORT is still in use after retries"
    exit 1
fi

# Display info
python - <<EOF
from rich.console import Console
from rich.panel import Panel
import os

console = Console()
host = os.getenv("DATA_COLLECTION_HOST", "0.0.0.0")
port = os.getenv("DATA_COLLECTION_PORT", "5001")
workers = os.getenv("DATA_COLLECTION_WORKERS", "1")
console.print(Panel("Student Data Collection App", style="green"))
console.print(f"Server URL: http://{host}:{port}", style="cyan")
console.print(f"Workers: {workers}", style="cyan")
EOF

# Start app
DATA_COLLECTION_HOST=$HOST DATA_COLLECTION_PORT=$PORT \
$PM2_CMD start server/app.py --name "data-collection-app" --interpreter python3

# Confirm
sleep 2
if $PM2_CMD describe "data-collection-app" > /dev/null 2>&1; then
    echo "✅ Data Collection App started successfully"
else
    echo "❌ Failed to start Data Collection App"
    exit 1
fi
