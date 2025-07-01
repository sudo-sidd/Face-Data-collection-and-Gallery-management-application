#!/bin/bash

# Launch script for the Gallery Manager (Main App)
# This script starts the staff-only gallery management application
#!/bin/bash

# Launch script for the Gallery Manager (Main App)
# This script starts the staff-only gallery management application

echo "✨ Starting Gallery Manager Application... ✨"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the application directory
cd "$SCRIPT_DIR"

# Check if Python environment is set up
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 is not installed or not in PATH"
    exit 1
fi

# Check if uvicorn is installed
if ! python3 -m pip show uvicorn &> /dev/null; then
    echo "🔄 Installing uvicorn..."
    python3 -m pip install uvicorn
fi

# Production configuration
# Use environment variables for host and port configuration
HOST=${GALLERY_HOST:-127.0.0.1}  # Default to localhost for security
PORT=${GALLERY_PORT:-5564}       # Default port

# Determine optimal number of workers based on CPU count
WORKERS=${GALLERY_WORKERS:-$(( $(nproc) * 2 + 1 ))}

# Check if gunicorn is installed (recommended for production)
if ! python3 -m pip show gunicorn &> /dev/null; then
    echo "🔄 Installing gunicorn for production deployment..."
    python3 -m pip install -q gunicorn uvicorn[standard]
fi

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "🔄 PM2 not found. Installing PM2 for background process management..."
    # Check if npm is installed
    if ! command -v npm &> /dev/null; then
        echo "❌ Error: npm is not installed. Please install Node.js and npm first."
        exit 1
    fi
    npm install -g pm2
fi

# Create logs directory if it doesn't exist
mkdir -p ./logs

# Create PM2 ecosystem file
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

# Start the application in background with PM2
echo "🚀 Launching Gallery Manager in production mode on $HOST:$PORT using PM2"
echo "ℹ️ For production, ensure this is behind a secure reverse proxy"
pm2 start ecosystem.config.js

echo "✅ Gallery Manager Application is running in the background"
echo "ℹ️ Use 'pm2 status' to check application status"
echo "ℹ️ Use 'pm2 logs gallery-manager' to view logs"
echo "ℹ️ Use 'pm2 stop gallery-manager' to stop the application"
