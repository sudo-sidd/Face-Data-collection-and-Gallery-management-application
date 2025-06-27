console.log("Dropdown debug utilities loaded");

// Check database and populate dropdowns with results or fallback values
async function debugDropdowns() {
    showAlertMessage("Checking database and fixing dropdowns...");
    
    try {
        // Direct API call
        console.log("Making direct API call to /batches");
        const response = await fetch('/batches');
        
        if (!response.ok) {
            throw new Error(`API returned ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log("Direct API response:", data);
        
        if (!data.years || !data.departments) {
            throw new Error("API response missing years or departments");
        }
        
        // Display the results
        showAlertMessage(`Found ${data.years.length} years and ${data.departments.length} departments. Updating dropdowns...`);
        
        // Force populate all dropdowns
        populateSelects(data.years, data.departments);
        
        return true;
    } catch (error) {
        console.error("Debug dropdown error:", error);
        
        // Use fallback values
        const fallbackYears = ["1st", "2nd", "3rd", "4th"];
        const fallbackDepartments = ["CS", "IT", "ECE", "EEE", "CIVIL"];
        
        showAlertMessage(`Error: ${error.message}. Using fallback values.`);
        populateSelects(fallbackYears, fallbackDepartments);
        
        return false;
    }
}

// Helper to populate all select elements
function populateSelects(years, departments) {
    // Gallery Year
    populateSelect('galleryYear', years, 'Year');
    
    // Gallery Department
    populateSelect('galleryDepartment', departments);
    
    // Process Videos Year
    populateSelect('batchYear', years, 'Year');
    
    // Process Videos Department
    populateSelect('department', departments);
}

// Helper to populate a specific select element
function populateSelect(id, items, suffix = '') {
    const select = document.getElementById(id);
    if (!select) {
        console.warn(`Select #${id} not found`);
        return;
    }
    
    // Save current selection
    const currentValue = select.value;
    
    // Clear and add placeholder
    select.innerHTML = '';
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = `Select ${suffix ? suffix : id}`;
    placeholder.disabled = true;
    placeholder.selected = true;
    select.appendChild(placeholder);
    
    // Add options
    items.forEach(item => {
        const option = document.createElement('option');
        option.value = item;
        option.textContent = suffix ? `${item} ${suffix}` : item;
        select.appendChild(option);
    });
    
    // Restore selection if possible
    if (currentValue) {
        select.value = currentValue;
    }
    
    console.log(`Populated ${id} with ${items.length} options`);
}

// Helper to show alert messages
function showAlertMessage(message, type = 'info') {
    // const alertDiv = document.createElement('div');
    // alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    // alertDiv.innerHTML = `
    //     ${message}
    //     <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    // `;
    
    // // Find a good place to show the alert
    // const target = document.querySelector('.content-section.active .card-body');
    // if (target) {
    //     target.insertBefore(alertDiv, target.firstChild);
    // } else {
    //     document.body.insertBefore(alertDiv, document.body.firstChild);
    // }
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.classList.remove('show');
        setTimeout(() => alertDiv.remove(), 300);
    }, 8000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log("Setting up dropdown debug tools");
    
    // Add event listener to debug button
    const debugBtn = document.getElementById('debugDropdowns');
    if (debugBtn) {
        debugBtn.addEventListener('click', debugDropdowns);
    }// else {
    //     // Add the debug button dynamically if it doesn't exist
    //     setTimeout(() => {
    //         const forms = [
    //             document.getElementById('createGalleryForm'),
    //             document.getElementById('processVideosForm')
    //         ];
            
    //         forms.forEach(form => {
    //             if (form) {
    //                 const btn = document.createElement('button');
    //                 btn.type = 'button';
    //                 btn.className = 'btn btn-sm btn-warning mt-2';
    //                 btn.innerHTML = '<i class="fas fa-bug me-2"></i>Debug Database & Dropdowns';
    //                 btn.onclick = debugDropdowns;
    //                 form.appendChild(btn);
    //             }
    //         });
    //     }, 1000);
    // }
    
    // Add a global debug function
    window.fixDropdowns = debugDropdowns;
    console.log("Added window.fixDropdowns() global function");
    
    // Force initial dropdown population after a short delay
    setTimeout(debugDropdowns, 1500);
});