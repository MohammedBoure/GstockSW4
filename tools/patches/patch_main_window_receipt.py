import os

filepath = r"d:\git\GstockSW4\ui\main_window.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = """                widget.tabs.addTab(widget.tab_barcode_config, "🏷️ Éditeur Étiquettes")"""
replacement = """                widget.tabs.addTab(widget.tab_barcode_config, "🏷️ Éditeur Étiquettes")
                widget.tabs.addTab(widget.tab_receipt_config, "🧾 Facture Thermique")"""

if "widget.tabs.addTab(widget.tab_receipt_config" not in content:
    content = content.replace(target, replacement)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed main_window.py for receipt tab")
else:
    print("Already fixed.")
