import sys
import os

# Add root project to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.base.database import Database
import logging

logging.basicConfig(level=logging.INFO)

db = Database()
query = """
CREATE TABLE IF NOT EXISTS Print_Templates (
    id INT PRIMARY KEY AUTO_INCREMENT,
    template_type VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    settings_json JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_type_name (template_type, name)
);
"""

try:
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
    print("SUCCESS: Print_Templates table created manually via app DB connection.")
except Exception as e:
    print(f"FAILED: {e}")
    
    # Try fallback for old MariaDB versions that don't support JSON type
    if "syntax" in str(e).lower() or "1064" in str(e):
        print("Attempting to create with TEXT instead of JSON for older DB versions...")
        query_fallback = """
        CREATE TABLE IF NOT EXISTS Print_Templates (
            id INT PRIMARY KEY AUTO_INCREMENT,
            template_type VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            settings_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY idx_type_name (template_type, name)
        );
        """
        try:
            with db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query_fallback)
                conn.commit()
            print("SUCCESS: Print_Templates table created with TEXT type.")
        except Exception as e2:
            print(f"FAILED FALLBACK: {e2}")
