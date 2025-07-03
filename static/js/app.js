const API_BASE_URL = '';  // Empty string for same-origin requests

// State management for collection app
const collectionAppState = {
    isStarting: false,
    isStopping: false,
    lastStatusCheck: 0,
    statusCheckThrottle: 2000 // 2 seconds
};

// Debounce utility function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// DOM ready event
document.addEventListener('DOMContentLoaded', function() {
    // Add debug logging
    
    // Navigation handling
    document.querySelectorAll('.nav-link, button[data-section]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const section = this.getAttribute('data-section');
            activateSection(section);
            
            if (section === 'createGalleries') {
                loadProcessedDatasets();
            }
            
            // Load student data folders when upload section is activated
            if (section === 'upload') {
                loadStudentDataFolders();
            }
            
            // Reload data when entering specific sections
            if (section === 'recognition') {
                console.log("Recognition section activated, reloading gallery checkboxes");
                loadGalleryCheckboxes();
            } else if (section === 'galleries') {
                console.log("Galleries section activated, reloading galleries list");
                loadGalleries();
            } else if (section === 'createGalleries') {
                console.log("Create Galleries section activated, loading processed datasets");
                loadProcessedDatasets();
            }
            
            if (section === 'recognition') {
                console.log("Recognition section activated, reinitializing");
                
                // Reload gallery checkboxes
                loadGalleryCheckboxes();
                
                // Reinitialize event listeners
                const recognitionImage = document.getElementById('recognitionImage');
                if (recognitionImage) {
                    recognitionImage.addEventListener('change', previewImage);
                }
                
                const btnRecognize = document.getElementById('btnRecognize');
                if (btnRecognize) {
                    btnRecognize.removeEventListener('click', performRecognition); // Remove any existing
                    btnRecognize.addEventListener('click', performRecognition);
                }
                
                // Update button state
                updateRecognizeButtonState();
            }
        });
    });
    
    // Add debug logging for forms
    
    // Add event listeners for admin forms
    const addBatchYearForm = document.getElementById('addBatchYearForm');
    if (addBatchYearForm) {
        addBatchYearForm.addEventListener('submit', handleAddBatchYear);
    } else {
        console.log("Batch year form not found");
    }
    
    const addDepartmentForm = document.getElementById('addDepartmentForm');
    if (addDepartmentForm) {
        addDepartmentForm.addEventListener('submit', handleAddDepartment);
    } else {
        console.log("Department form not found");
    }
    
    // Add event listener for process videos form
    const processVideosForm = document.getElementById('processVideosForm');
    if (processVideosForm) {
        processVideosForm.addEventListener('submit', handleProcessVideos);
    } else {
        console.log("Process videos form not found");
    }
    
    // Add event listener for create gallery form
    const createGalleryForm = document.getElementById('createGalleryForm');
    if (createGalleryForm) {
        createGalleryForm.addEventListener('submit', handleCreateGallery);
    } else {
        console.log("Create gallery form not found");
    }
    
    // Add event listeners for collection app buttons
    const launchCollectionBtn = document.getElementById('launchCollectionBtn');
    if (launchCollectionBtn) {
        launchCollectionBtn.addEventListener('click', function(e) {
            e.preventDefault();
            launchCollectionAppWithServer();
        });
    }
    
    const checkStatusBtn = document.getElementById('checkStatusBtn');
    if (checkStatusBtn) {
        checkStatusBtn.addEventListener('click', function(e) {
            e.preventDefault();
            showAlert('info', 'Checking collection app status...');
            checkCollectionAppStatus();
        });
    }
    
    const stopCollectionBtn = document.getElementById('stopCollectionBtn');
    if (stopCollectionBtn) {
        stopCollectionBtn.addEventListener('click', function(e) {
            e.preventDefault();
            stopCollectionAppServer();
        });
    }
    
    
    // Add reload button to recognition section
    const galleryCheckboxesHeaders = document.querySelectorAll('#recognition h5');
    let galleryCheckboxesHeader = null;
    for (const header of galleryCheckboxesHeaders) {
        if (header.textContent.includes('Select Galleries')) {
            galleryCheckboxesHeader = header;
            break;
        }
    }
    
    if (galleryCheckboxesHeader) {
        const reloadBtn = document.createElement('button');
        reloadBtn.className = 'btn btn-sm btn-outline-danger ms-2';
        reloadBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Reload';
        reloadBtn.addEventListener('click', function() {
            loadGalleryCheckboxes();
        });
        galleryCheckboxesHeader.appendChild(reloadBtn);
    }
    
    // Add event listener for reload galleries button in recognition section
    const reloadGalleriesBtn = document.getElementById('reloadGalleriesBtn');
    if (reloadGalleriesBtn) {
        reloadGalleriesBtn.addEventListener('click', function() {
            loadGalleryCheckboxes();
            showAlert('info', 'Reloading galleries...');
        });
    }
    
    // Add toast notification demo buttons
    const demoSuccessToast = document.getElementById('demoSuccessToast');
    if (demoSuccessToast) {
        demoSuccessToast.addEventListener('click', function() {
            showToast('success', 'Operation completed successfully!', {
                title: 'Success',
                duration: 5000
            });
        });
    }
    
    const demoErrorToast = document.getElementById('demoErrorToast');
    if (demoErrorToast) {
        demoErrorToast.addEventListener('click', function() {
            showToast('error', 'An error occurred while processing your request.', {
                title: 'Error',
                duration: 6000
            });
        });
    }
    
    const demoWarningToast = document.getElementById('demoWarningToast');
    if (demoWarningToast) {
        demoWarningToast.addEventListener('click', function() {
            showToast('warning', 'This action might have unintended consequences.', {
                title: 'Warning',
                duration: 5500
            });
        });
    }
    
    const demoInfoToast = document.getElementById('demoInfoToast');
    if (demoInfoToast) {
        demoInfoToast.addEventListener('click', function() {
            showToast('info', 'The system will be updated tonight at 12:00 AM.', {
                title: 'Information',
                duration: 5000
            });
        });
    }
    
    const demoCustomToast = document.getElementById('demoCustomToast');
    if (demoCustomToast) {
        demoCustomToast.addEventListener('click', function() {
            // Creating a more complex custom toast notification
            showToast('info', `
                <div class="mb-2">Processing complete for all videos.</div>
                <div class="progress" style="height: 5px">
                    <div class="progress-bar bg-success" role="progressbar" style="width: 100%"></div>
                </div>
                <div class="d-flex align-items-center justify-content-between mt-2">
                    <small class="text-light-emphasis">100% Complete</small>
                    <button class="btn btn-sm btn-light" onclick="activateSection('galleries')">
                        View Results
                    </button>
                </div>
            `, {
                title: 'Custom Notification',
                duration: 8000,
                timestamp: 'Just now',
            });
        });
    }
    
    // Initialize the application
    init();
    
    // Check collection app status on page load only
    setTimeout(() => {
        // Debug: Check if collection section exists
        const collectionSection = document.getElementById('collection');
        const statusContainer = document.querySelector('.app-status-container');
        console.log('DOM elements found:', {
            collectionSection: !!collectionSection,
            statusContainer: !!statusContainer
        });
        checkCollectionAppStatus();
    }, 1000);
    
    // Check if toast notifications system is working
    setTimeout(() => {
        // Show a welcome toast when the app first loads
        showToast('info', 'Welcome to Face Recognition Gallery Manager', {
            title: 'Welcome',
            duration: 5000
        });
    }, 1500);
});

// Initialize the application - update to include new gallery form selects
async function init() {
    try {
        console.log("Initializing application...");
        
        // Load data in sequence with proper error handling
        console.log("Starting loadBatchYearsAndDepartments...");
        await loadBatchYearsAndDepartments();
        console.log("Completed loadBatchYearsAndDepartments");
        
        console.log("Starting loadGalleries...");
        await loadGalleries();
        console.log("Completed loadGalleries");
        
        console.log("Starting loadGalleryCheckboxes...");
        await loadGalleryCheckboxes();
        console.log("Completed loadGalleryCheckboxes");
        
        console.log("Starting loadAdminData...");
        await loadAdminData();
        console.log("Completed loadAdminData");
        
        // Add image preview listener
        const recognitionImage = document.getElementById('recognitionImage');
        if (recognitionImage) {
            console.log("Adding recognition image change listener");
            recognitionImage.addEventListener('change', previewImage);
        }
        
        // Add recognize button listener
        const btnRecognize = document.getElementById('btnRecognize');
        if (btnRecognize) {
            console.log("Adding recognize button click listener");
            btnRecognize.removeEventListener('click', performRecognition);
            btnRecognize.addEventListener('click', performRecognition);
        }
        
        // Update recognize button state initially
        updateRecognizeButtonState();
        
        console.log("Application initialization complete");
        
    } catch (error) {
        console.error("Error during application initialization:", error);
        showAlert('error', 'Failed to initialize application properly: ' + error.message);
    }
}


// Load batch years and departments for dropdowns
async function loadBatchYearsAndDepartments() {
    try {
        console.log("Loading batch years and departments...");
        const response = await fetch(`${API_BASE_URL}/batches`);
        
        if (!response.ok) {
            throw new Error(`HTTPS ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log("Received data:", data);

        // Populate Batch Year dropdowns
        const batchYearSelects = ['batchYear', 'galleryYear'];
        batchYearSelects.forEach(selectId => {
            const select = document.getElementById(selectId);
            if (select) {
                select.innerHTML = '<option value="" selected disabled>Select Batch Year</option>';
                if (data.years && data.years.length > 0) {
                    data.years.forEach(year => {
                        select.innerHTML += `<option value="${year}">${year}</option>`;
                    });
                    console.log(`Populated ${selectId} with ${data.years.length} years`);
                } else {
                    console.warn(`No years data found for ${selectId}`);
                }
            } else {
                console.warn(`Element with ID ${selectId} not found`);
            }
        });

        // Populate Department dropdowns
        const departmentSelects = ['department', 'galleryDepartment'];
        departmentSelects.forEach(selectId => {
            const select = document.getElementById(selectId);
            if (select) {
                select.innerHTML = '<option value="" selected disabled>Select Department</option>';
                if (data.departments && data.departments.length > 0) {
                    data.departments.forEach(dept => {
                        select.innerHTML += `<option value="${dept.id}">${dept.name} (${dept.id})</option>`;
                    });
                    console.log(`Populated ${selectId} with ${data.departments.length} departments`);
                } else {
                    console.warn(`No departments data found for ${selectId}`);
                }
            } else {
                console.warn(`Element with ID ${selectId} not found`);
            }
        });

        // Show success message only on initial load
        if (data.years && data.years.length > 0 && data.departments && data.departments.length > 0) {
            console.log("Successfully loaded batch years and departments");
        }

    } catch (error) {
        console.error('Error loading batch years and departments:', error);
        showAlert('error', `Failed to load batch years and departments: ${error.message}`);
        
        // Set placeholder text for failed loads
        const allSelects = ['batchYear', 'galleryYear', 'department', 'galleryDepartment'];
        allSelects.forEach(selectId => {
            const select = document.getElementById(selectId);
            if (select) {
                select.innerHTML = '<option value="" disabled>Failed to load data</option>';
            }
        });
    }
}

// Load galleries for the galleries section - Simple file-based approach
async function loadGalleries() {
    const galleriesList = document.getElementById('galleriesList');
    const galleriesPlaceholder = document.getElementById('galleriesPlaceholder');
    
    if (!galleriesList) {
        console.error('galleriesList element not found in DOM');
        return;
    }
    
    console.log("Loading galleries...");
    try {
        // Load from file-based listing
        const response = await fetch(`${API_BASE_URL}/galleries`);
        const data = await response.json();
        console.log("Gallery data:", data);
        
        if (galleriesPlaceholder) {
            galleriesPlaceholder.style.display = 'none';
        }
        
        if (!data.galleries || data.galleries.length === 0) {
            console.log("No galleries found");
            galleriesList.innerHTML = '<div class="alert alert-info">No galleries available. Process some videos first.</div>';
            return;
        }
        
        // Clear the list
        galleriesList.innerHTML = '';
        console.log(`Found ${data.galleries.length} gallery files. Adding to list...`);
        
        // Add each gallery file
        for (const galleryFile of data.galleries) {
            // Extract year and department from filename
            const parts = galleryFile.replace('gallery_', '').replace('.pth', '').split('_');
            const department = parts[0];
            const year = parts[1];
            
            if (!department || !year) {
                console.warn(`Invalid gallery filename format: ${galleryFile}`);
                continue;
            }
            
            const listItem = document.createElement('a');
            listItem.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
            listItem.href = '#';
            listItem.setAttribute('data-year', year);
            listItem.setAttribute('data-department', department);
            
            listItem.innerHTML = `
                <div>
                    <h5 class="mb-1">${department} - ${year} </h5>
                    <small class="text-muted">Click to view details</small>
                </div>
                <div class="d-flex align-items-center">
                    <span class="badge bg-primary rounded-pill me-2 gallery-count">...</span>
                    <button class="btn btn-outline-danger btn-sm delete-gallery-btn ms-2" title="Delete Gallery">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            `;
            
            // Add click event for details
            listItem.addEventListener('click', async function(e) {
                e.preventDefault();
                const year = this.getAttribute('data-year');
                const department = this.getAttribute('data-department');
                
                // Fetch gallery details
                try {
                    const detailResponse = await fetch(`${API_BASE_URL}/galleries/${year}/${department}`);
                    const galleryInfo = await detailResponse.json();
                    
                    // Show gallery details
                    showGalleryDetailsModal(department, year, galleryInfo);
                } catch (error) {
                    console.error('Error fetching gallery details:', error);
                    showAlert('error', 'Failed to load gallery details');
                }
            });
            
            // Add click event for delete button
            const deleteBtn = listItem.querySelector('.delete-gallery-btn');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', async function(e) {
                    e.stopPropagation();
                    if (!confirm(`Are you sure you want to delete gallery for ${department} ${year}?`)) return;
                    try {
                        const response = await fetch(`${API_BASE_URL}/galleries/${year}/${department}`, { method: 'DELETE' });
                        if (!response.ok) {
                            const errData = await response.json().catch(() => ({}));
                            throw new Error(errData.detail || 'Failed to delete gallery');
                        }
                        showToast('success', `Deleted gallery for ${department} ${year}`, { duration: 3000 });
                        // Reload galleries list
                        await loadGalleries();
                    } catch (error) {
                        console.error('Error deleting gallery:', error);
                        showToast('error', error.message || 'Error deleting gallery', { duration: 5000 });
                    }
                });
            }
            
            galleriesList.appendChild(listItem);
            
            // Fetch count for this gallery
            fetchGalleryCount(department, year, listItem.querySelector('.gallery-count'));
        }
        
    } catch (error) {
        console.error('Error loading galleries:', error);
        galleriesList.innerHTML = '<div class="alert alert-danger">Failed to load galleries: ' + error.message + '</div>';
    }
}

// Fetch gallery count
async function fetchGalleryCount(department, year, countElement) {
    try {
        const response = await fetch(`${API_BASE_URL}/galleries/${year}/${department}`);
        const galleryInfo = await response.json();
        countElement.textContent = galleryInfo.count;
    } catch (error) {
        console.error(`Error fetching count for ${department} ${year}:`, error);
        countElement.textContent = 'N/A';
    }
}

// Add a specific function to check and update the recognize button state
function updateRecognizeButtonState() {
    const btnRecognize = document.getElementById('btnRecognize');
    if (!btnRecognize) return;
    
    const hasImage = document.getElementById('recognitionImage') && 
                    document.getElementById('recognitionImage').files.length > 0;
    const hasSelectedGalleries = document.querySelector('.gallery-checkbox:checked');
    
    console.log('Update recognize button state:', {hasImage, hasSelectedGalleries});
    
    // Enable button only if there's both an image AND at least one gallery selected
    btnRecognize.disabled = !(hasImage && hasSelectedGalleries);
}

// Load gallery checkboxes for recognition section
async function loadGalleryCheckboxes() {
    const galleryCheckboxes = document.getElementById('galleryCheckboxes');
    if (!galleryCheckboxes) return;
    
    try {
        console.log("Loading gallery checkboxes...");
        const response = await fetch(`${API_BASE_URL}/galleries`);
        const data = await response.json();
        
        console.log("Gallery checkboxes data:", data);
        
        galleryCheckboxes.innerHTML = '';
        
        if (!data.galleries || data.galleries.length === 0) {
            galleryCheckboxes.innerHTML = '<div class="alert alert-info">No galleries available. Process some videos first.</div>';
            return;
        }
        
        // Create checkbox for each gallery
        data.galleries.forEach(gallery => {
            // Extract year and department from filename
            // Format: gallery_DEPARTMENT_YEAR.pth
            const parts = gallery.replace('gallery_', '').replace('.pth', '').split('_');
            console.log(`Processing gallery checkbox for: ${gallery}, parts:`, parts);
            
            const department = parts[0];
            const year = parts[1];
            
            if (!department || !year) {
                console.warn(`Invalid gallery filename format: ${gallery}`);
                return;
            }
            
            const checkboxId = `gallery_cb_${department}_${year}`;
            
            const div = document.createElement('div');
            div.className = 'form-check';
            div.innerHTML = `
                <input class="form-check-input gallery-checkbox" type="checkbox" value="${gallery}" id="${checkboxId}">
                <label class="form-check-label" for="${checkboxId}">
                    ${department} - ${year} 
                </label>
            `;
            galleryCheckboxes.appendChild(div);
        });
        
        // Add event listeners to all checkboxes
        document.querySelectorAll('.gallery-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                updateRecognizeButtonState();
            });
        });
        
        // Update button state initially
        updateRecognizeButtonState();
        
        console.log(`Added ${data.galleries.length} gallery checkboxes`);
    } catch (error) {
        console.error('Error loading gallery checkboxes:', error);
        galleryCheckboxes.innerHTML = '<div class="alert alert-danger">Failed to load galleries: ' + error.message + '</div>';
    }
}

// Preview uploaded image
function previewImage(event) {
    const imagePreview = document.getElementById('imagePreview');
    if (!imagePreview) {
        console.error('Image preview element not found');
        return;
    }
    
    const file = event.target.files[0];
    if (!file) {
        console.log('No file selected');
        return;
    }
    
    console.log('Previewing image:', file.name);
    
    const reader = new FileReader();
    reader.onload = function(e) {
        console.log('Image loaded into reader');
        imagePreview.src = e.target.result;
        
        // Update recognize button state
        updateRecognizeButtonState();
    };
    
    reader.onerror = function(e) {
        console.error('Error reading file:', e);
        showAlert('error', 'Failed to load image preview');
    };
    
    reader.readAsDataURL(file);
}

// Updated performRecognition function with better debugging
async function performRecognition() {
    console.log("Perform recognition called");
    
    // Get selected galleries
    const selectedGalleries = Array.from(document.querySelectorAll('.gallery-checkbox:checked'))
        .map(cb => cb.value);
    
    console.log("Selected galleries:", selectedGalleries);
    
    if (selectedGalleries.length === 0) {
        console.error("No galleries selected");
        showAlert('error', 'Please select at least one gallery');
        return;
    }
    
    // Get uploaded image
    const imageInput = document.getElementById('recognitionImage');
    if (!imageInput || !imageInput.files[0]) {
        console.error("No image uploaded");
        showAlert('error', 'Please upload an image');
        return;
    }
    
    console.log("Image selected:", imageInput.files[0].name);
    
    // Create form data
    const formData = new FormData();
    formData.append('image', imageInput.files[0]);
    formData.append('threshold', 0.45); // Fixed threshold
    
    // Add selected galleries
    selectedGalleries.forEach(gallery => {
        formData.append('galleries', gallery);
    });
    
    // Show loading state
    const recognitionResults = document.getElementById('recognitionResults');
    recognitionResults.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p>Processing...</p>
        </div>
    `;
    
    // Send request
    try {
        console.log("Sending recognition request...");
        const response = await fetch(`${API_BASE_URL}/recognize`, {
            method: 'POST',
            body: formData
        });
        
        console.log("Recognition response status:", response.status);
        
        if (!response.ok) {
            let errorMessage = 'Failed to process image';
            try {
                const error = await response.json();
                errorMessage = error.detail || errorMessage;
            } catch (e) {
                console.error("Failed to parse error response:", e);
            }
            throw new Error(errorMessage);
        }
        
        const result = await response.json();
        console.log("Recognition result received:", result);
        
        // Display result image
        const resultImage = document.getElementById('resultImage');
        if (resultImage) {
            resultImage.src = `data:image/jpeg;base64,${result.image}`;
            console.log("Updated result image");
        } else {
            console.error("Result image element not found");
        }
        
        // Display detected faces
        let resultsHTML = '<h5>Recognition Results:</h5>';
        
        if (result.faces.length === 0) {
            resultsHTML += '<p>No faces detected</p>';
        } else {
            resultsHTML += '<ul class="list-group">';
            result.faces.forEach(face => {
                if (face.identity === 'Unknown') {
                    resultsHTML += `
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>Unknown person</span>
                        </li>
                    `;
                } else {
                    resultsHTML += `
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>${face.identity}</span>
                            <span class="badge bg-success">${(face.similarity * 100).toFixed(1)}% match</span>
                        </li>
                    `;
                }
            });
            resultsHTML += '</ul>';
        }
        
        recognitionResults.innerHTML = resultsHTML;
        console.log("Updated recognition results");
    } catch (error) {
        console.error('Error performing recognition:', error);
        recognitionResults.innerHTML = '<div class="alert alert-danger">Failed to process image: ' + error.message + '</div>';
    }
}

// Function to activate a section
function activateSection(sectionId) {
    console.log(`Activating section: ${sectionId}`);
    
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Show the selected section
    const selectedSection = document.getElementById(sectionId);
    if (selectedSection) {
        selectedSection.classList.add('active');
    } else {
        console.error(`Section with ID "${sectionId}" not found`);
    }
    
    // Perform specific actions for certain sections
    if (sectionId === 'galleries') {
        console.log("Galleries section activated, reloading galleries list");
        loadGalleries();
    } else if (sectionId === 'recognition') {
        console.log("Recognition section activated, reloading gallery checkboxes");
        loadGalleryCheckboxes();
    } else if (sectionId === 'createGalleries') {
        console.log("Create Galleries section activated, loading processed datasets");
        loadProcessedDatasets();
    } else if (sectionId === 'admin') {
        console.log("Admin section activated, loading admin data");
        loadAdminData();
    }
    
    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-section') === sectionId) {
            link.classList.add('active');
        }
    });
}

// Load admin data
async function loadAdminData() {
    try {
        const response = await fetch(`${API_BASE_URL}/database/stats`);
        const data = await response.json();

        // Update batch years count and list
        const batchYearsCount = document.getElementById('batchYearsCount');
        if (batchYearsCount) {
            batchYearsCount.textContent = data.batch_years_count;
        }

        const batchYearsList = document.getElementById('batchYearsList');
        if (batchYearsList) {
            batchYearsList.innerHTML = '';
            
            const yearsResponse = await fetch(`${API_BASE_URL}/batches`);
            const yearsData = await yearsResponse.json();
            
            yearsData.years.forEach(year => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `
                    <div class="d-flex align-items-center">
                        <i class="fas fa-graduation-cap text-primary me-3"></i>
                        <span class="fw-medium">${year}</span>
                    </div>
                    <button class="btn btn-sm btn-danger delete-batch-year" data-year="${year}">
                        <i class="fas fa-trash"></i>
                    </button>
                `;
                batchYearsList.appendChild(li);
            });
            
            // Add event listeners to delete buttons
            document.querySelectorAll('.delete-batch-year').forEach(button => {
                button.addEventListener('click', function() {
                    deleteBatchYear(this.getAttribute('data-year'));
                });
            });
        }

        // Update departments count and list
        const departmentsCount = document.getElementById('departmentsCount');
        if (departmentsCount) {
            departmentsCount.textContent = data.departments_count;
        }

        const departmentsList = document.getElementById('departmentsList');
        if (departmentsList) {
            departmentsList.innerHTML = '';
            
            const deptResponse = await fetch(`${API_BASE_URL}/batches`);
            const deptData = await deptResponse.json();
            
            deptData.departments.forEach(dept => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `
                    <div class="d-flex align-items-center">
                        <i class="fas fa-university text-success me-3"></i>
                        <div>
                            <span class="fw-medium">${dept.name}</span>
                            <br>
                            <small class="text-muted">ID: ${dept.id}</small>
                        </div>
                    </div>
                    <button class="btn btn-sm btn-danger delete-department" data-dept-id="${dept.id}">
                        <i class="fas fa-trash"></i>
                    </button>
                `;
                departmentsList.appendChild(li);
            });
            
            // Add event listeners to delete buttons
            document.querySelectorAll('.delete-department').forEach(button => {
                button.addEventListener('click', function() {
                    deleteDepartment(this.getAttribute('data-dept-id'));
                });
            });
        }
        
    } catch (error) {
        console.error('Error loading admin data:', error);
        showAlert('error', 'Failed to load admin data');
    }
}

// Add new batch year
async function handleAddBatchYear(event) {
    event.preventDefault();
    const newBatchYear = document.getElementById('newBatchYear').value.trim();
    
    if (!newBatchYear) {
        showAlert('error', 'Batch year cannot be empty');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/batches/year`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ year: newBatchYear })
        });
        
        if (response.ok) {
            showAlert('success', `Added batch year: ${newBatchYear}`);
            document.getElementById('newBatchYear').value = '';
            await loadAdminData();
            await loadBatchYearsAndDepartments();
        } else {
            const error = await response.json();
            showAlert('error', error.detail || 'Failed to add batch year');
        }
    } catch (error) {
        console.error('Error adding batch year:', error);
        showAlert('error', 'Failed to add batch year');
    }
}

// Delete batch year
async function deleteBatchYear(year) {
    if (!confirm(`Are you sure you want to delete the batch year "${year}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/batches/year/${year}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showAlert('success', `Deleted batch year: ${year}`);
            await loadAdminData();
            await loadBatchYearsAndDepartments();
        } else {
            const error = await response.json();
            showAlert('error', error.detail || 'Failed to delete batch year');
        }
    } catch (error) {
        console.error('Error deleting batch year:', error);
        showAlert('error', 'Failed to delete batch year');
    }
}

// Add new department
async function handleAddDepartment(event) {
    event.preventDefault();
    console.log("Department form submitted");
    
    const newDepartmentId = document.getElementById('newDepartmentId').value.trim();
    const newDepartmentName = document.getElementById('newDepartment').value.trim();
    
    console.log("New department ID:", newDepartmentId);
    console.log("New department name:", newDepartmentName);
    
    if (!newDepartmentId || !newDepartmentName) {
        showAlert('error', 'Both Department ID and Department Name are required');
        return;
    }
    
    try {
        console.log("Sending request to add department:", { department_id: newDepartmentId, department: newDepartmentName });
        const response = await fetch(`${API_BASE_URL}/batches/department`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                department_id: newDepartmentId, 
                department: newDepartmentName 
            })
        });
        
        console.log("Response status:", response.status);
        
        if (response.ok) {
            showAlert('success', `Added department: ${newDepartmentName} (ID: ${newDepartmentId})`);
            document.getElementById('newDepartmentId').value = '';
            document.getElementById('newDepartment').value = '';
            await loadAdminData();
            await loadBatchYearsAndDepartments();
        } else {
            const error = await response.json();
            console.error("Error response:", error);
            showAlert('error', error.detail || 'Failed to add department');
        }
    } catch (error) {
        console.error('Error adding department:', error);
        showAlert('error', 'Failed to add department');
    }
}

// Delete department
async function deleteDepartment(departmentId) {
    if (!confirm(`Are you sure you want to delete this department?`)) {
        return;
    }
    
    console.log("Deleting department with ID:", departmentId);
    
    try {
        const response = await fetch(`${API_BASE_URL}/batches/department/${departmentId}`, {
            method: 'DELETE'
        });
        
        console.log("Response status:", response.status);
        
        if (response.ok) {
            // Remove immediately from UI
            const items = document.querySelectorAll(`#departmentsList li`);
            for (const item of items) {
                const deleteBtn = item.querySelector('.delete-department');
                if (deleteBtn && deleteBtn.getAttribute('data-dept-id') === departmentId) {
                    item.remove();
                    break;
                }
            }
            
            showAlert('success', `Department deleted successfully`);
            
            // Reload all data
            await loadAdminData();
            await loadBatchYearsAndDepartments();
        } else {
            let errorMessage = 'Failed to delete department';
            try {
                const error = await response.json();
                errorMessage = error.detail || errorMessage;
            } catch (e) {
                console.error("Error parsing error response:", e);
            }
            showAlert('error', errorMessage);
        }
    } catch (error) {
        console.error('Error deleting department:', error);
        showAlert('error', 'Network error while deleting department');
    }
}

// Handle process videos form submission (OLD - deprecated in favor of new workflow)
/* async function handleProcessVideos(event) {
    event.preventDefault();
    console.log("Process videos form submitted");
    
    // Get form values
    const year = document.getElementById('batchYear').value;
    const department = document.getElementById('department').value;
    const videosDir = document.getElementById('videosDir').value;
    
    if (!year || !department || !videosDir) {
        showAlert('error', 'Please fill out all required fields');
        return;
    }
    
    // Show processing indicator
    const processingResult = document.getElementById('processingResult');
    processingResult.innerHTML = `
        <div class="alert alert-info">
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            Processing videos... This may take several minutes.
        </div>
    `;
    
    // Disable submit button
    const btnProcess = document.getElementById('btnProcess');
    if (btnProcess) {
        btnProcess.disabled = true;
        btnProcess.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Processing...';
    }
    
    try {
        // Create form data
        const formData = new FormData();
        formData.append('year', year);
        formData.append('department', department);
        formData.append('videos_dir', videosDir);
        
        // Send request
        const response = await fetch(`${API_BASE_URL}/process`, {
            method: 'POST',
            body: formData
        });
        
        console.log("Process response status:", response.status);
        
        if (!response.ok) {
            let errorMessage = 'Failed to process videos';
            try {
                const error = await response.json();
                errorMessage = error.detail || errorMessage;
            } catch (e) {
                console.error("Error parsing process response:", e);
            }
            throw new Error(errorMessage);
        }
        
        const result = await response.json();
        console.log("Process result:", result);
        
        // Display results
        let resultHTML = '<div class="alert alert-success">';
        resultHTML += '<h5 class="mb-3">Processing Completed</h5>';
        resultHTML += `<p>Videos have been processed and faces extracted. You can now create a gallery from this data.</p>`;
        resultHTML += `<ul class="list-unstyled">
            <li><strong>Videos Processed:</strong> ${result.processed_videos}</li>
            <li><strong>Frames Extracted:</strong> ${result.processed_frames}</li>
            <li><strong>Faces Detected:</strong> ${result.extracted_faces}</li>
        </ul>`;
        
        if (result.failed_videos && result.failed_videos.length > 0) {
            resultHTML += '<div class="mt-2">';
            resultHTML += '<strong>Failed Videos:</strong>';
            resultHTML += '<ul>';
            result.failed_videos.forEach(video => {
                resultHTML += `<li>${video}</li>`;
            });
            resultHTML += '</ul>';
            resultHTML += '</div>';
        }
        
        resultHTML += `<div class="mt-3">
            <a href="#" class="btn btn-success" onclick="activateSection('createGalleries'); loadProcessedDatasets();">
                <i class="fas fa-database me-2"></i>Create Gallery Now
            </a>
        </div>`;
        
        resultHTML += '</div>';
        processingResult.innerHTML = resultHTML;
    } catch (error) {
        console.error('Error processing videos:', error);
        processingResult.innerHTML = `
            <div class="alert alert-danger">
                Error: ${error.message || 'Failed to process videos'}
            </div>
        `;
    } finally {
        // Re-enable submit button
        if (btnProcess) {
            btnProcess.disabled = false;
            btnProcess.innerHTML = '<i class="fas fa-cog me-2"></i>Process Videos';
        }
    }
}
*/

// Function to handle gallery creation/update
async function handleCreateGallery(event) {
    event.preventDefault();
    console.log("Create gallery form submitted");
    
    // Get form values
    const year = document.getElementById('galleryYear').value;
    const department = document.getElementById('galleryDepartment').value;
    const updateExisting = document.getElementById('updateExisting').checked;
    
    if (!year || !department) {
        showAlert('error', 'Please select batch year and department');
        return;
    }
    
    // Show processing indicator
    const galleryCreationResult = document.getElementById('galleryCreationResult');
    galleryCreationResult.innerHTML = `
        <div class="alert alert-info">
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            Creating gallery... This may take some time.
        </div>
    `;
    
    // Disable submit button
    const btnCreateGallery = document.getElementById('btnCreateGallery');
    btnCreateGallery.disabled = true;
    btnCreateGallery.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Creating...';
    
    try {
        // Create form data
        const formData = new FormData();
        formData.append('year', year);
        formData.append('department', department);
        formData.append('update_existing', updateExisting);
        
        // Send request
        const response = await fetch(`${API_BASE_URL}/galleries/create`, {
            method: 'POST',
            body: formData
        });
        
        console.log("Gallery creation response status:", response.status);
        
        if (!response.ok) {
            let errorMessage = 'Failed to create gallery';
            try {
                const error = await response.json();
                errorMessage = error.detail || errorMessage;
            } catch (e) {
                console.error("Error parsing creation response:", e);
            }
            throw new Error(errorMessage);
        }
        
        const result = await response.json();
        console.log("Gallery creation result:", result);
        
        // Display results
        galleryCreationResult.innerHTML = `
            <div class="alert alert-success">
                <h5 class="mb-3">Gallery Created/Updated</h5>
                <ul class="list-unstyled">
                    <li><strong>Message:</strong> ${result.message}</li>
                    <li><strong>Identities:</strong> ${result.identities_count}</li>
                    <li><strong>Path:</strong> ${result.gallery_path}</li>
                </ul>
            </div>
        `;
        
        // Refresh galleries list
        await loadGalleries();
        
    } catch (error) {
        console.error('Error creating gallery:', error);
        galleryCreationResult.innerHTML = `
            <div class="alert alert-danger">
                Error: ${error.message || 'Failed to create gallery'}
            </div>
        `;
    } finally {
        // Re-enable submit button
        btnCreateGallery.disabled = false;
        btnCreateGallery.innerHTML = '<i class="fas fa-database me-2"></i>Create/Update Gallery';
    }
}

// Function to load processed datasets
async function loadProcessedDatasets() {
    const processedDatasets = document.getElementById('processedDatasets');
    if (!processedDatasets) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/check-directories`);
        const data = await response.json();
        
        // Format and display the processed datasets
        let html = '';
        
        if (data.data_dir_exists && Array.isArray(data.data_dir_files) && data.data_dir_files.length > 0) {
            html += '<div class="list-group">';
            
            // Filter only directories (batch_dept structure)
            let datasets = data.data_dir_files.filter(file => !file.includes('.'));
            datasets = datasets.sort((a, b) => a.localeCompare(b));
            
            if (datasets.length === 0) {
                html = '<div class="alert alert-info">No processed datasets found. Process videos first.</div>';
            } else {
                datasets.forEach(dataset => {
                    // Extract department and year from the dataset name (format: DEPT_YEAR)
                    const parts = dataset.split('_');
                    const department = parts[0] || 'Unknown';
                    const year = parts[1] || 'Unknown';
                    
                    html += `
                        <a href="#" class="list-group-item list-group-item-action" 
                           onclick="selectDatasetForGallery('${year}', '${department}')">
                            <div class="d-flex w-100 justify-content-between">
                                <h5 class="mb-1">${department} - ${year} </h5>
                            </div>
                            <small class="text-muted">Click to select for gallery creation</small>
                        </a>
                    `;
                });
            }
            
            html += '</div>';
        } else {
            html = '<div class="alert alert-info">No processed datasets found. Process videos first.</div>';
        }
        
        processedDatasets.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading processed datasets:', error);
        processedDatasets.innerHTML = '<div class="alert alert-danger">Failed to load processed datasets</div>';
    }
}

// Function to select a dataset for gallery creation
function selectDatasetForGallery(year, department) {
    // Set the dropdown values
    const yearSelect = document.getElementById('galleryYear');
    const deptSelect = document.getElementById('galleryDepartment');
    
    if (yearSelect && deptSelect) {
        // Set department and year
        Array.from(yearSelect.options).forEach(option => {
            if (option.value === year) {
                yearSelect.value = year;
            }
        });
        
        Array.from(deptSelect.options).forEach(option => {
            if (option.value === department) {
                deptSelect.value = department;
            }
        });
        
        // Scroll to form
        document.getElementById('createGalleryForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/**
 * Toast Notification System
 * A modern, customizable toast notification system with different styles and options
 */

// Global counter for unique toast IDs
let toastCounter = 0;

// Toast configuration - can be customized
const toastConfig = {
    duration: 5000,       // Default duration in ms
    position: 'top-end',  // Position of toasts (top-end, top-center, bottom-end, bottom-center)
    maxToasts: 5,         // Maximum number of toasts to display at once
    newestOnTop: true     // Whether to show newest toasts on top
};

// Ensure toast container exists with proper positioning
function createToastContainer() {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        
        // Set position based on configuration
        if (toastConfig.position === 'top-end') {
            container.style.top = '20px';
            container.style.right = '20px';
            container.style.left = 'auto';
            container.style.bottom = 'auto';
        } else if (toastConfig.position === 'top-center') {
            container.style.top = '20px';
            container.style.left = '50%';
            container.style.transform = 'translateX(-50%)';
            container.style.right = 'auto';
            container.style.bottom = 'auto';
        } else if (toastConfig.position === 'bottom-end') {
            container.style.bottom = '20px';
            container.style.right = '20px';
            container.style.top = 'auto';
            container.style.left = 'auto';
        } else if (toastConfig.position === 'bottom-center') {
            container.style.bottom = '20px';
            container.style.left = '50%';
            container.style.transform = 'translateX(-50%)';
            container.style.top = 'auto';
            container.style.right = 'auto';
        }
        
        document.body.appendChild(container);
    }
    
    // Limit number of toasts if needed
    const toasts = container.querySelectorAll('.toast');
    if (toasts.length >= toastConfig.maxToasts) {
        // Remove oldest toast to make room
        if (toastConfig.newestOnTop) {
            container.removeChild(container.lastChild);
        } else {
            container.removeChild(container.firstChild);
        }
    }
    
    return container;
}

/**
 * Show a toast notification
 * @param {string} type - The toast type: 'success', 'error', 'warning', 'info'
 * @param {string} message - The message to display
 * @param {Object} options - Optional configuration overrides
 * @param {number} options.duration - Duration in ms to show the toast
 * @param {string} options.title - Optional title for the toast
 * @param {boolean} options.closeButton - Whether to show a close button
 * @param {function} options.onClose - Callback when toast is closed
 */
function showToast(type, message, options = {}) {
    const container = createToastContainer();
    const toastId = `toast-${Date.now()}-${toastCounter++}`;
    
    // Determine toast type and styles
    let toastClass, iconClass, title;
    
    switch(type) {
        case 'success':
            toastClass = 'toast-success';
            iconClass = 'fa-check-circle';
            title = options.title || 'Success';
            break;
        case 'error':
            toastClass = 'toast-error';
            iconClass = 'fa-exclamation-circle';
            title = options.title || 'Error';
            break;
        case 'warning':
            toastClass = 'toast-warning';
            iconClass = 'fa-exclamation-triangle';
            title = options.title || 'Warning';
            break;
        case 'info':
        default:
            toastClass = 'toast-info';
            iconClass = 'fa-info-circle';
            title = options.title || 'Information';
            break;
    }
    
    // Create the toast element
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast ${toastClass}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    // Add the show class immediately to display the toast
    toast.classList.add('show');
    
    // Determine if we should show the title/header
    const showHeader = options.title !== false;
    
    // Create toast content
    let toastHTML = '';
    
    if (showHeader) {
        toastHTML += `
            <div class="toast-header">
                <i class="fas ${iconClass} me-2"></i>
                <strong class="me-auto">${title}</strong>
                <small>${options.timestamp || new Date().toLocaleTimeString()}</small>
                ${options.closeButton !== false ? '<button type="button" class="btn-close ms-2" aria-label="Close"></button>' : ''}
            </div>
        `;
    }
    
    toastHTML += `
        <div class="toast-body">
            <div class="d-flex align-items-center">
                ${!showHeader ? `<div class="toast-icon"><i class="fas ${iconClass}"></i></div>` : ''}
                <div>${message}</div>
                ${!showHeader && options.closeButton !== false ? '<button type="button" class="btn-close ms-auto" aria-label="Close"></button>' : ''}
            </div>
        </div>
        <div class="toast-progress"></div>
    `;
    
    toast.innerHTML = toastHTML;
    
    // Handle inserting based on newest position preference
    if (toastConfig.newestOnTop) {
        container.insertBefore(toast, container.firstChild);
    } else {
        container.appendChild(toast);
    }
    
    // Add click event to close button if it exists
    const closeBtn = toast.querySelector('.btn-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            dismissToast(toast, options.onClose);
        });
    }
    
    // Try to initialize using Bootstrap's Toast API if available
    try {
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const bsToast = new bootstrap.Toast(toast, {
                autohide: true,
                delay: options.duration || toastConfig.duration
            });
            bsToast.show();
        } else {
            // Fallback to our manual implementation
            const duration = options.duration || toastConfig.duration;
            setTimeout(() => {
                dismissToast(toast, options.onClose);
            }, duration);
        }
    } catch (e) {
        console.error('Error initializing Bootstrap toast:', e);
        // Fallback to our manual implementation
        const duration = options.duration || toastConfig.duration;
        setTimeout(() => {
            dismissToast(toast, options.onClose);
        }, duration);
    }
    
    // Return the toast ID so it can be referenced later
    return toastId;
}

/**
 * Helper function to dismiss a toast with animation
 */
function dismissToast(toast, callback) {
    if (!toast || toast.classList.contains('fade-out')) return;
    
    toast.classList.add('fade-out');
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
            if (typeof callback === 'function') callback();
        }
    }, 300);
}

/**
 * Maintain backward compatibility with existing showAlert function
 * by making it call our new showToast function
 */
function showAlert(type, message) {
    // Convert old type parameter to new format
    let toastType;
    switch (type) {
        case 'error':
            toastType = 'error';
            break;
        case 'success':
            toastType = 'success';
            break;
        case 'warning':
            toastType = 'warning';
            break;
        default:
            toastType = 'info';
    }
    
    // Call new function with equivalent parameters
    return showToast(toastType, message, {
        title: false, // Don't show header for backward compatibility
        closeButton: true
    });
}

// Make functions available globally so they can be used from other scripts
window.showToast = showToast;
window.showAlert = showAlert;
window.showPageAlert = showPageAlert;

/**
 * Show an in-page alert message (as opposed to toast notifications)
 * This replaces the showAlertMessage function from dropdown-debug.js
 * @param {string} message - Message to display
 * @param {string} type - Alert type: 'info', 'success', 'warning', 'danger'
 */
function showPageAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Find a good place to show the alert
    const target = document.querySelector('.content-section.active .card-body');
    if (target) {
        target.insertBefore(alertDiv, target.firstChild);
    } else {
        document.body.insertBefore(alertDiv, document.body.firstChild);
    }
    
    // Auto-dismiss after 8 seconds
    setTimeout(() => {
        alertDiv.classList.remove('show');
        setTimeout(() => alertDiv.remove(), 300);
    }, 8000);
    
    // Return the alert div in case the caller wants to do something with it
    return alertDiv;
}


// Add this function to manually reload galleries
function manuallyReloadGalleries() {
    console.log("Manually reloading galleries...");
    loadGalleries().then(() => {
        console.log("Galleries reloaded.");
        showAlert('success', 'Galleries reloaded');
    }).catch(err => {
        console.error("Error reloading galleries:", err);
        showAlert('error', 'Failed to reload galleries');
    });
}

// Face Collection App Launcher Functions
let collectionAppWindow = null;

function launchCollectionApp() {
    console.log('launchCollectionApp called');
    
    // First, start the collection app server
    startCollectionAppServer()
        .then(() => {
            console.log('Collection app server started, waiting 3 seconds...');
            // Wait a moment for the server to fully start
            return new Promise(resolve => setTimeout(resolve, 3000));
        })
        .then(() => {
            console.log('Getting collection app config...');
            // Now get the config and open the app
            return fetch('/api/collection-app-config');
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTPS error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(config => {
            console.log('Loaded collection app config from server:', config);
            // Use the values from the server endpoint
            const host = config.host || 'localhost';
            const port = config.port || 5001;
            const url = `https://${host}:${port}`;
            console.log(`Attempting to launch Face Collection App at ${url}`);
            
            // Try to open the window and store the reference
            collectionAppWindow = window.open(url, 'faceCollectionApp');
            
            // Check if the window was actually opened
            if (!collectionAppWindow || collectionAppWindow.closed || typeof collectionAppWindow.closed === 'undefined') {
                // Window wasn't opened - likely blocked by popup blocker
                showAlert('warning', 'Pop-up blocked! Please allow pop-ups for this site and try again');
                console.warn('Window.open was blocked by the browser');
                
                // Provide a manual link for the user to click
                const manualLink = `<a href="${url}" target="_blank" class="alert-link">Click here to open the Face Collection App</a>`;
                showPageAlert(`${manualLink} (App server is running but pop-up was blocked)`, 'warning');
            } else {
                collectionAppWindow.focus(); // Focus the new window
                showAlert('success', 'Face Collection App opened in new tab');
            }
        })
        .catch(error => {
            console.error('Failed to launch collection app:', error);
            showAlert('error', 'Failed to start Face Collection App. Please check the console for details.');
        });
}

// Add API endpoint to start collection app server with state management
async function startCollectionAppServer() {
    console.log('startCollectionAppServer called');
    
    try {
        showAlert('info', 'Starting Face Collection App server...');
        
        console.log('Making POST request to /api/start-collection-app');
        const response = await fetch('/api/start-collection-app', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        console.log('Response received:', response.status, response.statusText);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Response error:', errorText);
            throw new Error(`HTTPS error! Status: ${response.status} - ${errorText}`);
        }
        
        const result = await response.json();
        console.log('Collection app server start result:', result);
        
        if (result.success) {
            showAlert('success', result.message);
            // Update status after successful start with a longer delay
            setTimeout(() => {
                console.log('Checking status after server start completion...');
                checkCollectionAppStatus();
            }, 3000);
            return result;
        } else {
            throw new Error(result.message || 'Failed to start collection app server');
        }
    } catch (error) {
        console.error('Error starting collection app server:', error);
        showAlert('error', `Failed to start collection app server: ${error.message}`);
        throw error;
    }
}

// Add manual status check function with throttling
async function checkCollectionAppStatus() {
    try {
        console.log('Checking collection app status...');
        const response = await fetch('/api/collection-app-status');
        
        if (!response.ok) {
            throw new Error(`HTTPS error! Status: ${response.status}`);
        }
        
        const status = await response.json();
        console.log('Collection app status response:', status);
        
        // Update UI based on status
        const statusElement = document.getElementById('collection-app-status');
        const statusIndicator = document.getElementById('statusIndicator');
        
        if (statusElement) {
            if (status.running) {
                statusElement.textContent = `Running`;
                statusElement.className = 'ms-1 text-success';
                console.log('Status updated to running, showing access link');
                
                // Get config for host/port to show access link
                try {
                    const configResponse = await fetch('/api/collection-app-config');
                    const config = await configResponse.json();
                    console.log('Config loaded:', config);
                    showCollectionAppLink(config.host, config.port);
                } catch (configError) {
                    console.error('Error getting config:', configError);
                }
            } else {
                statusElement.textContent = 'Not Running';
                statusElement.className = 'ms-1 text-muted';
                console.log('Status updated to not running, hiding access link');
                
                // Hide access link when not running
                hideCollectionAppLink();
            }
        }
        
        if (statusIndicator) {
            if (status.running) {
                statusIndicator.className = 'fas fa-circle me-2 text-success';
            } else {
                statusIndicator.className = 'fas fa-circle me-2 text-danger';
            }
        }
        
        return status;
    } catch (error) {
        console.error('Error checking collection app status:', error);
        const statusElement = document.getElementById('collection-app-status');
        const statusIndicator = document.getElementById('statusIndicator');
        
        if (statusElement) {
            statusElement.textContent = 'Error checking status';
            statusElement.className = 'ms-1 text-warning';
        }
        
        if (statusIndicator) {
            statusIndicator.className = 'fas fa-circle me-2 text-warning';
        }
        
        hideCollectionAppLink();
        return { running: false, error: error.message };
    }
}

async function stopCollectionAppServer() {
    if (collectionAppState.isStopping) {
        console.log('Already stopping collection app, ignoring request');
        return;
    }
    
    collectionAppState.isStopping = true;
    
    try {
        updateCollectionAppStatus('Stopping...');
        const response = await fetch('/api/stop-collection-app', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showAlert('success', result.message);
                updateCollectionAppStatus('Not Running');
                // Hide the access link when stopped
                hideCollectionAppLink();
                // Refresh status after a short delay to confirm
                setTimeout(() => {
                    console.log('Checking status after stop...');
                    checkCollectionAppStatus();
                }, 2000);
            } else {
                showAlert('error', 'Failed to stop Face Collection App server: ' + result.message);
                // Check status to see actual state
                setTimeout(() => {
                    checkCollectionAppStatus();
                }, 1000);
            }
        }
    } catch (error) {
        console.error('Error stopping collection app server:', error);
        showAlert('error', 'Error stopping Face Collection App server');
        // Check status to see actual state
        setTimeout(() => {
            checkCollectionAppStatus();
        }, 1000);
    } finally {
        collectionAppState.isStopping = false;
    }
}

// Function to show collection app access link
function showCollectionAppLink(host, port) {
    console.log(`showCollectionAppLink called with host: ${host}, port: ${port}`);
    const url = `https://${host}:${port}`;
    
    // Check if link container already exists
    let linkContainer = document.getElementById('collection-app-link');
    
    if (!linkContainer) {
        console.log('Creating new link container');
        // Create link container
        linkContainer = document.createElement('div');
        linkContainer.id = 'collection-app-link';
        linkContainer.className = 'mt-3 p-3 bg-light border rounded';
        
        // Find the best place to insert it - try multiple strategies
        let insertionParent = null;
        let insertionPosition = null;
        
        // Strategy 1: After the app-status-container
        const statusContainer = document.querySelector('.app-status-container');
        if (statusContainer && statusContainer.parentNode) {
            console.log('Using strategy 1: after app-status-container');
            insertionParent = statusContainer.parentNode;
            insertionPosition = statusContainer.nextSibling;
        }
        
        // Strategy 2: In the collection section card body
        if (!insertionParent) {
            const collectionSection = document.getElementById('collection');
            if (collectionSection) {
                const cardBody = collectionSection.querySelector('.card-body');
                if (cardBody) {
                    console.log('Using strategy 2: in collection section card body');
                    insertionParent = cardBody;
                }
            }
        }
        
        // Strategy 3: After the button container
        if (!insertionParent) {
            const buttonContainer = document.querySelector('.d-flex.gap-3.flex-wrap');
            if (buttonContainer && buttonContainer.parentNode) {
                console.log('Using strategy 3: after button container');
                insertionParent = buttonContainer.parentNode;
                insertionPosition = buttonContainer.nextSibling;
            }
        }
        
        // Strategy 4: Fallback - append to collection section or body
        if (!insertionParent) {
            const collectionSection = document.getElementById('collection');
            if (collectionSection) {
                console.log('Using fallback strategy: append to collection section');
                insertionParent = collectionSection;
            } else {
                console.log('Using final fallback: append to body');
                insertionParent = document.body;
            }
        }
        
        // Insert the link container
        if (insertionPosition) {
            insertionParent.insertBefore(linkContainer, insertionPosition);
        } else {
            insertionParent.appendChild(linkContainer);
        }
        
        console.log('Link container inserted into DOM');
    } else {
        console.log('Using existing link container');
    }
    
    // Update link content
    linkContainer.innerHTML = `
        <div class="d-flex align-items-center justify-content-between">
            <div>
                <h6 class="mb-1 text-success">
                    <i class="fas fa-external-link-alt me-2"></i>
                    Face Collection App is Ready
                </h6>
                <small class="text-muted">Click to access the running application at ${host}:${port}</small>
            </div>
            <div>
                <a href="${url}" target="_blank" class="btn btn-success btn-sm me-2">
                    <i class="fas fa-external-link-alt me-1"></i>
                    Open App
                </a>
            </div>
        </div>
    `;
    
    linkContainer.style.display = 'block';
    console.log('Collection app link is now visible');
}

// Function to hide collection app access link
function hideCollectionAppLink() {
    console.log('hideCollectionAppLink called');
    const linkContainer = document.getElementById('collection-app-link');
    if (linkContainer) {
        linkContainer.style.display = 'none';
        console.log('Collection app link hidden');
    } else {
        console.log('No link container found to hide');
    }
}

function updateCollectionAppStatus(status) {
    const statusElement = document.getElementById('collection-app-status');
    const statusIndicator = document.getElementById('statusIndicator');
    
    if (statusElement) {
        statusElement.textContent = status;
        
        if (status === 'Running') {
            statusElement.className = 'ms-1 text-success';
            if (statusIndicator) {
                statusIndicator.className = 'fas fa-circle me-2 text-success';
            }
        } else if (status === 'Checking...' || status === 'Starting...' || status === 'Stopping...') {
            statusElement.className = 'ms-1 text-warning';
            if (statusIndicator) {
                statusIndicator.className = 'fas fa-circle me-2 text-warning';
            }
        } else {
            statusElement.className = 'ms-1 text-muted';
            if (statusIndicator) {
                statusIndicator.className = 'fas fa-circle me-2 text-secondary';
            }
        }
    }
}




// Enhanced launch function that tries to start the server if needed
const launchCollectionAppWithServer = debounce(async function() {
    if (collectionAppState.isStarting || collectionAppState.isStopping) {
        console.log('Collection app operation in progress, ignoring request');
        return;
    }
    
    updateCollectionAppStatus('Checking...');
    collectionAppState.isStarting = true;
    
    try {
        // First check if the app is already running
        const status = await checkCollectionAppStatus();
        
        if (status.running) {
            // Get config and launch
            const configResponse = await fetch('/api/collection-app-config');
            const config = await configResponse.json();
            const url = `https://${config.host}:${config.port}`;
            
            console.log(`Face Collection App is already running at ${url}`);
            
            // Try to open the window
            collectionAppWindow = window.open(url, 'faceCollectionApp');
            
            if (!collectionAppWindow || collectionAppWindow.closed || typeof collectionAppWindow.closed === 'undefined') {
                showAlert('warning', 'Pop-up blocked! Please allow pop-ups for this site or use the "Open App" button below.');
                showPageAlert(`<a href="${url}" target="_blank" class="alert-link">Click here to open the Face Collection App</a>`, 'info');
            } else {
                collectionAppWindow.focus();
                showAlert('success', 'Face Collection App opened in new tab');
            }
        } else {
            // Try to start the server
            updateCollectionAppStatus('Starting...');
            showAlert('info', 'Starting Face Collection App server...');
            await startCollectionAppServer();
            
            // Wait for server to start and then check status
            setTimeout(async () => {
                console.log('Checking status after server start...');
                const newStatus = await checkCollectionAppStatus();
                if (newStatus.running) {
                    showAlert('success', 'Face Collection App server started successfully! Use the "Open App" button to access it.');
                } else {
                    showAlert('warning', 'Server may still be starting. Please wait a moment and check status again.');
                }
            }, 4000); // Wait a bit longer for server to fully start
        }
    } catch (error) {
        console.error('Error in launchCollectionAppWithServer:', error);
        showAlert('error', `Failed to launch Face Collection App: ${error.message}`);
        updateCollectionAppStatus('Error');
    } finally {
        collectionAppState.isStarting = false;
    }
}, 1000);



// Enhanced gallery management functions - simplified
function addGalleryActionListeners() {
    // No additional action listeners needed for simple file-based galleries
    console.log("Gallery action listeners ready (simple mode)");
}



function showGalleryDetailsModal(department, year, galleryInfo) {
    // Create a simple modal-like alert with gallery details
    const identitiesList = galleryInfo.identities.slice(0, 10).join(', ');
    const moreText = galleryInfo.identities.length > 10 ? `... and ${galleryInfo.identities.length - 10} more` : '';
    
    const message = `Gallery Details:\n\n` +
                   `Department: ${department}\n` +
                   `Year: ${year}\n` +
                   `Total Identities: ${galleryInfo.count}\n\n` +
                   `Sample identities: ${identitiesList}${moreText}`;
    
    alert(message);
}

// Add event listener for new student data form
const selectStudentDataForm = document.getElementById('selectStudentDataForm');
if (selectStudentDataForm) {
    console.log("Student data form found");
    selectStudentDataForm.addEventListener('submit', handleLoadStudentData);
} else {
    console.log("Student data form not found");
}

// Add event listener for process student videos button
const btnProcessStudentVideos = document.getElementById('btnProcessStudentVideos');
if (btnProcessStudentVideos) {
    btnProcessStudentVideos.addEventListener('click', handleProcessStudentVideos);
}

// Add event listener for view pending students button
const btnViewPendingStudents = document.getElementById('btnViewPendingStudents');
if (btnViewPendingStudents) {
    btnViewPendingStudents.addEventListener('click', handleViewPendingStudents);
}

// Load available student data folders for the new workflow
async function loadStudentDataFolders() {
    try {
        console.log("Loading student data folders...");
        const response = await fetch(`${API_BASE_URL}/student-data/folders`);
        
        if (!response.ok) {
            console.error("Failed to load student data folders");
            return;
        }
        
        const data = await response.json();
        console.log("Student data folders:", data.folders);
        
        // Extract unique years and departments
        const years = [...new Set(data.folders.map(f => f.year))].sort();
        const depts = [...new Set(data.folders.map(f => f.dept))].sort();
        
        // Populate year dropdown
        const yearSelect = document.getElementById('studentBatchYear');
        if (yearSelect) {
            yearSelect.innerHTML = '<option value="" selected disabled>Select Batch Year</option>';
            years.forEach(year => {
                const option = document.createElement('option');
                option.value = year;
                option.textContent = year;
                yearSelect.appendChild(option);
            });
        }
        
        // Populate department dropdown
        const deptSelect = document.getElementById('studentDepartment');
        if (deptSelect) {
            deptSelect.innerHTML = '<option value="" selected disabled>Select Department</option>';
            depts.forEach(dept => {
                const option = document.createElement('option');
                option.value = dept;
                option.textContent = dept;
                deptSelect.appendChild(option);
            });
        }
        
    } catch (error) {
        console.error("Error loading student data folders:", error);
    }
}

// Handle load student data form submission
async function handleLoadStudentData(event) {
    event.preventDefault();
    console.log("Load student data form submitted");
    
    const year = document.getElementById('studentBatchYear').value;
    const department = document.getElementById('studentDepartment').value;
    
    if (!year || !department) {
        showAlert('error', 'Please select both batch year and department');
        return;
    }
    
    // Show loading indicator
    const btnLoad = document.getElementById('btnLoadStudentData');
    if (btnLoad) {
        btnLoad.disabled = true;
        btnLoad.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Loading...';
    }
    
    try {
        // Load student data summary
        const response = await fetch(`${API_BASE_URL}/student-data/${department}/${year}/summary`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load student data');
        }
        
        const summary = await response.json();
        console.log("Student data summary:", summary);
        
        // Update statistics display
        document.getElementById('totalStudents').textContent = summary.total_students;
        document.getElementById('studentsWithVideo').textContent = summary.students_with_video;
        document.getElementById('studentsPending').textContent = summary.students_pending;
        document.getElementById('studentsProcessed').textContent = summary.students_processed;
        
        // Show statistics section
        document.getElementById('studentDataStats').style.display = 'block';
        
        // Enable/disable process button based on pending count
        const btnProcess = document.getElementById('btnProcessStudentVideos');
        if (btnProcess) {
            btnProcess.disabled = summary.students_pending === 0;
            if (summary.students_pending > 0) {
                btnProcess.innerHTML = `<i class="fas fa-cog me-2"></i>Process ${summary.students_pending} Pending Videos`;
            } else {
                btnProcess.innerHTML = '<i class="fas fa-cog me-2"></i>No Videos to Process';
            }
        }
        
        // Store current selection for processing
        window.currentStudentData = { dept: department, year: year };
        
    } catch (error) {
        console.error("Error loading student data:", error);
        showAlert('error', error.message);
    } finally {
        if (btnLoad) {
            btnLoad.disabled = false;
            btnLoad.innerHTML = '<i class="fas fa-search me-2"></i>Load Student Data';
        }
    }
}

// Handle process student videos
async function handleProcessStudentVideos() {
    if (!window.currentStudentData) {
        showAlert('error', 'Please load student data first');
        return;
    }
    
    const { dept, year } = window.currentStudentData;
    
    // Show confirmation
    if (!confirm(`Are you sure you want to process all pending videos for ${dept} ${year}? This may take several minutes.`)) {
        return;
    }
    
    const btnProcess = document.getElementById('btnProcessStudentVideos');
    if (btnProcess) {
        btnProcess.disabled = true;
        btnProcess.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Processing...';
    }
    
    // Show processing indicator
    const processingResult = document.getElementById('processingResult');
    processingResult.innerHTML = `
        <div class="alert alert-info">
            <div class="spinner-border spinner-border-sm me-2" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            Processing student videos... This may take several minutes.
        </div>
    `;
    
    try {
        const response = await fetch(`${API_BASE_URL}/student-data/${dept}/${year}/process`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to process videos');
        }
        
        const result = await response.json();
        console.log("Processing result:", result);
        
        // Display results
        let resultHTML = '<div class="alert alert-success">';
        resultHTML += '<h5 class="mb-3">Processing Completed</h5>';
        resultHTML += `<p>${result.message}</p>`;
        resultHTML += `<ul class="list-unstyled">
            <li><strong>Processed:</strong> ${result.processed_count}</li>
            <li><strong>Total Pending:</strong> ${result.total_pending}</li>
        </ul>`;
        resultHTML += '</div>';
        
        processingResult.innerHTML = resultHTML;
        
        // Refresh the student data display
        setTimeout(() => {
            handleLoadStudentData(new Event('submit'));
        }, 1000);
        
    } catch (error) {
        console.error("Error processing videos:", error);
        processingResult.innerHTML = `
            <div class="alert alert-danger">
                <h5 class="mb-3">Processing Failed</h5>
                <p>${error.message}</p>
            </div>
        `;
    } finally {
        if (btnProcess) {
            btnProcess.disabled = false;
            btnProcess.innerHTML = '<i class="fas fa-cog me-2"></i>Process Pending Videos';
        }
    }
}

// Handle view pending students
async function handleViewPendingStudents() {
    if (!window.currentStudentData) {
        showAlert('error', 'Please load student data first');
        return;
    }
    
    const { dept, year } = window.currentStudentData;
    
    try {
        const response = await fetch(`${API_BASE_URL}/student-data/${dept}/${year}/pending`);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load pending students');
        }
        
        const data = await response.json();
        console.log("Pending students:", data.pending_students);
        
        const pendingList = document.getElementById('pendingStudentsList');
        const tableContainer = document.getElementById('pendingStudentsTable');
        
        if (data.pending_students.length === 0) {
            tableContainer.innerHTML = '<p class="text-muted">No pending students found.</p>';
        } else {
            let tableHTML = `
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Reg No</th>
                                <th>Name</th>
                                <th>Video Uploaded</th>
                                <th>Upload Time</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            data.pending_students.forEach(student => {
                const uploadTime = student.uploadTime ? new Date(student.uploadTime).toLocaleString() : 'N/A';
                tableHTML += `
                    <tr>
                        <td>${student.regNo}</td>
                        <td>${student.name}</td>
                        <td><span class="badge bg-success">Yes</span></td>
                        <td>${uploadTime}</td>
                    </tr>
                `;
            });
            
            tableHTML += '</tbody></table></div>';
            tableContainer.innerHTML = tableHTML;
        }
        
        pendingList.style.display = 'block';
        
    } catch (error) {
        console.error("Error loading pending students:", error);
        showAlert('error', error.message);
    }
}

