# ui/widgets/settings/receipt_visual_editor.py

import os
import io
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
    QComboBox, QPushButton, QLineEdit, QLabel, QCheckBox,
    QScrollArea, QSpinBox, QSplitter, QDoubleSpinBox, QTextEdit, QFileDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage
from branding import get_logo_path
import barcode
from barcode.writer import ImageWriter
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    logging.error(f"Missing PIL: {e}")

class ReceiptVisualEditor(QWidget):
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        
        self.zoom_factor = 1.0
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(200)
        self.preview_timer.timeout.connect(self.generate_preview)
        
        self.load_config()
        self.init_ui()
        self.trigger_preview()

    def load_config(self):
        # Default receipt config
        self.receipt_config = {
            "paper_width_mm": 80.0,
            "dpi": 203,
            "header": {
                "show": True,
                "text": "Nom Entreprise\nAdresse\nTel: 000000000",
                "align": "center",
                "size": 16
            },
            "logo": {
                "show": True,
                "path": "",
                "max_width_mm": 42.0,
                "max_height_mm": 18.0,
                "align": "center"
            },
            "font": {
                "family": "Segoe UI",
                "regular_path": "",
                "bold_path": ""
            },
            "info": {
                "show_date": True,
                "show_client": True,
                "show_cashier": True,
                "size": 12
            },
            "table": {
                "size": 12,
                "show_header": True,
                "show_unit_price": True,
                "show_price_before": True,
                "show_discount": True,
                "show_tva": True
            },
            "totals": {
                "size": 14,
                "bold": True
            },
            "footer": {
                "show": True,
                "text": "Merci pour votre visite!",
                "align": "center",
                "size": 14
            },
            "barcode": {
                "show": True,
                "height_mm": 10.0,
                "size": 12
            }
        }
        
        saved = {}
        if self.data_manager and hasattr(self.data_manager, 'config'):
            saved = self.data_manager.config.get("receipt_settings", {})
        if not saved and self.data_manager and hasattr(self.data_manager, 'printer'):
            saved = self.data_manager.printer.config.get("receipt_settings", {})
        if saved:
            for k, v in saved.items():
                if isinstance(v, dict) and k in self.receipt_config:
                    self.receipt_config[k].update(v)
                else:
                    self.receipt_config[k] = v

    def save_config(self):
        if self.data_manager and hasattr(self.data_manager, 'config'):
            self.data_manager.config["receipt_settings"] = self.receipt_config
        if self.data_manager and hasattr(self.data_manager, 'printer'):
            self.data_manager.printer.config["receipt_settings"] = self.receipt_config
            if self.cmb_template.currentText():
                self.data_manager.printer.config["active_receipt_template"] = self.cmb_template.currentText()

    def trigger_preview(self, *args):
        self.preview_timer.start()

    def zoom_in(self): 
        self.zoom_factor += 0.2
        self.generate_preview()
        
    def zoom_out(self): 
        if self.zoom_factor > 0.4: 
            self.zoom_factor -= 0.2
            self.generate_preview()
            
    def zoom_reset(self): 
        self.zoom_factor = 1.0
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

        # 1. Dimensions
        grp_gen = QGroupBox("📄 1. Papier et Dimensions")
        f_gen = QFormLayout(grp_gen)
        self.cmb_width = QComboBox()
        self.cmb_width.addItems(["80mm", "58mm"])
        if self.receipt_config["paper_width_mm"] == 58.0:
            self.cmb_width.setCurrentText("58mm")
        else:
            self.cmb_width.setCurrentText("80mm")
        self.cmb_width.currentTextChanged.connect(self.update_config_from_ui)
        f_gen.addRow("Largeur (Papier):", self.cmb_width)
        form_layout.addWidget(grp_gen)

        # 2. Logo and visual style
        grp_logo = QGroupBox("Logo et lisibilite")
        v_logo = QVBoxLayout(grp_logo)
        self.chk_logo = QCheckBox("Afficher le logo")
        self.chk_logo.setChecked(self.receipt_config["logo"].get("show", True))
        self.chk_logo.stateChanged.connect(self.update_config_from_ui)

        logo_path_layout = QHBoxLayout()
        self.txt_logo_path = QLineEdit(self.receipt_config["logo"].get("path", ""))
        self.txt_logo_path.setPlaceholderText(f"Logo par defaut: {get_logo_path()}")
        self.txt_logo_path.textChanged.connect(self.update_config_from_ui)
        btn_logo = QPushButton("Choisir...")
        btn_logo.clicked.connect(self.choose_logo)
        logo_path_layout.addWidget(self.txt_logo_path, 1)
        logo_path_layout.addWidget(btn_logo)

        logo_options = QFormLayout()
        self.sp_logo_w = QDoubleSpinBox(); self.sp_logo_w.setRange(10, 70); self.sp_logo_w.setSuffix(" mm")
        self.sp_logo_w.setValue(self.receipt_config["logo"].get("max_width_mm", 42.0))
        self.sp_logo_w.valueChanged.connect(self.update_config_from_ui)
        self.sp_logo_h = QDoubleSpinBox(); self.sp_logo_h.setRange(5, 40); self.sp_logo_h.setSuffix(" mm")
        self.sp_logo_h.setValue(self.receipt_config["logo"].get("max_height_mm", 18.0))
        self.sp_logo_h.valueChanged.connect(self.update_config_from_ui)
        self.cmb_logo_al = QComboBox(); self.cmb_logo_al.addItems(["left", "center", "right"])
        self.cmb_logo_al.setCurrentText(self.receipt_config["logo"].get("align", "center"))
        self.cmb_logo_al.currentTextChanged.connect(self.update_config_from_ui)
        logo_options.addRow("Fichier logo:", logo_path_layout)
        logo_options.addRow("Largeur max:", self.sp_logo_w)
        logo_options.addRow("Hauteur max:", self.sp_logo_h)
        logo_options.addRow("Alignement:", self.cmb_logo_al)

        style_options = QFormLayout()
        self.cmb_font = QComboBox(); self.cmb_font.addItems(["Segoe UI", "Arial", "Calibri", "Tahoma"])
        self.cmb_font.setCurrentText(self.receipt_config["font"].get("family", "Segoe UI"))
        self.cmb_font.currentTextChanged.connect(self.update_config_from_ui)
        style_options.addRow("Police:", self.cmb_font)
        v_logo.addWidget(self.chk_logo)
        v_logo.addLayout(logo_options)
        v_logo.addLayout(style_options)
        form_layout.addWidget(grp_logo)

        # 3. Product detail visibility and sizing
        grp_items = QGroupBox("Produits, prix et taxes")
        f_items = QFormLayout(grp_items)
        self.sp_table_sz = QSpinBox(); self.sp_table_sz.setRange(9, 28)
        self.sp_table_sz.setValue(self.receipt_config["table"].get("size", 13))
        self.sp_table_sz.valueChanged.connect(self.update_config_from_ui)
        self.chk_table_header = QCheckBox("Afficher l'en-tete")
        self.chk_table_header.setChecked(self.receipt_config["table"].get("show_header", True))
        self.chk_table_header.stateChanged.connect(self.update_config_from_ui)
        self.chk_unit_price = QCheckBox("Afficher prix unitaire HT")
        self.chk_unit_price.setChecked(self.receipt_config["table"].get("show_unit_price", True))
        self.chk_unit_price.stateChanged.connect(self.update_config_from_ui)
        self.chk_price_before = QCheckBox("Afficher prix avant remise")
        self.chk_price_before.setChecked(self.receipt_config["table"].get("show_price_before", True))
        self.chk_price_before.stateChanged.connect(self.update_config_from_ui)
        self.chk_line_discount = QCheckBox("Afficher remise si > 0")
        self.chk_line_discount.setChecked(self.receipt_config["table"].get("show_discount", True))
        self.chk_line_discount.stateChanged.connect(self.update_config_from_ui)
        self.chk_line_tva = QCheckBox("Afficher TVA si > 0")
        self.chk_line_tva.setChecked(self.receipt_config["table"].get("show_tva", True))
        self.chk_line_tva.stateChanged.connect(self.update_config_from_ui)
        self.sp_total_sz = QSpinBox(); self.sp_total_sz.setRange(12, 32)
        self.sp_total_sz.setValue(self.receipt_config["totals"].get("size", 18))
        self.sp_total_sz.valueChanged.connect(self.update_config_from_ui)
        self.chk_total_bold = QCheckBox("Total TTC en gras")
        self.chk_total_bold.setChecked(self.receipt_config["totals"].get("bold", True))
        self.chk_total_bold.stateChanged.connect(self.update_config_from_ui)
        f_items.addRow("Taille lignes:", self.sp_table_sz)
        f_items.addRow(self.chk_table_header)
        f_items.addRow(self.chk_unit_price)
        f_items.addRow(self.chk_price_before)
        f_items.addRow(self.chk_line_discount)
        f_items.addRow(self.chk_line_tva)
        f_items.addRow("Taille total:", self.sp_total_sz)
        f_items.addRow(self.chk_total_bold)
        form_layout.addWidget(grp_items)

        # 2. En-tête (Header)
        grp_header = QGroupBox("🏢 2. En-tête (Header)")
        v_head = QVBoxLayout(grp_header)
        self.chk_head = QCheckBox("Afficher l'En-tête")
        self.chk_head.setChecked(self.receipt_config["header"]["show"])
        self.chk_head.stateChanged.connect(self.update_config_from_ui)
        self.txt_head = QTextEdit(self.receipt_config["header"]["text"])
        self.txt_head.setMaximumHeight(80)
        self.txt_head.textChanged.connect(self.update_config_from_ui)
        
        h_head = QHBoxLayout()
        self.sp_head_sz = QSpinBox(); self.sp_head_sz.setRange(8, 36)
        self.sp_head_sz.setValue(self.receipt_config["header"]["size"])
        self.sp_head_sz.valueChanged.connect(self.update_config_from_ui)
        self.cmb_head_al = QComboBox(); self.cmb_head_al.addItems(["left", "center", "right"])
        self.cmb_head_al.setCurrentText(self.receipt_config["header"]["align"])
        self.cmb_head_al.currentTextChanged.connect(self.update_config_from_ui)
        h_head.addWidget(QLabel("Taille:")); h_head.addWidget(self.sp_head_sz)
        h_head.addWidget(QLabel("Align:")); h_head.addWidget(self.cmb_head_al)
        
        v_head.addWidget(self.chk_head)
        v_head.addWidget(self.txt_head)
        v_head.addLayout(h_head)
        form_layout.addWidget(grp_header)

        # 3. Informations
        grp_info = QGroupBox("🧾 3. Informations Facture")
        f_info = QFormLayout(grp_info)
        self.chk_date = QCheckBox("Afficher Date"); self.chk_date.setChecked(self.receipt_config["info"]["show_date"])
        self.chk_client = QCheckBox("Afficher Client"); self.chk_client.setChecked(self.receipt_config["info"]["show_client"])
        self.chk_cashier = QCheckBox("Afficher Caissier"); self.chk_cashier.setChecked(self.receipt_config["info"]["show_cashier"])
        self.sp_info_sz = QSpinBox(); self.sp_info_sz.setRange(8, 24); self.sp_info_sz.setValue(self.receipt_config["info"]["size"])
        self.chk_date.stateChanged.connect(self.update_config_from_ui)
        self.chk_client.stateChanged.connect(self.update_config_from_ui)
        self.chk_cashier.stateChanged.connect(self.update_config_from_ui)
        self.sp_info_sz.valueChanged.connect(self.update_config_from_ui)
        
        f_info.addRow(self.chk_date, self.chk_client)
        f_info.addRow(self.chk_cashier, None)
        f_info.addRow("Taille du texte:", self.sp_info_sz)
        form_layout.addWidget(grp_info)

        # 4. Pied de page & Code-barres
        grp_foot = QGroupBox("📝 4. Pied de page & Code-barres")
        v_foot = QVBoxLayout(grp_foot)
        
        self.chk_foot = QCheckBox("Afficher Pied de page")
        self.chk_foot.setChecked(self.receipt_config["footer"]["show"])
        self.chk_foot.stateChanged.connect(self.update_config_from_ui)
        self.txt_foot = QTextEdit(self.receipt_config["footer"]["text"])
        self.txt_foot.setMaximumHeight(60)
        self.txt_foot.textChanged.connect(self.update_config_from_ui)
        
        h_foot = QHBoxLayout()
        self.sp_foot_sz = QSpinBox(); self.sp_foot_sz.setRange(8, 36)
        self.sp_foot_sz.setValue(self.receipt_config["footer"]["size"])
        self.sp_foot_sz.valueChanged.connect(self.update_config_from_ui)
        h_foot.addWidget(QLabel("Taille:")); h_foot.addWidget(self.sp_foot_sz)
        
        line = QWidget(); line.setFixedHeight(1); line.setStyleSheet("background-color: #ddd;")
        
        self.chk_bc = QCheckBox("Afficher Code-barres (ID Facture)")
        self.chk_bc.setChecked(self.receipt_config["barcode"]["show"])
        self.chk_bc.stateChanged.connect(self.update_config_from_ui)
        
        h_bc = QHBoxLayout()
        self.sp_bc_h = QDoubleSpinBox(); self.sp_bc_h.setRange(5, 50)
        self.sp_bc_h.setValue(self.receipt_config["barcode"]["height_mm"])
        self.sp_bc_h.valueChanged.connect(self.update_config_from_ui)
        h_bc.addWidget(QLabel("Hauteur (mm):")); h_bc.addWidget(self.sp_bc_h)

        v_foot.addWidget(self.chk_foot)
        v_foot.addWidget(self.txt_foot)
        v_foot.addLayout(h_foot)
        v_foot.addWidget(line)
        v_foot.addWidget(self.chk_bc)
        v_foot.addLayout(h_bc)
        form_layout.addWidget(grp_foot)
        
        form_layout.addStretch()
        content.setLayout(form_layout)
        scroll.setWidget(content)
        left_layout.addWidget(scroll)

        # Preview Panel
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
        self.lbl_preview.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.lbl_preview.setStyleSheet("background-color: #e0e0e0; margin: 10px;")
        scroll_prev.setWidget(self.lbl_preview)
        l_prev.addWidget(scroll_prev)
        
        right_layout.addWidget(grp_prev)

        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([400, 600])
        self.load_templates()

    def choose_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir le logo de la facture",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self.txt_logo_path.setText(path)

    def update_config_from_ui(self):
        if not hasattr(self, 'cmb_width'): return
        
        self.receipt_config["paper_width_mm"] = 58.0 if "58" in self.cmb_width.currentText() else 80.0
        
        self.receipt_config["header"]["show"] = self.chk_head.isChecked()
        self.receipt_config["header"]["text"] = self.txt_head.toPlainText()
        self.receipt_config["header"]["size"] = self.sp_head_sz.value()
        self.receipt_config["header"]["align"] = self.cmb_head_al.currentText()

        self.receipt_config["logo"]["show"] = self.chk_logo.isChecked()
        self.receipt_config["logo"]["path"] = self.txt_logo_path.text().strip()
        self.receipt_config["logo"]["max_width_mm"] = self.sp_logo_w.value()
        self.receipt_config["logo"]["max_height_mm"] = self.sp_logo_h.value()
        self.receipt_config["logo"]["align"] = self.cmb_logo_al.currentText()
        self.receipt_config["font"]["family"] = self.cmb_font.currentText()
        
        self.receipt_config["info"]["show_date"] = self.chk_date.isChecked()
        self.receipt_config["info"]["show_client"] = self.chk_client.isChecked()
        self.receipt_config["info"]["show_cashier"] = self.chk_cashier.isChecked()
        self.receipt_config["info"]["size"] = self.sp_info_sz.value()

        self.receipt_config["table"]["size"] = self.sp_table_sz.value()
        self.receipt_config["table"]["show_header"] = self.chk_table_header.isChecked()
        self.receipt_config["table"]["show_unit_price"] = self.chk_unit_price.isChecked()
        self.receipt_config["table"]["show_price_before"] = self.chk_price_before.isChecked()
        self.receipt_config["table"]["show_discount"] = self.chk_line_discount.isChecked()
        self.receipt_config["table"]["show_tva"] = self.chk_line_tva.isChecked()
        self.receipt_config["totals"]["size"] = self.sp_total_sz.value()
        self.receipt_config["totals"]["bold"] = self.chk_total_bold.isChecked()
        
        self.receipt_config["footer"]["show"] = self.chk_foot.isChecked()
        self.receipt_config["footer"]["text"] = self.txt_foot.toPlainText()
        self.receipt_config["footer"]["size"] = self.sp_foot_sz.value()
        
        self.receipt_config["barcode"]["show"] = self.chk_bc.isChecked()
        self.receipt_config["barcode"]["height_mm"] = self.sp_bc_h.value()

        self.save_config()
        self.trigger_preview()

    def generate_preview(self):
        try:
            printer = getattr(self.data_manager, "printer", None)
            if printer and hasattr(printer, "_create_receipt_image"):
                sample_data = {
                    "id": "2026/0001",
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "client": "Client Exemple",
                    "cashier": "Caisse Demo",
                    "currency": "DA",
                    "logo_path": self.receipt_config["logo"].get("path") or get_logo_path(),
                    "items": [
                        {
                            "name": "Produit A",
                            "qty": 2,
                            "unit_price_ht": 500.0,
                            "price_before": 1000.0,
                            "discount_percent": 5.0,
                            "discount_amount": 50.0,
                            "net_ht": 950.0,
                            "tva_percent": 19.0,
                            "tva_amount": 180.5,
                            "total": 1130.5,
                        },
                        {
                            "name": "Produit B",
                            "qty": 1,
                            "unit_price_ht": 1200.0,
                            "price_before": 1200.0,
                            "discount_percent": 0.0,
                            "discount_amount": 0.0,
                            "net_ht": 1200.0,
                            "tva_percent": 19.0,
                            "tva_amount": 228.0,
                            "total": 1428.0,
                        },
                    ],
                    "subtotal_ht": 2200.0,
                    "remise_total": 50.0,
                    "net_ht": 2150.0,
                    "tva_total": 408.5,
                    "total": 2558.5,
                }
                img = printer._create_receipt_image(sample_data, config_override=self.receipt_config)
                qimg = QImage(img.convert("RGBA").tobytes("raw", "RGBA"), img.size[0], img.size[1], QImage.Format_RGBA8888)
                final_w = int(qimg.width() * self.zoom_factor)
                final_h = int(qimg.height() * self.zoom_factor)
                qimg_scaled = qimg.scaled(final_w, final_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_preview.setPixmap(QPixmap.fromImage(qimg_scaled))
                self.lbl_preview.setFixedSize(final_w, final_h)
                return
        except Exception as e:
            logging.error(f"Receipt preview error: {e}", exc_info=True)

        px_per_mm = 8.0 # 203 dpi
        w_px = int(self.receipt_config["paper_width_mm"] * px_per_mm)
        margin = int(2 * px_per_mm)
        print_w = w_px - (margin * 2)
        
        # Determine total height dynamically
        # Start with a generous height, we'll crop it at the end
        h_px = 3000
        img = Image.new('L', (w_px, h_px), 255)
        draw = ImageDraw.Draw(img)
        
        current_y = margin
        
        def get_font(size_pt, bold=False):
            try:
                font_name = "arialbd.ttf" if bold else "arial.ttf"
                return ImageFont.truetype(font_name, size_pt)
            except:
                return ImageFont.load_default()
                
        def draw_text(text, y, font, align="left", fill=0):
            lines = text.split('\n')
            new_y = y
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                lw = bbox[2] - bbox[0]
                lh = bbox[3] - bbox[1] + 4
                
                if align == "center":
                    x = (w_px - lw) // 2
                elif align == "right":
                    x = w_px - margin - lw
                else:
                    x = margin
                    
                draw.text((x, new_y), line, font=font, fill=fill)
                new_y += lh
            return new_y
            
        # 1. Header
        if self.receipt_config["header"]["show"]:
            f_head = get_font(self.receipt_config["header"]["size"], bold=True)
            current_y = draw_text(self.receipt_config["header"]["text"], current_y, f_head, self.receipt_config["header"]["align"])
            current_y += 10
            
        # Divider
        draw.line([(margin, current_y), (w_px-margin, current_y)], fill=0, width=2)
        current_y += 10

        # 2. Info
        f_info = get_font(self.receipt_config["info"]["size"])
        draw_text("Facture: #FCT-260713", current_y, f_info)
        current_y += self.receipt_config["info"]["size"] + 4
        
        if self.receipt_config["info"]["show_date"]:
            draw_text(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", current_y, f_info)
            current_y += self.receipt_config["info"]["size"] + 4
        if self.receipt_config["info"]["show_client"]:
            draw_text("Client: Client Passager", current_y, f_info)
            current_y += self.receipt_config["info"]["size"] + 4
        if self.receipt_config["info"]["show_cashier"]:
            draw_text("Caissier: Admin", current_y, f_info)
            current_y += self.receipt_config["info"]["size"] + 4

        current_y += 5
        draw.line([(margin, current_y), (w_px-margin, current_y)], fill=0, width=1)
        current_y += 10

        # 3. Table Headers
        f_table = get_font(self.receipt_config["table"]["size"])
        draw_text("Article", margin, f_table)
        draw_text("Qte", margin + int(print_w * 0.5), f_table)
        draw_text("Prix", margin + int(print_w * 0.7), f_table)
        draw_text("Total", w_px - margin - 40, f_table) # Approximate right align
        
        current_y += self.receipt_config["table"]["size"] + 4
        draw.line([(margin, current_y), (w_px-margin, current_y)], fill=0, width=1)
        current_y += 10

        # 4. Items (Sample)
        items = [("Produit A", "2", "500", "1000"), ("Produit B", "1", "1200", "1200")]
        for item, q, p, t in items:
            draw_text(item, margin, f_table)
            draw_text(q, margin + int(print_w * 0.5), f_table)
            draw_text(p, margin + int(print_w * 0.7), f_table)
            draw_text(t, w_px - margin - 40, f_table)
            current_y += self.receipt_config["table"]["size"] + 6

        draw.line([(margin, current_y), (w_px-margin, current_y)], fill=0, width=2)
        current_y += 10

        # 5. Totals
        f_tot = get_font(self.receipt_config["totals"]["size"], bold=True)
        draw_text("TOTAL A PAYER:", margin + int(print_w * 0.2), f_tot)
        current_y = draw_text("2200 DA", current_y, f_tot, align="right")
        current_y += 20
        
        # 6. Footer
        if self.receipt_config["footer"]["show"]:
            f_foot = get_font(self.receipt_config["footer"]["size"])
            current_y = draw_text(self.receipt_config["footer"]["text"], current_y, f_foot, align="center")
            current_y += 20
            
        # 7. Barcode
        if self.receipt_config["barcode"]["show"]:
            try:
                bc_class = barcode.get_barcode_class('code128') 
                writer = ImageWriter()
                opts = {"module_width": 0.4, "module_height": 8.0, "quiet_zone": 1.0, "write_text": False}
                
                fp = io.BytesIO()
                bc_obj = bc_class("FCT-260713", writer=writer)
                bc_obj.write(fp, options=opts)
                fp.seek(0)
                bc_img = Image.open(fp).convert("L")
                
                target_w = int(print_w * 0.8)
                target_h = int(self.receipt_config["barcode"]["height_mm"] * px_per_mm)
                bc_img = bc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                
                bc_x = (w_px - target_w) // 2
                img.paste(bc_img, (bc_x, current_y))
                current_y += target_h + 5
                
                # barcode text
                f_bc = get_font(self.receipt_config["barcode"]["size"])
                current_y = draw_text("FCT-260713", current_y, f_bc, align="center")
                current_y += 20
            except Exception as e:
                logging.error(f"Error drawing barcode: {e}")

        # Crop image to actual height used
        img = img.crop((0, 0, w_px, current_y + margin))

        # Convert to QPixmap
        img_bytes = img.convert("RGBA").tobytes("raw", "RGBA")
        qimg = QImage(img_bytes, img.size[0], img.size[1], QImage.Format_RGBA8888)
        
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
        
        templates = self.tpl_mgr.get_templates('receipt')
        if not templates:
            # Create a default if DB is empty
            self.tpl_mgr.save_template('receipt', 'Standard', self.receipt_config)
            templates = self.tpl_mgr.get_templates('receipt')
            
        for t in templates:
            self.cmb_template.addItem(t['name'], t['settings'])
            
        # Select active template from local config
        active_name = self.data_manager.printer.config.get("active_receipt_template", "Standard")
        idx = self.cmb_template.findText(active_name)
        if idx >= 0:
            self.cmb_template.setCurrentIndex(idx)
            self.receipt_config = self.cmb_template.itemData(idx)
        else:
            if self.cmb_template.count() > 0:
                self.cmb_template.setCurrentIndex(0)
                self.receipt_config = self.cmb_template.itemData(0)
                self.data_manager.printer.config["active_receipt_template"] = self.cmb_template.currentText()
            else:
                pass
            
        self.cmb_template.blockSignals(False)
        self.update_ui_from_config()

    def on_template_changed(self, text):
        idx = self.cmb_template.findText(text)
        if idx >= 0:
            self.receipt_config = self.cmb_template.itemData(idx)
            self.data_manager.printer.config["active_receipt_template"] = text
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
            self.data_manager.printer.config["active_receipt_template"] = name
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
                self.data_manager.printer.config["active_receipt_template"] = new_name
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

        self.chk_logo.blockSignals(True); self.chk_logo.setChecked(self.receipt_config["logo"].get("show", True)); self.chk_logo.blockSignals(False)
        self.txt_logo_path.blockSignals(True); self.txt_logo_path.setText(self.receipt_config["logo"].get("path", "")); self.txt_logo_path.blockSignals(False)
        self.sp_logo_w.blockSignals(True); self.sp_logo_w.setValue(self.receipt_config["logo"].get("max_width_mm", 42.0)); self.sp_logo_w.blockSignals(False)
        self.sp_logo_h.blockSignals(True); self.sp_logo_h.setValue(self.receipt_config["logo"].get("max_height_mm", 18.0)); self.sp_logo_h.blockSignals(False)
        self.cmb_logo_al.blockSignals(True); self.cmb_logo_al.setCurrentText(self.receipt_config["logo"].get("align", "center")); self.cmb_logo_al.blockSignals(False)
        self.cmb_font.blockSignals(True); self.cmb_font.setCurrentText(self.receipt_config["font"].get("family", "Segoe UI")); self.cmb_font.blockSignals(False)
        
        self.chk_date.blockSignals(True); self.chk_date.setChecked(self.receipt_config["info"]["show_date"]); self.chk_date.blockSignals(False)
        self.chk_client.blockSignals(True); self.chk_client.setChecked(self.receipt_config["info"]["show_client"]); self.chk_client.blockSignals(False)
        self.chk_cashier.blockSignals(True); self.chk_cashier.setChecked(self.receipt_config["info"]["show_cashier"]); self.chk_cashier.blockSignals(False)
        self.sp_info_sz.blockSignals(True); self.sp_info_sz.setValue(self.receipt_config["info"]["size"]); self.sp_info_sz.blockSignals(False)

        self.sp_table_sz.blockSignals(True); self.sp_table_sz.setValue(self.receipt_config["table"].get("size", 13)); self.sp_table_sz.blockSignals(False)
        self.chk_table_header.blockSignals(True); self.chk_table_header.setChecked(self.receipt_config["table"].get("show_header", True)); self.chk_table_header.blockSignals(False)
        self.chk_unit_price.blockSignals(True); self.chk_unit_price.setChecked(self.receipt_config["table"].get("show_unit_price", True)); self.chk_unit_price.blockSignals(False)
        self.chk_price_before.blockSignals(True); self.chk_price_before.setChecked(self.receipt_config["table"].get("show_price_before", True)); self.chk_price_before.blockSignals(False)
        self.chk_line_discount.blockSignals(True); self.chk_line_discount.setChecked(self.receipt_config["table"].get("show_discount", True)); self.chk_line_discount.blockSignals(False)
        self.chk_line_tva.blockSignals(True); self.chk_line_tva.setChecked(self.receipt_config["table"].get("show_tva", True)); self.chk_line_tva.blockSignals(False)
        self.sp_total_sz.blockSignals(True); self.sp_total_sz.setValue(self.receipt_config["totals"].get("size", 18)); self.sp_total_sz.blockSignals(False)
        self.chk_total_bold.blockSignals(True); self.chk_total_bold.setChecked(self.receipt_config["totals"].get("bold", True)); self.chk_total_bold.blockSignals(False)
        
        self.chk_foot.blockSignals(True); self.chk_foot.setChecked(self.receipt_config["footer"]["show"]); self.chk_foot.blockSignals(False)
        self.txt_foot.blockSignals(True); self.txt_foot.setPlainText(self.receipt_config["footer"]["text"]); self.txt_foot.blockSignals(False)
        self.sp_foot_sz.blockSignals(True); self.sp_foot_sz.setValue(self.receipt_config["footer"]["size"]); self.sp_foot_sz.blockSignals(False)
        
        self.chk_bc.blockSignals(True); self.chk_bc.setChecked(self.receipt_config["barcode"]["show"]); self.chk_bc.blockSignals(False)
        self.sp_bc_h.blockSignals(True); self.sp_bc_h.setValue(self.receipt_config["barcode"]["height_mm"]); self.sp_bc_h.blockSignals(False)
