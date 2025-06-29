import sqlite3
import os

def get_batch_years_and_departments():
    """Fetch batch years and departments from the main app.db"""
    # Path to the main app.db
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'app.db')
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT year FROM batch_years ORDER BY year')
        years = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT department_id, name FROM departments ORDER BY name')
        departments = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        return {"years": years, "departments": departments}
    finally:
        conn.close()
