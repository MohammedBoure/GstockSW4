import os

filepath = r"d:\git\GstockSW4\database\printer_manager.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = """        cfg = self.config.get("receipt_settings", {"""
replacement = """        # Fetch template from DB if available
        active_template = self.config.get("active_receipt_template", "Standard")
        cfg = None
        if self.db:
            try:
                from .template_manager import TemplateManager
                tpl_mgr = TemplateManager(self.db)
                cfg = tpl_mgr.get_template_by_name('receipt', active_template)
            except Exception as e:
                import logging
                logging.error(f"Error fetching receipt template from DB: {e}")
        
        if not cfg:
            cfg = self.config.get("receipt_settings", {
"""

if "active_receipt_template" not in content:
    # First, let's make sure printer_manager has access to db
    # PrinterManager.__init__ accepts db_instance=None.
    content = content.replace(target, replacement)
    
    # We should also replace the closing brace of the fallback cfg dict if we want to structure it cleanly,
    # but the string replacement approach is easy since I matched the exact dict opening.
    # Wait, the fallback is a default dictionary. Let's make sure syntax is valid.
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated printer_manager.py to fetch template from DB")
else:
    print("printer_manager already uses active_receipt_template")
