import os
import json
import uuid
import shutil
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import qrcode
from io import BytesIO
import base64
from db_utils import (
    get_batch_years_and_departments,
    validate_student_login,
    get_student_name as db_get_student_name,
    get_department_code as db_get_department_code
)
from dotenv import load_dotenv

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from src.services.student_data_service import process_students_videos

# Load environment variables at module level
load_dotenv()

# Get host, port, and workers from environment variables or use defaults
host = os.environ.get("DATA_COLLECTION_HOST", "0.0.0.0")
# print(f"Data PORT : ", os.environ.get("DATA_COLLECTION_PORT", 8001))
port = 8000 #int(os.environ.get("DATA_COLLECTION_PORT", 8001))
workers = int(os.environ.get("DATA_COLLECTION_WORKERS", "1").strip().split()[0])

app = Flask(__name__, static_folder='static')

# Configure CORS for HTTP compatibility
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
        "supports_credentials": False  # Set to False for HTTP
    }
})

# Add security headers for better browser compatibility
@app.after_request
def after_request(response):
    # Allow all origins for development (HTTP mode)
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    
    # Basic security headers (suitable for HTTP)
    response.headers.add('X-Content-Type-Options', 'nosniff')
    response.headers.add('X-Frame-Options', 'SAMEORIGIN')
    
    return response

# Handle preflight requests
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization,X-Requested-With")
        response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS")
        return response

# Configuration
# Get the absolute path to the root project directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'student_data')
GALLERY_DIR = os.path.join(PROJECT_ROOT, 'gallery', 'data')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(GALLERY_DIR, exist_ok=True)

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

def get_department_id(name: str):
    data = get_batch_years_and_departments()
    departments = data['departments']
    
    for department in departments:
        if department["name"] == name:
            return department["id"]
    
    return None

def extract_year_from_regno(regno: str) -> tuple:
    """Extract admission year and graduation year from registration number"""
    try:
        if len(regno) >= 6:
            # For registration numbers like 714023247046, extract the year part (23)
            year_part = regno[4:6]  # Extract positions 4-5
            year = int(year_part)
            
            # Convert 2-digit year to 4-digit admission year
            if year >= 90:  # Assume 90-99 means 1990-1999
                admission_year = 1900 + year
            else:  # 00-89 means 2000-2089
                admission_year = 2000 + year
            
            # Calculate graduation year (admission year + 4 for undergraduate)
            graduation_year = admission_year + 4
                
            return str(admission_year), str(graduation_year)
    except (ValueError, IndexError):
        pass
    
    # Default fallback
    return "2023", "2027"

def get_year_display(regno: str) -> str:
    """Get year display format like '2023 - 2027'"""
    admission_year, graduation_year = extract_year_from_regno(regno)
    return f"{admission_year} - {graduation_year}"

def get_graduation_year(regno: str) -> str:
    """Get graduation year for folder structure"""
    _, graduation_year = extract_year_from_regno(regno)
    return graduation_year

def extract_dept_code_from_regno(regno: str) -> str:
    """Extract department code from registration number"""
    try:
        if len(regno) >= 9:
            # For registration numbers like 714023247046, extract the dept code (247)
            dept_code = regno[6:9]  # Extract positions 6-8
            return dept_code
    except (ValueError, IndexError):
        pass
    
    # Default fallback
    return None

def get_department_name_by_code(dept_code: str) -> str:
    """Get department name from department code"""
    try:
        result, status_code = db_get_department_code(dept_code)
        if result.get('success'):
            return result.get('dept_code')  # This returns the department name
    except Exception as e:
        print(f"Error getting department name: {e}")
    
    return None

# Routes
@app.route('/')
def index():
    static_folder = app.static_folder or 'static'
    return send_from_directory(static_folder, 'index.html')

@app.route('/login')
def login():
    static_folder = app.static_folder or 'static'
    return send_from_directory(static_folder, 'login.html')
    
@app.route('/api/check-login', methods=['GET'])
def check_login():
    # Check if student is logged in using localStorage on client side
    # This endpoint is mainly to enable server-side redirection
    return jsonify({'success': False, 'message': 'Not logged in'}), 401

@app.route('/api/session/start', methods=['POST'])
def start_session():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    student_id = data.get('studentId')  # Registration Number
    name = data.get('name')  # Full Name
    year_display = data.get('year_display') or data.get('year')  # Full display format like "2023 - 2027"
    dept_name = data.get('dept')  # Department name like "AIML"
    section = data.get('section', '').strip().upper()  # Section with preprocessing
    
    if not all([student_id, dept_name]):
        return jsonify({"error": "Student ID and department are required"}), 400
    
    # Validate section field
    if not section:
        return jsonify({"error": "Section is required"}), 400
    
    # Validate section format (1 character, letters only)
    import re
    if not re.match(r'^[A-Z]$', section):
        return jsonify({"error": "Section should be 1 character (letter only)"}), 400
    
    # Extract department code from registration number
    dept_code = extract_dept_code_from_regno(student_id)
    if not dept_code:
        return jsonify({"error": "Invalid registration number format"}), 400
    
    # Get graduation year for folder structure
    graduation_year = get_graduation_year(student_id)
    
    # Create unique session ID
    session_id = str(uuid.uuid4())
    
    # Use department code and graduation year for directory structure
    dept_year_dir = os.path.join(DATA_DIR, f"{dept_code}_{graduation_year}")
    os.makedirs(dept_year_dir, exist_ok=True)
    
    # Create student directory within department-year folder
    student_dir = os.path.join(dept_year_dir, student_id)
    os.makedirs(student_dir, exist_ok=True)
    
    # Create session info - store both ID and name
    admission_year, _ = extract_year_from_regno(student_id)
    session_data = {
        "sessionId": session_id,
        "regNo": student_id,
        "name": name,
        "year": graduation_year,  # Store graduation year for consistency
        "admission_year": admission_year,  # Store admission year for reference
        "year_display": year_display,  # Store the display format
        "dept": dept_name,
        "dept_id": dept_code,  # Store the department code
        "section": section,  # Store the section
        "batch": f"Batch{graduation_year}",
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
    
    # Save student data to database
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
        from src.database.models import save_student_to_database
        save_student_to_database(session_data)
    except Exception as e:
        print(f"Error saving student to database: {e}")
    
    return jsonify({"sessionId": session_id, "studentId": student_id}), 200

@app.route('/api/upload/<session_id>', methods=['POST'])
def upload_video(session_id):
    if 'video' not in request.files:
        return jsonify({"error": "No video provided"}), 400
    
    file = request.files['video']
    student_id = request.form.get('studentId')
    name = request.form.get('name')
    year_display = request.form.get('year')  # This is now display format
    dept_name = request.form.get('dept')
    
    if not student_id:
        return jsonify({"error": "Registration Number is required"}), 400
    
    # Extract department code from registration number
    dept_code = extract_dept_code_from_regno(student_id)
    if not dept_code:
        return jsonify({"error": "Invalid registration number format"}), 400
    
    # Get graduation year for folder structure
    graduation_year = get_graduation_year(student_id)
    
    # Use department code and graduation year for directory structure
    dept_year_dir = os.path.join(DATA_DIR, f"{dept_code}_{graduation_year}")
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
    
    # Store original session data for re-attempting users (in case upload fails)
    original_session_data = session_data.copy()
    is_reattempting_user = session_data.get("videoUploaded", False)
    
    if is_reattempting_user:
        print(f"Re-attempting user {student_id}: Preserving original session data in case of upload failure")
    
    # Save the original WebM video (temporary)
    webm_filename = f"{student_id}.webm"
    webm_path = os.path.join(student_dir, webm_filename)
    file.save(webm_path)
    
    # Verify the WebM file was saved successfully
    if not os.path.exists(webm_path):
        # Restore original session data for re-attempting users
        if is_reattempting_user:
            try:
                with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                    json.dump(original_session_data, f, indent=2)
                print(f"Restored original session data for re-attempting user {student_id}")
            except Exception as restore_error:
                print(f"Warning: Could not restore original session data: {restore_error}")
        return jsonify({
            "success": False,
            "message": "Failed to save WebM video file"
        }), 500
    
    webm_size = os.path.getsize(webm_path)
    print(f"Saved WebM video to {webm_path} ({webm_size} bytes)")
    
    if webm_size == 0:
        # Restore original session data for re-attempting users
        if is_reattempting_user:
            try:
                with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                    json.dump(original_session_data, f, indent=2)
                print(f"Restored original session data for re-attempting user {student_id}")
            except Exception as restore_error:
                print(f"Warning: Could not restore original session data: {restore_error}")
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
            # Restore original session data for re-attempting users
            if is_reattempting_user:
                try:
                    with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                        json.dump(original_session_data, f, indent=2)
                    print(f"Restored original session data for re-attempting user {student_id}")
                except Exception as restore_error:
                    print(f"Warning: Could not restore original session data: {restore_error}")
            return jsonify({
                "success": False,
                "message": f"Failed to convert video. Tried multiple codecs but none worked. Last error: {process.stderr}"
            }), 500
            
        print(f"Converted video to MP4 format: {mp4_path}")
        
        # Verify the MP4 file was created and has content
        if not os.path.exists(mp4_path):
            # Restore original session data for re-attempting users
            if is_reattempting_user:
                try:
                    with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                        json.dump(original_session_data, f, indent=2)
                    print(f"Restored original session data for re-attempting user {student_id}")
                except Exception as restore_error:
                    print(f"Warning: Could not restore original session data: {restore_error}")
            return jsonify({
                "success": False,
                "message": "MP4 file was not created successfully"
            }), 500
            
        mp4_size = os.path.getsize(mp4_path)
        if mp4_size == 0:
            # Restore original session data for re-attempting users
            if is_reattempting_user:
                try:
                    with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                        json.dump(original_session_data, f, indent=2)
                    print(f"Restored original session data for re-attempting user {student_id}")
                except Exception as restore_error:
                    print(f"Warning: Could not restore original session data: {restore_error}")
            return jsonify({
                "success": False,
                "message": "MP4 file is empty"
            }), 500
            
        print(f"MP4 file created successfully: {mp4_path} ({mp4_size} bytes)")
        
        if is_reattempting_user:
            print(f"Re-attempting user {student_id}: Will update JSON only after successful upload")
        else:
            print(f"New user {student_id}: Will update JSON after successful upload")
        
        # Update session data - only mark video as uploaded, no face extraction
        session_data["videoUploaded"] = True
        session_data["uploadTime"] = datetime.now().isoformat()
        session_data["facesExtracted"] = False  # Will be set to True when processed in gallery manager
        session_data["facesOrganized"] = False  # Will be set to True when organized in gallery manager
        session_data["facesCount"] = 0  # Will be updated during processing
        session_data["videoPath"] = mp4_path  # Store video path for reference
        session_data["dept"] = dept_name
        # Update additional fields if provided in form data
        # if name:
        #     session_data["name"] = name
        if graduation_year:
            session_data["year"] = graduation_year
        if dept_code:
            session_data["dept_id"] = dept_code
        if year_display:
            session_data["year_display"] = year_display
        
        # For re-attempting users: Only update JSON after successful video upload
        # For new users: Update JSON immediately after successful video upload (existing behavior)
        student_json_file = os.path.join(student_dir, f"{student_id}.json")
        
        # Save updated session data with student reg number as filename only
        with open(student_json_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        # Verify the JSON file was written correctly
        try:
            with open(student_json_file, 'r') as f:
                verification_data = json.load(f)
                if not verification_data.get("videoUploaded"):
                    raise ValueError("JSON verification failed - videoUploaded not set")
            print(f"Successfully updated and verified session data: {student_json_file}")
        except Exception as e:
            print(f"Error verifying JSON file: {e}")
            return jsonify({
                "success": False,
                "message": f"Failed to save session data: {str(e)}"
            }), 500
        
        # Only delete the WebM file AFTER all operations are successful
        try:
            os.remove(webm_path)
            print(f"Deleted temporary WebM file: {webm_path}")
        except Exception as e:
            print(f"Warning: Could not delete WebM file: {e}")
            # This is non-critical, so we don't fail the entire upload
        
        # Keep the MP4 video file for reference
        print(f"Keeping MP4 video file for reference: {mp4_path}")
        
        return jsonify({
            "success": True,
            "message": "Video uploaded and converted successfully. Ready for processing in gallery manager.",
            "facesCount": 0,  # No faces extracted yet
            "facesOrganized": False,
            "videoPath": mp4_path
        }), 200
    
    except subprocess.TimeoutExpired:
        print(f"FFmpeg conversion timed out after 2 minutes")
        # Restore original session data for re-attempting users
        if is_reattempting_user:
            try:
                with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                    json.dump(original_session_data, f, indent=2)
                print(f"Restored original session data for re-attempting user {student_id}")
            except Exception as restore_error:
                print(f"Warning: Could not restore original session data: {restore_error}")
        return jsonify({
            "success": False,
            "message": "Video conversion timed out. The video file might be too large or corrupted."
        }), 500
    except FileNotFoundError:
        print(f"FFmpeg not found in system PATH")
        # Restore original session data for re-attempting users
        if is_reattempting_user:
            try:
                with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                    json.dump(original_session_data, f, indent=2)
                print(f"Restored original session data for re-attempting user {student_id}")
            except Exception as restore_error:
                print(f"Warning: Could not restore original session data: {restore_error}")
        return jsonify({
            "success": False,
            "message": "FFmpeg is not installed or not found in system PATH."
        }), 500
    except PermissionError as e:
        print(f"Permission error during video processing: {e}")
        # Restore original session data for re-attempting users
        if is_reattempting_user:
            try:
                with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                    json.dump(original_session_data, f, indent=2)
                print(f"Restored original session data for re-attempting user {student_id}")
            except Exception as restore_error:
                print(f"Warning: Could not restore original session data: {restore_error}")
        return jsonify({
            "success": False,
            "message": f"Permission error: Unable to write video files. Check directory permissions."
        }), 500
    except OSError as e:
        print(f"OS error during video processing: {e}")
        # Restore original session data for re-attempting users
        if is_reattempting_user:
            try:
                with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                    json.dump(original_session_data, f, indent=2)
                print(f"Restored original session data for re-attempting user {student_id}")
            except Exception as restore_error:
                print(f"Warning: Could not restore original session data: {restore_error}")
        return jsonify({
            "success": False,
            "message": f"System error during video processing: {str(e)}"
        }), 500
    except json.JSONDecodeError as e:
        print(f"JSON error when updating session data: {e}")
        # Restore original session data for re-attempting users
        if is_reattempting_user:
            try:
                with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                    json.dump(original_session_data, f, indent=2)
                print(f"Restored original session data for re-attempting user {student_id}")
            except Exception as restore_error:
                print(f"Warning: Could not restore original session data: {restore_error}")
        return jsonify({
            "success": False,
            "message": f"Error updating session data: Invalid JSON format."
        }), 500
    except Exception as e:
        print(f"Unexpected error processing video: {e}")
        import traceback
        traceback.print_exc()
        # Restore original session data for re-attempting users
        if is_reattempting_user:
            try:
                with open(os.path.join(student_dir, f"{student_id}.json"), 'w') as f:
                    json.dump(original_session_data, f, indent=2)
                print(f"Restored original session data for re-attempting user {student_id}")
            except Exception as restore_error:
                print(f"Warning: Could not restore original session data: {restore_error}")
        return jsonify({
            "success": False,
            "message": f"Unexpected error processing video: {str(e)}"
        }), 500

@app.route('/api/reset-faces/<session_id>', methods=['POST'])
def reset_faces(session_id):
    data = request.json if request.json else {}
    student_id = data.get('studentId')
    year_display = data.get('year')  # This is now display format
    dept_name = data.get('dept')
    
    if not student_id:
        return jsonify({"error": "Student ID is required"}), 400
    
    # Extract department code from registration number
    dept_code = extract_dept_code_from_regno(student_id)
    if not dept_code:
        return jsonify({"error": "Invalid registration number format"}), 400
    
    # Get graduation year for folder structure
    graduation_year = get_graduation_year(student_id)
    
    # Use department code and graduation year for directory structure
    dept_year_dir = os.path.join(DATA_DIR, f"{dept_code}_{graduation_year}")
    student_dir = os.path.join(dept_year_dir, student_id)
    
    # Also check gallery directory for cleanup
    gallery_dept_year_dir = os.path.join(GALLERY_DIR, f"{dept_code}_{graduation_year}")
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
    # Check if SSL certificates exist to determine protocol
    cert_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'certs', 'cert.pem')
    key_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'certs', 'key.pem')
    
    # Use HTTPS if certificates exist, otherwise HTTP
    if os.path.exists(cert_file) and os.path.exists(key_file):
        url = f"https://{request.host}"
        protocol_info = "HTTPS (Secure)"
        alt_url = f"http://{request.host.split(':')[0]}:8001"
    else:
        url = f"http://{request.host}"
        protocol_info = "HTTP (Insecure - Camera may not work)"
        alt_url = f"https://{request.host.split(':')[0]}:8001"
    
    img = qrcode.make(url)
    
    # Convert to base64 for display
    buffered = BytesIO()
    img.save(buffered)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    # Return simple HTML with QR code and protocol information
    return f"""
    <html>
        <head><title>Scan to connect</title></head>
        <body style="text-align: center; padding: 50px;">
            <h1>Scan this QR code with your phone</h1>
            <img src="data:image/png;base64,{img_str}">
            <p>Protocol: <strong>{protocol_info}</strong></p>
            <p>Primary URL: <a href="{url}">{url}</a></p>
            <br>
            <div style="background: #f0f0f0; padding: 15px; border-radius: 8px; max-width: 400px; margin: 0 auto;">
                <h3>📱 Mobile Setup Instructions:</h3>
                <ol style="text-align: left;">
                    <li>Scan the QR code or visit the URL above</li>
                    <li>If using HTTPS, accept the security warning</li>
                    <li>Allow camera permissions when prompted</li>
                </ol>
            </div>
        </body>
    </html>
    """

@app.route('/about')
def about():
    static_folder = app.static_folder or 'static'
    return send_from_directory(static_folder, 'about.html')

@app.route('/api/process-videos', methods=['POST'])
def api_process_videos():
    data = request.json or {}
    dept = data.get('dept')
    year = data.get('year')
    if not dept or not year:
        return jsonify({"success": False, "error": "Department and year are required."}), 400
    result = process_students_videos(dept, year)
    return jsonify(result)

@app.route('/api/student-login', methods=['POST'])
def student_login():
    data = request.get_json()
    regno = data.get('regno')
    dob = data.get('dob')
    if not regno or not dob:
        return jsonify({'success': False, 'message': 'Register number and DOB required.'}), 400
    
    result, status_code = validate_student_login(regno, dob)
    return jsonify(result), status_code

@app.route('/api/get-student-name', methods=['POST'])
def get_student_name():
    data = request.get_json()
    regno = data.get('regno')
    if not regno:
        return jsonify({'success': False, 'message': 'Register number required.'}), 400
    
    result, status_code = db_get_student_name(regno)
    return jsonify(result), status_code

@app.route('/api/get-department-code', methods=['POST'])
def get_department_code():
    data = request.get_json()
    dept_id = data.get('dept_id')
    if not dept_id:
        return jsonify({'success': False, 'message': 'Department ID required.'}), 400
    
    result, status_code = db_get_department_code(dept_id)
    return jsonify(result), status_code

@app.route('/api/get-student-status', methods=['POST'])
def get_student_status():
    data = request.get_json()
    regno = data.get('regno')
    if not regno:
        return jsonify({'success': False, 'message': 'Register number required.'}), 400
    
    try:
        # Extract department code from registration number
        dept_code = extract_dept_code_from_regno(regno)
        if not dept_code:
            return jsonify({'success': False, 'message': 'Invalid registration number format.'}), 400
        
        # Get department name from code
        department_name = get_department_name_by_code(dept_code)
        if not department_name:
            return jsonify({'success': False, 'message': 'Department not found for this registration number.'}), 404
        
        # Get student info from database
        student_result, status_code = db_get_student_name(regno)
        
        if not student_result.get('success'):
            return jsonify({'success': False, 'message': 'Student not found.'}), 404
        
        name = student_result.get('name')
        graduation_year = get_graduation_year(regno)
        
        # Construct the expected folder path based on department code and graduation year
        dept_year_folder = f"{dept_code}_{graduation_year}"
        student_folder_path = os.path.join(PROJECT_ROOT, 'data', 'student_data', dept_year_folder, regno)
        json_file_path = os.path.join(student_folder_path, f"{regno}.json")
        
        # Check if student folder exists
        if not os.path.exists(student_folder_path):
            return jsonify({
                'success': True,
                'status': 'new',
                'message': 'Ready for first-time data collection',
                'icon': 'bi-person-plus',
                'color': 'info'
            })
        
        # Check if JSON file exists
        if not os.path.exists(json_file_path):
            return jsonify({
                'success': True,
                'status': 'new',
                'message': 'Ready for first-time data collection',
                'icon': 'bi-person-plus',
                'color': 'info'
            })
        
        # Read and parse JSON file
        with open(json_file_path, 'r') as f:
            student_data = json.load(f)
        
        # Check if video file exists
        video_files = [f for f in os.listdir(student_folder_path) if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]
        
        if not video_files:
            return jsonify({
                'success': True,
                'status': 'no_video',
                'message': 'Please upload video for processing',
                'icon': 'bi-camera-video',
                'color': 'warning'
            })
        
        # Check quality check status - handle both camelCase and lowercase
        quality_check = student_data.get('qualityCheck') or student_data.get('qualitycheck')
        
        if not quality_check:
            return jsonify({
                'success': True,
                'status': 'processing',
                'message': 'Waiting for quality check. Please check your status after some time to see if any action is needed.',
                'icon': 'bi-hourglass-split',
                'color': 'warning'
            })
        
        # Check if quality check passed - handle both string and object format
        quality_status = None
        if isinstance(quality_check, str):
            quality_status = quality_check
        elif isinstance(quality_check, dict):
            quality_status = quality_check.get('status')
        
        if quality_status == 'pass':
            return jsonify({
                'success': True,
                'status': 'pass',
                'message': 'Quality check passed - No actions needed',
                'icon': 'bi-check-circle',
                'color': 'success'
            })
        else:
            return jsonify({
                'success': True,
                'status': 'failed',
                'message': 'Video failed on quality check - Please follow the instructions and try again',
                'icon': 'bi-x-circle',
                'color': 'danger'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error checking status: {str(e)}'}), 500

if __name__ == '__main__':
    import sys
    from gunicorn.app.wsgiapp import run

    # Run migration on startup to ensure data is in correct structure
    migrate_student_data()

    # Check if SSL certificates exist
    cert_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'certs', 'cert.pem')
    key_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'certs', 'key.pem')
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        # Run with HTTPS
        print(f"🔐 Starting HTTPS server on {host}:{port}")
        print(f"📜 Using certificate: {cert_file}")
        print(f"🔑 Using private key: {key_file}")
        sys.argv = [
            "gunicorn", 
            "app:app", 
            f"--bind={host}:{port}", 
            f"--workers={workers}",
            f"--certfile={cert_file}",
            f"--keyfile={key_file}"
        ]
    else:
        # port=8000
        # Run with HTTP (fallback)
        print(f"⚠️  SSL certificates not found. Starting HTTP server on {host}:{port}")
        print(f"💡 To enable HTTPS, run: ./generate_ssl_certs.sh")
        sys.argv = ["gunicorn", "app:app", f"--bind={host}:{port}", f"--workers={workers}"]
    
    run()
