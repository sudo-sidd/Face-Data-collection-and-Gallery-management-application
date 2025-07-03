document.addEventListener('DOMContentLoaded', () => {
    // Check for secure context
    if (!navigator.mediaDevices) {
        // Create error message
        const errorSection = document.createElement('div');
        errorSection.className = 'section error-section';
        errorSection.innerHTML = `
            <h2>Camera API Not Available</h2>
            <p>This browser doesn't support camera access from this URL.</p>
            <p>Please try one of the following:</p>
            <ul>
                <li>Give this site access to your camera</li>
                <li>Use Chrome or Firefox</li>
                <li>Enable HTTPS for this application</li>
            </ul>
        `;
        
        document.querySelector('.container').prepend(errorSection);
    }

    // Configuration
    const config = {
        videoLength: 8,  // Changed from 10 to 15
        apiBase: '/api'
    };
    
    // State management
    const state = {
        sessionId: null,
        studentId: null,
        name: null,
        year: null,
        dept: null,
        mediaRecorder: null,
        recordedChunks: [],
        stream: null,
        countdownTimer: null
    };
    
    // DOM Elements - add retry button
    const elements = {
        video: document.getElementById('video'),
        studentForm: document.getElementById('student-form'),
        registration: document.getElementById('registration'),
        cameraSection: document.getElementById('camera-section'),
        completion: document.getElementById('completion'),
        restart: document.getElementById('restart'),
        retry: document.getElementById('retry'),  // Add this line
        progress: document.getElementById('progress')
    };
    
    // Set up event listeners - add retry handler
    elements.studentForm.addEventListener('submit', handleFormSubmit);
    elements.restart.addEventListener('click', handleRestart);
    elements.retry.addEventListener('click', handleRetry);  // Add this line
    

    async function loadBatchYearsAndDepartments() {
        try {
            const response = await fetch('/api/batches');
            const data = await response.json();

            // Populate Batch Year
            const batchYearSelect = document.getElementById('year');
            if (batchYearSelect) {
                batchYearSelect.innerHTML = '<option value="" selected disabled>Select Year</option>';
                for (const year of data.years) {
                    batchYearSelect.innerHTML += `<option value="${year}">${year}</option>`;
                }
            }

            // Populate Department
            const departmentSelect = document.getElementById('dept');
            if (departmentSelect) {
                departmentSelect.innerHTML = '<option value="" selected disabled>Select Department</option>';
                for (const dept of data.departments) {
                    departmentSelect.innerHTML += `<option value="${dept.id}">${dept.name} (${dept.id})</option>`;
                }
            }
        } catch (error) {
            console.error('Error loading batch years and departments:', error);
        }
    }

    // Call the function after DOM is loaded
    loadBatchYearsAndDepartments();



    // Handle student form submission
    async function handleFormSubmit(event) {
        event.preventDefault();
        
        state.studentId = document.getElementById('studentId').value;
        state.name = document.getElementById('name').value;
        state.year = document.getElementById('year').value;
        state.dept = document.getElementById('dept').value;
        
        try {
            const response = await fetch(`${config.apiBase}/session/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    studentId: state.studentId,
                    name: state.name,
                    year: state.year,
                    dept: state.dept
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                state.sessionId = data.sessionId;
                initCamera();
            } else {
                alert(`Error: ${data.message || 'Failed to start session'}`);
            }
        } catch (error) {
            console.error('Error starting session:', error);
            alert('Failed to connect to the server. Please try again.');
        }
    }

async function startRecording() {
  const startRecordBtn = document.getElementById('startRecord');
  const stopRecordBtn = document.getElementById('stopRecord');
  const countdown = document.getElementById('countdown');

  // Clear previous recording data
  state.recordedChunks = [];
  let timeLeft = config.videoLength;

  // UI Setup
  startRecordBtn.disabled = true;
  stopRecordBtn.disabled = false;
  elements.progress.style.width = '0%';

  // Start recording
  state.mediaRecorder.start();

  // Countdown logic
  countdown.textContent = `Recording: ${timeLeft}s remaining`;
  state.countdownTimer = setInterval(() => {
    timeLeft--;

    // Update progress
    const progressPercent = ((config.videoLength - timeLeft) / config.videoLength) * 100;
    elements.progress.style.width = `${progressPercent}%`;
    countdown.textContent = `Recording: ${timeLeft}s remaining`;

    // Instruction updates
    if (timeLeft <= 3) {
      document.getElementById('instruction').textContent = "Make a neutral and then smiling expression";
    } else if (timeLeft <= 6) {
      document.getElementById('instruction').textContent = "Look slightly up and down";
    } else if (timeLeft <= 12) {
      document.getElementById('instruction').textContent = "Slowly turn your head left and right";
    } else {
      document.getElementById('instruction').textContent = "Look straight at the camera";
    }

    // Auto-stop
    if (timeLeft <= 0) {
      clearInterval(state.countdownTimer);
      if (state.mediaRecorder.state !== 'inactive') {
        state.mediaRecorder.stop();
        startRecordBtn.disabled = false;
        stopRecordBtn.disabled = true;
        countdown.textContent = "Processing...";
      }
    }
  }, 1000);
}

async function initCamera(autoStart = false) {
  elements.registration.classList.add('hidden');
  elements.cameraSection.classList.remove('hidden');

  const startRecordBtn = document.getElementById('startRecord');
  const stopRecordBtn = document.getElementById('stopRecord');

  try {
    // Access webcam
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'user',
        width: { ideal: 640 },
        height: { ideal: 480 }
      }
    });
    elements.video.srcObject = state.stream;

    // Initialize MediaRecorder
    state.mediaRecorder = new MediaRecorder(state.stream);

    state.mediaRecorder.ondataavailable = event => {
      if (event.data && event.data.size > 0) {
        state.recordedChunks.push(event.data);
      }
    };

    state.mediaRecorder.onstop = () => {
      const videoBlob = new Blob(state.recordedChunks, { type: 'video/webm' });
      if (state.stream) {
        state.stream.getTracks().forEach(track => track.stop());
      }
      uploadVideo(videoBlob);
    };

    // Button listeners
    if (startRecordBtn) {
      startRecordBtn.addEventListener('click', startRecording);
    }
    if (stopRecordBtn) {
      stopRecordBtn.addEventListener('click', () => {
        if (state.countdownTimer) clearInterval(state.countdownTimer);
        if (state.mediaRecorder.state !== 'inactive') {
          state.mediaRecorder.stop();
          startRecordBtn.disabled = false;
          stopRecordBtn.disabled = true;
          document.getElementById('countdown').textContent = "Processing...";
        }
      });
    }

    // Auto-start recording if requested
    if (autoStart) startRecording();

  } catch (error) {
    console.error('Error accessing camera:', error);
    alert('Failed to access camera. Please try accessing this site via localhost.');
    handleRestart();
  }
}


    
    // Upload video to server
async function uploadVideo(blob) {
    const instruction = document.getElementById('instruction');
    const countdown = document.getElementById('countdown');

    const loadingSpinner = document.createElement('div');
    loadingSpinner.className = 'loading-spinner';
    countdown.parentNode.insertBefore(loadingSpinner, countdown.nextSibling);

    countdown.textContent = "Processing your video";
    instruction.textContent = "Uploading video to server...";

    const formData = new FormData();
    formData.append('video', blob, `student_${state.studentId}_video.webm`);
    formData.append('studentId', state.studentId);
    formData.append('name', state.name);
    formData.append('year', state.year);
    formData.append('dept', state.dept);

    try {
        let processingStep = 0;
        const processingSteps = [
            "Uploading video to server...",
            "Converting video format...",
            "Analyzing video frames...",
            "Detecting faces in frames...",
            "Processing and saving face images..."
        ];

        const statusInterval = setInterval(() => {
            processingStep = (processingStep + 1) % processingSteps.length;
            instruction.textContent = processingSteps[processingStep];
        }, 2000);

        const response = await fetch(`${config.apiBase}/upload/${state.sessionId}`, {
            method: 'POST',
            body: formData
        });

        clearInterval(statusInterval);

        if (response.ok) {
            instruction.textContent = "Processing complete! Face images extracted successfully.";
            loadingSpinner.remove();
            elements.cameraSection.classList.add('hidden');
            elements.completion.classList.remove('hidden');
        } else {
            console.error('Upload failed:', await response.text());
            instruction.textContent = "Error: Failed to process video.";
            alert('Failed to upload video. Please try again.');
            handleRestart();  // 👈 redirect to form page
        }
    } catch (error) {
        console.error('Error uploading video:', error);
        instruction.textContent = "Error: Connection issue.";
        alert('Failed to upload video. Please check your connection and try again.');
        handleRestart();  // 👈 redirect to form page
    }
}

    
    // Handle restart button
    function handleRestart() {
        // Clean up resources
        if (state.countdownTimer) {
            clearInterval(state.countdownTimer);
        }
        
        if (state.stream) {
            state.stream.getTracks().forEach(track => track.stop());
        }
        
        // Reset state
        state.sessionId = null;
        state.studentId = null;
        state.name = null;
        state.year = null;
        state.dept = null;
        state.mediaRecorder = null;
        state.recordedChunks = [];
        state.stream = null;
        
        // Reset UI
        elements.studentForm.reset();
        elements.progress.style.width = '0%';
        
        // Remove recording controls
        const controls = document.querySelector('.recording-controls');
        if (controls) controls.remove();
        
        // Show registration screen
        elements.completion.classList.add('hidden');
        elements.cameraSection.classList.add('hidden');
        elements.registration.classList.remove('hidden');
    }
    
    // Add the retry handler function
    async function handleRetry() {
        try {
            // Show loading state
            elements.retry.disabled = true;
            elements.retry.textContent = "Processing...";
            
            // Reset faces folder via API
            const response = await fetch(`${config.apiBase}/reset-faces/${state.sessionId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    studentId: state.studentId,
                    year: state.year,
                    dept: state.dept
                })
            });
            
            if (!response.ok) {
                throw new Error("Failed to reset data");
            }
            
            // Keep student information but reset recording state
            state.mediaRecorder = null;
            state.recordedChunks = [];
            state.stream = null;
            
            // Reset UI
            elements.progress.style.width = '0%';
            
            // Remove recording controls if they exist
            const controls = document.querySelector('.recording-controls');
            if (controls) controls.remove();
            
            // Go back to camera screen
            elements.completion.classList.add('hidden');
            elements.cameraSection.classList.remove('hidden');
            
            // Reset retry button for next time
            elements.retry.disabled = false;
            elements.retry.textContent = "Try Again";
            
            // Initialize camera for new recording
            initCamera();
        } catch (error) {
            console.error('Error during retry:', error);
            alert('Failed to reset. Please try again.');
            
            // Reset retry button state
            elements.retry.disabled = false;
            elements.retry.textContent = "Try Again";
        }
    }
});

// Expose functions to global scope
window.initCamera = initCamera;
window.startRecording = startRecording;
window.handleRestart = handleRestart;
window.handleRetry = handleRetry;