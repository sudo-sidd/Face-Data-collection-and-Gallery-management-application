import os
import sqlite3
from contextlib import contextmanager
from typing import List, Optional, Dict, Any

# Single consolidated database for all application data
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "app.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

@contextmanager
def get_db_connection():
    """Get a database connection with context management."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize the database with required tables."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create batch_years table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create departments table with custom department_id
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id TEXT UNIQUE NOT NULL,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create galleries table to track gallery files
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS galleries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year_id INTEGER,
            department_id INTEGER,
            file_path TEXT UNIQUE NOT NULL,
            identity_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (year_id) REFERENCES batch_years (id),
            FOREIGN KEY (department_id) REFERENCES departments (id)
        )
        ''')
        
        # Insert default data if tables are empty
        cursor.execute("SELECT COUNT(*) FROM batch_years")
        if cursor.fetchone()[0] == 0:
            default_years = ["2029", "2028", "2027", "2026"]
            cursor.executemany("INSERT OR IGNORE INTO batch_years (year) VALUES (?)", 
                              [(year,) for year in default_years])
        
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            default_departments = [
                ("DPT001", "CS"),
                ("DPT002", "IT"), 
                ("DPT003", "ECE"),
                ("DPT004", "EEE"),
                ("DPT005", "CIVIL")
            ]
            cursor.executemany("INSERT OR IGNORE INTO departments (department_id, name) VALUES (?, ?)", 
                             default_departments)
        
        conn.commit()

def get_batch_years():
    """Get all batch years from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT year FROM batch_years ORDER BY year")
        return [row['year'] for row in cursor.fetchall()]

def get_departments():
    """Get all departments from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT department_id, name FROM departments ORDER BY name, department_id")
        return [{"id": row['department_id'], "name": row['name']} for row in cursor.fetchall()]

def get_department_names():
    """Get just the department names (for backward compatibility)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM departments ORDER BY name")
        return [row['name'] for row in cursor.fetchall()]

def get_department_ids():
    """Get just the department IDs (for backward compatibility)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT department_id FROM departments ORDER BY name")
        return [row['department_id'] for row in cursor.fetchall()]

def get_department_by_id(department_id: str) -> Optional[Dict[str, str]]:
    """Get department by its custom ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT department_id, name FROM departments WHERE department_id = ?", (department_id,))
        row = cursor.fetchone()
        if row:
            return {"id": row['department_id'], "name": row['name']}
        return None

def get_department_by_name(name: str) -> Optional[Dict[str, str]]:
    """Get department by its name."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT department_id, name FROM departments WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return {"id": row['department_id'], "name": row['name']}
        return None

def add_batch_year(year):
    """Add a new batch year to the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO batch_years (year) VALUES (?)", (year,))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Year already exists
            return False

def delete_batch_year(year):
    """Delete a batch year from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM batch_years WHERE year = ?", (year,))
        conn.commit()
        return cursor.rowcount > 0

def add_department(department_id: str, name: str):
    """Add a new department to the database with custom ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO departments (department_id, name) VALUES (?, ?)", (department_id, name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Department ID or name already exists
            return False

def delete_department(department_id: str):
    """Delete a department from the database by its custom ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM departments WHERE department_id = ?", (department_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_gallery_info(year: str, department: str) -> Optional[Dict[str, Any]]:
    """Get gallery information for a specific year and department."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT g.*, by.year, d.name as department_name, d.department_id
        FROM galleries g
        JOIN batch_years by ON g.year_id = by.id
        JOIN departments d ON g.department_id = d.id
        WHERE by.year = ? AND d.name = ?
        ''', (year, department))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def register_gallery(year: str, department: str, file_path: str, identity_count: int = 0) -> bool:
    """Register a gallery file in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get year and department IDs
        cursor.execute("SELECT id FROM batch_years WHERE year = ?", (year,))
        year_row = cursor.fetchone()
        if not year_row:
            return False
        
        cursor.execute("SELECT id FROM departments WHERE name = ?", (department,))
        dept_row = cursor.fetchone()
        if not dept_row:
            return False
        
        year_id = year_row[0]
        dept_id = dept_row[0]
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO galleries (year_id, department_id, file_path, identity_count, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (year_id, dept_id, file_path, identity_count))
            conn.commit()
            return True
        except sqlite3.Error:
            return False

def update_gallery_count(file_path: str, identity_count: int) -> bool:
    """Update the identity count for a gallery."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE galleries 
        SET identity_count = ?, updated_at = CURRENT_TIMESTAMP
        WHERE file_path = ?
        ''', (identity_count, file_path))
        conn.commit()
        return cursor.rowcount > 0

def list_all_galleries() -> List[Dict[str, Any]]:
    """List all registered galleries with their details."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT g.*, by.year, d.name as department_name, d.department_id
        FROM galleries g
        JOIN batch_years by ON g.year_id = by.id
        JOIN departments d ON g.department_id = d.id
        ORDER BY by.year, d.name
        ''')
        
        return [dict(row) for row in cursor.fetchall()]

def remove_gallery(year: str, department: str) -> bool:
    """Remove a gallery registration from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        DELETE FROM galleries 
        WHERE year_id = (SELECT id FROM batch_years WHERE year = ?)
        AND department_id = (SELECT id FROM departments WHERE name = ?)
        ''', (year, department))
        conn.commit()
        return cursor.rowcount > 0

def get_database_stats() -> Dict[str, Any]:
    """Get database statistics."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM batch_years")
        batch_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM departments")
        dept_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM galleries")
        gallery_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(identity_count) FROM galleries")
        total_identities = cursor.fetchone()[0] or 0
        
        return {
            "batch_years_count": batch_count,
            "departments_count": dept_count,
            "galleries_count": gallery_count,
            "total_identities": total_identities,
            "database_path": DB_PATH
        }

# Initialize the database when the module is imported
init_db()