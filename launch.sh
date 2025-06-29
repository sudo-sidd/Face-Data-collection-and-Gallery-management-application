#!/bin/bash

# Launch script for the Gallery Manager (Main App)
# This script starts the staff-only gallery management application

echo "Starting Gallery Manager Application..."

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the application directory
cd "$SCRIPT_DIR"

# Check if Python environment is set up
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed or not in PATH"
    exit 1
fi

# Install requirements if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Start the main application
echo "Launching Gallery Manager on http://localhost:5564"
python3 src/main.py

echo "Gallery Manager Application stopped."
