document.addEventListener('DOMContentLoaded', () => {
    document.body.style.overflow = 'auto';
    document.documentElement.style.overflow = 'auto';
    
    // Student login enforcement
    if (!localStorage.getItem('studentRegNo')) {
        fetch('/api/check-login', {
            method: 'GET',
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) {
                window.location.href = '/login';
            }
        })
        .catch(error => {
            console.error('Login check failed:', error);
            window.location.href = '/login';
        });
        return;
    }
    // Check for secure context
    // if (!navigator.mediaDevices) {
    //     // Create error message
    //     const errorSection = document.createElement('div');
    //     errorSection.className = 'section error-section';
    //     errorSection.innerHTML = `
    //         <h2>Camera API Not Available</h2>
    //         <p>This browser doesn't support camera access from this URL.</p>
    //         <p>Please try one of the following:</p>
    //         <ul>
    //             <li>Give this site access to your camera</li>
    //             <li>Use Chrome or Firefox</li>
    //             <li>Enable HTTPS for this application</li>
    //         </ul>
    //     `;
        
    //     document.querySelector('.container').prepend(errorSection);
    // }
    
    // Initialize elements that might be missing
    const ensureInstructionElement = () => {
        if (!document.getElementById('instruction')) {
            const controlsDiv = document.querySelector('.controls');
            if (controlsDiv) {
                const instructionDiv = document.createElement('div');
                instructionDiv.id = 'instruction';
                instructionDiv.textContent = 'Follow the instructions below';
                controlsDiv.appendChild(instructionDiv);
            }
        }
        return document.getElementById('instruction');
    };

    // Configuration
    const config = {
        videoLength: 8,  // Changed from 10 to 15
        apiBase: '/api'
    };
    
    // State management
    const state = {
        sessionId: null,
        studentId: null,
        name: null, // Add name to state
        year: null,
        dept: null,
        section: null, // Add section to state
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
    

    async function loadBatchYearsAndDepartments() {
        const regNoInput = document.getElementById('studentId');
        const yearField = document.getElementById('year');
        const deptField = document.getElementById('dept');

        regNoInput.addEventListener("input", async () => {
            const regNo = regNoInput.value.trim();
            if (/^\d{12}$/.test(regNo)) {
                const pattern = /^(\d{4})(\d{2})(\d{3})(\d{3})$/;
                const match = regNo.match(pattern);
                if (match) {
                    const [, firstPart, year, deptId, rollNo] = match;
                    const fullYear = 2000 + parseInt(year);
                    const gradYear = fullYear + 4;
                    yearField.value = `${fullYear} - ${gradYear}`;
                    // Fetch department code from backend using deptId
                    try {
                        const response = await fetch(`/api/get-department-code`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ dept_id: deptId })
                        });
                        const data = await response.json();
                        if (data.success) {
                            deptField.value = data.dept_code;
                        } else {
                            deptField.value = deptId; // fallback to id if not found
                        }
                    } catch (e) {
                        deptField.value = deptId;
                    }
                }
            } else {
                yearField.value = "";
                deptField.value = "";
            }
        });
    }
    // Call the function after DOM is loaded
    loadBatchYearsAndDepartments();



    // Handle student form submission
async function handleFormSubmit(event) {
    event.preventDefault();
    
    state.studentId = document.getElementById('studentId').value;
    state.name = document.getElementById('name').value; // Get the name from the form
    state.year = document.getElementById('year').value; // Get the year from the form (e.g., "2023 - 2027")
    state.dept = document.getElementById('dept').value;
    state.section = document.getElementById('section').value.trim().toUpperCase(); // Get and preprocess section

    // Validate that year field has a value
    if (!state.year) {
        alert('Please enter a valid registration number to auto-fill the year field.');
        return;
    }

    // Validate that dept field has a value
    if (!state.dept) {
        alert('Please enter a valid registration number to auto-fill the department field.');
        return;
    }

    // Validate section field
    if (!state.section) {
        alert('Please enter your section.');
        return;
    }

    // Validate section format (should be 1 character, letters only)
    if (!/^[A-Z]$/.test(state.section)) {
        alert('Section should be 1 character (letter only).');
        return;
    }

    // Handle year splitting safely - extract graduation year for backend
    let passOutYear;
    if (state.year.includes(' - ')) {
        const [batchYear, gradYear] = state.year.split(" - ");
        passOutYear = gradYear;
    } else {
        passOutYear = state.year;
    }

    try {
        const response = await fetch(`${config.apiBase}/session/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                studentId: state.studentId,
                name: state.name, // Send name to backend
                year: passOutYear, // Send graduation year
                year_display: state.year, // Send full display format (e.g., "2023 - 2027")
                dept: state.dept, // Send department name (e.g., "AIML")
                section: state.section // Send section to backend
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            state.sessionId = data.sessionId;
            // Call initCamera directly since it's in the same scope
            await initCamera();
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
  const countdown = document.getElementById('countdown') || document.createElement('div');
  
  if (!countdown.id) {
    countdown.id = 'countdown';
    const controlsDiv = document.querySelector('.controls');
    if (controlsDiv) {
      controlsDiv.appendChild(countdown);
    }
  }

  // Ensure instruction element exists
  const instructionEl = ensureInstructionElement();

  // Clear previous recording data
  state.recordedChunks = [];
  let timeLeft = config.videoLength;

  // UI Setup
  if (startRecordBtn) {
    startRecordBtn.disabled = true;
    startRecordBtn.classList.add('hidden');
  }
  elements.progress.style.width = '0%';

  // Start recording
  if (state.mediaRecorder) {
    state.mediaRecorder.start();
  } else {
    console.error('MediaRecorder not initialized');
    alert('Camera not ready. Please reload the page and try again.');
    return;
  }

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
      instructionEl.textContent = "Make a neutral and then smiling expression";
    } else if (timeLeft <= 6) {
      instructionEl.textContent = "Look slightly up and down";
    } else if (timeLeft <= 12) {
      instructionEl.textContent = "Slowly turn your head left and right";
    } else {
      instructionEl.textContent = "Look straight at the camera";
    }

    // Auto-stop
    if (timeLeft <= 0) {
      clearInterval(state.countdownTimer);
      if (state.mediaRecorder.state !== 'inactive') {
        state.mediaRecorder.stop();
        startRecordBtn.disabled = false;
        startRecordBtn.classList.remove('hidden');
        countdown.textContent = "Processing...";
      }
    }
  }, 1000);
}

async function initCamera(autoStart = false) {
  elements.registration.classList.add('hidden');
  elements.cameraSection.classList.remove('hidden');

  const startRecordBtn = document.getElementById('startRecord');
  // Stop record button removed as requested

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

    // Button listeners - stop button removed as requested
    if (startRecordBtn) {
      startRecordBtn.addEventListener('click', startRecording);
    }

    // Auto-start recording if requested
    if (autoStart) startRecording();

  } catch (error) {
    console.error('Error accessing camera:', error);
    alert('Failed to access camera.');
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
    
    // Extract graduation year from state.year if it contains a range
    let passOutYear;
    if (state.year && state.year.includes(' - ')) {
        passOutYear = state.year.split(' - ')[1];
    } else {
        passOutYear = state.year;
    }
    
    formData.append('year', passOutYear);
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
    } finally {
        // Clear localStorage data
        localStorage.removeItem('studentRegNo');
        // Remove any other stored data if necessary
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
        state.name = null; // Reset name
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
    
    // Add event listener for retry button if it exists
    if (elements.retry) {
        elements.retry.addEventListener('click', handleRetry);
    }
    
    // Admin: Process Videos button handler
    const processBtn = document.getElementById('process-videos-btn');
    if (processBtn) {
        processBtn.addEventListener('click', async () => {
            const year = document.getElementById('process-year').value.trim();
            const dept = document.getElementById('process-dept').value.trim();
            const statusDiv = document.getElementById('process-status');
            if (!year || !dept) {
                statusDiv.textContent = 'Please enter both year and department.';
                statusDiv.style.color = 'red';
                return;
            }
            
            statusDiv.style.color = '#333';
            try {
                const response = await fetch('/api/process-videos', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ year, dept })
                });
                let resultText = await response.text();
                let result;
                try {
                    result = JSON.parse(resultText);
                } catch (e) {
                    // Try to provide more helpful error info
                    statusDiv.textContent = 'Server error: ' + (resultText || e.message);
                    statusDiv.style.color = 'red';
                    return;
                }
                if (result && typeof result === 'object' && 'success' in result) {
                    if (result.success) {
                        statusDiv.textContent = result.message || 'Processing complete!';
                        statusDiv.style.color = 'green';
                    } else {
                        statusDiv.textContent = (result.error || result.message || 'Processing failed.') + (result.details ? ('\nDetails: ' + JSON.stringify(result.details)) : '');
                        statusDiv.style.color = 'red';
                    }
                } else {
                    statusDiv.textContent = 'Unexpected server response.';
                    statusDiv.style.color = 'red';
                }
            } catch (err) {
                // Improved error handling for network/server errors
                if (err instanceof TypeError && err.message.includes('Failed to fetch')) {
                    statusDiv.textContent = 'Network error: Could not reach backend server. Please check if the server is running and reachable.';
                } else {
                    statusDiv.textContent = 'Network or server error: ' + (err.message || err);
                }
                statusDiv.style.color = 'red';
            }
        });
    }
});

// Expose functions to global scope
window.initCamera = initCamera;
window.startRecording = startRecording;
window.handleRestart = handleRestart;
window.handleRetry = handleRetry;

// Autofill name when registration number is entered
const regNoInput = document.getElementById('studentId');
const nameInput = document.getElementById('name');
regNoInput.addEventListener('blur', async function() {
    const regno = regNoInput.value.trim();
    if (/^\d{12}$/.test(regno)) {
        try {
            const response = await fetch('/api/get-student-name', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ regno })
            });
            const data = await response.json();
            if (data.success) {
                nameInput.value = data.name;
            } else {
                nameInput.value = '';
            }
        } catch (e) {
            nameInput.value = '';
        }
    } else {
        nameInput.value = '';
    }
});