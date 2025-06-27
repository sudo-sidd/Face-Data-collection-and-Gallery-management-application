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
    console.log("DOM content loaded");
    
    // Navigation handling
    document.querySelectorAll('.nav-link, button[data-section]').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const section = this.getAttribute('data-section');
            activateSection(section);
            console.log(`Activated section: ${section}`);
            
            if (section === 'createGalleries') {
                loadProcessedDatasets();
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
                    console.log("Recognition button listener initialized");
                }
                
                // Update button state
                updateRecognizeButtonState();
            }
        });
    });
    
    // Add debug logging for forms
    console.log("Adding form event listeners");
    
    // Add event listeners for admin forms
    const addBatchYearForm = document.getElementById('addBatchYearForm');
    if (addBatchYearForm) {
        console.log("Batch year form found");
        addBatchYearForm.addEventListener('submit', handleAddBatchYear);
    } else {
        console.log("Batch year form not found");
    }
    
    const addDepartmentForm = document.getElementById('addDepartmentForm');
    if (addDepartmentForm) {
        console.log("Department form found");
        addDepartmentForm.addEventListener('submit', handleAddDepartment);
    } else {
        console.log("Department form not found");
    }
    
    // Add event listener for process videos form
    const processVideosForm = document.getElementById('processVideosForm');
    if (processVideosForm) {
        console.log("Adding event listener for process videos form");
        processVideosForm.addEventListener('submit', handleProcessVideos);
    } else {
        console.log("Process videos form not found");
    }
    
    // Add event listener for create gallery form
    const createGalleryForm = document.getElementById('createGalleryForm');
    if (createGalleryForm) {
        console.log("Adding event listener for create gallery form");
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
    
    // Add reload button to galleries section
    const galleriesCardHeader = document.querySelector('#galleries .card-header');
    if (galleriesCardHeader) {
        const reloadBtn = document.createElement('button');
        reloadBtn.className = 'btn btn-sm btn-light float-end';
        reloadBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Reload';
        reloadBtn.addEventListener('click', manuallyReloadGalleries);
        galleriesCardHeader.appendChild(reloadBtn);
    }
    
    // Add reload button to recognition section
    const galleryCheckboxesHeader = document.querySelector('#recognition h5:contains("Select Galleries")');
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
    
    // Initialize the application
    init();
});

// Initialize the application - update to include new gallery form selects
async function init() {
    await loadBatchYearsAndDepartments();
    await loadGalleries();
    await loadGalleryCheckboxes();
    await loadAdminData();
    
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
        btnRecognize.removeEventListener('click', performRecognition); // Remove any existing
        btnRecognize.addEventListener('click', performRecognition);
    }
    
    // Update recognize button state initially
    updateRecognizeButtonState();
}

// Replace the loadBatchYearsAndDepartments function with this version
async function loadBatchYearsAndDepartments() {
    console.log("Loading batch years and departments...");
    try {
        const response = await fetch(`${API_BASE_URL}/batches`);
        
        if (!response.ok) {
            console.error(`API request failed: ${response.status} ${response.statusText}`);
            const text = await response.text();
            console.error("Response text:", text);
            throw new Error(`API request failed: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("Batch years and departments data:", data);
        
        // Special handling for malformed data
        if (!data.years || !data.departments) {
            console.error("API response missing years or departments:", data);
            throw new Error("API response missing years or departments");
        }
        
        // Simple direct approach - update each dropdown manually
        
        // Gallery year select
        const galleryYearSelect = document.getElementById('galleryYear');
        if (galleryYearSelect) {
            galleryYearSelect.innerHTML = '<option value="" selected disabled>Select Batch Year</option>';
            for (const year of data.years) {
                galleryYearSelect.innerHTML += `<option value="${year}">${year} Year</option>`;
            }
            console.log(`Updated galleryYear with ${data.years.length} options`);
        } else {
            console.warn("galleryYear select not found in DOM");
        }
        
        // Gallery department select
        const galleryDeptSelect = document.getElementById('galleryDepartment');
        if (galleryDeptSelect) {
            galleryDeptSelect.innerHTML = '<option value="" selected disabled>Select Department</option>';
            for (const dept of data.departments) {
                galleryDeptSelect.innerHTML += `<option value="${dept}">${dept}</option>`;
            }
            console.log(`Updated galleryDepartment with ${data.departments.length} options`);
        } else {
            console.warn("galleryDepartment select not found in DOM");
        }
        
        // Process videos year select
        const batchYearSelect = document.getElementById('batchYear');
        if (batchYearSelect) {
            batchYearSelect.innerHTML = '<option value="" selected disabled>Select Batch Year</option>';
            for (const year of data.years) {
                batchYearSelect.innerHTML += `<option value="${year}">${year} Year</option>`;
            }
            console.log(`Updated batchYear with ${data.years.length} options`);
        } else {
            console.warn("batchYear select not found in DOM");
        }
        
        // Process videos department select
        const departmentSelect = document.getElementById('department');
        if (departmentSelect) {
            departmentSelect.innerHTML = '<option value="" selected disabled>Select Department</option>';
            for (const dept of data.departments) {
                departmentSelect.innerHTML += `<option value="${dept}">${dept}</option>`;
            }
            console.log(`Updated department with ${data.departments.length} options`);
        } else {
            console.warn("department select not found in DOM");
        }
        
        return true;
    } catch (error) {
        console.error('Error loading batch years and departments:', error);
        showAlert('error', `Failed to load batch years and departments: ${error.message}`);
        return false;
    }
}

// Load galleries for the galleries section
async function loadGalleries() {
    const galleriesList = document.getElementById('galleriesList');
    const galleriesPlaceholder = document.getElementById('galleriesPlaceholder');
    
    if (!galleriesList) {
        console.error('galleriesList element not found in DOM');
        return;
    }
    
    console.log("Loading galleries...");
    try {
        const response = await fetch(`${API_BASE_URL}/galleries`);
        console.log("Galleries API response status:", response.status);
        
        const data = await response.json();
        console.log("Galleries data:", data);
        
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
        console.log(`Found ${data.galleries.length} galleries. Adding to list...`);
        
        // Add each gallery
        for (const galleryFile of data.galleries) {
            // Extract year and department from filename
            // Format: gallery_DEPARTMENT_YEAR.pth
            const parts = galleryFile.replace('gallery_', '').replace('.pth', '').split('_');
            console.log(`Processing gallery file: ${galleryFile}, parts:`, parts);
            
            const department = parts[0];
            const year = parts[1];
            
            if (!department || !year) {
                console.warn(`Invalid gallery filename format: ${galleryFile}`);
                continue;
            }
            
            console.log(`Adding gallery for ${department} - ${year} Year`);
            
            const listItem = document.createElement('a');
            listItem.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
            listItem.href = '#';
            listItem.setAttribute('data-year', year);
            listItem.setAttribute('data-department', department);
            
            listItem.innerHTML = `
                <div>
                    <h5 class="mb-1">${department} - ${year} Year</h5>
                    <small class="text-muted">Click to view details</small>
                </div>
                <span class="badge bg-primary rounded-pill gallery-count">...</span>
            `;
            
            // Add click event
            listItem.addEventListener('click', async function(e) {
                e.preventDefault();
                const year = this.getAttribute('data-year');
                const department = this.getAttribute('data-department');
                
                // Fetch gallery details
                try {
                    const detailResponse = await fetch(`${API_BASE_URL}/galleries/${year}/${department}`);
                    const galleryInfo = await detailResponse.json();
                    
                    // Show modal with gallery details
                    // For simplicity, just show an alert
                    alert(`Gallery: ${department} - ${year} Year\nIdentities: ${galleryInfo.count}\n${galleryInfo.identities.join(', ')}`);
                } catch (error) {
                    console.error('Error fetching gallery details:', error);
                    showAlert('error', 'Failed to load gallery details');
                }
            });
            
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
                    ${department} - ${year} Year
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
        const response = await fetch(`${API_BASE_URL}/batches`);
        const data = await response.json();
        
        // Populate batch years list
        const batchYearsList = document.getElementById('batchYearsList');
        if (batchYearsList) {
            batchYearsList.innerHTML = '';
            
            data.years.forEach(year => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `
                    <span>${year} Year</span>
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
        
        // Populate departments list
        const departmentsList = document.getElementById('departmentsList');
        if (departmentsList) {
            departmentsList.innerHTML = '';
            
            data.departments.forEach(dept => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `
                    <span>${dept}</span>
                    <button class="btn btn-sm btn-danger delete-department" data-dept="${dept}">
                        <i class="fas fa-trash"></i>
                    </button>
                `;
                departmentsList.appendChild(li);
            });
            
            // Add event listeners to delete buttons
            document.querySelectorAll('.delete-department').forEach(button => {
                button.addEventListener('click', function() {
                    deleteDepartment(this.getAttribute('data-dept'));
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
    
    const newDepartment = document.getElementById('newDepartment').value.trim();
    console.log("New department value:", newDepartment);
    
    if (!newDepartment) {
        showAlert('error', 'Department cannot be empty');
        return;
    }
    
    try {
        console.log("Sending request to add department:", newDepartment);
        const response = await fetch(`${API_BASE_URL}/batches/department`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ department: newDepartment })
        });
        
        console.log("Response status:", response.status);
        
        if (response.ok) {
            showAlert('success', `Added department: ${newDepartment}`);
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
async function deleteDepartment(department) {
    if (!confirm(`Are you sure you want to delete the department "${department}"?`)) {
        return;
    }
    
    console.log("Deleting department:", department);
    
    try {
        const response = await fetch(`${API_BASE_URL}/batches/department/${department}`, {
            method: 'DELETE'
        });
        
        console.log("Response status:", response.status);
        
        if (response.ok) {
            // Remove immediately from UI
            const items = document.querySelectorAll(`#departmentsList li`);
            for (const item of items) {
                if (item.querySelector('span').textContent.trim() === department) {
                    item.remove();
                }
            }
            
            showAlert('success', `Deleted department: ${department}`);
            
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

// Handle process videos form submission
async function handleProcessVideos(event) {
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
            const datasets = data.data_dir_files.filter(file => !file.includes('.'));
            
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
                                <h5 class="mb-1">${department} - ${year} Year</h5>
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

// Helper function to show alerts
function showAlert(type, message) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : 'success'} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insert at the top of the current active section
    const activeSection = document.querySelector('.content-section.active');
    if (activeSection) {
        activeSection.insertBefore(alertDiv, activeSection.firstChild);
    }
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.classList.remove('show');
        setTimeout(() => alertDiv.remove(), 300);
    }, 5000);
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
    // Open the data collection app in a new window/tab
    window.open('http://localhost:5001', '_blank');
    showAlert('success', 'Face Collection App opened in new tab');
}

// Add manual status check function with throttling
async function checkCollectionAppStatus() {
    const now = Date.now();
    if (now - collectionAppState.lastStatusCheck < collectionAppState.statusCheckThrottle) {
        console.log('Status check throttled');
        return false;
    }
    
    collectionAppState.lastStatusCheck = now;
    updateCollectionAppStatus('Checking...');
    
    try {
        const response = await fetch('/api/collection-app-status');
        if (response.ok) {
            const status = await response.json();
            updateCollectionAppStatus(status.running ? 'Running' : 'Not Running');
            if (status.running) {
                showAlert('success', `Face Collection App is running (PID: ${status.pid})`);
            } else {
                showAlert('info', 'Face Collection App is not running');
            }
            return status.running;
        }
    } catch (error) {
        updateCollectionAppStatus('Unknown');
        showAlert('error', 'Could not check Face Collection App status');
        return false;
    }
}

function updateCollectionAppStatus(status) {
    const statusText = document.getElementById('statusText');
    if (statusText) {
        statusText.textContent = status;
        statusText.className = status === 'Running' ? 'text-success fw-bold' : 'text-muted';
    }
}

// Add API endpoint to start collection app server with state management
async function startCollectionAppServer() {
    if (collectionAppState.isStarting) {
        console.log('Already starting collection app, ignoring request');
        return;
    }
    
    collectionAppState.isStarting = true;
    
    try {
        updateCollectionAppStatus('Starting...');
        const response = await fetch('/api/start-collection-app', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showAlert('success', result.message);
                updateCollectionAppStatus('Running');
                // Wait a moment then launch the app
                setTimeout(() => {
                    launchCollectionApp();
                }, 2000);
            } else {
                showAlert('error', 'Failed to start Face Collection App server: ' + result.message);
                updateCollectionAppStatus('Not Running');
            }
        }
    } catch (error) {
        console.error('Error starting collection app server:', error);
        showAlert('error', 'Error starting Face Collection App server');
        updateCollectionAppStatus('Unknown');
    } finally {
        collectionAppState.isStarting = false;
    }
}

// Add API endpoint to stop collection app server with state management
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
            } else {
                showAlert('error', 'Failed to stop Face Collection App server: ' + result.message);
            }
        }
    } catch (error) {
        console.error('Error stopping collection app server:', error);
        showAlert('error', 'Error stopping Face Collection App server');
    } finally {
        collectionAppState.isStopping = false;
    }
}

// Enhanced launch function that tries to start the server if needed
const launchCollectionAppWithServer = debounce(async function() {
    if (collectionAppState.isStarting || collectionAppState.isStopping) {
        console.log('Collection app operation in progress, ignoring request');
        return;
    }
    
    updateCollectionAppStatus('Checking...');
    
    // First check if the app is already running
    const isRunning = await checkCollectionAppStatus();
    
    if (isRunning) {
        launchCollectionApp();
    } else {
        // Try to start the server
        showAlert('info', 'Starting Face Collection App server...');
        await startCollectionAppServer();
    }
}, 1000); // 1 second debounce

// Simple launch function that opens the app in a new tab
function launchCollectionApp() {
    const url = 'http://localhost:5001';
    window.open(url, '_blank');
    showAlert('info', 'Opening Face Collection App in new tab');
}