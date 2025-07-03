#!/bin/bash

# Define colors for rich text output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}Setting up Face_data-application for production...${NC}"

# Ensure we're in the project root directory
cd "$(dirname "$0")"

# Create necessary directories if they don't exist
echo -e "${BLUE}Creating required directories...${NC}"
mkdir -p gallery/data
mkdir -p gallery/galleries
mkdir -p logs

# Creating python virtual environment
echo -e "${BLUE}Creating Python virtual environment...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 is not installed. Please install Python 3.x before running this script.${NC}"
    exit 1
fi

python3 -m venv venv
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create Python virtual environment. Please check your Python installation.${NC}"
    exit 1
fi
echo -e "${GREEN}Python virtual environment created successfully.${NC}"

# Activate the virtual environment
echo -e "${BLUE}Activating Python virtual environment...${NC}"
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to activate Python virtual environment. Please check your shell configuration.${NC}"
    exit 1
fi  
echo -e "${GREEN}Python virtual environment activated.${NC}"

# Install Python dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
python -m pip install --upgrade pip
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    # Install core dependencies based on imports in main.py
    echo -e "${YELLOW}No requirements.txt found, installing core dependencies...${NC}"
    pip install fastapi uvicorn python-multipart torch torchvision scipy pillow opencv-python ultralytics albumentations
fi

# Initialize database if it doesn't exist
echo -e "${BLUE}Checking database...${NC}"
if [ ! -f data/app.db ]; then
    echo -e "${YELLOW}Initializing database...${NC}"
    python src/database.py
else
    echo -e "${GREEN}Database already exists.${NC}"
fi

# Check if LightCNN model weights exist, if not download them
echo -e "${BLUE}Checking LightCNN checkpoints...${NC}"
if [ ! -f "src/checkpoints/LightCNN_29Layers_V2_checkpoint.pth.tar" ]; then
    echo -e "${YELLOW}LightCNN model weights not found. Attempting to download...${NC}"
    mkdir -p src/checkpoints
    pip install gdown
    gdown --id 1CUdlD83CYpiC-KedxLM9b8nG0ZAltsP4 --output src/checkpoints/LightCNN_29Layers_V2_checkpoint.pth.tar
    
    # Verify download was successful
    if [ ! -f "src/checkpoints/LightCNN_29Layers_V2_checkpoint.pth.tar" ]; then
        echo -e "${RED}WARNING: Failed to download LightCNN model weights!${NC}"
        echo -e "${YELLOW}Please manually download from: https://drive.google.com/file/d/1CUdlD83CYpiC-KedxLM9b8nG0ZAltsP4/view?usp=sharing${NC}"
        echo -e "${YELLOW}and place them in src/checkpoints/${NC}"
    else
        echo -e "${GREEN}LightCNN model weights downloaded successfully.${NC}"
    fi
else
    echo -e "${GREEN}LightCNN model weights already exist.${NC}"
fi

# Check if YOLO face detection model exists
if [ ! -f "src/yolo/weights/yolo11n-face.pt" ]; then
    echo -e "${RED}WARNING: YOLO model weights not found!${NC}"
    echo -e "${YELLOW}Please download YOLO face detection model weights and place them in src/yolo/weights/${NC}"
fi

# Set proper permissions
chmod +x src/*.py


# Install pm2 if not found
echo -e "${BLUE}Checking for PM2...${NC}"
if ! command -v pm2 &> /dev/null; then
    echo -e "${YELLOW}PM2 not found. Installing PM2...${NC}"
    # Check if npm is available
    if command -v npm &> /dev/null; then
        npm install -g pm2
        if command -v pm2 &> /dev/null; then
            echo -e "${GREEN}PM2 installed successfully.${NC}"
        else
            echo -e "${RED}Failed to install PM2. Please install it manually: npm install -g pm2${NC}"
        fi
    else
        echo -e "${RED}npm not found. Please install Node.js and npm first, then install PM2 with: npm install -g pm2${NC}"
    fi
else
    echo -e "${GREEN}PM2 is already installed.${NC}"
fi

# Create or update environment variables
echo -e "${BLUE}Setting up environment variables...${NC}"
ENV_FILE=".env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Creating new .env file with default values...${NC}"
    cat > "$ENV_FILE" << EOF
# Gallery Manager Configuration
GALLERY_MANAGER_HOST=0.0.0.0
GALLERY_MANAGER_PORT=8000
GALLERY_WORKERS=2  # Adjust based on your server's CPU cores

# Data Collection Configuration
DATA_COLLECTION_HOST=0.0.0.0
DATA_COLLECTION_PORT=8001
DATA_COLLECTION_WORKERS=5  # Adjust based on your server's CPU cores
EOF
    echo -e "${GREEN}Environment file created.${NC}"
else
    echo -e "${GREEN}Environment file already exists.${NC}"
    
    # Check and add missing variables if needed
    if ! grep -q "GALLERY_MANAGER_HOST" "$ENV_FILE"; then
        echo "GALLERY_MANAGER_HOST=0.0.0.0" >> "$ENV_FILE"
    fi
    if ! grep -q "GALLERY_MANAGER_PORT" "$ENV_FILE"; then
        echo "GALLERY_MANAGER_PORT=8000" >> "$ENV_FILE"
    fi
    if ! grep -q "DATA_COLLECTION_HOST" "$ENV_FILE"; then
        echo "DATA_COLLECTION_HOST=0.0.0.0" >> "$ENV_FILE"
    fi
    if ! grep -q "DATA_COLLECTION_PORT" "$ENV_FILE"; then
        echo "DATA_COLLECTION_PORT=8001" >> "$ENV_FILE"
    fi
fi

echo -e "${GREEN}Environment variables configured.${NC}"

chmod +x launch.sh
chmod +x data_collection/launch.sh

echo -e "${BOLD}${GREEN}Setup complete! 🎉${NC}"