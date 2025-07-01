#!/bin/bash

# Launch script for the Student Data Collection App
# This script starts the student-facing data collection application
echo "Starting Student Data Collection Application..."

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the application directory
cd "$SCRIPT_DIR"

# Create student data directory if it doesn't exist
mkdir -p "../data/student_data"

# Load environment variables from .env file in base directory
if [ -f "../../.env" ]; then
    echo "Loading configuration from base directory .env file"
    source "../../.env"
    HOST=${DATA_COLLECTION_HOST:-0.0.0.0}
    PORT=${DATA_COLLECTION_PORT:-5001}
    WORKERS=${DATA_COLLECTION_WORKERS:-1}
else
    echo "Warning: base directory .env file not found"
    HOST="0.0.0.0"
    PORT="5001"
    WORKERS="1"
fi

# Stop existing instance if running to avoid port conflicts
pm2 delete "data-collection-app" 2>/dev/null || true

# Wait a moment for the process to fully stop
sleep 2

# Check if port is already in use and wait for it to be free
MAX_RETRIES=10
RETRY_COUNT=0
while nc -z $HOST $PORT 2>/dev/null && [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "Port $PORT is still in use, waiting... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if nc -z $HOST $PORT 2>/dev/null; then
    echo "Error: Port $PORT is still in use after waiting. Please check for running processes."
    exit 1
fi

# Display with rich formatting
python3 -c '
from rich.console import Console
from rich.panel import Panel
import os
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()

# Get environment variables
host = os.environ.get("DATA_COLLECTION_HOST", "0.0.0.0")
port = int(os.environ.get("DATA_COLLECTION_PORT", 8000))
workers = int(os.environ.get("DATA_COLLECTION_WORKERS", 1))

console = Console()

# Create a panel for the app title
console.print(Panel("Student Data Collection App", style="green"))

# Display the connection information
console.print(f"Server URL: http://{host}:{port}", style="cyan")
console.print(f"Local URL: http://{os.popen("hostname").read().strip()}:{port}", style="cyan")
console.print(f"Workers: {workers}", style="cyan")
'

pm2 delete "data-collection-app" 2>/dev/null || true

# Start with environment variables for host and port
DATA_COLLECTION_HOST=$HOST DATA_COLLECTION_PORT=$PORT pm2 start server/app.py --name "data-collection-app" --interpreter python3

# Verify the process started successfully
sleep 2
if pm2 describe "data-collection-app" > /dev/null 2>&1; then
    echo "Data collection app started successfully"
else
    echo "Error: Failed to start data collection app"
    exit 1
fi