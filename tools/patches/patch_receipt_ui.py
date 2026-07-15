import os

filepath = r"d:\git\GstockSW4\ui\widgets\settings\receipt_visual_editor.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# We need to insert the Template Management UI section
target = """        # 1. Dimensions"""
replacement = """        # 0. Template Management
        grp_tpl = QGroupBox("📋 0. Modèles (Templates)")
        v_tpl = QVBoxLayout(grp_tpl)
        
        h_combo = QHBoxLayout()
        self.cmb_template = QComboBox()
        self.cmb_template.currentTextChanged.connect(self.on_template_changed)
        h_combo.addWidget(QLabel("Modèle actuel:"))
        h_combo.addWidget(self.cmb_template, 1)
        
        h_btn = QHBoxLayout()
        btn_new = QPushButton("➕ Nouveau")
        btn_save = QPushButton("💾 Enregistrer")
        btn_ren = QPushButton("✏️ Renommer")
        btn_del = QPushButton("🗑️ Supprimer")
        
        btn_new.clicked.connect(self.new_template)
        btn_save.clicked.connect(self.save_template)
        btn_ren.clicked.connect(self.rename_template)
        btn_del.clicked.connect(self.delete_template)
        
        h_btn.addWidget(btn_new)
        h_btn.addWidget(btn_save)
        h_btn.addWidget(btn_ren)
        h_btn.addWidget(btn_del)
        
        v_tpl.addLayout(h_combo)
        v_tpl.addLayout(h_btn)
        form_layout.addWidget(grp_tpl)

        # 1. Dimensions"""

if "grp_tpl = QGroupBox" not in content:
    content = content.replace(target, replacement)
    
    # We also need to add the methods
    methods_addition = """
    def load_templates(self):
        from database.template_manager import TemplateManager
        if not hasattr(self, 'tpl_mgr'):
            self.tpl_mgr = TemplateManager(self.data_manager.db)
        
        self.cmb_template.blockSignals(True)
        self.cmb_template.clear()
        
        templates = self.tpl_mgr.get_templates('receipt')
        if not templates:
            # Create a default if DB is empty
            self.tpl_mgr.save_template('receipt', 'Standard', self.receipt_config)
            templates = self.tpl_mgr.get_templates('receipt')
            
        for t in templates:
            self.cmb_template.addItem(t['name'], t['settings'])
            
        # Select active template from local config
        active_name = self.data_manager.config.get("active_receipt_template", "Standard")
        idx = self.cmb_template.findText(active_name)
        if idx >= 0:
            self.cmb_template.setCurrentIndex(idx)
            self.receipt_config = self.cmb_template.itemData(idx)
        else:
            self.cmb_template.setCurrentIndex(0)
            self.receipt_config = self.cmb_template.itemData(0)
            self.data_manager.config["active_receipt_template"] = self.cmb_template.currentText()
            
        self.cmb_template.blockSignals(False)
        self.update_ui_from_config()

    def on_template_changed(self, text):
        idx = self.cmb_template.findText(text)
        if idx >= 0:
            self.receipt_config = self.cmb_template.itemData(idx)
            self.data_manager.config["active_receipt_template"] = text
            self.update_ui_from_config()
            self.trigger_preview()

    def new_template(self):
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        name, ok = QInputDialog.getText(self, "Nouveau modèle", "Nom du nouveau modèle:")
        if ok and name:
            if self.cmb_template.findText(name) >= 0:
                QMessageBox.warning(self, "Erreur", "Ce nom existe déjà.")
                return
            self.tpl_mgr.save_template('receipt', name, self.receipt_config)
            self.data_manager.config["active_receipt_template"] = name
            self.load_templates()

    def save_template(self):
        from PySide6.QtWidgets import QMessageBox
        name = self.cmb_template.currentText()
        if name:
            self.tpl_mgr.save_template('receipt', name, self.receipt_config)
            QMessageBox.information(self, "Succès", "Modèle enregistré dans la base de données.")
            self.load_templates()

    def rename_template(self):
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        old_name = self.cmb_template.currentText()
        if not old_name: return
        new_name, ok = QInputDialog.getText(self, "Renommer", "Nouveau nom:", text=old_name)
        if ok and new_name and new_name != old_name:
            success, msg = self.tpl_mgr.rename_template('receipt', old_name, new_name)
            if success:
                self.data_manager.config["active_receipt_template"] = new_name
                self.load_templates()
            else:
                QMessageBox.warning(self, "Erreur", msg)

    def delete_template(self):
        from PySide6.QtWidgets import QMessageBox
        name = self.cmb_template.currentText()
        if not name: return
        if self.cmb_template.count() <= 1:
            QMessageBox.warning(self, "Erreur", "Vous ne pouvez pas supprimer le dernier modèle.")
            return
            
        reply = QMessageBox.question(self, "Confirmer", f"Supprimer le modèle '{name}' ?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.tpl_mgr.delete_template('receipt', name)
            # Switch to first available
            self.load_templates()

    def update_ui_from_config(self):
        self.cmb_width.blockSignals(True)
        self.cmb_width.setCurrentText(f"{int(self.receipt_config.get('paper_width_mm', 80))}mm")
        self.cmb_width.blockSignals(False)
        
        self.chk_head.blockSignals(True); self.chk_head.setChecked(self.receipt_config["header"]["show"]); self.chk_head.blockSignals(False)
        self.txt_head.blockSignals(True); self.txt_head.setPlainText(self.receipt_config["header"]["text"]); self.txt_head.blockSignals(False)
        self.sp_head_sz.blockSignals(True); self.sp_head_sz.setValue(self.receipt_config["header"]["size"]); self.sp_head_sz.blockSignals(False)
        self.cmb_head_al.blockSignals(True); self.cmb_head_al.setCurrentText(self.receipt_config["header"]["align"]); self.cmb_head_al.blockSignals(False)
        
        self.chk_date.blockSignals(True); self.chk_date.setChecked(self.receipt_config["info"]["show_date"]); self.chk_date.blockSignals(False)
        self.chk_client.blockSignals(True); self.chk_client.setChecked(self.receipt_config["info"]["show_client"]); self.chk_client.blockSignals(False)
        self.chk_cashier.blockSignals(True); self.chk_cashier.setChecked(self.receipt_config["info"]["show_cashier"]); self.chk_cashier.blockSignals(False)
        self.sp_info_sz.blockSignals(True); self.sp_info_sz.setValue(self.receipt_config["info"]["size"]); self.sp_info_sz.blockSignals(False)
        
        self.chk_foot.blockSignals(True); self.chk_foot.setChecked(self.receipt_config["footer"]["show"]); self.chk_foot.blockSignals(False)
        self.txt_foot.blockSignals(True); self.txt_foot.setPlainText(self.receipt_config["footer"]["text"]); self.txt_foot.blockSignals(False)
        self.sp_foot_sz.blockSignals(True); self.sp_foot_sz.setValue(self.receipt_config["footer"]["size"]); self.sp_foot_sz.blockSignals(False)
        
        self.chk_bc.blockSignals(True); self.chk_bc.setChecked(self.receipt_config["barcode"]["show"]); self.chk_bc.blockSignals(False)
        self.sp_bc_h.blockSignals(True); self.sp_bc_h.setValue(self.receipt_config["barcode"]["height_mm"]); self.sp_bc_h.blockSignals(False)
"""
    
    # We must call self.load_templates() at the end of init_ui
    content = content.replace("        self.splitter.setSizes([400, 600])", "        self.splitter.setSizes([400, 600])\n        self.load_templates()")
    
    content += methods_addition

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated receipt_visual_editor.py with DB Templates support.")
else:
    print("Already updated.")
