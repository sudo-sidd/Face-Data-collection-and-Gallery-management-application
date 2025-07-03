#!/usr/bin/env python3
"""
Database migration script to add department_id field to existing departments table.
This script handles the migration from the old structure to the new one.
"""

import os
import sqlite3
from contextlib import contextmanager

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "app.db")

@contextmanager
def get_db_connection():
    """Get a database connection with context management."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def check_if_migration_needed():
    """Check if the migration is needed by looking for department_id column."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(departments)")
        columns = [row['name'] for row in cursor.fetchall()]
        return 'department_id' not in columns

def migrate_database():
    """Migrate the database to add department_id field."""
    if not check_if_migration_needed():
        print("Migration not needed - department_id column already exists.")
        return
    
    print("Starting database migration...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create a backup of the current departments table
        print("Creating backup of departments table...")
        cursor.execute("CREATE TABLE departments_backup AS SELECT * FROM departments")
        
        # Get existing departments
        cursor.execute("SELECT id, name FROM departments ORDER BY id")
        existing_departments = cursor.fetchall()
        
        # Drop the old table
        cursor.execute("DROP TABLE departments")
        
        # Create new table with department_id field
        print("Creating new departments table with department_id field...")
        cursor.execute('''
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id TEXT UNIQUE NOT NULL,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Migrate existing data with generated department IDs
        print("Migrating existing department data...")
        for i, dept in enumerate(existing_departments, 1):
            # Generate department ID based on existing data
            # For existing departments, we'll use a pattern like DPT001, DPT002, etc.
            dept_id = f"DPT{i:03d}"
            dept_name = dept['name']
            
            try:
                cursor.execute(
                    "INSERT INTO departments (department_id, name) VALUES (?, ?)",
                    (dept_id, dept_name)
                )
                print(f"Migrated: {dept_name} -> {dept_id}")
            except sqlite3.IntegrityError as e:
                print(f"Error migrating {dept_name}: {e}")
        
        # Update foreign key constraints in galleries table if it exists
        try:
            cursor.execute("PRAGMA foreign_keys=OFF")
            
            # Check if galleries table exists and has the old structure
            cursor.execute("PRAGMA table_info(galleries)")
            gallery_columns = [row['name'] for row in cursor.fetchall()]
            
            if 'department_id' in gallery_columns:
                # The galleries table already has department_id, but it might be referencing the old structure
                # We need to update the foreign key references
                print("Updating galleries table foreign key references...")
                
                # Get all galleries with their current department references
                cursor.execute('''
                SELECT g.id, g.year_id, g.department_id as old_dept_id, d.department_id as new_dept_id
                FROM galleries g
                JOIN departments d ON g.department_id = d.id
                ''')
                
                galleries = cursor.fetchall()
                
                # Update each gallery to reference the new department structure
                for gallery in galleries:
                    cursor.execute('''
                    UPDATE galleries 
                    SET department_id = (SELECT id FROM departments WHERE department_id = ?)
                    WHERE id = ?
                    ''', (gallery['new_dept_id'], gallery['id']))
            
            cursor.execute("PRAGMA foreign_keys=ON")
            
        except Exception as e:
            print(f"Warning: Could not update galleries table: {e}")
        
        conn.commit()
        print("Database migration completed successfully!")
        
        # Show the migrated data
        print("\nMigrated departments:")
        cursor.execute("SELECT department_id, name FROM departments ORDER BY name")
        for row in cursor.fetchall():
            print(f"  {row['department_id']}: {row['name']}")

def main():
    """Main migration function."""
    if not os.path.exists(DB_PATH):
        print(f"Database file not found at {DB_PATH}")
        print("Creating new database with updated schema...")
        # Import and run init_db to create the database with new schema
        import database
        database.init_db()
        print("New database created with updated schema!")
        return
    
    try:
        migrate_database()
    except Exception as e:
        print(f"Migration failed: {e}")
        print("Please check the database file and try again.")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 