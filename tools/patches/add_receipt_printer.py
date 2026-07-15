import os

# 1. Update settings_tab.py
filepath = r"d:\git\GstockSW4\ui\widgets\settings\settings_tab.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Default settings
target1 = """            "selected_printer": "","""
replacement1 = """            "selected_printer": "",
            "selected_receipt_printer": "","""
if target1 in content:
    content = content.replace(target1, replacement1)

# _setup_printer_tab UI
target2 = """        self.combo_printers = QComboBox()
        try:
            printers = win32print.EnumPrinters(2)
            printer_names = [p[2] for p in printers]
            self.combo_printers.addItems(printer_names)
        except:
            self.combo_printers.addItem("Erreur lors de la liste des imprimantes")

        current_p = self.settings.get("selected_printer", "")
        if current_p:
            idx = self.combo_printers.findText(current_p)
            if idx >= 0: self.combo_printers.setCurrentIndex(idx)

        self.spin_width = QSpinBox()"""
replacement2 = """        self.combo_printers = QComboBox()
        self.combo_receipt_printers = QComboBox()
        try:
            printers = win32print.EnumPrinters(2)
            printer_names = [p[2] for p in printers]
            self.combo_printers.addItems(printer_names)
            self.combo_receipt_printers.addItems(printer_names)
        except:
            self.combo_printers.addItem("Erreur lors de la liste des imprimantes")
            self.combo_receipt_printers.addItem("Erreur")

        current_p = self.settings.get("selected_printer", "")
        if current_p:
            idx = self.combo_printers.findText(current_p)
            if idx >= 0: self.combo_printers.setCurrentIndex(idx)
            
        current_rp = self.settings.get("selected_receipt_printer", "")
        if current_rp:
            idx_r = self.combo_receipt_printers.findText(current_rp)
            if idx_r >= 0: self.combo_receipt_printers.setCurrentIndex(idx_r)

        self.spin_width = QSpinBox()"""
if target2 in content:
    content = content.replace(target2, replacement2)

# form_print.addRow
target3 = """        form_print.addRow("Imprimante :", self.combo_printers)
        form_print.addRow("Largeur (mm) :", self.spin_width)"""
replacement3 = """        form_print.addRow("Imprimante (Code-Barres) :", self.combo_printers)
        form_print.addRow("Imprimante (Fiche/Ticket) :", self.combo_receipt_printers)
        form_print.addRow("Largeur (mm) :", self.spin_width)"""
if target3 in content:
    content = content.replace(target3, replacement3)

# save_settings
target4 = """        self.settings["selected_printer"] = self.combo_printers.currentText()
        self.settings["label_width"] = self.spin_width.value()"""
replacement4 = """        self.settings["selected_printer"] = self.combo_printers.currentText()
        self.settings["selected_receipt_printer"] = self.combo_receipt_printers.currentText()
        self.settings["label_width"] = self.spin_width.value()"""
if target4 in content:
    content = content.replace(target4, replacement4)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated settings_tab.py")

# 2. Update printer_manager.py
filepath_pm = r"d:\git\GstockSW4\database\printer_manager.py"
with open(filepath_pm, 'r', encoding='utf-8') as f:
    content_pm = f.read()

target_pm1 = """    def print_receipt(self, invoice_data):
        self.reload_settings()
        printer_name = self.config.get('selected_printer')"""
replacement_pm1 = """    def print_receipt(self, invoice_data):
        self.reload_settings()
        printer_name = self.config.get('selected_receipt_printer') or self.config.get('selected_printer')"""
if target_pm1 in content_pm:
    content_pm = content_pm.replace(target_pm1, replacement_pm1)

with open(filepath_pm, 'w', encoding='utf-8') as f:
    f.write(content_pm)
print("Updated printer_manager.py")
