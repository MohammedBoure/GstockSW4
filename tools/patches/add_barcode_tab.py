import os

filepath = r"d:\git\GstockSW4\ui\widgets\settings\settings_tab.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

import_target = "from .pdf_config_tab import PdfConfigWidget"
import_replacement = "from .pdf_config_tab import PdfConfigWidget\nfrom .barcode_visual_editor import BarcodeVisualEditor"
if "from .barcode_visual_editor import BarcodeVisualEditor" not in content:
    content = content.replace(import_target, import_replacement)

init_target = """        self.tab_system = QWidget()
        self._setup_system_tab()"""
init_replacement = """        self.tab_system = QWidget()
        self._setup_system_tab()

        self.tab_barcode_config = BarcodeVisualEditor(self.data_manager)"""
if "self.tab_barcode_config =" not in content:
    content = content.replace(init_target, init_replacement)

addtab_target = """        self.tabs.addTab(self.tab_db, "Base de données")
        self.tabs.addTab(self.tab_printer, "Imprimante & Code-barres")"""
addtab_replacement = """        self.tabs.addTab(self.tab_db, "Base de données")
        self.tabs.addTab(self.tab_printer, "Imprimante (Général)")
        self.tabs.addTab(self.tab_barcode_config, "Éditeur Étiquettes")"""
if "self.tabs.addTab(self.tab_barcode_config" not in content:
    content = content.replace(addtab_target, addtab_replacement)

save_target = """        self.data_manager.config["label_height"] = self.spin_lbl_h.value()
        self.data_manager.config["gap"] = self.spin_gap.value()"""
save_replacement = """        self.data_manager.config["label_height"] = self.spin_lbl_h.value()
        self.data_manager.config["gap"] = self.spin_gap.value()
        
        # Save barcode visual config
        if hasattr(self, 'tab_barcode_config'):
            self.data_manager.config["label_settings"] = self.tab_barcode_config.label_config"""
if "self.tab_barcode_config.label_config" not in content:
    content = content.replace(save_target, save_replacement)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated settings_tab.py to integrate BarcodeVisualEditor")
