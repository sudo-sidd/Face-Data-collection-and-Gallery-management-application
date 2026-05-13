"""
Database Server - A separate microservice for handling all database operations.
This server exposes REST API endpoints for database queries.
Uses SQLite (app.db) instead of MySQL.
"""

import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Get server configuration from environment
host = os.environ.get("DB_SERVER_HOST", "0.0.0.0")
port = int(os.environ.get("DB_SERVER_PORT", 8002))

# Path to the SQLite database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")


def get_db_connection():
    """Create and return a SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS batch_years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id TEXT UNIQUE NOT NULL,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_no BIGINT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            dob DATE,
            department TEXT,
            regulation TEXT,
            semester TEXT,
            section TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ SQLite database initialised at {DB_PATH}")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "healthy", "database": "sqlite", "db_path": DB_PATH}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Batch years & departments
# ---------------------------------------------------------------------------

@app.route('/api/batch-years-departments', methods=['GET'])
def get_batch_years_and_departments():
    """Fetch batch years and departments from the SQLite database."""
    try:
        conn = get_db_connection()

        years = [row["year"] for row in conn.execute(
            "SELECT year FROM batch_years ORDER BY year"
        ).fetchall()]

        departments = [
            {"id": row["id"], "name": row["name"], "department_id": row["department_id"]}
            for row in conn.execute(
                "SELECT id, department_id, name FROM departments ORDER BY name"
            ).fetchall()
        ]

        conn.close()
        return jsonify({"success": True, "years": years, "departments": departments}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# Student login
# ---------------------------------------------------------------------------

@app.route('/api/student-login', methods=['POST'])
def student_login():
    """Validate student login credentials."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No JSON body provided.'}), 400

    regno = data.get('regno')
    dob = data.get('dob')

    if not regno or not dob:
        return jsonify({'success': False, 'message': 'Register number and DOB required.'}), 400

    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT 1 FROM students WHERE register_no = ? AND dob = ?",
            (str(regno), str(dob))
        ).fetchone()
        conn.close()

        if row:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid register number or date of birth.'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Student name / info
# ---------------------------------------------------------------------------

@app.route('/api/student-name', methods=['POST'])
def get_student_name():
    """Get student name and department by register number."""
    data = request.get_json()
    regno = data.get('regno') if data else None

    if not regno:
        return jsonify({'success': False, 'message': 'Register number required.'}), 400

    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT name, department, regulation FROM students WHERE register_no = ?",
            (str(regno),)
        ).fetchone()
        conn.close()

        if row:
            return jsonify({
                'success': True,
                'name': row['name'],
                'department': row['department'],
                'year': row['regulation'],
            }), 200
        else:
            return jsonify({'success': False, 'message': 'No student found.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Department code lookup
# ---------------------------------------------------------------------------

@app.route('/api/department-code', methods=['POST'])
def get_department_code():
    """Get department name/code by department_id."""
    data = request.get_json()
    dept_id = data.get('dept_id') if data else None

    if not dept_id:
        return jsonify({'success': False, 'message': 'Department ID required.'}), 400

    try:
        conn = get_db_connection()
        row = conn.execute(
            "SELECT name FROM departments WHERE department_id = ?",
            (str(dept_id),)
        ).fetchone()
        conn.close()

        if row:
            return jsonify({'success': True, 'dept_code': row['name']}), 200
        else:
            return jsonify({'success': False, 'message': 'No department found.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Add department / batch year
# ---------------------------------------------------------------------------

@app.route('/api/add-department', methods=['POST'])
def add_department():
    """Add a new department."""
    data = request.get_json()
    name = data.get('name') if data else None
    department_id = data.get('department_id', name) if data else None

    if not name:
        return jsonify({'success': False, 'message': 'Department name required.'}), 400

    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT OR IGNORE INTO departments (department_id, name) VALUES (?, ?)",
            (str(department_id), name)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Department added successfully.'}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/add-batch-year', methods=['POST'])
def add_batch_year():
    """Add a new batch year."""
    data = request.get_json()
    year = data.get('year') if data else None

    if not year:
        return jsonify({'success': False, 'message': 'Year required.'}), 400

    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT OR IGNORE INTO batch_years (year) VALUES (?)",
            (str(year),)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Batch year added successfully.'}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Add / list students
# ---------------------------------------------------------------------------

@app.route('/api/add-student', methods=['POST'])
def add_student():
    """Add a new student."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No JSON body.'}), 400

    register_no = data.get('register_no')
    name = data.get('name')
    dob = data.get('dob')  # YYYY-MM-DD
    department = data.get('department') or data.get('department_id')
    regulation = data.get('regulation') or data.get('batch_year')
    section = data.get('section')

    if not register_no or not name:
        return jsonify({'success': False, 'message': 'Register number and name are required.'}), 400

    try:
        conn = get_db_connection()
        conn.execute(
            """INSERT INTO students (register_no, name, dob, department, regulation, section)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(register_no), name, dob, department, str(regulation) if regulation else None, section)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Student added successfully.'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Student with this register number already exists.'}), 409
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/list-students', methods=['GET'])
def list_students():
    """List all students."""
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT register_no, name, dob, department, regulation FROM students ORDER BY register_no"
        ).fetchall()
        conn.close()

        students = [
            {
                'register_no': str(row['register_no']),
                'name': row['name'],
                'dob': str(row['dob']) if row['dob'] else None,
                'department': row['department'],
                'batch_year': row['regulation'],
            }
            for row in rows
        ]
        return jsonify({'success': True, 'students': students}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print(f"🗄️  Starting SQLite Database Server on {host}:{port}")
    print(f"📂 Using database: {DB_PATH}")
    init_database()
    app.run(host=host, port=port, debug=False)
