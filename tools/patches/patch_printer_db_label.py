import os

filepath = r"d:\git\GstockSW4\database\printer_manager.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = """        label_settings = self.config.get("label_settings")"""
replacement = """        # Fetch template from DB if available
        active_template = self.config.get("active_label_template", "Standard")
        label_settings = None
        if self.db:
            try:
                from .template_manager import TemplateManager
                tpl_mgr = TemplateManager(self.db)
                label_settings = tpl_mgr.get_template_by_name('label', active_template)
            except Exception as e:
                import logging
                logging.error(f"Error fetching label template from DB: {e}")
        
        if not label_settings:
            label_settings = self.config.get("label_settings")"""

if "active_label_template" not in content:
    content = content.replace(target, replacement)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated printer_manager.py to fetch label template from DB")
else:
    print("printer_manager already uses active_label_template")
