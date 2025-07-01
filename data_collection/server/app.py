import os
import json
import uuid
import sqlite3
import shutil
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import qrcode
from io import BytesIO
import base64
import cv2
import numpy as np
import tempfile
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import torch
from ultralytics import YOLO
from db_utils import get_batch_years_and_departments

app = Flask(__name__, static_folder='static')
CORS(app)

# Configuration
# Get the absolute path to the root project directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'student_data')
GALLERY_DIR = os.path.join(PROJECT_ROOT, 'gallery', 'data')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(GALLERY_DIR, exist_ok=True)

# Add path to shared YOLO model
YOLO_MODEL_PATH = os.path.join(PROJECT_ROOT, 'src', 'yolo', 'weights', 'yolo11n-face.pt')

# Check if GPU is available
DEVICE = 'cuda:0' if torch.cuda.is_available() else 'cpu'
print(f"Using device for YOLO: {DEVICE}")

# Thread pool for async processing (5 users per thread)
MAX_WORKERS = 3  # Adjust based on your CPU/GPU resources
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
# Task queue to limit concurrent user processing
task_queue = queue.Queue(maxsize=15)  # 5 users per thread × 3 threads
processing_tasks = {}  # Track task status by session ID




# Face processing functions
def preprocess_face_for_lightcnn(face_img, target_size=(128, 128)):
    """
    Process a face image for LightCNN:
    - Convert to grayscale
    - Resize to target size
    """
    try:
        # Handle empty or invalid images
        if face_img is None or face_img.size == 0:
            print("Warning: Empty face image received")
            return None
            
        # Convert to grayscale
        if len(face_img.shape) == 3:  # Color image
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        else:  # Already grayscale
            gray = face_img
        
        # Resize to target size
        resized = cv2.resize(gray, target_size, interpolation=cv2.INTER_LANCZOS4)
        
        # Ensure single channel output
        if len(resized.shape) > 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            
        return resized
        
    except Exception as e:
        print(f"Error in face preprocessing: {e}")
        return None

def extract_faces_from_video(video_path, output_dir, face_confidence=0.3, face_padding=0.2):
    """Extract faces from video and save preprocessed images using YOLO"""
    # Check if output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize face detector with YOLO
    try:
        face_model = YOLO(YOLO_MODEL_PATH)
        print(f"Loaded YOLO model from {YOLO_MODEL_PATH}")
    except Exception as e:
        print(f"Error loading YOLO model: {e}")
        print("Falling back to OpenCV Haar cascade")
        # Fallback to Haar cascade if YOLO model fails to load
        use_yolo = False
        # Initialize Haar cascade for fallback
        try:
            import cv2.data
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        except:
            # Fallback path
            face_cascade = cv2.CascadeClassifier('/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml')
            if face_cascade.empty():
                print("Warning: Could not load Haar cascade, face detection may fail")
                face_cascade = None
    else:
        use_yolo = True
        face_cascade = None
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return 0
    
    # Get video properties
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video info: {frame_count} frames, {fps} fps, {width}x{height} resolution")
    
    # Initialize counters
    faces_saved = 0
    processed_frames = 0
    
    # Use a lower sample rate to process more frames
    sample_rate = 8  # Process every 3th frame
    frames_per_sample = 3
    
    
    # Process each frame in the video
    for current_frame in range(0, frame_count, sample_rate):
        print(f"Processing frame batch starting at frame {current_frame}")
        
        # Process next frames_per_sample frames
        for i in range(frames_per_sample):
            # Make sure we don't go beyond the end of the video
            if current_frame + i >= frame_count:
                break
            
            # Set position and read frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame + i)
            ret, frame = cap.read()
            if not ret:
                print(f"Failed to read frame {current_frame + i}")
                break
            
            processed_frames += 1
            
            # Detect faces using YOLO or fallback to Haar cascade
            if use_yolo:
                # YOLO face detection
                results = face_model(frame, conf=face_confidence)
                
                # Check detection results
                if len(results) > 0:
                    print(f"YOLO detection on frame {current_frame + i}: {len(results)} results")
                    
                    if hasattr(results[0], 'boxes') and len(results[0].boxes) > 0:
                        print(f"  Found {len(results[0].boxes)} boxes")
                        
                        # Collect all valid faces with their areas
                        valid_faces = []
                        
                        for j, box in enumerate(results[0].boxes):
                            # Get bounding box coordinates
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            conf = float(box.conf[0])
                            
                            print(f"  Box {j}: coords={x1},{y1},{x2},{y2}, conf={conf:.2f}")
                            
                            # Skip if below confidence threshold
                            if conf < face_confidence:
                                print(f"  Skipping box {j} - confidence too low")
                                continue
                            
                            # Calculate face area
                            face_width = x2 - x1
                            face_height = y2 - y1
                            face_area = face_width * face_height
                            
                            # Store face info for comparison
                            valid_faces.append({
                                'index': j,
                                'area': face_area,
                                'coords': (x1, y1, x2, y2),
                                'conf': conf
                            })
                        
                        # Only process the biggest face if any valid faces found
                        if valid_faces:
                            # Sort by area (biggest first)
                            valid_faces.sort(key=lambda x: x['area'], reverse=True)
                            biggest_face = valid_faces[0]
                            
                            print(f"  Processing biggest face (index {biggest_face['index']}) with area {biggest_face['area']}")
                            
                            x1, y1, x2, y2 = biggest_face['coords']
                            
                            # Add padding around face
                            face_width = x2 - x1
                            face_height = y2 - y1
                            pad_x = int(face_width * face_padding)
                            pad_y = int(face_height * face_padding)
                            
                            # Ensure coordinates are within frame boundaries
                            x1 = max(0, x1 - pad_x)
                            y1 = max(0, y1 - pad_y)
                            x2 = min(frame.shape[1], x2 + pad_x)
                            y2 = min(frame.shape[0], y2 + pad_y)
                            
                            # Crop face
                            face = frame[y1:y2, x1:x2]
                            
                            # Skip if face crop is empty
                            if face.size > 0 and face.shape[0] > 0 and face.shape[1] > 0:
                                # Preprocess face
                                processed_face = preprocess_face_for_lightcnn(face)
                                
                                # Create unique filename
                                timestamp = int(time.time() * 1000)
                                filename = f"frame{current_frame+i}_biggest_face_{timestamp}.jpg"
                                filepath = os.path.join(output_dir, filename)
                                
                                if processed_face is not None:
                                    # Ensure single channel (grayscale)
                                    if len(processed_face.shape) > 2:
                                        processed_face = cv2.cvtColor(processed_face, cv2.COLOR_BGR2GRAY)
                                    # Double-check the size
                                    if processed_face.shape != (128, 128):
                                        processed_face = cv2.resize(processed_face, (128, 128), interpolation=cv2.INTER_LANCZOS4)
                                    # Save the image
                                    cv2.imwrite(filepath, processed_face)
                                    faces_saved += 1
                                    print(f"  Saved biggest face from frame {current_frame+i}")
            else:
                # Fallback to Haar cascade detection
                if face_cascade is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(
                        gray, 
                        scaleFactor=1.1, 
                        minNeighbors=5, 
                        minSize=(30, 30)
                    )
                    
                    # Only process the biggest face if multiple faces detected
                    if len(faces) > 0:
                        # Calculate areas and find biggest face
                        face_areas = []
                        for j, (x, y, w, h) in enumerate(faces):
                            area = w * h
                            face_areas.append((area, j, x, y, w, h))
                        
                        # Sort by area (biggest first) and take the first one
                        face_areas.sort(reverse=True)
                        biggest_area, biggest_idx, x, y, w, h = face_areas[0]
                        
                        print(f"Frame {current_frame+i}: Processing biggest face (area={biggest_area}) out of {len(faces)} detected")
                        
                        # Add padding around face
                        pad_x = int(w * face_padding)
                        pad_y = int(h * face_padding)
                        
                        # Ensure coordinates are within frame boundaries
                        x1 = max(0, x - pad_x)
                        y1 = max(0, y - pad_y)
                        x2 = min(frame.shape[1], x + w + pad_x)
                        y2 = min(frame.shape[0], y + h + pad_y)
                        
                        # Crop face
                        face = frame[y1:y2, x1:x2]
                        
                        # Skip if face crop is empty
                        if face.size > 0 and face.shape[0] > 0 and face.shape[1] > 0:
                            # Preprocess face
                            processed_face = preprocess_face_for_lightcnn(face)
                            
                            # Create unique filename
                            timestamp = int(time.time() * 1000)
                            filename = f"frame{current_frame+i}_biggest_face_{timestamp}.jpg"
                            filepath = os.path.join(output_dir, filename)
                            
                            if processed_face is not None:
                                # Ensure single channel (grayscale)
                                if len(processed_face.shape) > 2:
                                    processed_face = cv2.cvtColor(processed_face, cv2.COLOR_BGR2GRAY)
                                # Double-check the size
                                if processed_face.shape != (128, 128):
                                    processed_face = cv2.resize(processed_face, (128, 128), interpolation=cv2.INTER_LANCZOS4)
                                # Save the image
                                cv2.imwrite(filepath, processed_face)
                                faces_saved += 1
                                print(f"  Saved biggest face from frame {current_frame+i}")
                else:
                    print(f"Warning: No face detection available for frame {current_frame+i}")
    
    # Close resources
    cap.release()
    
    return faces_saved

def organize_processed_faces_to_gallery(student_data, processed_faces_dir):
    """
    Organize processed face images into the gallery structure based on student's dept and year.
    
    Args:
        student_data (dict): Student information containing regNo, dept, year, name
        processed_faces_dir (str): Path to the directory containing processed face images
        
    Returns:
        str: Path to the organized gallery directory for this student
    """
    try:
        # Extract student information
        reg_no = student_data.get('regNo')
        dept = student_data.get('dept', 'Unknown')
        year = student_data.get('year', 'Unknown')
        name = student_data.get('name', 'Unknown')
        
        if not reg_no:
            print("Error: Registration number not found in student data")
            return None
            
        # Create group directory name based on dept and year
        group_name = f"{dept}_{year}"
        group_dir = os.path.join(GALLERY_DIR, group_name)
        
        # Create group directory if it doesn't exist
        os.makedirs(group_dir, exist_ok=True)
        print(f"Ensured gallery group directory exists: {group_dir}")
        
        # Create student directory within the group (images go directly here)
        student_gallery_dir = os.path.join(group_dir, reg_no)
        os.makedirs(student_gallery_dir, exist_ok=True)
        print(f"Created student gallery directory: {student_gallery_dir}")
        
        # Create or update student metadata file
        metadata_file = os.path.join(student_gallery_dir, 'metadata.json')
        metadata = {
            'regNo': reg_no,
            'name': name,
            'dept': dept,
            'year': year,
            'group': group_name,
            'lastUpdated': datetime.now().isoformat(),
            'processedImagesPath': student_gallery_dir
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"Created/updated metadata file: {metadata_file}")
        
        # Check if processed faces directory exists and has images
        if not os.path.exists(processed_faces_dir):
            print(f"Warning: Processed faces directory does not exist: {processed_faces_dir}")
            return student_gallery_dir
            
        # Get list of processed face images
        image_files = [f for f in os.listdir(processed_faces_dir) 
                      if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        
        if not image_files:
            print(f"Warning: No image files found in {processed_faces_dir}")
            return student_gallery_dir
            
        print(f"Found {len(image_files)} processed face images to organize")
        
        # Copy processed images to gallery structure (directly in student directory)
        copied_count = 0
        for image_file in image_files:
            src_path = os.path.join(processed_faces_dir, image_file)
            dst_path = os.path.join(student_gallery_dir, image_file)
            
            try:
                shutil.move(src_path, dst_path)
                copied_count += 1
                print(f"Copied {image_file} to gallery")
            except Exception as e:
                print(f"Error copying {image_file}: {e}")
                
        print(f"Successfully organized {copied_count} face images into gallery structure")
        print(f"Gallery location: {student_gallery_dir}")
        
        # Update group summary file
        group_summary_file = os.path.join(group_dir, 'group_summary.json')
        
        # Load existing summary or create new one
        if os.path.exists(group_summary_file):
            with open(group_summary_file, 'r') as f:
                group_summary = json.load(f)
        else:
            group_summary = {
                'groupName': group_name,
                'dept': dept,
                'year': year,
                'students': {},
                'totalStudents': 0,
                'lastUpdated': datetime.now().isoformat()
            }
        
        # Update student entry in group summary
        group_summary['students'][reg_no] = {
            'name': name,
            'regNo': reg_no,
            'imageCount': copied_count,
            'lastProcessed': datetime.now().isoformat(),
            'galleryPath': student_gallery_dir
        }
        
        group_summary['totalStudents'] = len(group_summary['students'])
        group_summary['lastUpdated'] = datetime.now().isoformat()
        
        # Save updated group summary
        with open(group_summary_file, 'w') as f:
            json.dump(group_summary, f, indent=2)
        
        print(f"Updated group summary: {group_summary_file}")
        print(f"Group '{group_name}' now has {group_summary['totalStudents']} students")
        
        return student_gallery_dir
        
    except Exception as e:
        print(f"Error organizing processed faces to gallery: {e}")
        return None

# Helper function to find student directory (for migration compatibility)
def find_student_directory(student_id, year=None, dept=None):
    """Find student directory in new dept_year structure or old structure"""
    # First try new structure if year and dept provided
    if year and dept:
        new_path = os.path.join(DATA_DIR, f"{dept}_{year}", student_id)
        if os.path.exists(new_path):
            return new_path
    
    # Try old structure (direct in DATA_DIR)
    old_path = os.path.join(DATA_DIR, student_id)
    if os.path.exists(old_path):
        return old_path
    
    # Search through all dept_year directories
    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
        if os.path.isdir(item_path):
            student_path = os.path.join(item_path, student_id)
            if os.path.exists(student_path):
                return student_path
    
    return None

# Migration function
def migrate_student_data():
    """Migrate existing student data from old structure to new dept_year structure"""
    print("Checking for student data migration...")
    
    # Get batch years and departments from database
    try:
        data = get_batch_years_and_departments()
        years = data.get('years', [])
        departments = data.get('departments', [])
    except Exception as e:
        print(f"Error getting batch data for migration: {e}")
        return
    
    # Look for directories in DATA_DIR that don't follow the new naming pattern
    if not os.path.exists(DATA_DIR):
        return
        
    migrated_count = 0
    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
        
        # Skip if it's not a directory
        if not os.path.isdir(item_path):
            continue
            
        # Skip if it already follows the new pattern (contains underscore and matches dept_year)
        if '_' in item and any(item.endswith(f"_{year}") for year in years):
            continue
            
        # This appears to be an old student directory
        print(f"Found old student directory: {item}")
        
        # Try to find session files to get year and dept
        session_files = [f for f in os.listdir(item_path) if f.endswith('.json')]
        
        if session_files:
            session_file = os.path.join(item_path, session_files[0])
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                student_year = session_data.get('year')
                student_dept = session_data.get('dept')
                
                if student_year and student_dept:
                    # Create new directory structure
                    dept_year_dir = os.path.join(DATA_DIR, f"{student_dept}_{student_year}")
                    os.makedirs(dept_year_dir, exist_ok=True)
                    
                    # Move student directory
                    new_student_path = os.path.join(dept_year_dir, item)
                    if not os.path.exists(new_student_path):
                        shutil.move(item_path, new_student_path)
                        print(f"Migrated {item} to {student_dept}_{student_year}/{item}")
                        migrated_count += 1
                    else:
                        print(f"Warning: {new_student_path} already exists, skipping migration for {item}")
                        
            except Exception as e:
                print(f"Error migrating {item}: {e}")
    
    if migrated_count > 0:
        print(f"Successfully migrated {migrated_count} student directories")
    else:
        print("No student directories found that need migration")

# Routes
@app.route('/')
def index():
    static_folder = app.static_folder or 'static'
    return send_from_directory(static_folder, 'index.html')

@app.route('/api/session/start', methods=['POST'])
def start_session():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    student_id = data.get('studentId')  # Registration Number
    name = data.get('name')
    year = data.get('year')
    dept = data.get('dept')
    
    if not all([student_id, name, year, dept]):
        return jsonify({"error": "All student details are required"}), 400
    
    # Create unique session ID
    session_id = str(uuid.uuid4())
    
    # Create department-year directory structure
    dept_year_dir = os.path.join(DATA_DIR, f"{dept}_{year}")
    os.makedirs(dept_year_dir, exist_ok=True)
    
    # Create student directory within department-year folder
    student_dir = os.path.join(dept_year_dir, student_id)
    os.makedirs(student_dir, exist_ok=True)
    
    # Create session info
    session_data = {
        "sessionId": session_id,
        "regNo": student_id,
        "name": name,
        "year": year,
        "dept": dept,
        "batch": f"Batch{year}",  # Create batch from year
        "startTime": datetime.now().isoformat(),
        "videoUploaded": False,
        "facesExtracted": False,
        "facesOrganized": False,
        "videoPath": "",
        "facesCount": 0
    }
    
    # Save session data with student ID as filename only
    with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
        json.dump(session_data, f, indent=2)
    
    return jsonify({"sessionId": session_id, "studentId": student_id}), 200

@app.route('/api/upload/<session_id>', methods=['POST'])
def upload_video(session_id):
    if 'video' not in request.files:
        return jsonify({"error": "No video provided"}), 400
    
    file = request.files['video']
    student_id = request.form.get('studentId')
    name = request.form.get('name')
    year = request.form.get('year')
    dept = request.form.get('dept')
    
    if not student_id:
        return jsonify({"error": "Registration Number is required"}), 400
    
    # Create department-year directory structure
    dept_year_dir = os.path.join(DATA_DIR, f"{dept}_{year}")
    os.makedirs(dept_year_dir, exist_ok=True)
    
    # Create student directory within department-year folder
    student_dir = os.path.join(dept_year_dir, student_id)
    os.makedirs(student_dir, exist_ok=True)
    
    # Get existing session data using student ID filename only
    session_file = os.path.join(student_dir, f"{student_id}.json")
    if not os.path.exists(session_file):
        return jsonify({"error": "Invalid session"}), 404
    
    with open(session_file, 'r') as f:
        session_data = json.load(f)
    
    # Save the original WebM video (temporary)
    webm_filename = f"{student_id}.webm"
    webm_path = os.path.join(student_dir, webm_filename)
    file.save(webm_path)
    
    # Verify the WebM file was saved successfully
    if not os.path.exists(webm_path):
        return jsonify({
            "success": False,
            "message": "Failed to save WebM video file"
        }), 500
    
    webm_size = os.path.getsize(webm_path)
    print(f"Saved WebM video to {webm_path} ({webm_size} bytes)")
    
    if webm_size == 0:
        return jsonify({
            "success": False,
            "message": "WebM video file is empty"
        }), 500
    
    # Convert WebM to MP4 using FFmpeg
    mp4_filename = f"{student_id}.mp4"
    mp4_path = os.path.join(student_dir, mp4_filename)
    
    try:
        # Check if FFmpeg is available
        import subprocess
        
        try:
            ffmpeg_check = subprocess.run(['ffmpeg', '-version'], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE, 
                         text=True,
                         check=True)
            print(f"FFmpeg is available. Version info: {ffmpeg_check.stdout.split('version')[1].split('Copyright')[0].strip() if 'version' in ffmpeg_check.stdout else 'Unknown'}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"FFmpeg check failed: {e}")
            return jsonify({
                "success": False,
                "message": f"FFmpeg is not installed or not available in PATH. Error: {str(e)}"
            }), 500
        
        # Run FFmpeg to convert the file with encoders available on this system
        
        # List of video encoders to try (in order of preference)
        # Based on available encoders from FFmpeg installation
        video_encoders = ['mpeg4', 'libopenh264', 'libvpx', 'libvpx_vp8', 'libvpx_vp9', 'mjpeg']
        audio_encoders = ['mp3', 'libmp3lame', 'pcm_s16le', 'aac']
        
        conversion_successful = False
        
        # Try each video encoder until one works
        for video_codec in video_encoders:
            if conversion_successful:
                break
                
            print(f"Trying video codec: {video_codec}")
            
            # Try with audio first
            for audio_codec in audio_encoders:
                cmd = [
                    'ffmpeg', 
                    '-i', webm_path,  # Input file
                    '-c:v', video_codec,  # Video codec
                    '-c:a', audio_codec,  # Audio codec
                    '-movflags', '+faststart',  # Optimize for web streaming
                    '-y',               # Overwrite output without asking
                    mp4_path            # Output file
                ]
                
                print(f"Running FFmpeg command: {' '.join(cmd)}")
                
                process = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120  # 2 minute timeout
                )
                
                print(f"FFmpeg process completed with return code: {process.returncode}")
                if process.stdout:
                    print(f"FFmpeg stdout: {process.stdout}")
                if process.stderr:
                    print(f"FFmpeg stderr: {process.stderr}")
                
                if process.returncode == 0:
                    print(f"Video conversion successful with {video_codec}/{audio_codec}")
                    conversion_successful = True
                    break
                else:
                    print(f"Failed with {video_codec}/{audio_codec}: {process.stderr}")
            
            # If audio codecs failed, try without audio
            if not conversion_successful:
                print(f"Trying {video_codec} without audio...")
                cmd_no_audio = [
                    'ffmpeg', 
                    '-i', webm_path,
                    '-c:v', video_codec,
                    '-an',  # No audio
                    '-y',
                    mp4_path
                ]
                
                print(f"Running FFmpeg command: {' '.join(cmd_no_audio)}")
                
                process = subprocess.run(
                    cmd_no_audio,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120
                )
                
                print(f"FFmpeg process completed with return code: {process.returncode}")
                if process.stdout:
                    print(f"FFmpeg stdout: {process.stdout}")
                if process.stderr:
                    print(f"FFmpeg stderr: {process.stderr}")
                
                if process.returncode == 0:
                    print(f"Video conversion successful with {video_codec} (no audio)")
                    conversion_successful = True
                    break
                else:
                    print(f"Failed with {video_codec} (no audio): {process.stderr}")
        
        if not conversion_successful:
            print("All FFmpeg conversion attempts failed")
            return jsonify({
                "success": False,
                "message": f"Failed to convert video. Tried multiple codecs but none worked. Last error: {process.stderr}"
            }), 500
            
        print(f"Converted video to MP4 format: {mp4_path}")
        
        # Verify the MP4 file was created and has content
        if not os.path.exists(mp4_path):
            return jsonify({
                "success": False,
                "message": "MP4 file was not created successfully"
            }), 500
            
        mp4_size = os.path.getsize(mp4_path)
        if mp4_size == 0:
            return jsonify({
                "success": False,
                "message": "MP4 file is empty"
            }), 500
            
        print(f"MP4 file created successfully: {mp4_path} ({mp4_size} bytes)")
        
        # Delete the WebM file now that conversion is complete
        try:
            os.remove(webm_path)
            print(f"Deleted temporary WebM file: {webm_path}")
        except Exception as e:
            print(f"Warning: Could not delete WebM file: {e}")
        
        # Update session data - only mark video as uploaded, no face extraction
        session_data["videoUploaded"] = True
        session_data["uploadTime"] = datetime.now().isoformat()
        session_data["facesExtracted"] = False  # Will be set to True when processed in gallery manager
        session_data["facesOrganized"] = False  # Will be set to True when organized in gallery manager
        session_data["facesCount"] = 0  # Will be updated during processing
        session_data["videoPath"] = mp4_path  # Store video path for reference
        
        # Update additional fields if provided in form data
        if name:
            session_data["name"] = name
        if year:
            session_data["year"] = year
        if dept:
            session_data["dept"] = dept
        
        # Save updated session data with student reg number as filename only
        student_json_file = os.path.join(student_dir, f"{student_id}.json")
        with open(student_json_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        # Keep the MP4 video file for reference
        print(f"Keeping MP4 video file for reference: {mp4_path}")
        
        return jsonify({
            "success": True,
            "message": "Video uploaded and converted successfully. Ready for processing in gallery manager.",
            "facesCount": 0,  # No faces extracted yet
            "facesOrganized": False,
            "videoPath": mp4_path
        }), 200
    
    except Exception as e:
        print(f"Error processing video: {e}")
        return jsonify({
            "success": False,
            "message": f"Error processing video: {str(e)}"
        }), 500

@app.route('/api/reset-faces/<session_id>', methods=['POST'])
def reset_faces(session_id):
    data = request.json if request.json else {}
    student_id = data.get('studentId')
    year = data.get('year')
    dept = data.get('dept')
    
    if not student_id:
        return jsonify({"error": "Student ID is required"}), 400
    if not year:
        return jsonify({"error": "Year is required"}), 400
    if not dept:
        return jsonify({"error": "Department is required"}), 400
    
    # Get path to gallery directory using dept_year structure instead of faces directory
    dept_year_dir = os.path.join(DATA_DIR, f"{dept}_{year}")
    student_dir = os.path.join(dept_year_dir, student_id)
    
    # Also check gallery directory for cleanup
    gallery_dept_year_dir = os.path.join(GALLERY_DIR, f"{dept}_{year}")
    gallery_student_dir = os.path.join(gallery_dept_year_dir, student_id)
    
    # Reset both data collection faces and gallery faces if they exist
    reset_success = False
    
    if os.path.exists(gallery_student_dir):
        try:
            # Delete all image files in gallery directory
            for file in os.listdir(gallery_student_dir):
                file_path = os.path.join(gallery_student_dir, file)
                if os.path.isfile(file_path) and file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    os.unlink(file_path)
            reset_success = True
            print(f"Cleared gallery faces from: {gallery_student_dir}")
        except Exception as e:
            print(f"Error clearing gallery faces: {e}")
    
    # Reset session data using student ID filename
    session_file = os.path.join(student_dir, f"{student_id}.json")
    if os.path.exists(session_file):
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            session_data["facesExtracted"] = False
            session_data["facesOrganized"] = False
            session_data["facesCount"] = 0
            session_data["resetTime"] = datetime.now().isoformat()
            
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            reset_success = True
        except Exception as e:
            print(f"Error updating session data: {e}")
    
    if reset_success:
        return jsonify({
            "success": True, 
            "message": "Face data reset successfully"
        }), 200
    else:
        return jsonify({
            "error": "No face data found to reset"
        }), 404

@app.route('/api/batches', methods=['GET'])
def get_batches():
    """API endpoint to get batch years and departments for dropdowns"""
    return jsonify(get_batch_years_and_departments())

@app.route('/qr')
def generate_qr():
    # Generate QR code for the HTTPS URL
    url = f"https://{request.host}"
    img = qrcode.make(url)
    
    # Convert to base64 for display
    buffered = BytesIO()
    img.save(buffered)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    # Return simple HTML with QR code
    return f"""
    <html>
        <head><title>Scan to connect</title></head>
        <body style="text-align: center; padding: 50px;">
            <h1>Scan this QR code with your phone</h1>
            <img src="data:image/png;base64,{img_str}">
            <p>Or visit: <a href="{url}">{url}</a></p>
        </body>
    </html>
    """

if __name__ == '__main__':
    # Run migration on startup to ensure data is in correct structure
    migrate_student_data()
    
    # For development, you can generate a self-signed certificate:
    # openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
    # Then uncomment the ssl_context line below
    
    # Check if SSL certificates exist
    import os
    cert_file = os.path.join(os.path.dirname(__file__), 'cert.pem')
    key_file = os.path.join(os.path.dirname(__file__), 'key.pem')
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("SSL certificates found. Starting HTTPS server...")
        app.run(host='0.0.0.0', port=5001, ssl_context=(cert_file, key_file))
    else:
        print("No SSL certificates found. Starting HTTP server...")
        print("For camera access, either:")
        print("1. Access via https://localhost:5001 (if using SSH tunnel)")
        print("2. Generate SSL certificates with:")
        print("   openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365")
        print("3. Or use Chrome with --unsafely-treat-insecure-origin-as-secure flag")
        app.run(host='0.0.0.0', port=5001)