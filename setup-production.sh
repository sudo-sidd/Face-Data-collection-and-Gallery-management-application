#!/bin/bash

echo "Setting up Face_data-application for production..."

# Ensure we're in the project root directory
cd "$(dirname "$0")"

# Create necessary directories if they don't exist
echo "Creating required directories..."
mkdir -p gallery/data
mkdir -p gallery/galleries
mkdir -p logs

# Install Python dependencies
echo "Installing Python dependencies..."
python -m pip install --upgrade pip
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    # Install core dependencies based on imports in main.py
    pip install fastapi uvicorn python-multipart torch torchvision scipy pillow opencv-python ultralytics albumentations
fi

# Install PM2 if not already installed
if ! command -v pm2 &> /dev/null; then
    echo "PM2 not found, installing..."
    npm install pm2@latest -g
else
    echo "PM2 already installed"
fi

# Initialize database if it doesn't exist
echo "Checking database..."
if [ ! -f data/app.db ]; then
    echo "Initializing database..."
    python src/database.py
fi

# Check if LightCNN model weights exist, if not warn the user
if [ ! -f "src/checkpoints/LightCNN_29Layers_V2_checkpoint.pth.tar" ]; then
    echo "WARNING: LightCNN model weights not found!"
    echo "Please download LightCNN model weights and place them in src/checkpoints/"
fi

# Check if YOLO face detection model exists
if [ ! -f "src/yolo/weights/yolo11n-face.pt" ]; then
    echo "WARNING: YOLO model weights not found!"
    echo "Please download YOLO face detection model weights and place them in src/yolo/weights/"
fi

# Set proper permissions
chmod +x src/*.py

# Create a script to activate the environment and start the application
cat > start-app.sh << EOL
#!/bin/bash
source env/bin/activate
pm2 start ecosystem.config.js
EOL

chmod +x start-app.sh

echo "Setup complete! You can manage the application with the following commands:"
echo "To start: ./start-app.sh"
echo "To stop: pm2 stop face-data-application"
echo "To restart: pm2 restart face-data-application"
echo "To monitor: pm2 monit"
echo "To view logs: pm2 logs face-data-application"
echo "To view status: pm2 status"