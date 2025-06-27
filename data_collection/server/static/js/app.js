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
        videoLength: 15,  // Changed from 10 to 15
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
    
    // Initialize camera using the simpler approach from test.html
    async function initCamera() {
        elements.registration.classList.add('hidden');
        elements.cameraSection.classList.remove('hidden');
        
        // Create and add recording controls
        const controls = document.createElement('div');
        controls.className = 'recording-controls';
        controls.innerHTML = `
            <div id="countdown" class="timer">Ready to record</div>
            <button id="startRecord" class="btn primary">Start Recording (15s)</button>
            <button id="stopRecord" class="btn secondary" disabled>Stop Recording</button>
            <div class="instructions-container">
                <h3>Instructions:</h3>
                <ul>
                    <li><strong>Position:</strong> Hold phone at arm's length from your face</li>
                    <li><strong>Lighting:</strong> Choose a well-lit area with light on your face</li>
                    <li><strong>Framing:</strong> Ensure only your face is visible and avoid reflections</li>
                    <li><strong>Follow this 15-second sequence:</strong></li>
                    <li>1. <strong>Look directly at camera</strong> with neutral expression (3 sec)</li>
                    <li>2. <strong>Slowly rotate head</strong> left then right, keeping eyes visible (6 sec)</li>
                    <li>4. <strong>Change expression</strong> from neutral to smiling (3 sec)</li>
                </ul>
            </div>
        `;
        elements.cameraSection.appendChild(controls);
        
        const startRecordBtn = document.getElementById('startRecord');
        const stopRecordBtn = document.getElementById('stopRecord');
        const countdown = document.getElementById('countdown');
        
        try {
            // Get camera stream
            state.stream = await navigator.mediaDevices.getUserMedia({ 
                video: {
                    facingMode: 'user',
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                }
            });
            elements.video.srcObject = state.stream;
            
            // Set up MediaRecorder
            state.mediaRecorder = new MediaRecorder(state.stream);
            
            // Collect data when available
            state.mediaRecorder.ondataavailable = event => {
                if (event.data && event.data.size > 0) {
                    state.recordedChunks.push(event.data);
                }
            };
            
            // Handle recording completion
            state.mediaRecorder.onstop = () => {
                const videoBlob = new Blob(state.recordedChunks, { type: 'video/webm' });
                
                // Stop camera immediately after recording is complete
                if (state.stream) {
                    state.stream.getTracks().forEach(track => track.stop());
                }
                
                // Now upload the video
                uploadVideo(videoBlob);
            };
            
            // Add event listeners to buttons
            startRecordBtn.addEventListener('click', () => {
                // Clear previous recording data
                state.recordedChunks = [];
                let timeLeft = config.videoLength;
                
                // Update UI
                startRecordBtn.disabled = true;
                stopRecordBtn.disabled = false;
                elements.progress.style.width = '0%';
                
                // Start recording
                state.mediaRecorder.start();
                
                // Start countdown
                countdown.textContent = `Recording: ${timeLeft}s remaining`;
                state.countdownTimer = setInterval(() => {
                    timeLeft--;
                    // Update progress bar
                    const progressPercent = ((config.videoLength - timeLeft) / config.videoLength) * 100;
                    elements.progress.style.width = `${progressPercent}%`;
                    
                    countdown.textContent = `Recording: ${timeLeft}s remaining`;
                    
                    // Update recording instructions - adjusted for 15 seconds
                    if (timeLeft <= 3) {
                        document.getElementById('instruction').textContent = "Make a neutral and then smiling expression";
                    } else if (timeLeft <= 6) {
                        document.getElementById('instruction').textContent = "Look slightly up and down";
                    } else if (timeLeft <= 12) {
                        document.getElementById('instruction').textContent = "Slowly turn your head left and right";
                    } else {
                        document.getElementById('instruction').textContent = "Look straight at the camera";
                    }
                    
                    // Auto-stop when time is up
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
            });
            
            stopRecordBtn.addEventListener('click', () => {
                if (state.countdownTimer) {
                    clearInterval(state.countdownTimer);
                }
                if (state.mediaRecorder.state !== 'inactive') {
                    state.mediaRecorder.stop();
                    startRecordBtn.disabled = false;
                    stopRecordBtn.disabled = true;
                    countdown.textContent = "Processing...";
                }
            });
            
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
        
        // Create a loading spinner
        const loadingSpinner = document.createElement('div');
        loadingSpinner.className = 'loading-spinner';
        countdown.parentNode.insertBefore(loadingSpinner, countdown.nextSibling);
        
        // Update status message
        countdown.textContent = "Processing your video";
        instruction.textContent = "Uploading video to server...";
        
        const formData = new FormData();
        formData.append('video', blob, `student_${state.studentId}_video.webm`);
        formData.append('studentId', state.studentId);
        formData.append('name', state.name);
        formData.append('year', state.year);
        formData.append('dept', state.dept);
        
        try {
            // Show detailed processing steps
            let processingStep = 0;
            const processingSteps = [
                "Uploading video to server...",
                "Converting video format...",
                "Analyzing video frames...",
                "Detecting faces in frames...",
                "Processing and saving face images..."
            ];
            
            // Update processing step message every 2 seconds
            const statusInterval = setInterval(() => {
                processingStep = (processingStep + 1) % processingSteps.length;
                instruction.textContent = processingSteps[processingStep];
            }, 2000);
            
            const response = await fetch(`${config.apiBase}/upload/${state.sessionId}`, {
                method: 'POST',
                body: formData
            });
            
            // Clear interval once request completes
            clearInterval(statusInterval);
            
            if (response.ok) {
                // Show completion message
                instruction.textContent = "Processing complete! Face images extracted successfully.";
                
                // Remove spinner and show completion screen
                loadingSpinner.remove();
                elements.cameraSection.classList.add('hidden');
                elements.completion.classList.remove('hidden');
            } else {
                console.error('Upload failed:', await response.text());
                instruction.textContent = "Error: Failed to process video.";
                alert('Failed to upload video. Please try again.');
            }
        } catch (error) {
            console.error('Error uploading video:', error);
            instruction.textContent = "Error: Connection issue.";
            alert('Failed to upload video. Please check your connection and try again.');
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
                    studentId: state.studentId
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