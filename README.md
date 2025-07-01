# Face Recognition Gallery Manager

A comprehensive face recognition system designed for academic institutions to collect, process, and manage student facial data for identification purposes.

## Overview

The Face Recognition Gallery Manager is a modern web application that combines video-based face data collection with advanced face recognition capabilities. Built with Python, FastAPI, and modern web technologies, it provides a complete solution for managing face recognition galleries organized by department and batch year.

## Features

### 🎥 Video Data Collection

- Web-based video recording interface for student data collection
- Real-time face detection and extraction during recording
- Automatic video processing and face cropping
- Support for multiple video formats (MP4, AVI, MOV, MKV)

### 🧠 Advanced Face Recognition

- LightCNN-based deep learning model for feature extraction
- YOLO v11 for accurate face detection
- High-accuracy face matching with configurable similarity thresholds
- Real-time face recognition from uploaded images

### 📁 Gallery Management

- Organize face galleries by department and batch year
- Support for multiple gallery selection during recognition
- Automatic gallery creation from processed video data
- Database integration for gallery metadata management

### 🔧 Administration Tools

- Batch year and department management
- Video processing with frame extraction
- Data augmentation for improved recognition accuracy
- Gallery synchronization and cleanup tools

### 📊 Processing Features

- Bulk video processing from directories
- Automatic face extraction and preprocessing
- Image augmentation for training data enhancement
- Progress tracking and error reporting

## Technology Stack

### Backend

- **FastAPI** - Modern Python web framework
- **PyTorch** - Deep learning framework
- **OpenCV** - Computer vision library
- **SQLite** - Database for metadata storage
- **Ultralytics YOLO** - Face detection
- **PIL/Pillow** - Image processing

### Frontend

- **HTML5/CSS3** - Modern web interface
- **JavaScript** - Interactive functionality
- **Bootstrap 5** - Responsive design
- **Font Awesome** - Icons and UI elements

### Machine Learning

- **LightCNN** - Lightweight convolutional neural network for face recognition
- **YOLO v11** - Real-time object detection for face detection
- **Albumentations** - Image augmentation library

## Installation

### Prerequisites

- Python 3.12v or higher
- CUDA-compatible GPU (optional, for faster processing)
- FFmpeg (for video processing)

### Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd Face-Data-collection-and-Gallery-management-application
   ```
2. **Create virtual environment**

   ```bash
   python -m venv envs/face-rec
   source envs/face-rec/bin/activate  # On Windows: envs\face-rec\Scripts\activate
   ```
3. **Install dependencies**

   ```bash
   pip install -r requirements.txt

   #download checkpoints file from : https://drive.google.com/file/d/1CUdlD83CYpiC-KedxLM9b8nG0ZAltsP4/view?usp=sharing
   ```
4. **Download model weights**

   - Place LightCNN model weights in `src/checkpoints`
   - YOLO weights will be downloaded automatically
5. **Initialize database**

   ```bash
   python src/migrate_database.py
   ```

## Usage

### Starting the Application

#### Development Mode

```bash
python src/main.py
```

#### Production Mode

```bash
bash setup-production.sh
pm2 start ecosystem.config.js
```

The application will be available at `http://localhost:5564`

### Core Workflows

#### 1. Data Collection

1. Navigate to the **Admin** section
2. Click "Launch Collection App" to start the data collection interface
3. Students can access the collection interface to record their videos
4. Videos are automatically processed and faces extracted

#### 2. Gallery Creation

1. Go to **Create Galleries** section
2. Select the department and batch year
3. Choose the directory containing processed videos
4. Configure augmentation settings if needed
5. Click "Create Gallery" to generate the face recognition gallery

#### 3. Face Recognition

1. Navigate to **Recognition** section
2. Select one or more galleries to search against
3. Upload an image containing faces
4. View recognition results with similarity scores

#### 4. Gallery Management

1. Visit **Galleries** section to view all created galleries
2. Check gallery statistics and student counts
3. Delete or update galleries as needed

### Configuration

#### Environment Variables

- `MODEL_PATH` - Path to LightCNN model weights
- `YOLO_PATH` - Path to YOLO model weights
- `DATA_DIR` - Directory for storing processed data
- `GALLERY_DIR` - Directory for storing gallery files

#### Database Configuration

The application uses SQLite by default. Database file is located at `data/app.db`.

## API Documentation

The application provides a comprehensive REST API. Once running, visit `http://localhost:5564/docs` for interactive API documentation.

### Key Endpoints

- `POST /process` - Process videos to extract faces
- `POST /galleries/create` - Create face recognition gallery
- `POST /recognize` - Recognize faces in uploaded image
- `GET /galleries` - List all available galleries
- `POST /batches/year` - Add new batch year
- `POST /batches/department` - Add new department

## Directory Structure

```
├── data/                          # Application data
│   ├── app.db                    # SQLite database
│   └── student_data/             # Processed student data
├── gallery/                      # Gallery management
│   ├── data/                     # Organized face data
│   └── galleries/                # Gallery files (.pth)
├── src/                          # Source code
│   ├── main.py                   # Main FastAPI application
│   ├── database.py               # Database operations
│   ├── gallery_manager.py        # Gallery management logic
│   ├── checkpoints/              # Model weights
│   └── yolo/weights/             # YOLO model weights
├── static/                       # Web interface files
│   ├── index.html               # Main interface
│   ├── about.html               # About page
│   ├── css/                     # Stylesheets
│   └── js/                      # JavaScript files
└── data_collection/              # Face data collection app
    └── server/                   # Collection server
```

## Performance Optimization

### GPU Acceleration

- CUDA support for faster face detection and recognition
- Automatic device selection (CUDA/CPU)
- Batch processing for improved throughput

### Image Augmentation

- Configurable augmentation ratio (0.0 to 1.0)
- Multiple augmentation techniques:
  - Resolution scaling
  - Brightness/contrast adjustment
  - Gaussian blur
  - Combined transformations

### Database Optimization

- Indexed queries for fast gallery lookups
- Efficient metadata storage
- Gallery registration tracking

## Troubleshooting

### Common Issues

1. **Port already in use**

   - Check if another instance is running
   - Use different port in configuration
2. **Model weights not found**

   - Ensure model files are in correct directories
   - Check file permissions
3. **CUDA out of memory**

   - Reduce batch size
   - Use CPU mode instead
4. **Video processing fails**

   - Verify FFmpeg installation
   - Check video file format support

### Debug Mode

Enable debug logging by setting environment variable:

```bash
export DEBUG=1
python src/main.py
```

*This application was developed by AI & ML students as a comprehensive solution for academic face recognition needs.*
