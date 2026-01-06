"""
Database Server - A separate microservice for handling all database operations.
This server exposes REST API endpoints for database queries.
"""

import os
import mysql.connector
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


def get_mysql_connection_without_db():
    """Create and return a MySQL connection without selecting a database"""
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", "")
    )


def init_database():
    """Initialize database and tables if they don't exist"""
    database_name = os.environ.get("MYSQL_DATABASE", "face_app")
    
    # Create database if not exists
    conn = get_mysql_connection_without_db()
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}`")
    cursor.execute(f"USE `{database_name}`")
    
    # Create batch_years table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS batch_years (
            id INT AUTO_INCREMENT PRIMARY KEY,
            year INT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create departments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            department_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            register_no VARCHAR(50) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            dob DATE NOT NULL,
            department_id INT,
            batch_year INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(department_id),
            FOREIGN KEY (batch_year) REFERENCES batch_years(year)
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Database and tables initialized successfully")


def get_mysql_connection():
    """Create and return a MySQL database connection"""
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DATABASE", "face_app")
    )


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_mysql_connection()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route('/api/batch-years-departments', methods=['GET'])
def get_batch_years_and_departments():
    """Fetch batch years and departments from the MySQL database"""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT year FROM batch_years ORDER BY year')
        years = [row[0] for row in cursor.fetchall()]
        
        cursor.execute('SELECT department_id, name FROM departments ORDER BY name')
        departments = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "years": years, "departments": departments}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/student-login', methods=['POST'])
def student_login():
    """Validate student login credentials"""
    data = request.get_json()
    regno = data.get('regno')
    dob = data.get('dob')
    
    if not regno or not dob:
        return jsonify({'success': False, 'message': 'Register number and DOB required.'}), 400
    
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM students WHERE register_no=%s AND dob=%s", (regno, dob))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'message': 'Invalid register number or date of birth.'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/student-name', methods=['POST'])
def get_student_name():
    """Get student name, year and department by register number"""
    data = request.get_json()
    regno = data.get('regno')
    
    if not regno:
        return jsonify({'success': False, 'message': 'Register number required.'}), 400
    
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.name, s.batch_year, d.name as department 
            FROM students s 
            LEFT JOIN departments d ON s.department_id = d.department_id 
            WHERE s.register_no=%s
        """, (regno,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            name, batch_year, department = result
            # Calculate year display format (admission_year - graduation_year)
            if batch_year:
                admission_year = batch_year - 4
                year_display = f"{admission_year} - {batch_year}"
            else:
                year_display = None
            
            return jsonify({
                'success': True, 
                'name': name,
                'year': year_display,
                'department': department
            }), 200
        else:
            return jsonify({'success': False, 'message': 'No student found.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/department-code', methods=['POST'])
def get_department_code():
    """Get department code by department ID"""
    data = request.get_json()
    dept_id = data.get('dept_id')
    
    if not dept_id:
        return jsonify({'success': False, 'message': 'Department ID required.'}), 400
    
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM departments WHERE department_id=%s", (dept_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return jsonify({'success': True, 'dept_code': result[0]}), 200
        else:
            return jsonify({'success': False, 'message': 'No department found.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/add-department', methods=['POST'])
def add_department():
    """Add a new department"""
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({'success': False, 'message': 'Department name required.'}), 400
    
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT IGNORE INTO departments (name) VALUES (%s)", (name,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Department added successfully.'}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/add-batch-year', methods=['POST'])
def add_batch_year():
    """Add a new batch year"""
    data = request.get_json()
    year = data.get('year')
    
    if not year:
        return jsonify({'success': False, 'message': 'Year required.'}), 400
    
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT IGNORE INTO batch_years (year) VALUES (%s)", (year,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Batch year added successfully.'}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/add-student', methods=['POST'])
def add_student():
    """Add a new student"""
    data = request.get_json()
    register_no = data.get('register_no')
    name = data.get('name')
    dob = data.get('dob')  # Expected format: YYYY-MM-DD
    department_id = data.get('department_id')
    batch_year = data.get('batch_year')
    
    if not register_no or not name or not dob:
        return jsonify({'success': False, 'message': 'Register number, name, and DOB are required.'}), 400
    
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (register_no, name, dob, department_id, batch_year) VALUES (%s, %s, %s, %s, %s)",
            (register_no, name, dob, department_id, batch_year)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Student added successfully.'}), 201
    except mysql.connector.IntegrityError:
        return jsonify({'success': False, 'message': 'Student with this register number already exists.'}), 409
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/list-students', methods=['GET'])
def list_students():
    """List all students"""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.register_no, s.name, s.dob, d.name as department, s.batch_year 
            FROM students s 
            LEFT JOIN departments d ON s.department_id = d.department_id
            ORDER BY s.register_no
        """)
        students = []
        for row in cursor.fetchall():
            students.append({
                'register_no': row[0],
                'name': row[1],
                'dob': str(row[2]),
                'department': row[3],
                'batch_year': row[4]
            })
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'students': students}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


def seed_sample_data():
    """Seed sample data for testing if tables are empty"""
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM students")
        if cursor.fetchone()[0] > 0:
            cursor.close()
            conn.close()
            print("📊 Sample data already exists, skipping seed")
            return
        
        # Add sample batch years
        sample_years = [2025, 2026, 2027, 2028]
        for year in sample_years:
            cursor.execute("INSERT IGNORE INTO batch_years (year) VALUES (%s)", (year,))
        
        # Add sample departments (using department codes as IDs)
        sample_departments = [
            (247, 'AIML'),
            (243, 'CSE'),
            (244, 'ECE'),
            (245, 'EEE'),
            (246, 'MECH')
        ]
        for dept_id, name in sample_departments:
            cursor.execute(
                "INSERT IGNORE INTO departments (department_id, name) VALUES (%s, %s)",
                (dept_id, name)
            )
        
        # Add sample students
        sample_students = [
            ('714023247078', 'Sample Student 1', '2005-01-15', 247, 2027),
            ('714023247090', 'Sample Student 2', '2005-03-20', 247, 2027),
            ('714023243001', 'CSE Student 1', '2005-05-10', 243, 2027),
        ]
        for register_no, name, dob, dept_id, batch_year in sample_students:
            cursor.execute(
                "INSERT IGNORE INTO students (register_no, name, dob, department_id, batch_year) VALUES (%s, %s, %s, %s, %s)",
                (register_no, name, dob, dept_id, batch_year)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Sample data seeded successfully")
    except Exception as e:
        print(f"⚠️ Error seeding sample data: {e}")


if __name__ == '__main__':
    print(f"🗄️  Starting Database Server on {host}:{port}")
    init_database()
    seed_sample_data()
    app.run(host=host, port=port, debug=False)
