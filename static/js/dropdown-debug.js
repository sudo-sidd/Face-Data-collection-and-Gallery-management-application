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
        const fallbackYears = ["2029", "2028", "2027", "2026"];
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

// Helper to show alert messages - using the centralized function from app.js
function showAlertMessage(message, type = 'info') {
    // Use showToast from app.js for unified notification system
    if (type === 'error') type = 'danger';
    if (window.showToast) {
        window.showToast(type === 'danger' ? 'error' : type, message, { title: false });
    } else if (window.showAlert) {
        window.showAlert(type === 'danger' ? 'error' : 'success', message);
    } else {
        console.log(`${type.toUpperCase()}: ${message}`);
    }
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