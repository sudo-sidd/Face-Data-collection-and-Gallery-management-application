"""
Database utilities - Client module for communicating with the Database Server.
All database operations are performed via HTTP requests to the database server.
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database server URL
DB_SERVER_URL = os.environ.get("DB_SERVER_URL", "http://localhost:8002")


def get_batch_years_and_departments():
    """Fetch batch years and departments from the database server"""
    try:
        response = requests.get(f"{DB_SERVER_URL}/api/batch-years-departments", timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            return {"years": data.get("years", []), "departments": data.get("departments", [])}
        else:
            raise Exception(data.get("error", "Unknown error"))
    except requests.RequestException as e:
        print(f"Error connecting to database server: {e}")
        return {"years": [], "departments": []}


def validate_student_login(regno, dob):
    """Validate student login credentials via database server"""
    try:
        response = requests.post(
            f"{DB_SERVER_URL}/api/student-login",
            json={"regno": regno, "dob": dob},
            timeout=10
        )
        return response.json(), response.status_code
    except requests.RequestException as e:
        return {"success": False, "message": f"Database server error: {str(e)}"}, 500


def get_student_name(regno):
    """Get student name by register number via database server"""
    try:
        response = requests.post(
            f"{DB_SERVER_URL}/api/student-name",
            json={"regno": regno},
            timeout=10
        )
        return response.json(), response.status_code
    except requests.RequestException as e:
        return {"success": False, "message": f"Database server error: {str(e)}"}, 500


def get_department_code(dept_id):
    """Get department code by department ID via database server"""
    try:
        response = requests.post(
            f"{DB_SERVER_URL}/api/department-code",
            json={"dept_id": dept_id},
            timeout=10
        )
        return response.json(), response.status_code
    except requests.RequestException as e:
        return {"success": False, "message": f"Database server error: {str(e)}"}, 500
