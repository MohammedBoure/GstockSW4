import os

filepath = r"d:\git\GstockSW4\database\base\schema_initializer.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

new_table = """
        cursor.execute(\"\"\"CREATE TABLE IF NOT EXISTS Print_Templates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            template_type VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            settings_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;\"\"\")
        logging.info("Table Print_Templates prête.")
"""

if "Print_Templates" not in content:
    # Insert before the end of _initialize_schema
    target = """        # --- 11. System Logs ---"""
    content = content.replace(target, new_table + "\n" + target)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added Print_Templates to schema_initializer.py")
else:
    print("Print_Templates already exists.")
