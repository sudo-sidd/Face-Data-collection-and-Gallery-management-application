import os
import cv2
import shutil
import uuid
import numpy as np
from enum import Enum
from typing import List, Optional, Dict, Tuple, Union, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
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

# Get the current directory of the script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY_DIR = os.path.join(BASE_DIR, 'gallery')

# Add gallery directory to system path
sys.path.append(GALLERY_DIR)
from gallery_manager import create_gallery, update_gallery, load_model, extract_embedding, create_gallery_from_embeddings, update_gallery_from_embeddings
import database

# Default paths using relative paths
DEFAULT_MODEL_PATH = os.path.join(BASE_DIR, "src", "checkpoints", "LightCNN_29Layers_V2_checkpoint.pth.tar")
DEFAULT_YOLO_PATH = os.path.join(BASE_DIR, "src", "yolo", "weights", "yolo11n-face.pt")
BASE_DATA_DIR = os.path.join(BASE_DIR, "gallery", "data")
BASE_GALLERY_DIR = os.path.join(BASE_DIR, "gallery", "galleries")

# Create necessary directories if they don't exist
os.makedirs(BASE_DATA_DIR, exist_ok=True)
os.makedirs(BASE_GALLERY_DIR, exist_ok=True)

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

def get_gallery_path(year: str, department: str) -> str:
    """Generate a standardized gallery path based on batch year and department"""
    filename = f"gallery_{department}_{year}.pth"
    return os.path.join(BASE_GALLERY_DIR, filename)

def get_data_path(year: str, department: str) -> str:
    """Generate a standardized data path for storing preprocessed faces"""
    return os.path.join(BASE_DATA_DIR, f"{department}_{year}")

def extract_frames(video_path: str, output_dir: str, max_frames: int = 30, interval: int = 10) -> List[str]:
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
        # Downscaling and Upscaling
        A.Compose([
            A.Resize(height=32, width=32),  # Downscale to low resolution
            A.Resize(height=128, width=128)  # Upscale back to original size
        ]),
        A.Compose([
            A.Resize(height=24, width=24),  # Downscale to low resolution
            A.Resize(height=128, width=128)  # Upscale back to original size
        ]),
        
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

def augment_face_image(image, num_augmentations=2):
    """
    Generate augmented versions of a face image in-memory
    
    Args:
        image: Original face image (numpy array)
        num_augmentations: Number of augmented versions to generate
    
    Returns:
        List of augmented images (numpy arrays)
    """
    augmentations_list = create_face_augmentations()
    augmented_images = []
    
    for i in range(num_augmentations):
        # Select random augmentation
        selected_aug = random.choice(augmentations_list)
        
        # Apply augmentation
        if isinstance(selected_aug, A.Compose):
            augmented = selected_aug(image=image)
        else:
            aug_pipeline = A.Compose([selected_aug])
            augmented = aug_pipeline(image=image)
        
        augmented_images.append(augmented['image'])
    
    return augmented_images

def process_videos_directory(videos_dir: str, year: str, department: str) -> ProcessingResult:
    """
    Process all videos in a directory, extract frames, detect faces,
    and update or create a gallery file
    
    Args:
        videos_dir: Path to directory containing videos
        year: Batch year
        department: Department name
    
    Returns:
        ProcessingResult containing statistics about the processing
    """
    # Setup paths
    data_path = get_data_path(year, department)
    gallery_path = get_gallery_path(year, department)
    os.makedirs(data_path, exist_ok=True)
    
    # Track statistics
    processed_videos = 0
    processed_frames = 0
    extracted_faces = 0
    failed_videos = []
    
    # Process videos
    model = load_model(DEFAULT_MODEL_PATH)  # Load face recognition model
    student_embeddings = {}
    
    # Check each file in the directory
    for filename in os.listdir(videos_dir):
        if not filename.lower().endswith(('.mp4', '.avi', '.mov')):
            continue
            
        # Get student name from filename (without extension)
        student_name = os.path.splitext(filename)[0]
        video_path = os.path.join(videos_dir, filename)
        
        # Create output directories
        frames_dir = os.path.join(data_path, student_name, "frames")
        faces_dir = os.path.join(data_path, student_name, "faces")
        os.makedirs(frames_dir, exist_ok=True)
        os.makedirs(faces_dir, exist_ok=True)
        
        try:
            # Extract frames from video
            frame_paths = extract_frames(video_path, frames_dir)
            processed_frames += len(frame_paths)
            
            # Process each frame
            student_faces = []
            for frame_path in frame_paths:
                # Detect and crop faces
                face_paths = detect_and_crop_faces(frame_path, faces_dir)
                extracted_faces += len(face_paths)
                student_faces.extend(face_paths)
            
            # Generate embeddings for the student's faces
            if student_faces:
                embeddings = [extract_embedding(face_path, model) for face_path in student_faces]
                # Average the embeddings to get a representative embedding for the student
                student_embeddings[student_name] = np.mean(embeddings, axis=0)
            
            processed_videos += 1
            
        except Exception as e:
            print(f"Error processing video {filename}: {e}")
            failed_videos.append(filename)
    
    # Update or create gallery
    gallery_updated = False
    if student_embeddings:
        if os.path.exists(gallery_path):
            # Update existing gallery
            update_gallery_from_embeddings(gallery_path, student_embeddings)
        else:
            # Create new gallery
            create_gallery_from_embeddings(gallery_path, student_embeddings)
        gallery_updated = True
    
    return ProcessingResult(
        processed_videos=processed_videos,
        processed_frames=processed_frames,
        extracted_faces=extracted_faces,
        failed_videos=failed_videos,
        gallery_updated=gallery_updated,
        gallery_path=gallery_path
    )

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
    threshold: float = 0.50,
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
    results = yolo_model(frame,conf=0.7)
    
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

@app.get("/batches", summary="Get available batch years and departments")
async def get_batches():
    """Get available batch years and departments."""
    return {
        "years": database.get_batch_years(),
        "departments": database.get_departments()
    }

@app.get("/galleries", summary="Get all available galleries")
async def list_galleries():
    """List all available face recognition galleries"""
    
    if not os.path.exists(BASE_GALLERY_DIR):
        return {"galleries": []}
    
    # Find all gallery files
    galleries = []
    for file in os.listdir(BASE_GALLERY_DIR):
        if file.endswith(".pth") and file.startswith("gallery_"):
            galleries.append(file)
    
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
    videos_dir: str = Form(...),
    background_tasks: BackgroundTasks = None
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
    if department not in database.get_departments():
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
    - year: Batch year (e.g., "1st", "2nd")
    - department: Department name (e.g., "CS", "IT")
    - update_existing: Whether to update an existing gallery or create a new one
    - augment_ratio: Ratio of images to augment (0.0 to 1.0)
    - augs_per_image: Number of augmentations per selected image
    """
    # Validate batch year and department
    if year not in database.get_batch_years():
        raise HTTPException(status_code=400, detail=f"Invalid batch year: {year}")
    if department not in database.get_departments():
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
    department = dept_data.get("department")
    if not department:
        raise HTTPException(status_code=400, detail="Department is required")
    
    success = database.add_department(department)
    if not success:
        raise HTTPException(status_code=400, detail=f"Department '{department}' already exists")
    
    return {"message": f"Added department: {department}", "success": True}

@app.delete("/batches/department/{department}", status_code=200, summary="Delete a department")
async def delete_department(department: str):
    # Check if any galleries are using this department in the database
    galleries = database.list_all_galleries()
    dept_galleries = [g for g in galleries if g['department_name'] == department]
    
    if dept_galleries:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete department '{department}' as it is used by {len(dept_galleries)} galleries"
        )
    
    if department not in database.get_departments():
        raise HTTPException(status_code=404, detail=f"Department '{department}' not found")
    
    success = database.delete_department(department)
    if not success:
        raise HTTPException(status_code=404, detail=f"Department '{department}' not found")
    
    return {"message": f"Deleted department: {department}", "success": True}

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
    if department not in database.get_departments():
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
    if department not in database.get_departments():
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
    
    Parameters:ize
    - image: Image file to analyze
    - galleries: List of gallery filenames
    - threshold: Similarity threshold (0-1)
    
    Returns:
    - Base64 encoded image with annotations
    - List of recognized faces
    """
    # Read the image
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")
    
    # Process galleries
    gallery_paths = []
    for gallery_name in galleries:
        if gallery_name.startswith('gallery_') and gallery_name.endswith('.pth'):
            gallery_path = os.path.join(BASE_GALLERY_DIR, gallery_name)
            if os.path.exists(gallery_path):
                gallery_paths.append(gallery_path)
    
    if not gallery_paths:
        raise HTTPException(status_code=400, detail="No valid galleries found")
    
    # Perform recognition
    result_img, faces = recognize_faces(
        img, 
        gallery_paths=gallery_paths,
        model_path=DEFAULT_MODEL_PATH,
        yolo_path=DEFAULT_YOLO_PATH,
        threshold=threshold
    )
    
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
    
    # Return results
    return {
        "image": img_base64,
        "faces": serializable_faces,
        "count": len(serializable_faces)
    }

import subprocess
import threading
import time
import signal
import psutil

# Global variable to track collection app process
collection_app_process = None
collection_app_lock = threading.Lock()

def is_port_in_use(port):
    """Check if a port is in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def check_process_running(process):
    """Check if a process is running, handling both subprocess.Popen and psutil.Process"""
    if process is None:
        return False
    
    try:
        if hasattr(process, 'poll'):
            # subprocess.Popen object
            return process.poll() is None
        elif hasattr(process, 'is_running'):
            # psutil.Process object
            return process.is_running()
        else:
            return False
    except (psutil.NoSuchProcess, AttributeError):
        return False

def get_process_pid(process):
    """Get PID from either subprocess.Popen or psutil.Process"""
    try:
        return process.pid if process else None
    except (AttributeError, psutil.NoSuchProcess):
        return None

def find_collection_app_process():
    """Find if the collection app is already running by checking port 5001"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if this is our collection app process
                cmdline = proc.info['cmdline']
                if cmdline and 'app.py' in ' '.join(cmdline) and any('data_collection' in arg for arg in cmdline):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return None

@app.post("/api/start-collection-app", summary="Start the face collection application")
async def start_collection_app():
    """Start the face collection application server"""
    global collection_app_process
    
    with collection_app_lock:
        try:
            # Check if process is already running
            if check_process_running(collection_app_process):
                return {
                    "success": True,
                    "message": "Face Collection App is already running",
                    "pid": get_process_pid(collection_app_process)
                }
            
            # Check if another instance is running on port 5001
            if is_port_in_use(5001):
                existing_proc = find_collection_app_process()
                if existing_proc:
                    collection_app_process = existing_proc
                    return {
                        "success": True,
                        "message": "Face Collection App is already running (found existing process)",
                        "pid": existing_proc.pid
                    }
            
            # Path to the face collection app
            collection_app_path = os.path.join(
                BASE_DIR, 
                "data_collection",
                "server",
                "app.py"
            )
            
            if not os.path.exists(collection_app_path):
                return {
                    "success": False,
                    "message": "Face Collection App not found at expected location"
                }
            
            # Start the collection app
            collection_app_dir = os.path.join(BASE_DIR, "data_collection")
            launch_script = os.path.join(collection_app_dir, "launch.sh")
            
            if os.path.exists(launch_script):
                # Use launch script if it exists
                collection_app_process = subprocess.Popen(
                    ["bash", "launch.sh"],
                    cwd=collection_app_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid  # Create new process group
                )
            else:
                # Fallback: run app.py directly
                collection_app_process = subprocess.Popen(
                    ["python", "server/app.py"],
                    cwd=collection_app_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid  # Create new process group
                )
            
            # Give it a moment to start
            time.sleep(2)
            
            # Check if it started successfully
            if collection_app_process.poll() is None:
                return {
                    "success": True,
                    "message": "Face Collection App started successfully",
                    "pid": collection_app_process.pid
                }
            else:
                stdout, stderr = collection_app_process.communicate()
                return {
                    "success": False,
                    "message": f"Face Collection App failed to start. Error: {stderr.decode()}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error starting Face Collection App: {str(e)}"
            }

@app.post("/api/stop-collection-app", summary="Stop the face collection application")
async def stop_collection_app():
    """Stop the face collection application server"""
    global collection_app_process
    
    with collection_app_lock:
        try:
            stopped = False
            
            # First, try to stop our tracked process
            if collection_app_process:
                try:
                    if hasattr(collection_app_process, 'terminate'):
                        print(f"Terminating tracked process with PID: {get_process_pid(collection_app_process)}")
                        collection_app_process.terminate()
                        
                        # Wait for graceful termination
                        try:
                            if hasattr(collection_app_process, 'wait'):
                                collection_app_process.wait(timeout=3)
                        except Exception as timeout_error:
                            print(f"Graceful termination timed out: {timeout_error}, forcing kill...")
                            if hasattr(collection_app_process, 'kill'):
                                collection_app_process.kill()
                        
                        stopped = True
                        print("Successfully stopped tracked process")
                        
                except (psutil.NoSuchProcess, ProcessLookupError):
                    print("Tracked process already terminated")
                    stopped = True
                except Exception as e:
                    print(f"Error stopping tracked process: {e}")
                
                collection_app_process = None
            
            # Also try to find and stop any existing collection app processes
            try:
                existing_processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            cmdline_str = ' '.join(cmdline)
                            # Look for Python processes running the collection app
                            if ('app.py' in cmdline_str and 
                                ('data_collection' in cmdline_str or 
                                 'server' in cmdline_str or
                                 '5001' in cmdline_str)):
                                existing_processes.append(proc)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                
                # Stop all found processes
                for proc in existing_processes:
                    try:
                        print(f"Found existing collection app process with PID: {proc.pid}")
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            print(f"Force killing process {proc.pid}")
                            proc.kill()
                        stopped = True
                        print(f"Successfully stopped process {proc.pid}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                    except Exception as e:
                        print(f"Error stopping process {proc.pid}: {e}")
                        
            except Exception as e:
                print(f"Error searching for existing processes: {e}")
            
            # Additional cleanup: kill any process using port 5001
            try:
                result = subprocess.run(['lsof', '-t', '-i:5001'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            pid_int = int(pid.strip())
                            print(f"Killing process using port 5001: PID {pid_int}")
                            os.kill(pid_int, signal.SIGTERM)
                            time.sleep(1)
                            # Check if still running and force kill
                            try:
                                os.kill(pid_int, 0)  # Check if process exists
                                print(f"Force killing stubborn process: PID {pid_int}")
                                os.kill(pid_int, signal.SIGKILL)
                            except ProcessLookupError:
                                pass  # Process already dead
                            stopped = True
                        except (ValueError, ProcessLookupError, PermissionError) as e:
                            print(f"Could not kill process {pid}: {e}")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass  # lsof not available or timed out
            except Exception as e:
                print(f"Error using lsof to find port usage: {e}")
            
            if stopped:
                return {
                    "success": True,
                    "message": "Face Collection App stopped successfully"
                }
            else:
                return {
                    "success": True,
                    "message": "Face Collection App was not running"
                }
                
        except Exception as e:
            print(f"Error in stop_collection_app: {e}")
            return {
                "success": False,
                "message": f"Error stopping Face Collection App: {str(e)}"
            }

@app.get("/api/collection-app-status", summary="Check face collection app status")
async def get_collection_app_status():
    """Check if the face collection application is running"""
    global collection_app_process
    
    with collection_app_lock:
        try:
            # Check our tracked process
            is_running = False
            pid = None
            
            if collection_app_process:
                is_running = check_process_running(collection_app_process)
                if is_running:
                    pid = get_process_pid(collection_app_process)
                else:
                    # Process died, clear the reference
                    collection_app_process = None
            
            # If no tracked process, check if there's an existing one
            if not is_running:
                existing_proc = find_collection_app_process()
                if existing_proc:
                    collection_app_process = existing_proc
                    is_running = True
                    pid = existing_proc.pid
            
            # Double-check by testing the port
            if not is_running:
                is_running = is_port_in_use(5001)
            
            return {
                "running": is_running,
                "pid": pid,
                "port_in_use": is_port_in_use(5001)
            }
        except Exception as e:
            return {
                "running": False,
                "pid": None,
                "port_in_use": False,
                "error": str(e)
            }

# Check processing status endpoint could be added here if needed

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5564)