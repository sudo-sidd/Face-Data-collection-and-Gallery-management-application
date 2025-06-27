import os
import sqlite3
from contextlib import contextmanager

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
            year TEXT UNIQUE NOT NULL
        )
        ''')
        
        # Create departments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        ''')
        
        # Insert default data if tables are empty
        cursor.execute("SELECT COUNT(*) FROM batch_years")
        if cursor.fetchone()[0] == 0:
            default_years = ["1st", "2nd", "3rd", "4th"]
            cursor.executemany("INSERT OR IGNORE INTO batch_years (year) VALUES (?)", 
                              [(year,) for year in default_years])
        
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            default_departments = ["CS", "IT", "ECE", "EEE", "CIVIL"]
            cursor.executemany("INSERT OR IGNORE INTO departments (name) VALUES (?)", 
                             [(dept,) for dept in default_departments])
        
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
        cursor.execute("SELECT name FROM departments ORDER BY name")
        return [row['name'] for row in cursor.fetchall()]

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

def add_department(department):
    """Add a new department to the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO departments (name) VALUES (?)", (department,))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Department already exists
            return False

def delete_department(department):
    """Delete a department from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM departments WHERE name = ?", (department,))
        conn.commit()
        return cursor.rowcount > 0

# Initialize the database when the module is imported
init_db()