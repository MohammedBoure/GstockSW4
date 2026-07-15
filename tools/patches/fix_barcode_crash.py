import os

filepath = r"d:\git\GstockSW4\ui\widgets\settings\barcode_visual_editor.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# We need to insert the Template Management UI section
target = """        grp_gen = QGroupBox("🖨️ 1. Dimensions (mm)")"""
replacement = """        # 0. Template Management
        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QLabel, QGroupBox, QVBoxLayout
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

        grp_gen = QGroupBox("🖨️ 1. Dimensions (mm)")"""

if "grp_tpl = QGroupBox" not in content:
    content = content.replace(target, replacement)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed barcode_visual_editor.py UI.")
else:
    print("Already fixed.")
