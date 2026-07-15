import os

filepath = r"d:\git\GstockSW4\ui\widgets\inventory\tabs_batches\_filters.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target1 = """        automate_id  = self.combo_automate.currentData()"""
replacement1 = """        automate_id  = self.combo_automate.currentData()
        supplier_id  = getattr(self, 'combo_supplier', None) and self.combo_supplier.currentData()"""
content = content.replace(target1, replacement1)

target2 = """            if automate_id and row.get('Preferred_Automate_ID')  != automate_id: continue"""
replacement2 = """            if automate_id and row.get('Preferred_Automate_ID')  != automate_id: continue
            if supplier_id and row.get('Supplier_ID')            != supplier_id: continue"""
content = content.replace(target2, replacement2)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated _filters.py for Supplier_ID")
