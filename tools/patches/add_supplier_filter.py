import os

# 1. Update _combos.py
file_combos = r"d:\git\GstockSW4\ui\widgets\inventory\tabs_batches\_combos.py"
with open(file_combos, "r", encoding="utf-8") as f:
    content = f.read()

new_combo = """
def populate_suppliers(self):
    self.combo_supplier.clear()
    self.combo_supplier.addItem("🚚 Fournisseurs", None)
    try:
        conn = self.manager.db.get_raw_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT Supplier_ID, Supplier_Name FROM Suppliers WHERE Deleted_At IS NULL ORDER BY Supplier_Name")
        for row in cursor.fetchall():
            self.combo_supplier.addItem(row['Supplier_Name'], row['Supplier_ID'])
        _adjust_combo_view_width(self.combo_supplier)
    except Exception as e:
        print(f"Error loading suppliers: {e}")
"""
if "def populate_suppliers" not in content:
    with open(file_combos, "a", encoding="utf-8") as f:
        f.write("\n" + new_combo)

# 2. Update __init__.py
file_init = r"d:\git\GstockSW4\ui\widgets\inventory\tabs_batches\__init__.py"
with open(file_init, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "from ._combos       import populate_families, populate_manufacturers, populate_automates",
    "from ._combos       import populate_families, populate_manufacturers, populate_automates, populate_suppliers"
)
content = content.replace(
    "populate_automates     = populate_automates",
    "populate_automates     = populate_automates\n    populate_suppliers     = populate_suppliers"
)
with open(file_init, "w", encoding="utf-8") as f:
    f.write(content)

# 3. Update _ui.py
file_ui = r"d:\git\GstockSW4\ui\widgets\inventory\tabs_batches\_ui.py"
with open(file_ui, "r", encoding="utf-8") as f:
    content = f.read()

target_ui = """    self.combo_automate.currentIndexChanged.connect(self.apply_filters_local)"""
replacement_ui = """    self.combo_automate.currentIndexChanged.connect(self.apply_filters_local)

    self.combo_supplier = QComboBox()
    self.combo_supplier.addItem("🚚 Fournisseurs", None)
    self.combo_supplier.setFixedWidth(130)
    self.populate_suppliers()
    self.combo_supplier.currentIndexChanged.connect(self.apply_filters_local)"""
if "self.combo_supplier = QComboBox()" not in content:
    content = content.replace(target_ui, replacement_ui)
    
    target_ui_2 = """    row2.addWidget(self.combo_automate)"""
    replacement_ui_2 = """    row2.addWidget(self.combo_automate)\n    row2.addWidget(self.combo_supplier)"""
    content = content.replace(target_ui_2, replacement_ui_2)

    with open(file_ui, "w", encoding="utf-8") as f:
        f.write(content)

print("Updated files for Supplier filter in UI.")
