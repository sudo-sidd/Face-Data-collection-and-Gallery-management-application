#!/bin/bash

# Launch script for the Gallery Manager (Main App)
# This script starts the staff-only gallery management application using PM2

echo "✨ Starting Gallery Manager Application... ✨"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 is not installed or not in PATH"
    exit 1
fi

# Check virtual environment
if [ ! -d "./venv" ]; then
    echo "❌ Error: Virtual environment not found at ./venv"
    echo "ℹ️ Please run ./setup-production.sh first to create the virtual environment"
    exit 1
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source ./venv/bin/activate

# Check activation
if [[ "$VIRTUAL_ENV" != *"venv" ]]; then
    echo "❌ Error: Failed to activate virtual environment"
    exit 1
fi

echo "✅ Virtual environment activated: $VIRTUAL_ENV"

# Ensure dependencies are installed
if ! python3 -m pip show gunicorn &> /dev/null; then
    echo "🔄 Installing gunicorn and uvicorn..."
    python3 -m pip install -q gunicorn uvicorn[standard]
fi

# Ensure PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "🔄 PM2 not found. Installing PM2..."
    if ! command -v npm &> /dev/null; then
        echo "❌ Error: npm is not installed. Please install Node.js and npm first."
        exit 1
    fi
    npm install -g pm2
fi

# Create logs directory
mkdir -p ./logs

# Create PM2 config
cat > ecosystem.config.js << EOL
module.exports = {
    apps: [{
        name: "gallery-manager",
        script: "python3",
        args: "src/main.py",
        instances: 1,
        autorestart: true,
        watch: false,
        max_memory_restart: "1G",
        env: {
            NODE_ENV: "production",
            PYTHONPATH: "\${PWD}"
        },
        out_file: "./logs/out.log",
        error_file: "./logs/error.log",
        log_date_format: "YYYY-MM-DD HH:mm:ss",
        merge_logs: true
    }]
}
EOL

# Remove previous instance if running
pm2 delete gallery-manager 2>/dev/null || true

# Start application
echo "🚀 Launching Gallery Manager..."
pm2 start ecosystem.config.js

echo "✅ Gallery Manager is running in the background"
echo "ℹ️ Use 'pm2 status' to check status"
echo "ℹ️ Use 'pm2 logs gallery-manager' to view logs"
