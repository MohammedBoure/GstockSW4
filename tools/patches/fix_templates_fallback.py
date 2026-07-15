import os

def patch_fallback(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    target = """        else:
            self.cmb_template.setCurrentIndex(0)
            self.label_config = self.cmb_template.itemData(0)
            self.data_manager.printer.config["active_label_template"] = self.cmb_template.currentText()"""

    replacement = """        else:
            if self.cmb_template.count() > 0:
                self.cmb_template.setCurrentIndex(0)
                self.label_config = self.cmb_template.itemData(0)
                self.data_manager.printer.config["active_label_template"] = self.cmb_template.currentText()
            else:
                pass # keep self.label_config as loaded in load_config()"""

    content = content.replace(target, replacement)
    
    target_receipt = """        else:
            self.cmb_template.setCurrentIndex(0)
            self.receipt_config = self.cmb_template.itemData(0)
            self.data_manager.printer.config["active_receipt_template"] = self.cmb_template.currentText()"""

    replacement_receipt = """        else:
            if self.cmb_template.count() > 0:
                self.cmb_template.setCurrentIndex(0)
                self.receipt_config = self.cmb_template.itemData(0)
                self.data_manager.printer.config["active_receipt_template"] = self.cmb_template.currentText()
            else:
                pass"""

    content = content.replace(target_receipt, replacement_receipt)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

patch_fallback(r"d:\git\GstockSW4\ui\widgets\settings\barcode_visual_editor.py")
patch_fallback(r"d:\git\GstockSW4\ui\widgets\settings\receipt_visual_editor.py")
