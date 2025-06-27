console.log("Debug utilities loaded");

// Direct DOM event listeners for critical functionality
document.addEventListener('DOMContentLoaded', function() {
    console.log("Debug script initialized");
    
    // Debug for admin forms
    setupFormDebugHandlers();
    
    // Listen for all button clicks to debug
    document.addEventListener('click', function(e) {
        const target = e.target;
        if (target.tagName === 'BUTTON' || target.parentElement.tagName === 'BUTTON') {
            const button = target.tagName === 'BUTTON' ? target : target.parentElement;
            console.log(`Button clicked: ${button.textContent.trim()} | Classes: ${button.className}`);
        }
        
        // Specifically handle delete buttons
        if (target.classList.contains('delete-department') || 
            (target.parentElement && target.parentElement.classList.contains('delete-department'))) {
            const button = target.classList.contains('delete-department') ? target : target.parentElement;
            const dept = button.getAttribute('data-dept');
            console.log(`Delete department button clicked: ${dept}`);
        }
    });
    
    // Force refresh admin data periodically
    setTimeout(refreshAdminData, 5000);
});

function setupFormDebugHandlers() {
    const addBatchYearForm = document.getElementById('addBatchYearForm');
    if (addBatchYearForm) {
        console.log("Setting up batch year form debug handler");
        addBatchYearForm.addEventListener('submit', function(e) {
            console.log("Batch year form submitted (debug handler)");
            // Let the main handler process it
        });
    }
    
    const addDepartmentForm = document.getElementById('addDepartmentForm');
    if (addDepartmentForm) {
        console.log("Setting up department form debug handler");
        addDepartmentForm.addEventListener('submit', function(e) {
            console.log("Department form submitted (debug handler)");
            // Force direct form submission as a fallback
            if (!window.handleAddDepartment) {
                e.preventDefault();
                debugAddDepartment(e);
            }
            // Let the main handler process it
        });
    }
}

// Fallback direct submission
async function debugAddDepartment(event) {
    event.preventDefault();
    console.log("DEBUG: Direct department form submission");
    
    const newDepartment = document.getElementById('newDepartment').value.trim();
    console.log("DEBUG: New department value:", newDepartment);
    
    if (!newDepartment) {
        alert('Department cannot be empty');
        return;
    }
    
    try {
        const response = await fetch('/batches/department', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ department: newDepartment })
        });
        
        console.log("DEBUG: Response status:", response.status);
        
        if (response.ok) {
            alert(`Added department: ${newDepartment}`);
            document.getElementById('newDepartment').value = '';
            refreshAdminData();
        } else {
            const errorText = await response.text();
            console.error("DEBUG: Error response:", errorText);
            try {
                const error = JSON.parse(errorText);
                alert(error.detail || 'Failed to add department');
            } catch {
                alert('Failed to add department');
            }
        }
    } catch (error) {
        console.error('DEBUG: Error adding department:', error);
        alert('Failed to add department');
    }
}

// Force refresh admin data
async function refreshAdminData() {
    console.log("DEBUG: Force refreshing admin data");
    
    if (window.loadAdminData) {
        await window.loadAdminData();
        console.log("DEBUG: Admin data refreshed via main function");
    } else {
        // Fallback refresh
        try {
            const response = await fetch('/batches');
            const data = await response.json();
            
            updateDepartmentsList(data.departments);
            updateBatchYearsList(data.years);
            
            console.log("DEBUG: Admin data refreshed via fallback");
        } catch (error) {
            console.error("DEBUG: Error refreshing admin data:", error);
        }
    }
    
    // Schedule next refresh at a much longer interval (5 minutes instead of 30 seconds)
    setTimeout(refreshAdminData, 300000); // 5 minutes
}

// Update the departments list
function updateDepartmentsList(departments) {
    const departmentsList = document.getElementById('departmentsList');
    if (!departmentsList) return;
    
    departmentsList.innerHTML = '';
    
    departments.forEach(dept => {
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
}

// Update the batch years list
function updateBatchYearsList(years) {
    const batchYearsList = document.getElementById('batchYearsList');
    if (!batchYearsList) return;
    
    batchYearsList.innerHTML = '';
    
    years.forEach(year => {
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
}

// Fix for department deletion
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('delete-department') || 
        (e.target.parentElement && e.target.parentElement.classList.contains('delete-department'))) {
        
        const button = e.target.classList.contains('delete-department') ? 
            e.target : e.target.parentElement;
        
        const dept = button.getAttribute('data-dept');
        if (dept) {
            e.preventDefault();
            e.stopPropagation();
            debugDeleteDepartment(dept);
        }
    }
});

// Debug department deletion function
async function debugDeleteDepartment(department) {
    console.log("DEBUG: Deleting department:", department);
    
    if (!confirm(`Are you sure you want to delete the department "${department}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/batches/department/${department}`, {
            method: 'DELETE'
        });
        
        console.log("DEBUG: Delete response status:", response.status);
        
        if (response.ok) {
            // Remove from UI immediately
            const items = document.querySelectorAll(`#departmentsList li`);
            for (const item of items) {
                if (item.querySelector('span').textContent.trim() === department) {
                    item.remove();
                }
            }
            
            alert(`Deleted department: ${department}`);
            refreshAdminData();
        } else {
            const errorText = await response.text();
            console.error("DEBUG: Delete error response:", errorText);
            try {
                const error = JSON.parse(errorText);
                alert(error.detail || 'Failed to delete department');
            } catch {
                alert('Failed to delete department');
            }
        }
    } catch (error) {
        console.error('DEBUG: Error deleting department:', error);
        alert('Failed to delete department');
    }
}