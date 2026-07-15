import os

def patch_file(filepath, template_key):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We want to replace self.data_manager.config.get(...) and self.data_manager.config[...]
    # with self.data_manager.printer.config
    
    # 1. In load_templates
    target1 = f'self.data_manager.config.get("active_{template_key}_template"'
    replacement1 = f'self.data_manager.printer.config.get("active_{template_key}_template"'
    
    target2 = f'self.data_manager.config["active_{template_key}_template"]'
    replacement2 = f'self.data_manager.printer.config["active_{template_key}_template"]'
    
    content = content.replace(target1, replacement1)
    content = content.replace(target2, replacement2)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Patched {filepath}")

patch_file(r"d:\git\GstockSW4\ui\widgets\settings\barcode_visual_editor.py", "label")
patch_file(r"d:\git\GstockSW4\ui\widgets\settings\receipt_visual_editor.py", "receipt")
