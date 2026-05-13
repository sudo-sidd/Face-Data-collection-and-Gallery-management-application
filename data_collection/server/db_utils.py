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


def _request_json(method, path, payload=None, timeout=10):
    """Send a JSON request to the database server and return a parsed payload."""
    try:
        response = requests.request(
            method,
            f"{DB_SERVER_URL}{path}",
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as e:
        return {"success": False, "message": f"Database server error: {str(e)}"}, 500

    try:
        data = response.json()
    except ValueError:
        body = response.text.strip()
        message = body or f"Database server returned a non-JSON response (HTTP {response.status_code})."
        return {"success": False, "message": message}, response.status_code

    return data, response.status_code


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
    return _request_json(
        "POST",
        "/api/student-login",
        payload={"regno": regno, "dob": dob},
    )


def get_student_name(regno):
    """Get student name by register number via database server"""
    return _request_json(
        "POST",
        "/api/student-name",
        payload={"regno": regno},
    )


def get_department_code(dept_id):
    """Get department code by department ID via database server"""
    return _request_json(
        "POST",
        "/api/department-code",
        payload={"dept_id": dept_id},
    )
