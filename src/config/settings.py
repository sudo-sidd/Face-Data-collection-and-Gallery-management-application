import os
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()

# Get the current directory of the script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GALLERY_DIR = os.path.join(BASE_DIR, 'gallery')

# Environment variables
HOST = os.environ.get("GALLERY_MANAGER_HOST", "0.0.0.0")
PORT = int(os.environ.get("GALLERY_MANAGER_PORT", 8873))
WORKERS = int(os.environ.get("GALLERY_MANAGER_WORKERS", 1))

COLLECTION_APP_HOST = os.environ.get("DATA_COLLECTION_HOST", "localhost")
COLLECTION_APP_PORT = 8873 # int(os.environ.get("DATA_COLLECTION_PORT", 5001))

# Default paths using relative paths
DEFAULT_MODEL_PATH = os.path.join(BASE_DIR, "src", "checkpoints", "LightCNN_29Layers_V2_checkpoint.pth.tar")
DEFAULT_YOLO_PATH = os.path.join(BASE_DIR, "src", "yolo", "weights", "yolo11n-face.pt")
BASE_DATA_DIR = os.path.join(BASE_DIR, "gallery", "data")
BASE_GALLERY_DIR = os.path.join(BASE_DIR, "gallery", "galleries")
STUDENT_DATA_DIR = os.path.join(BASE_DIR, "data", "student_data")

# Create necessary directories if they don't exist
os.makedirs(BASE_DATA_DIR, exist_ok=True)
os.makedirs(BASE_GALLERY_DIR, exist_ok=True)
os.makedirs(STUDENT_DATA_DIR, exist_ok=True)
