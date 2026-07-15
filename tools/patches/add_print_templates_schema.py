import os

filepath = r"d:\git\GstockSW4\database\base\schema_initializer.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

target = """    """ + """CREATE TABLE IF NOT EXISTS SystemLogs (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT UNSIGNED,
        log_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        module VARCHAR(50),
        action VARCHAR(100),
        details TEXT,
        ip_address VARCHAR(50),
        FOREIGN KEY (user_id) REFERENCES Users(User_ID) ON DELETE SET NULL
    );\"\"\""""

replacement = target + """,

    \"\"\"CREATE TABLE IF NOT EXISTS Print_Templates (
        id INT PRIMARY KEY AUTO_INCREMENT,
        template_type VARCHAR(50) NOT NULL,
        name VARCHAR(100) NOT NULL,
        settings_json JSON,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY idx_type_name (template_type, name)
    );\"\"\""""

if "Print_Templates" not in content:
    content = content.replace(target, replacement)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added Print_Templates to schema_initializer.py")
else:
    print("Already added.")
