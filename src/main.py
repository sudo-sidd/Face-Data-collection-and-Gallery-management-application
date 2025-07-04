import os
import cv2
import shutil
import uuid
import sqlite3
import numpy as np
import json
import time
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Tuple, Union, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import base64
from ultralytics import YOLO
import torch
from scipy.spatial.distance import cosine
from PIL import Image
from torchvision import transforms
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import random
import albumentations as A
import sys
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()

# Get host, port, and workers from environment variables or use defaults
host = os.environ.get("GALLERY_MANAGER_HOST", "0.0.0.0")
port = int(os.environ.get("GALLERY_MANAGER_PORT", 8000))
workers = int(os.environ.get("GALLERY_MANAGER_WORKERS", 1))

collection_app_host = os.environ.get("DATA_COLLECTION_HOST", "localhost")
collection_app_port = int(os.environ.get("DATA_COLLECTION_PORT", 5001))


# Get the current directory of the script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY_DIR = os.path.join(BASE_DIR, 'gallery')

# Add src directory to system path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from gallery_manager import create_gallery, update_gallery, load_model, extract_embedding, create_gallery_from_embeddings, update_gallery_from_embeddings
import database

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

app = FastAPI(title="Face Recognition Gallery Manager", 
              description="API for managing face recognition galleries for students by batch and department")

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class BatchInfo(BaseModel):
    year: str
    department: str

class GalleryInfo(BaseModel):
    gallery_path: str
    identities: List[str]
    count: int

class ProcessingResult(BaseModel):
    processed_videos: int
    processed_frames: int
    extracted_faces: int
    failed_videos: List[str]
    gallery_updated: bool
    gallery_path: str

class StudentInfo(BaseModel):
    sessionId: str
    regNo: str
    name: str
    year: str
    dept: str
    batch: str
    startTime: str
    videoUploaded: bool
    facesExtracted: bool
    facesOrganized: bool
    videoPath: str
    facesCount: int

class StudentDataSummary(BaseModel):
    total_students: int
    students_with_video: int
    students_without_video: int
    students_processed: int
    students_pending: int
    department: str
    year: str

def get_gallery_path(year: str, department: str) -> str:
    """Generate a standardized gallery path based on batch year and department"""
    filename = f"{department}_{year}.pth"
    return os.path.join(BASE_GALLERY_DIR, filename)

def get_data_path(year: str, department: str) -> str:
    """Generate a standardized data path for storing preprocessed faces"""
    return os.path.join(BASE_DATA_DIR, f"{department}_{year}")

def get_batch_years_and_departments():
    """Fetch batch years and departments from the main app.db"""
    # Path to the main app.db
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'app.db')
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT year FROM batch_years ORDER BY year')
        years = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT department_id, name FROM departments ORDER BY name')
        departments = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        return {"years": years, "departments": departments}
    finally:
        conn.close()


def extract_frames(video_path: str, output_dir: str, max_frames: int = 1000, interval: int = 1) -> List[str]:
    """
    Extract frames from a video at specified intervals
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save extracted frames
        max_frames: Maximum number of frames to extract
        interval: Extract a frame every 'interval' frames
    
    Returns:
        List of paths to extracted frames
    """
    import cv2  # Import here to avoid circular imports
    
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return []
    
    frame_paths = []
    frame_count = 0
    saved_count = 0
    
    while saved_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % interval == 0:
            # Save frame as image
            frame_path = os.path.join(output_dir, f"frame_{saved_count:03d}.jpg")
            cv2.imwrite(frame_path, frame)
            frame_paths.append(frame_path)
            saved_count += 1
            
        frame_count += 1
    
    cap.release()
    return frame_paths

def detect_and_crop_faces(image_path: str, output_dir: str, yolo_path: str = DEFAULT_YOLO_PATH) -> List[str]:
    """
    Detect, crop, and preprocess faces from an image using YOLO
    
    Args:
        image_path: Path to the input image
        output_dir: Directory to save preprocessed face images
        yolo_path: Path to YOLO model weights
        
    Returns:
        List of paths to preprocessed face images
    """
    import cv2
    
    print(f"Processing image: {image_path}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Load YOLO model
    model = YOLO(yolo_path)
    
    # Read image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image {image_path}")
        return []
    
    # Detect faces
    results = model(img)
    
    print(f"YOLO detected {sum(len(r.boxes) for r in results)} faces in {image_path}")
    
    face_paths = []
    for i, result in enumerate(results):
        for j, box in enumerate(result.boxes):
            # Get bounding box coordinates
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            # Add some padding around the face
            h, w = img.shape[:2]
            face_w = x2 - x1
            face_h = y2 - y1
            pad_x = int(face_w * 0.2)
            pad_y = int(face_h * 0.2)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w, x2 + pad_x)
            y2 = min(h, y2 + pad_y)
            
            print(f"Face {j} dimensions before padding: {x2-x1}x{y2-y1}")
            print(f"Face {j} dimensions after padding: {max(0, x1-pad_x)}-{min(w, x2+pad_x)}x{max(0, y1-pad_y)}-{min(h, y2+pad_y)}")
            
            # Skip if face coordinates are too small
            if (x2 - x1) < 32 or (y2 - y1) < 32:
                print(f"Skipping face {j} in {image_path} - too small ({x2-x1}x{y2-y1})")
                continue
                
            # Crop face
            face = img[y1:y2, x1:x2]
            
            # Skip empty faces or irregular shapes
            if face.size == 0 or face.shape[0] <= 0 or face.shape[1] <= 0:
                print(f"Skipping face {j} in {image_path} - invalid dimensions")
                continue
            
            # Save original cropped face for reference
            img_name = os.path.basename(image_path)
            original_face_path = os.path.join(output_dir, f"{os.path.splitext(img_name)[0]}_face_orig_{j}.jpg")
            # cv2.imwrite(original_face_path, face)
            
            # Preprocess face properly for LightCNN:
            
            # 1. Convert to grayscale
            if len(face.shape) == 3:  # Color image
                gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
            else:  # Already grayscale
                gray = face
                
            # 2. Resize to 128x128 (LightCNN input size)
            # Use INTER_LANCZOS4 for best quality when downsizing
            resized = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_LANCZOS4)
            
            # 3. Normalize pixel values to [0, 1] range
            normalized = resized.astype(np.float32) / 255.0
            
            # 4. Apply histogram equalization for better contrast
            equalized = cv2.equalizeHist(resized)
            
            # 5. Save preprocessed face
            face_path = os.path.join(output_dir, f"{os.path.splitext(img_name)[0]}_face_{j}.jpg")
            cv2.imwrite(face_path, equalized)
            face_paths.append(face_path)
    
    return face_paths

def create_face_augmentations():
    """Create a set of specific augmentations for face images"""
    augmentations = [
        # Brightness and Contrast Adjustment
        A.RandomBrightnessContrast(p=1.0, brightness_limit=(-0.2, 0.2), contrast_limit=(-0.2, 0.2)),
        
        # Gaussian Blur
        A.GaussianBlur(p=1.0, blur_limit=(3, 7)),
        
        # Combined: Downscale + Blur
        A.Compose([
            A.Resize(height=48, width=48),
            A.Resize(height=128, width=128),
            A.GaussianBlur(p=1.0, blur_limit=(2, 5))
        ]),
        A.Compose([
            A.Resize(height=32, width=32),
            A.Resize(height=128, width=128),
            A.GaussianBlur(p=1.0, blur_limit=(2, 5))
        ]),
    ]
    return augmentations

def augment_face_image(image, num_augmentations=3):
    """
    Generate augmented versions of a face image in-memory
    
    This function applies a specific augmentation strategy:
    1. Always applies both downscale-upscale augmentations (32x32 and 24x24)
    2. Applies one additional random augmentation from the remaining list
    
    Args:
        image: Original face image (numpy array)
        num_augmentations: Number of augmented versions to generate (default 3)
    
    Returns:
        List of augmented images (numpy arrays)
    """
    augmentations_list = create_face_augmentations()
    augmented_images = []
    
    # Define the two specific downscale-upscale augmentations that should always be applied
    mandatory_augmentations = [
        # 32x32 downscale-upscale (index 0)
        A.Compose([
            A.Resize(height=32, width=32),
            A.Resize(height=128, width=128)
        ]),
        # 24x24 downscale-upscale (index 1)
        A.Compose([
            A.Resize(height=24, width=24),
            A.Resize(height=128, width=128)
        ])
    ]
    
    # Apply the two mandatory downscale-upscale augmentations
    for aug in mandatory_augmentations:
        augmented = aug(image=image)
        augmented_images.append(augmented['image'])
    
    # Apply additional random augmentations from the remaining list
    # Exclude the first two augmentations (the downscale-upscale ones)
    remaining_augmentations = augmentations_list[2:]  # Skip the first two
    
    additional_augs_needed = max(0, num_augmentations - 2)  # We already applied 2
    for i in range(additional_augs_needed):
        # Select random augmentation from remaining list
        selected_aug = random.choice(remaining_augmentations)
        
        # Apply augmentation
        if isinstance(selected_aug, A.Compose):
            augmented = selected_aug(image=image)
        else:
            aug_pipeline = A.Compose([selected_aug])
            augmented = aug_pipeline(image=image)
        
        augmented_images.append(augmented['image'])
    
    return augmented_images


def get_gallery_info(gallery_path: str) -> Optional[GalleryInfo]:
    """
    Get information about a gallery file
    
    Args:
        gallery_path: Path to gallery file
    
    Returns:
        GalleryInfo or None if file doesn't exist
    """
    if not os.path.exists(gallery_path):
        return None
    
    # Load the gallery file
    try:
        import torch
        gallery_data = torch.load(gallery_path)
        
        # Handle both formats
        if isinstance(gallery_data, dict) and "identities" in gallery_data:
            identities = gallery_data["identities"]
        else:
            identities = list(gallery_data.keys())
            
        count = len(identities)
        
        return GalleryInfo(
            gallery_path=gallery_path,
            identities=identities,
            count=count
        )
    except Exception as e:
        print(f"Error loading gallery file: {e}")
        return None

def recognize_faces(
    frame: np.ndarray, 
    gallery_paths: Union[str, List[str]], 
    model_path: str = DEFAULT_MODEL_PATH,
    yolo_path: str = DEFAULT_YOLO_PATH,
    threshold: float = 0.45,
    model=None,
    device=None,
    yolo_model=None
) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """
    Recognize faces in a given frame using one or more galleries.
    Implements a no-duplicate rule where each identity appears only once.
    
    Args:
        frame: Input image (numpy array in BGR format from cv2)
        gallery_paths: Single gallery path or list of gallery paths
        model_path: Path to LightCNN model
        yolo_path: Path to YOLO face detection model
        threshold: Minimum similarity threshold (0-1)
        model: Pre-loaded model (optional)
        device: Pre-loaded device (optional)
        yolo_model: Pre-loaded YOLO model (optional)
        
    Returns:
        Tuple containing:
            - Annotated frame with bounding boxes and labels
            - List of recognized identities with details
    """
    if isinstance(gallery_paths, str):
        gallery_paths = [gallery_paths]
    
    # Load model and YOLO if not provided
    if model is None or device is None:
        model, device = load_model(model_path)
    
    if yolo_model is None:
        yolo_model = YOLO(yolo_path)
    
    # Load and combine all galleries
    combined_gallery = {}
    for gallery_path in gallery_paths:
        if os.path.exists(gallery_path):
            try:
                gallery_data = torch.load(gallery_path)
                # Handle different gallery formats
                if isinstance(gallery_data, dict):
                    if "identities" in gallery_data:
                        combined_gallery.update(gallery_data["identities"])
                    else:
                        combined_gallery.update(gallery_data)
            except Exception as e:
                print(f"Error loading gallery {gallery_path}: {e}")
    
    if not combined_gallery:
        return frame, []
    
    # Step 1: Detect faces using YOLO
    face_detections = []
    results = yolo_model(frame,conf=0.65)
    
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            # Add padding around face
            h, w = frame.shape[:2]
            face_w, face_h = x2 - x1, y2 - y1
            pad_x = int(face_w * 0.2)
            pad_y = int(face_h * 0.2)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w, x2 + pad_x)
            y2 = min(h, y2 + pad_y)
            
            if (x2 - x1) < 32 or (y2 - y1) < 32:
                print(f"  WOULD SKIP FACE  - too small (testing with 5000px threshold)")
                continue
        
            # Extract face image
            face = frame[y1:y2, x1:x2]
            
            # Skip if face is too small
            if face.size == 0 or face.shape[0] < 10 or face.shape[1] < 10:
                continue
                
            # Convert BGR to grayscale PIL image
            face_pil = Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2GRAY))
            
            # Transform for model input
            transform = transforms.Compose([
                transforms.Resize((128, 128)),
                transforms.ToTensor(),
            ])
            
            # Prepare for the model
            face_tensor = transform(face_pil).unsqueeze(0).to(device)
            
            # Extract embedding
            with torch.no_grad():
                _, embedding = model(face_tensor)
                face_embedding = embedding.cpu().squeeze().numpy()
            
            # Find all potential matches above threshold
            matches = []
            for identity, gallery_embedding in combined_gallery.items():
                similarity = 1 - cosine(face_embedding, gallery_embedding)
                if similarity >= threshold:
                    matches.append((identity, similarity))
            
            # Sort matches by similarity (highest first)
            matches.sort(key=lambda x: x[1], reverse=True)
            
            face_detections.append({
                "bbox": (x1, y1, x2, y2),
                "matches": matches,
                "embedding": face_embedding
            })
    
    # Step 2: Assign identities without duplicates - using greedy approach
    face_detections.sort(key=lambda x: x["matches"][0][1] if x["matches"] else 0, reverse=True)
    
    assigned_identities = set()
    detected_faces = []
    
    for face in face_detections:
        x1, y1, x2, y2 = face["bbox"]
        matches = face["matches"]
        
        # Find the best non-assigned match
        best_match = None
        best_score = 0.0
        
        for identity, score in matches:
            if identity not in assigned_identities:
                best_match = identity
                best_score = float(score)
                break
        
        # Store recognition result
        if best_match:
            detected_faces.append({
                "identity": best_match,
                "similarity": best_score,
                "bounding_box": [int(x1), int(y1), int(x2), int(y2)]
            })
            assigned_identities.add(best_match)
        else:
            # No match found - mark as unknown
            detected_faces.append({
                "identity": "Unknown",
                "similarity": 0.0,
                "bounding_box": [int(x1), int(y1), int(x2), int(y2)]
            })
    
    # Step 3: Draw annotations as the final step
    result_img = frame.copy()
    
    for face_info in detected_faces:
        identity = face_info["identity"]
        similarity = face_info["similarity"]
        x1, y1, x2, y2 = face_info["bounding_box"]
        
        # Choose color based on whether it's a known or unknown face
        color = (0, 255, 0) if identity != "Unknown" else (0, 0, 255)
        
        # Draw bounding box
        cv2.rectangle(result_img, (x1, y1), (x2, y2), color, 2)
        
        # Draw label
        label = f"{identity} ({similarity:.2f})" if identity != "Unknown" else "Unknown"
        
        # Create slightly darker shade for text background
        text_bg_color = (int(color[0] * 0.7), int(color[1] * 0.7), int(color[2] * 0.7))
        
        # Get text size for better positioning
        text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        text_w, text_h = text_size
        
        # Draw text background
        cv2.rectangle(result_img, 
                     (x1, y1 - text_h - 8), 
                     (x1 + text_w, y1), 
                     text_bg_color, -1)
        
        # Draw text
        cv2.putText(result_img, 
                   label, 
                   (x1, y1 - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, (255, 255, 255), 2)
    
    return result_img, detected_faces

@app.get("/", response_class=FileResponse)
async def serve_spa():
    return FileResponse("static/index.html")

@app.get("/about", response_class=FileResponse)
async def about():
    return FileResponse(os.path.join("static", "about.html"))

@app.get("/batches", summary="Get available batch years and departments")
async def get_batches():
    """Get available batch years and departments."""
    years = database.get_batch_years()
    departments = database.get_departments()
    print(f"DEBUG: Years: {years}")
    print(f"DEBUG: Departments: {departments}")
    return {
        "years": years,
        "departments": departments
    }

@app.get("/galleries", summary="Get all available galleries")
async def list_galleries():
    """List all available face recognition galleries"""
    
    if not os.path.exists(BASE_GALLERY_DIR):
        print(f"DEBUG: Gallery directory does not exist: {BASE_GALLERY_DIR}")
        return {"galleries": []}
    
    # Find all gallery files
    galleries = []
    all_files = os.listdir(BASE_GALLERY_DIR)
    print(f"DEBUG: All files in {BASE_GALLERY_DIR}: {all_files}")
    
    for file in all_files:
        if file.endswith(".pth"):
            galleries.append(file)
            print(f"DEBUG: Found gallery file: {file}")
    
    print(f"DEBUG: Returning galleries: {galleries}")
    return {"galleries": galleries}

@app.get("/galleries/{year}/{department}", response_model=Optional[GalleryInfo], 
         summary="Get information about a specific gallery")
async def get_gallery(year: str, department: str):
    gallery_path = get_gallery_path(year, department)
    gallery_info = get_gallery_info(gallery_path)
    
    if gallery_info is None:
        raise HTTPException(status_code=404, 
                           detail=f"No gallery found for {department} {year} batch")
    
    return gallery_info

@app.post("/process", response_model=ProcessingResult, 
          summary="Process videos to extract frames and detect faces")
async def process_videos(
    year: str = Form(...),
    department: str = Form(...),
    videos_dir: str = Form(...)
):
    """
    Process videos to extract faces and store them in the dataset
    
    Parameters:
    - year: Batch year (e.g., "1st", "2nd")
    - department: Department name (e.g., "CS", "IT")
    - videos_dir: Path to directory containing student videos
    """
    # Validation code remains the same
    if year not in database.get_batch_years():
        raise HTTPException(status_code=400, detail=f"Invalid batch year: {year}")
    if department not in database.get_department_ids():  # use department IDs instead of names
        raise HTTPException(status_code=400, detail=f"Invalid department: {department}")
    
    if not os.path.exists(videos_dir):
        raise HTTPException(status_code=400, detail=f"Directory not found: {videos_dir}")
    
    # Get data path
    data_path = get_data_path(year, department)
    os.makedirs(data_path, exist_ok=True)
    
    # Find video files
    video_files = []
    for file in os.listdir(videos_dir):
        if file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            video_path = os.path.join(videos_dir, file)
            student_name = os.path.splitext(file)[0]
            video_files.append((video_path, student_name))
    
    if not video_files:
        raise HTTPException(status_code=400, detail="No video files found in the specified directory")
    
    # Process each video - ONLY extract frames and faces
    processed_videos = 0
    processed_frames = 0
    extracted_faces = 0
    failed_videos = []
    
    for video_path, student_name in video_files:
        try:
            # Create student directory
            student_dir = os.path.join(data_path, student_name)
            os.makedirs(student_dir, exist_ok=True)
            
            # Extract frames
            frames = extract_frames(video_path, student_dir)
            if not frames:
                failed_videos.append(os.path.basename(video_path))
                continue
            
            processed_frames += len(frames)
            
            # Process each frame to extract faces
            student_faces = []
            for frame_path in frames:
                face_paths = detect_and_crop_faces(frame_path, student_dir, DEFAULT_YOLO_PATH)
                student_faces.extend(face_paths)
                # Delete the original frame to save space
                os.remove(frame_path)
            
            extracted_faces += len(student_faces)
            
            # Check if we got any faces
            if not student_faces:
                print(f"Warning: No faces detected for {student_name}")
                failed_videos.append(os.path.basename(video_path))
                continue
            
            processed_videos += 1
            
        except Exception as e:
            print(f"Error processing video {video_path}: {e}")
            failed_videos.append(os.path.basename(video_path))
    
    return {
        "processed_videos": processed_videos,
        "processed_frames": processed_frames,
        "extracted_faces": extracted_faces,
        "failed_videos": failed_videos,
        "gallery_updated": False,  # Always false since we're not updating galleries
        "gallery_path": ""  # Empty since no gallery is created
    }

@app.post("/galleries/create", 
          summary="Create or update a gallery from preprocessed face data")
async def create_gallery_endpoint(
    year: str = Form(...),
    department: str = Form(...),
    update_existing: bool = Form(False),
    augment_ratio: float = Form(1.0),
    augs_per_image: int = Form(2)
):
    """
    Create or update a gallery from preprocessed face data
    
    Parameters:
    - year: Batch year (e.g., '2026', "2027") pass out years
    - department: Department ID 
    - update_existing: Whether to update an existing gallery or create a new one
    - augment_ratio: Ratio of images to augment (0.0 to 1.0)
    - augs_per_image: Number of augmentations per selected image
    """
    # Validate batch year and department
    if year not in database.get_batch_years():
        raise HTTPException(status_code=400, detail=f"Invalid batch year: {year}")
    if department not in database.get_department_ids():
        raise HTTPException(status_code=400, detail=f"Invalid department: {department}")
    
    # Get paths
    data_path = get_data_path(year, department)
    gallery_path = get_gallery_path(year, department)
    
    # Check if data exists
    if not os.path.exists(data_path):
        raise HTTPException(status_code=404, detail=f"No processed data found for {department} {year}. Process videos first.")
    
    # Check if gallery exists when not updating
    if not update_existing and os.path.exists(gallery_path):
        raise HTTPException(status_code=400, detail=f"Gallery already exists for {department} {year}. Use update_existing=True to update.")
    
    try:
        if update_existing and os.path.exists(gallery_path):
            # Update existing gallery with augmentation
            update_gallery(DEFAULT_MODEL_PATH, gallery_path, data_path, gallery_path, 
                          augment_ratio=augment_ratio, augs_per_image=augs_per_image)
            message = f"Updated gallery for {department} {year} with augmentation"
        else:
            # Create new gallery with augmentation
            create_gallery(DEFAULT_MODEL_PATH, data_path, gallery_path,
                          augment_ratio=augment_ratio, augs_per_image=augs_per_image)
            message = f"Created gallery for {department} {year} with augmentation"
        
        # Get gallery info
        gallery_info = get_gallery_info(gallery_path)
        identity_count = gallery_info.count if gallery_info else 0
        
        # Register gallery in database
        database.register_gallery(year, department, gallery_path, identity_count)
        
        return {
            "message": message,
            "gallery_path": gallery_path,
            "identities_count": identity_count,
            "augmentation_applied": augment_ratio > 0 and augs_per_image > 0,
            "augment_ratio": augment_ratio,
            "augs_per_image": augs_per_image,
            "success": True
        }
    except Exception as e:
        print(f"Error creating/updating gallery with augmentation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create/update gallery: {str(e)}")

@app.post("/batches/year", status_code=201, summary="Add a new batch year")
async def add_batch_year(year_data: dict):
    year = year_data.get("year")
    if not year:
        raise HTTPException(status_code=400, detail="Year is required")
    
    success = database.add_batch_year(year)
    if not success:
        raise HTTPException(status_code=400, detail=f"Batch year '{year}' already exists")
    
    return {"message": f"Added batch year: {year}", "success": True}

@app.delete("/batches/year/{year}", status_code=200, summary="Delete a batch year")
async def delete_batch_year(year: str):
    # Check if any galleries are using this year in the database
    galleries = database.list_all_galleries()
    year_galleries = [g for g in galleries if g['year'] == year]
    
    if year_galleries:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete year '{year}' as it is used by {len(year_galleries)} galleries"
        )
    
    if year not in database.get_batch_years():
        raise HTTPException(status_code=404, detail=f"Batch year '{year}' not found")
    
    success = database.delete_batch_year(year)
    if not success:
        raise HTTPException(status_code=404, detail=f"Batch year '{year}' not found")
    
    return {"message": f"Deleted batch year: {year}", "success": True}

@app.post("/batches/department", status_code=201, summary="Add a new department")
async def add_department(dept_data: dict):
    print(f"DEBUG: Received department data: {dept_data}")
    department_id = dept_data.get("department_id")
    department_name = dept_data.get("department")
    
    print(f"DEBUG: Extracted department_id: {department_id}")
    print(f"DEBUG: Extracted department_name: {department_name}")
    
    if not department_id or not department_name:
        print(f"DEBUG: Validation failed - department_id: {department_id}, department_name: {department_name}")
        raise HTTPException(status_code=400, detail="Both department_id and department name are required")
    
    success = database.add_department(department_id, department_name)
    if not success:
        raise HTTPException(status_code=400, detail=f"Department ID '{department_id}' or name '{department_name}' already exists")
    
    return {"message": f"Added department: {department_name} (ID: {department_id})", "success": True}

@app.delete("/batches/department/{department_id}", status_code=200, summary="Delete a department")
async def delete_department(department_id: str):
    # Check if any galleries are using this department in the database
    galleries = database.list_all_galleries()
    dept_galleries = [g for g in galleries if g['department_id'] == department_id]
    
    if dept_galleries:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete department '{department_id}' as it is used by {len(dept_galleries)} galleries"
        )
    
    # Check if department exists
    dept_info = database.get_department_by_id(department_id)
    if not dept_info:
        raise HTTPException(status_code=404, detail=f"Department with ID '{department_id}' not found")
    
    success = database.delete_department(department_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Department with ID '{department_id}' not found")
    
    return {"message": f"Deleted department: {dept_info['name']} (ID: {department_id})", "success": True}

@app.get("/check-directories", summary="Check if directories exist and are accessible")
async def check_directories():
    """Debug endpoint to check if directories exist and are accessible"""
    data_dir_exists = os.path.exists(BASE_DATA_DIR)
    gallery_dir_exists = os.path.exists(BASE_GALLERY_DIR)
    
    data_dir_files = []
    gallery_dir_files = []
    
    try:
        if data_dir_exists:
            data_dir_files = os.listdir(BASE_DATA_DIR)
    except Exception as e:
        data_dir_files = [f"Error: {str(e)}"]
    
    try:
        if gallery_dir_exists:
            gallery_dir_files = os.listdir(BASE_GALLERY_DIR)
    except Exception as e:
        gallery_dir_files = [f"Error: {str(e)}"]
    
    return {
        "data_dir_exists": data_dir_exists,
        "gallery_dir_exists": gallery_dir_exists,
        "data_dir_path": BASE_DATA_DIR,
        "gallery_dir_path": BASE_GALLERY_DIR,
        "data_dir_files": data_dir_files,
        "gallery_dir_files": gallery_dir_files
    }

@app.get("/galleries/registered", summary="Get all registered galleries from database")
async def list_registered_galleries():
    """List all galleries registered in the database with their metadata"""
    galleries = database.list_all_galleries()
    return {
        "galleries": galleries,
        "count": len(galleries)
    }

@app.get("/database/stats", summary="Get database statistics")
async def get_database_stats():
    """Get comprehensive database statistics"""
    return database.get_database_stats()

@app.delete("/galleries/{year}/{department}", status_code=200, summary="Delete a gallery")
async def delete_gallery(year: str, department: str):
    """Delete a gallery file and remove it from the database"""
    # Validate batch year and department
    if year not in database.get_batch_years():
        raise HTTPException(status_code=400, detail=f"Invalid batch year: {year}")
    if department not in database.get_department_ids():  # use department IDs instead of names
        raise HTTPException(status_code=400, detail=f"Invalid department: {department}")
    
    # Get gallery path
    gallery_path = get_gallery_path(year, department)
    
    # Check if gallery exists
    if not os.path.exists(gallery_path):
        raise HTTPException(status_code=404, detail=f"No gallery found for {department} {year}")
    
    try:
        # Remove gallery file
        os.remove(gallery_path)
        
        # Remove from database
        database.remove_gallery(year, department)
        
        return {
            "message": f"Deleted gallery for {department} {year}",
            "success": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete gallery: {str(e)}")

@app.post("/galleries/{year}/{department}/sync", summary="Sync gallery file with database")
async def sync_gallery_with_database(year: str, department: str):
    """Sync an existing gallery file with the database"""
    # Validate batch year and department
    if year not in database.get_batch_years():
        raise HTTPException(status_code=400, detail=f"Invalid batch year: {year}")
    if department not in database.get_department_ids():  # use department IDs instead of names
        raise HTTPException(status_code=400, detail=f"Invalid department: {department}")
    
    # Get gallery path
    gallery_path = get_gallery_path(year, department)
    
    # Check if gallery exists
    if not os.path.exists(gallery_path):
        raise HTTPException(status_code=404, detail=f"No gallery found for {department} {year}")
    
    try:
        # Get gallery info
        gallery_info = get_gallery_info(gallery_path)
        if not gallery_info:
            raise HTTPException(status_code=500, detail="Failed to read gallery file")
        
        # Register/update in database
        success = database.register_gallery(year, department, gallery_path, gallery_info.count)
        
        if success:
            return {
                "message": f"Successfully synced gallery for {department} {year}",
                "identities_count": gallery_info.count,
                "success": True
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to register gallery in database")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync gallery: {str(e)}")

@app.post("/recognize", summary="Recognize faces in an uploaded image")
async def recognize_image(
    image: UploadFile = File(...),
    galleries: List[str] = Form(...),
    threshold: float = Form(0.45)
):
    """
    Recognize faces in an uploaded image using selected galleries
    
    Parameters:
    - image: Image file to analyze
    - galleries: List of gallery filenames
    - threshold: Similarity threshold (0-1)
    
    Returns:
    - Base64 encoded image with annotations
    - List of recognized faces
    """
    try:
        print(f"DEBUG: Starting recognition process")
        print(f"DEBUG: Received image: {image.filename}")
        print(f"DEBUG: Received galleries: {galleries}")
        print(f"DEBUG: Received threshold: {threshold}")
        
        # Read the image
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        print(f"DEBUG: Image loaded successfully, shape: {img.shape}")
        
        # Debug: Print gallery directory info
        print(f"DEBUG: Gallery directory: {BASE_GALLERY_DIR}")
        print(f"DEBUG: Gallery directory exists: {os.path.exists(BASE_GALLERY_DIR)}")
        
        # List all files in gallery directory for debugging
        if os.path.exists(BASE_GALLERY_DIR):
            all_gallery_files = os.listdir(BASE_GALLERY_DIR)
            print(f"DEBUG: All files in gallery directory: {all_gallery_files}")
        else:
            print(f"DEBUG: Gallery directory does not exist: {BASE_GALLERY_DIR}")
            raise HTTPException(status_code=500, detail=f"Gallery directory does not exist: {BASE_GALLERY_DIR}")
        
        # Process galleries - Fixed logic to handle actual gallery files
        gallery_paths = []
        for gallery_name in galleries:
            print(f"DEBUG: Processing gallery name: '{gallery_name}'")
            
            # Clean the gallery name
            clean_name = gallery_name.strip()
            
            # Try multiple naming patterns
            possible_paths = [
                os.path.join(BASE_GALLERY_DIR, clean_name),  # Direct name as received from frontend
                os.path.join(BASE_GALLERY_DIR, f"{clean_name}.pth") if not clean_name.endswith('.pth') else os.path.join(BASE_GALLERY_DIR, clean_name),  # Add .pth if missing
                os.path.join(BASE_GALLERY_DIR, f"gallery_{clean_name}"),  # With gallery_ prefix
            ]
            
            # Remove duplicates while preserving order
            seen = set()
            unique_paths = []
            for path in possible_paths:
                if path not in seen:
                    seen.add(path)
                    unique_paths.append(path)
            
            # Find the first existing file
            found_path = None
            for path in unique_paths:
                print(f"DEBUG: Checking path: {path}")
                if os.path.exists(path):
                    found_path = path
                    print(f"DEBUG: Found gallery at: {path}")
                    break
            
            if found_path:
                gallery_paths.append(found_path)
                print(f"DEBUG: Successfully added gallery path: {found_path}")
            else:
                print(f"DEBUG: Gallery '{gallery_name}' not found. Tried paths:")
                for path in unique_paths:
                    print(f"  - {path} (exists: {os.path.exists(path)})")
        
        print(f"DEBUG: Final gallery_paths list: {gallery_paths}")
        
        if not gallery_paths:
            # Provide detailed error information
            available_galleries = []
            if os.path.exists(BASE_GALLERY_DIR):
                available_galleries = [f for f in os.listdir(BASE_GALLERY_DIR) if f.endswith('.pth')]
            
            error_detail = {
                "error": "No valid galleries found",
                "requested_galleries": galleries,
                "available_galleries": available_galleries,
                "gallery_directory": BASE_GALLERY_DIR
            }
            print(f"DEBUG: Error details: {error_detail}")
            raise HTTPException(status_code=400, detail=f"No valid galleries found. Requested: {galleries}, Available: {available_galleries}")
        
        print(f"DEBUG: Starting face recognition with {len(gallery_paths)} galleries")
        
        # Perform recognition
        result_img, faces = recognize_faces(
            img, 
            gallery_paths=gallery_paths,
            model_path=DEFAULT_MODEL_PATH,
            yolo_path=DEFAULT_YOLO_PATH,
            threshold=threshold
        )
        
        print(f"DEBUG: Recognition completed, found {len(faces)} faces")
        
        # Convert result image to base64
        _, buffer = cv2.imencode('.jpg', result_img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # Make sure all numpy values are converted to standard Python types
        serializable_faces = []
        for face in faces:
            serializable_face = {
                "identity": face["identity"],
                "similarity": float(face["similarity"]),  # Convert numpy.float32 to Python float
                "bounding_box": [int(x) for x in face["bounding_box"]]  # Convert numpy values to Python ints
            }
            serializable_faces.append(serializable_face)
        
        print(f"DEBUG: Returning results with {len(serializable_faces)} faces")
        
        # Return results
        return {
            "image": img_base64,
            "faces": serializable_faces,
            "count": len(serializable_faces)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"DEBUG: Unexpected error in recognize_image: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def get_student_data_folders():
    """Get all department-year folders from student data directory"""
    folders = []
    if os.path.exists(STUDENT_DATA_DIR):
        for folder in os.listdir(STUDENT_DATA_DIR):
            folder_path = os.path.join(STUDENT_DATA_DIR, folder)
            if os.path.isdir(folder_path) and "_" in folder:
                dept, year = folder.split("_", 1)
                folders.append({"folder": folder, "dept": dept, "year": year})
    return folders

def get_students_in_folder(dept: str, year: str) -> List[StudentInfo]:
    """Get all students in a specific department-year folder"""
    students = []
    folder_path = os.path.join(STUDENT_DATA_DIR, f"{dept}_{year}")
    
    if os.path.exists(folder_path):
        for student_folder in os.listdir(folder_path):
            student_path = os.path.join(folder_path, student_folder)
            if os.path.isdir(student_path):
                # Look for student JSON file
                json_file = os.path.join(student_path, f"{student_folder}.json")
                if os.path.exists(json_file):
                    try:
                        with open(json_file, 'r') as f:
                            data = json.load(f)
                            students.append(StudentInfo(**data))
                    except Exception as e:
                        print(f"Error reading student data {json_file}: {e}")
    
    return students

def get_student_data_summary(dept: str, year: str) -> StudentDataSummary:
    """Get summary statistics for students in a department-year"""
    students = get_students_in_folder(dept, year)
    
    total = len(students)
    with_video = sum(1 for s in students if s.videoUploaded)
    without_video = total - with_video
    processed = sum(1 for s in students if s.facesExtracted)
    pending = with_video - processed
    
    return StudentDataSummary(
        total_students=total,
        students_with_video=with_video,
        students_without_video=without_video,
        students_processed=processed,
        students_pending=pending,
        department=dept,
        year=year
    )

import subprocess
import threading
import time
import signal
import psutil

# Global variable to track collection app process
collection_app_process_name = "data-collection-app"  # Name of the process in PM2

@app.post("/api/start-collection-app", summary="Start the face collection application")
async def start_collection_app():
    """Start the face collection application server using the launch script"""
    try:
        # Check if already running in PM2
        status_cmd = subprocess.run(
            ["pm2", "list"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        # Check if our app is in the list and online
        if collection_app_process_name in status_cmd.stdout and "online" in status_cmd.stdout:
            return {
                "success": True,
                "message": "Face Collection App is already running in PM2",
                "process_name": collection_app_process_name
            }
        
        # Path to the launch script
        launch_script = os.path.join(BASE_DIR, "data_collection", "launch.sh")
        
        # Execute the launch script
        start_cmd = subprocess.run(
            ["/bin/bash", launch_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if start_cmd.returncode == 0:
            return {
                "success": True,
                "message": "Face Collection App started successfully",
                "process_name": collection_app_process_name
            }
        else:
            return {
                "success": False,
                "message": f"Failed to start Face Collection App: {start_cmd.stderr}"
            }
                
    except Exception as e:
        return {
            "success": False,
            "message": f"Error starting Face Collection App: {str(e)}"
        }

@app.post("/api/stop-collection-app", summary="Stop the face collection application")
async def stop_collection_app():
    """Stop the face collection application server using PM2"""
    try:
        # Check if running in PM2
        status_cmd = subprocess.run(
            ["pm2", "list"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        # If process is not in the list, it's not running
        if collection_app_process_name not in status_cmd.stdout:
            return {
                "success": True,
                "message": "Face Collection App was not running"
            }
        
        # Stop the app with PM2
        stop_cmd = subprocess.run(
            ["pm2", "delete", collection_app_process_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if stop_cmd.returncode == 0:
            return {
                "success": True,
                "message": f"Face Collection App stopped successfully"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to stop Face Collection App: {stop_cmd.stderr}"
            }
                
    except Exception as e:
        return {
            "success": False,
            "message": f"Error stopping Face Collection App: {str(e)}"
        }

@app.get("/api/collection-app-status", summary="Check face collection app status")
async def get_collection_app_status():
    """Check if the face collection application is running using PM2"""
    try:
        # Get status from PM2
        status_cmd = subprocess.run(
            ["pm2", "list"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        # Check if our process is in the list and running
        is_running = collection_app_process_name in status_cmd.stdout and "online" in status_cmd.stdout
        
        if is_running:
            # Get more details if needed
            detail_cmd = subprocess.run(
                ["pm2", "describe", collection_app_process_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            return {
                "running": True,
                "process_name": collection_app_process_name,
                "details": detail_cmd.stdout
            }
        else:
            return {
                "running": False,
                "process_name": collection_app_process_name
            }
                
    except Exception as e:
        return {
            "running": False,
            "error": str(e)
        }

@app.get("/student-data/folders", 
         summary="Get available student data folders (dept_year)")
async def get_available_folders():
    """Get all available department-year folders from student data"""
    folders = get_student_data_folders()
    return {"folders": folders}

@app.get("/student-data/{dept}/{year}/summary", 
         response_model=StudentDataSummary,
         summary="Get summary of students in a department-year")
async def get_student_summary(dept: str, year: str):
    """Get summary statistics for students in a specific department and year"""
    return get_student_data_summary(dept, year)

@app.get("/student-data/{dept}/{year}/students", 
         summary="Get list of students in a department-year")
async def get_students_list(dept: str, year: str):
    """Get detailed list of all students in a specific department and year"""
    students = get_students_in_folder(dept, year)
    return {"students": [student.dict() for student in students]}

@app.get("/student-data/{dept}/{year}/pending", 
         summary="Get students pending processing")
async def get_pending_students(dept: str, year: str):
    """Get list of students who have uploaded videos but haven't been processed yet"""
    students = get_students_in_folder(dept, year)
    pending = [s for s in students if s.videoUploaded and not s.facesExtracted]
    return {"pending_students": [student.dict() for student in pending]}

def process_student_video(student: StudentInfo) -> Dict[str, Any]:
    """Process a single student's video to extract faces and organize them in gallery structure"""
    try:
        # Source paths (where video is stored)
        student_source_folder = os.path.join(STUDENT_DATA_DIR, f"{student.dept}_{student.year}", student.regNo)
        video_path = os.path.join(student_source_folder, f"{student.regNo}.mp4")
        
        if not os.path.exists(video_path):
            return {"success": False, "error": f"Video file not found: {video_path}"}
        
        # Destination paths (gallery data structure)
        gallery_data_dir = os.path.join(BASE_DATA_DIR, f"{student.dept}_{student.year}")
        student_gallery_folder = os.path.join(gallery_data_dir, student.regNo)
        
        # Create gallery data directory structure
        os.makedirs(student_gallery_folder, exist_ok=True)
        
        # Create temporary frames directory for processing
        temp_frames_dir = os.path.join(student_source_folder, "temp_frames")
        os.makedirs(temp_frames_dir, exist_ok=True)
        
        # Extract frames from video
        frame_paths = extract_frames(video_path, temp_frames_dir)
        
        # Process each frame to extract faces and save them in gallery structure
        all_face_paths = []
        for frame_path in frame_paths:
            face_paths = detect_and_crop_faces(frame_path, student_gallery_folder)
            all_face_paths.extend(face_paths)
        
        # Clean up temporary frames directory
        try:
            for frame_path in frame_paths:
                if os.path.exists(frame_path):
                    os.remove(frame_path)
            if os.path.exists(temp_frames_dir):
                os.rmdir(temp_frames_dir)
        except Exception as e:
            print(f"Warning: Could not clean up temporary frames: {e}")
        
        # Update student JSON file (only one JSON file per student)
        json_file = os.path.join(student_source_folder, f"{student.regNo}.json")
        if os.path.exists(json_file):
            with open(json_file, 'r') as f:
                student_data = json.load(f)
        else:
            student_data = student.dict()
        
        # Update processing status
        student_data["facesExtracted"] = True
        student_data["facesOrganized"] = True
        student_data["facesCount"] = len(all_face_paths)
        
        # Save updated JSON file
        with open(json_file, 'w') as f:
            json.dump(student_data, f, indent=2)
        
        return {
            "success": True, 
            "faces_extracted": len(all_face_paths),
            "frames_processed": len(frame_paths),
            "gallery_path": student_gallery_folder
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/student-data/{dept}/{year}/process", 
          summary="Process students' videos to extract faces")
async def process_students_videos(dept: str, year: str):
    """Process all pending students' videos in a department-year to extract faces"""
    try:
        # Get pending students
        students = get_students_in_folder(dept, year)
        pending_students = [s for s in students if s.videoUploaded and not s.facesExtracted]
        
        if not pending_students:
            return {
                "success": True,
                "message": "No pending students to process",
                "processed_count": 0
            }
        
        # Process each student
        results = []
        processed_count = 0
        
        for student in pending_students:
            result = process_student_video(student)
            results.append({
                "student": student.regNo,
                "name": student.name,
                "result": result
            })
            
            if result["success"]:
                processed_count += 1
        
        return {
            "success": True,
            "message": f"Processed {processed_count} out of {len(pending_students)} students",
            "processed_count": processed_count,
            "total_pending": len(pending_students),
            "details": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing students: {str(e)}")

@app.get("/api/collection-app-config", summary="Get face collection app configuration")
async def get_collection_app_config():
    return {
        "host": collection_app_host,
        "port": collection_app_port
    }

if __name__ == "__main__":
    import uvicorn
    
    print(f"Starting server on {host}:{port} with {workers} workers")
    uvicorn.run("main:app", host=host, port=port, workers=workers)