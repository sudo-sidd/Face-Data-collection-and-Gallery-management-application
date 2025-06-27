#!/bin/bash

# Launch script for the Student Data Collection App
# This script starts the student-facing data collection application

echo "Starting Student Data Collection Application..."

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the application directory
cd "$SCRIPT_DIR"

# Check if Python environment is set up
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed or not in PATH"
    exit 1
fi

# Install Flask and other requirements if needed
echo "Checking Python dependencies..."
pip3 install flask flask-cors opencv-python ultralytics pillow qrcode[pil] torch torchvision

# Create student data directory if it doesn't exist
mkdir -p "../data/student_data"

# Start the data collection application
echo "Launching Student Data Collection App on http://localhost:5001"
python3 server/app.py

echo "Student Data Collection Application stopped."
