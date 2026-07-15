import os

filepath = r"d:\git\GstockSW4\database\base\schema_initializer.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = '    """ALTER TABLE Inventory_Batches ADD COLUMN External_Barcode VARCHAR(100) NULL;""",'
replacement = target + """
    \"\"\"ALTER TABLE Inventory_Batches ADD COLUMN Supplier_ID INT UNSIGNED NULL;\"\"\",
    \"\"\"ALTER TABLE Inventory_Batches ADD CONSTRAINT fk_batch_supplier FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON DELETE SET NULL ON UPDATE CASCADE;\"\"\","""

if target in content:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content.replace(target, replacement))
    print("Added Supplier_ID to schema")
else:
    print("Target not found")
