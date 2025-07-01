#!/bin/bash

# Launcher script for Face Collection App
# This script prioritizes HTTP for better browser compatibility

echo "=== Face Collection App Launcher ==="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to check if a port is in use
check_port() {
    local port=$1
    if command -v netstat >/dev/null 2>&1; then
        netstat -tuln | grep ":$port " >/dev/null 2>&1
    elif command -v ss >/dev/null 2>&1; then
        ss -tuln | grep ":$port " >/dev/null 2>&1
    else
        # Fallback: try to connect to the port
        timeout 1 bash -c "</dev/tcp/localhost/$port" >/dev/null 2>&1
    fi
}

# Check if app is already running
if check_port 5001; then
    echo "⚠️  Port 5001 is already in use."
    echo "The Face Collection App might already be running."
    echo ""
    echo "Try accessing:"
    echo "   HTTP:  http://localhost:5001"
    echo "   HTTPS: https://localhost:5001"
    echo ""
    echo "If you want to restart the app, stop the existing process first."
    exit 1
fi

echo "🚀 Starting Face Collection App..."
echo ""

# Start with HTTP for better compatibility
echo "📡 The app will be available at:"
echo "   Primary:   http://localhost:5001"
echo "   Secondary: https://localhost:5001 (if SSL is working)"
echo ""
echo "💡 Use the HTTP link for best browser compatibility"
echo ""

# Set environment variables for better Flask behavior
export FLASK_ENV=production
export FLASK_DEBUG=0

# Start the app
echo "Starting server..."
python3 app.py

echo ""
echo "👋 Face Collection App has stopped."
