# ui/widgets/settings/barcode_visual_editor.py

import os
import json
import io
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
    QComboBox, QPushButton, QLineEdit, QLabel, QCheckBox,
    QScrollArea, QSpinBox, QMessageBox, QSplitter, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor
import barcode
from barcode.writer import ImageWriter

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as e:
    logging.error(f"Missing PIL: {e}")

class BarcodeVisualEditor(QWidget):
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        
        self.zoom_factor = 2.0
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self.generate_preview)
        
        self.load_config()
        self.init_ui()
        self.trigger_preview()

    def load_config(self):
        # Default configuration
        self.label_config = {
            "label_width_mm": 40.0,
            "label_height_mm": 20.0,
            "dpi": 203, # 8 px per mm
            "elements": {
                "barcode": {"show": True, "x": 2.0, "y": 2.0, "width": 30.0, "height": 8.0, "text_size": 10},
                "product": {"show": True, "x": 2.0, "y": 12.0, "size": 14, "font": "arial.ttf", "angle": 0},
                "lot": {"show": True, "x": 35.0, "y": 2.0, "size": 10, "font": "arial.ttf", "angle": 90, "prefix": "LOT: "},
                "expiry": {"show": True, "x": 35.0, "y": 10.0, "size": 10, "font": "arial.ttf", "angle": 90, "prefix": "EXP: "},
                "company": {"show": False, "text": "Labo Algérie", "x": 2.0, "y": 0.5, "size": 10, "font": "arial.ttf", "angle": 0}
            }
        }
        
        # Load from config.json
        if self.data_manager and hasattr(self.data_manager, 'config'):
            saved = self.data_manager.config.get("label_settings", {})
            if saved:
                for k, v in saved.items():
                    if k == "elements" and isinstance(v, dict):
                        for ek, ev in v.items():
                            if ek in self.label_config["elements"]:
                                self.label_config["elements"][ek].update(ev)
                    else:
                        self.label_config[k] = v

    def save_config(self):
        if self.data_manager and hasattr(self.data_manager, 'config'):
            self.data_manager.config["label_settings"] = self.label_config
            # Not saving to disk here, it will be saved when user clicks global "Save" in settings tab

    def trigger_preview(self, *args):
        self.preview_timer.start()

    def zoom_in(self): 
        self.zoom_factor += 0.5
        self.generate_preview()
        
    def zoom_out(self): 
        if self.zoom_factor > 0.5: 
            self.zoom_factor -= 0.5
            self.generate_preview()
            
    def zoom_reset(self): 
        self.zoom_factor = 2.0
        self.generate_preview()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal) 
        main_layout.addWidget(self.splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form_layout = QVBoxLayout(content)

        # 1. General Settings
        # 0. Template Management
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

        grp_gen = QGroupBox("🖨️ 1. Dimensions (mm)")
        f_gen = QFormLayout(grp_gen)
        
        self.sp_w = QDoubleSpinBox()
        self.sp_w.setRange(10, 200)
        self.sp_w.setValue(self.label_config["label_width_mm"])
        self.sp_h = QDoubleSpinBox()
        self.sp_h.setRange(10, 200)
        self.sp_h.setValue(self.label_config["label_height_mm"])
        
        self.sp_w.valueChanged.connect(self.update_config_from_ui)
        self.sp_h.valueChanged.connect(self.update_config_from_ui)

        f_gen.addRow("Largeur (mm):", self.sp_w)
        f_gen.addRow("Hauteur (mm):", self.sp_h)
        form_layout.addWidget(grp_gen)

        # 2. Elements Settings
        grp_el = QGroupBox("📝 2. Éléments et Positions (mm)")
        v_el = QVBoxLayout(grp_el)

        # Helper to create row
        def create_element_row(key, label, is_barcode=False, has_prefix=False, has_text=False):
            el = self.label_config["elements"][key]
            row_main = QVBoxLayout()
            
            h_top = QHBoxLayout()
            chk = QCheckBox(label)
            chk.setChecked(el["show"])
            chk.stateChanged.connect(self.update_config_from_ui)
            h_top.addWidget(chk)
            
            inp_prefix, inp_text = None, None
            if has_prefix:
                inp_prefix = QLineEdit(el.get("prefix", ""))
                inp_prefix.setPlaceholderText("Préfixe (ex: LOT:)")
                inp_prefix.textChanged.connect(self.update_config_from_ui)
                h_top.addWidget(inp_prefix)
            if has_text:
                inp_text = QLineEdit(el.get("text", ""))
                inp_text.setPlaceholderText("Texte libre")
                inp_text.textChanged.connect(self.update_config_from_ui)
                h_top.addWidget(inp_text)
                
            row_main.addLayout(h_top)
            
            h_bot = QHBoxLayout()
            sx = QDoubleSpinBox(); sx.setRange(0, 300); sx.setValue(el["x"])
            sy = QDoubleSpinBox(); sy.setRange(0, 300); sy.setValue(el["y"])
            sx.valueChanged.connect(self.update_config_from_ui)
            sy.valueChanged.connect(self.update_config_from_ui)
            h_bot.addWidget(QLabel("X:")); h_bot.addWidget(sx)
            h_bot.addWidget(QLabel("Y:")); h_bot.addWidget(sy)
            
            sz = QSpinBox(); sz.setRange(4, 72)
            sz.setValue(el.get("text_size" if is_barcode else "size", 10))
            sz.valueChanged.connect(self.update_config_from_ui)
            h_bot.addWidget(QLabel("Taille:")); h_bot.addWidget(sz)
            
            if is_barcode:
                sw = QDoubleSpinBox(); sw.setRange(5, 200); sw.setValue(el.get("width", 30))
                sh = QDoubleSpinBox(); sh.setRange(2, 100); sh.setValue(el.get("height", 8))
                sw.valueChanged.connect(self.update_config_from_ui)
                sh.valueChanged.connect(self.update_config_from_ui)
                h_bot.addWidget(QLabel("W:")); h_bot.addWidget(sw)
                h_bot.addWidget(QLabel("H:")); h_bot.addWidget(sh)
                setattr(self, f"sp_{key}_w", sw)
                setattr(self, f"sp_{key}_h", sh)
            else:
                cmb_a = QComboBox(); cmb_a.addItems(["0°", "90°", "270°"])
                cmb_a.setCurrentText(f"{el.get('angle', 0)}°")
                cmb_a.currentTextChanged.connect(self.update_config_from_ui)
                h_bot.addWidget(QLabel("Angle:")); h_bot.addWidget(cmb_a)
                setattr(self, f"cmb_{key}_a", cmb_a)

            row_main.addLayout(h_bot)
            
            # Divider
            line = QWidget()
            line.setFixedHeight(1)
            line.setStyleSheet("background-color: #ddd; margin: 5px 0;")
            row_main.addWidget(line)
            
            v_el.addLayout(row_main)
            
            setattr(self, f"chk_{key}", chk)
            setattr(self, f"sp_{key}_x", sx)
            setattr(self, f"sp_{key}_y", sy)
            setattr(self, f"sp_{key}_sz", sz)
            if has_prefix: setattr(self, f"inp_{key}_pref", inp_prefix)
            if has_text: setattr(self, f"inp_{key}_txt", inp_text)

        create_element_row("barcode", "Code-barres:", is_barcode=True)
        create_element_row("product", "Nom du Produit:")
        create_element_row("lot", "Numéro de Lot:", has_prefix=True)
        create_element_row("expiry", "Date d'Expiration:", has_prefix=True)
        create_element_row("company", "En-tête (Nom Société):", has_text=True)

        form_layout.addWidget(grp_el)
        form_layout.addStretch()
        
        content.setLayout(form_layout)
        scroll.setWidget(content)
        left_layout.addWidget(scroll)

        # Preview Panel (Right)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        grp_prev = QGroupBox("👁️ Aperçu (Prévisualisation)")
        l_prev = QVBoxLayout(grp_prev)
        
        tools_h = QHBoxLayout()
        btn_zout = QPushButton("➖ Zoom Out"); btn_zout.clicked.connect(self.zoom_out)
        btn_zres = QPushButton("🔄 Reset Zoom"); btn_zres.clicked.connect(self.zoom_reset)
        btn_zin = QPushButton("➕ Zoom In"); btn_zin.clicked.connect(self.zoom_in)
        tools_h.addWidget(btn_zout); tools_h.addWidget(btn_zres); tools_h.addWidget(btn_zin)
        l_prev.addLayout(tools_h)

        scroll_prev = QScrollArea()
        scroll_prev.setAlignment(Qt.AlignCenter)
        self.lbl_preview = QLabel()
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #e0e0e0;")
        scroll_prev.setWidget(self.lbl_preview)
        l_prev.addWidget(scroll_prev)
        
        right_layout.addWidget(grp_prev)

        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([400, 600])
        self.load_templates()

    def update_config_from_ui(self):
        # Prevent update loop
        if not hasattr(self, 'sp_w'): return
        
        self.label_config["label_width_mm"] = self.sp_w.value()
        self.label_config["label_height_mm"] = self.sp_h.value()
        
        for key in ["barcode", "product", "lot", "expiry", "company"]:
            el = self.label_config["elements"][key]
            chk = getattr(self, f"chk_{key}")
            sx = getattr(self, f"sp_{key}_x")
            sy = getattr(self, f"sp_{key}_y")
            sz = getattr(self, f"sp_{key}_sz")
            
            el["show"] = chk.isChecked()
            el["x"] = sx.value()
            el["y"] = sy.value()
            
            if key == "barcode":
                el["text_size"] = sz.value()
                el["width"] = self.sp_barcode_w.value()
                el["height"] = self.sp_barcode_h.value()
            else:
                el["size"] = sz.value()
                cmb_a = getattr(self, f"cmb_{key}_a")
                el["angle"] = int(cmb_a.currentText().replace("°", ""))
                
            if key in ["lot", "expiry"]:
                inp = getattr(self, f"inp_{key}_pref")
                el["prefix"] = inp.text()
                
            if key == "company":
                inp = getattr(self, f"inp_{key}_txt")
                el["text"] = inp.text()
                
        self.save_config()
        self.trigger_preview()

    def generate_preview(self):
        px_per_mm = 8.0 # 203 dpi
        w_px = int(self.label_config["label_width_mm"] * px_per_mm)
        h_px = int(self.label_config["label_height_mm"] * px_per_mm)
        
        if w_px <= 0 or h_px <= 0:
            return
            
        img = Image.new('L', (w_px, h_px), 255)
        draw = ImageDraw.Draw(img)
        
        els = self.label_config["elements"]
        
        def draw_text(text, x_mm, y_mm, size_pt, angle, font_name="arial.ttf"):
            try:
                f = ImageFont.truetype(font_name, size_pt)
            except:
                f = ImageFont.load_default()
            
            x_px = int(x_mm * px_per_mm)
            y_px = int(y_mm * px_per_mm)
            
            if angle == 0:
                draw.text((x_px, y_px), text, font=f, fill=0)
            else:
                bbox = draw.textbbox((0, 0), text, font=f)
                txt_img = Image.new('L', (bbox[2]-bbox[0]+10, bbox[3]-bbox[1]+10), 255)
                txt_draw = ImageDraw.Draw(txt_img)
                txt_draw.text((5, 5), text, font=f, fill=0)
                txt_img = txt_img.rotate(angle, expand=True, fillcolor=255)
                img.paste(txt_img, (x_px, y_px))

        # Company
        if els["company"]["show"]:
            draw_text(els["company"].get("text", "Labo"), els["company"]["x"], els["company"]["y"], els["company"]["size"], els["company"]["angle"])
            
        # Product
        if els["product"]["show"]:
            draw_text("PRODUIT TEST 123", els["product"]["x"], els["product"]["y"], els["product"]["size"], els["product"]["angle"])
            
        # Lot
        if els["lot"]["show"]:
            draw_text(f"{els['lot'].get('prefix', '')}L-45879", els["lot"]["x"], els["lot"]["y"], els["lot"]["size"], els["lot"]["angle"])
            
        # Expiry
        if els["expiry"]["show"]:
            draw_text(f"{els['expiry'].get('prefix', '')}2028-12-31", els["expiry"]["x"], els["expiry"]["y"], els["expiry"]["size"], els["expiry"]["angle"])
            
        # Barcode
        if els["barcode"]["show"]:
            b_el = els["barcode"]
            try:
                bc_class = barcode.get_barcode_class('code128')
                writer = ImageWriter()
                opts = {"module_width": 0.5, "module_height": 10.0, "quiet_zone": 1.0, "write_text": False}
                
                fp = io.BytesIO()
                bc_obj = bc_class("123456789012", writer=writer)
                bc_obj.write(fp, options=opts)
                fp.seek(0)
                bc_img = Image.open(fp).convert("L")
                
                target_w = int(b_el["width"] * px_per_mm)
                target_h = int(b_el["height"] * px_per_mm)
                bc_img = bc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                
                img.paste(bc_img, (int(b_el["x"] * px_per_mm), int(b_el["y"] * px_per_mm)))
                
                # Barcode Text
                try:
                    f_bc = ImageFont.truetype("arial.ttf", b_el["text_size"])
                except:
                    f_bc = ImageFont.load_default()
                
                text_y = int(b_el["y"] * px_per_mm) + target_h + 2
                text_x = int(b_el["x"] * px_per_mm) + (target_w // 4)
                draw.text((text_x, text_y), "123456789012", font=f_bc, fill=0)
            except Exception as e:
                logging.error(f"Error drawing barcode preview: {e}")

        # Border for preview
        draw.rectangle([0, 0, w_px-1, h_px-1], outline=0)

        # Convert to QPixmap
        img_bytes = img.convert("RGBA").tobytes("raw", "RGBA")
        qimg = QImage(img_bytes, img.size[0], img.size[1], QImage.Format_RGBA8888)
        
        # Scale for UI display
        final_w = int(qimg.width() * self.zoom_factor)
        final_h = int(qimg.height() * self.zoom_factor)
        qimg_scaled = qimg.scaled(final_w, final_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        self.lbl_preview.setPixmap(QPixmap.fromImage(qimg_scaled))
        self.lbl_preview.setFixedSize(final_w, final_h)


    def load_templates(self):
        from database.template_manager import TemplateManager
        if not hasattr(self, 'tpl_mgr'):
            self.tpl_mgr = TemplateManager(self.data_manager.db)
        
        self.cmb_template.blockSignals(True)
        self.cmb_template.clear()
        
        templates = self.tpl_mgr.get_templates('label')
        if not templates:
            # Create a default if DB is empty
            self.tpl_mgr.save_template('label', 'Standard', self.label_config)
            templates = self.tpl_mgr.get_templates('label')
            
        for t in templates:
            self.cmb_template.addItem(t['name'], t['settings'])
            
        # Select active template from local config
        active_name = self.data_manager.printer.config.get("active_label_template", "Standard")
        idx = self.cmb_template.findText(active_name)
        if idx >= 0:
            self.cmb_template.setCurrentIndex(idx)
            self.label_config = self.cmb_template.itemData(idx)
        else:
            if self.cmb_template.count() > 0:
                self.cmb_template.setCurrentIndex(0)
                self.label_config = self.cmb_template.itemData(0)
                self.data_manager.printer.config["active_label_template"] = self.cmb_template.currentText()
            else:
                pass # keep self.label_config as loaded in load_config()
            
        self.cmb_template.blockSignals(False)
        self.update_ui_from_config()

    def on_template_changed(self, text):
        idx = self.cmb_template.findText(text)
        if idx >= 0:
            self.label_config = self.cmb_template.itemData(idx)
            self.data_manager.printer.config["active_label_template"] = text
            self.update_ui_from_config()
            self.trigger_preview()

    def new_template(self):
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        name, ok = QInputDialog.getText(self, "Nouveau modèle", "Nom du nouveau modèle:")
        if ok and name:
            if self.cmb_template.findText(name) >= 0:
                QMessageBox.warning(self, "Erreur", "Ce nom existe déjà.")
                return
            self.tpl_mgr.save_template('label', name, self.label_config)
            self.data_manager.printer.config["active_label_template"] = name
            self.load_templates()

    def save_template(self):
        from PySide6.QtWidgets import QMessageBox
        name = self.cmb_template.currentText()
        if name:
            self.tpl_mgr.save_template('label', name, self.label_config)
            QMessageBox.information(self, "Succès", "Modèle enregistré dans la base de données.")
            self.load_templates()

    def rename_template(self):
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        old_name = self.cmb_template.currentText()
        if not old_name: return
        new_name, ok = QInputDialog.getText(self, "Renommer", "Nouveau nom:", text=old_name)
        if ok and new_name and new_name != old_name:
            success, msg = self.tpl_mgr.rename_template('label', old_name, new_name)
            if success:
                self.data_manager.printer.config["active_label_template"] = new_name
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
            self.tpl_mgr.delete_template('label', name)
            self.load_templates()

    def update_ui_from_config(self):
        self.sp_w.blockSignals(True); self.sp_w.setValue(self.label_config["label_width_mm"]); self.sp_w.blockSignals(False)
        self.sp_h.blockSignals(True); self.sp_h.setValue(self.label_config["label_height_mm"]); self.sp_h.blockSignals(False)
        
        for key in ["barcode", "product", "lot", "expiry", "company"]:
            el = self.label_config["elements"][key]
            chk = getattr(self, f"chk_{key}", None)
            if chk:
                chk.blockSignals(True); chk.setChecked(el["show"]); chk.blockSignals(False)
                
            sx = getattr(self, f"sp_{key}_x", None)
            if sx:
                sx.blockSignals(True); sx.setValue(el["x"]); sx.blockSignals(False)
                
            sy = getattr(self, f"sp_{key}_y", None)
            if sy:
                sy.blockSignals(True); sy.setValue(el["y"]); sy.blockSignals(False)
                
            sz = getattr(self, f"sp_{key}_sz", None)
            if sz:
                sz.blockSignals(True)
                sz.setValue(el.get("text_size" if key == "barcode" else "size", 10))
                sz.blockSignals(False)
                
            if key == "barcode":
                sw = getattr(self, "sp_barcode_w", None)
                if sw: sw.blockSignals(True); sw.setValue(el.get("width", 30)); sw.blockSignals(False)
                sh = getattr(self, "sp_barcode_h", None)
                if sh: sh.blockSignals(True); sh.setValue(el.get("height", 8)); sh.blockSignals(False)
            else:
                cmb_a = getattr(self, f"cmb_{key}_a", None)
                if cmb_a:
                    cmb_a.blockSignals(True)
                    cmb_a.setCurrentText(f"{el.get('angle', 0)}°")
                    cmb_a.blockSignals(False)
                    
            if key in ["lot", "expiry"]:
                inp_pref = getattr(self, f"inp_{key}_pref", None)
                if inp_pref:
                    inp_pref.blockSignals(True); inp_pref.setText(el.get("prefix", "")); inp_pref.blockSignals(False)
                    
            if key == "company":
                inp_txt = getattr(self, f"inp_{key}_txt", None)
                if inp_txt:
                    inp_txt.blockSignals(True); inp_txt.setText(el.get("text", "")); inp_txt.blockSignals(False)
