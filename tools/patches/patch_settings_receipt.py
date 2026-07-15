import os

filepath = r"d:\git\GstockSW4\ui\widgets\settings\settings_tab.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

import_target = "from .barcode_visual_editor import BarcodeVisualEditor"
import_replacement = "from .barcode_visual_editor import BarcodeVisualEditor\nfrom .receipt_visual_editor import ReceiptVisualEditor"
if "from .receipt_visual_editor import ReceiptVisualEditor" not in content:
    content = content.replace(import_target, import_replacement)

init_target = """        self.tab_barcode_config = BarcodeVisualEditor(self.data_manager)"""
init_replacement = """        self.tab_barcode_config = BarcodeVisualEditor(self.data_manager)
        self.tab_receipt_config = ReceiptVisualEditor(self.data_manager)"""
if "self.tab_receipt_config =" not in content:
    content = content.replace(init_target, init_replacement)

save_target = """        if hasattr(self, 'tab_barcode_config'):
            self.data_manager.config["label_settings"] = self.tab_barcode_config.label_config"""
save_replacement = """        if hasattr(self, 'tab_barcode_config'):
            self.data_manager.config["label_settings"] = self.tab_barcode_config.label_config
        
        # Save thermal receipt config
        if hasattr(self, 'tab_receipt_config'):
            self.data_manager.config["receipt_settings"] = self.tab_receipt_config.receipt_config"""
if "self.tab_receipt_config.receipt_config" not in content:
    content = content.replace(save_target, save_replacement)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated settings_tab.py to integrate ReceiptVisualEditor")
