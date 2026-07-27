# database/managers/printer_manager.py

import os
import json
import logging
import io
import win32print
import barcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont, ImageOps
import sys
from branding import get_app_name, get_logo_path

def get_external_path(filename):
    """ Récupère le chemin absolu du fichier, compatible avec PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.abspath("."), filename)

CONFIG_FILE = get_external_path("config.json")

class PrinterManager:
    """
    Gère la conception et l'impression des étiquettes de codes-barres pour le laboratoire.
    Structure de l'étiquette : Code-barres (haut) -> Nom du produit -> Lot & Expiration.
    """
    def __init__(self, db_instance=None):
        self.db = db_instance
        self.local_settings = None
        self.config = {
            "selected_printer": "",
            "selected_receipt_printer": "",
            "label_width": 50,
            "label_height": 30,
            "gap": 2,
            "font_size_name": 18,
            "font_size_info": 16,
            "font_size_barcode": 14,
            "active_receipt_template": "Standard",
            "receipt_settings": {},
            "receipt_logo_path": "",
            "lab_name": "",
            "lab_address": "",
            "lab_nif": "",
            "lab_rc": "",
        }
        self.reload_settings()

    def set_local_settings(self, local_settings):
        """Use the current user's local settings for printer configuration."""
        self.local_settings = local_settings
        self.reload_settings()

    def reload_settings(self):
        """Reload printer settings from the current user's local store."""
        try:
            if self.local_settings is not None:
                data = self.local_settings.load_general(self.config)
            elif os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            for key in self.config.keys():
                if key in data:
                    self.config[key] = data[key]
        except Exception as e:
            logging.error(f"PrinterManager settings load failed: {e}")

    def get_available_printers(self):
        """ Retourne la liste des imprimantes installées sur le système """
        try:
            printers = win32print.EnumPrinters(2)
            return [p[2] for p in printers] if printers else []
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des imprimantes : {e}")
            return []

    # ----------------------------------------------------------------
    # 1. CONCEPTION DE L'ÉTIQUETTE
    # ----------------------------------------------------------------
    def _create_label_image(self, product_name, barcode_data, lot_number, expiry_date):
        """ 
        تصميم الملصق بناءً على الإعدادات المرئية من config.json 
        """
        px_per_mm = 8.0 # 203 dpi
        
        # Fetch template from DB if available
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
            label_settings = self.config.get("label_settings")
        if label_settings:
            w_px = int(label_settings.get("label_width_mm", 40) * px_per_mm)
            h_px = int(label_settings.get("label_height_mm", 20) * px_per_mm)
            els = label_settings.get("elements", {})
        else:
            w_px = int(self.config.get("label_width", 40) * px_per_mm)
            h_px = int(self.config.get("label_height", 20) * px_per_mm)
            els = {
                "barcode": {"show": True, "x": 2.0, "y": 2.0, "width": 30.0, "height": 8.0, "text_size": 10},
                "product": {"show": True, "x": 2.0, "y": 12.0, "size": 14, "angle": 0},
                "lot": {"show": True, "x": 35.0, "y": 2.0, "size": 10, "angle": 90, "prefix": "LOT: "},
                "expiry": {"show": True, "x": 35.0, "y": 10.0, "size": 10, "angle": 90, "prefix": "EXP: "},
                "company": {"show": False, "text": "Labo Algérie", "x": 2.0, "y": 0.5, "size": 10, "angle": 0}
            }

        img = Image.new('L', (w_px, h_px), 255) 
        draw = ImageDraw.Draw(img)
        
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
        if els.get("company", {}).get("show"):
            c_el = els["company"]
            draw_text(c_el.get("text", ""), c_el["x"], c_el["y"], c_el["size"], c_el.get("angle", 0))
            
        # Product
        if els.get("product", {}).get("show"):
            p_el = els["product"]
            draw_text(str(product_name).upper(), p_el["x"], p_el["y"], p_el["size"], p_el.get("angle", 0))
            
        # Lot
        if els.get("lot", {}).get("show"):
            l_el = els["lot"]
            draw_text(f"{l_el.get('prefix', '')}{lot_number}", l_el["x"], l_el["y"], l_el["size"], l_el.get("angle", 90))
            
        # Expiry
        if els.get("expiry", {}).get("show"):
            e_el = els["expiry"]
            exp_str = str(expiry_date)[:10] if expiry_date and str(expiry_date) != "None" else ""
            draw_text(f"{e_el.get('prefix', '')}{exp_str}", e_el["x"], e_el["y"], e_el["size"], e_el.get("angle", 90))
            
        # Barcode
        if els.get("barcode", {}).get("show"):
            b_el = els["barcode"]
            bc_text = str(barcode_data)
            try:
                bc_class = barcode.get_barcode_class('code128') 
                writer = ImageWriter()
                opts = {"module_width": 0.5, "module_height": 10.0, "quiet_zone": 1.0, "write_text": False}
                
                fp = io.BytesIO()
                bc_obj = bc_class(bc_text, writer=writer)
                bc_obj.write(fp, options=opts)
                fp.seek(0)
                bc_img = Image.open(fp).convert("L")
                
                target_w = int(b_el.get("width", 30) * px_per_mm)
                target_h = int(b_el.get("height", 8) * px_per_mm)
                bc_img = bc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                
                img.paste(bc_img, (int(b_el["x"] * px_per_mm), int(b_el["y"] * px_per_mm)))
                
                try:
                    f_bc = ImageFont.truetype("arial.ttf", b_el.get("text_size", 10))
                except:
                    f_bc = ImageFont.load_default()
                
                text_y = int(b_el["y"] * px_per_mm) + target_h + 2
                text_x = int(b_el["x"] * px_per_mm) + (target_w // 4)
                draw.text((text_x, text_y), bc_text, font=f_bc, fill=0)
            except Exception as e:
                logging.error(f"Error in label design: {e}")

        return img.convert('1')

    # ----------------------------------------------------------------
    # 2. CONVERSION DE L'IMAGE EN COMMANDES TSPL
    # ----------------------------------------------------------------
    def _image_to_tspl(self, pil_img, copies=1):
        """ Convertit l'image PIL en langage de programmation TSPL """
        w_mm = self.config['label_width']
        h_mm = self.config['label_height']
        gap = self.config['gap']
        
        W, H = pil_img.size
        Wb = (W + 7) // 8 
        
        data = pil_img.tobytes()
        
        cmds = [
            f"SIZE {w_mm} mm, {h_mm} mm",
            f"GAP {gap} mm, 0 mm",
            "DIRECTION 1",
            "CLS",
            f"BITMAP 0,0,{Wb},{H},0,"
        ]
        
        header = "\r\n".join(cmds).encode("ascii")
        footer = f"\r\nPRINT {copies}\r\n".encode("ascii")
        
        return header + data + footer

    # ----------------------------------------------------------------
    # 3. EXÉCUTION DE L'IMPRESSION
    # ----------------------------------------------------------------
    def print_label(self, product_name, barcode_data, lot_number, expiry_date, copies=1):
        """ Envoie le travail d'impression à l'imprimante sélectionnée """
        self.reload_settings()
        
        printer_name = self.config.get('selected_printer')
        if not printer_name:
            return False, "Aucune imprimante sélectionnée dans les paramètres."

        try:
            img = self._create_label_image(product_name, barcode_data, lot_number, expiry_date)
            if not img:
                return False, "Échec de la création du design de l'étiquette."

            raw_data = self._image_to_tspl(img, copies)

            hprinter = win32print.OpenPrinter(printer_name)
            try:
                job_info = ("Travail Etiquette LIMS", None, "RAW")
                win32print.StartDocPrinter(hprinter, 1, job_info)
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, raw_data)
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
            
            logging.info(f"Étiquette imprimée pour {product_name} sur {printer_name}")
            return True, "Commande d'impression envoyée avec succès."

        except Exception as e:
            logging.error(f"Exception lors de l'impression : {e}")
            return False, f"Erreur d'impression : {e}"
    # ----------------------------------------------------------------
    # 4. IMPRESSION FACTURE (TICKET THERMIQUE)
    # ----------------------------------------------------------------
    def _create_receipt_image_legacy(self, invoice_data):
        from datetime import datetime
        px_per_mm = 8.0 # 203 dpi
        
        # Fetch template from DB if available
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

            "paper_width_mm": 80.0,
            "header": {"show": True, "text": "Nom Entreprise", "align": "center", "size": 16},
            "info": {"show_date": True, "show_client": True, "show_cashier": True, "size": 12},
            "table": {"size": 12, "show_header": True},
            "totals": {"size": 14, "bold": True},
            "footer": {"show": True, "text": "Merci!", "align": "center", "size": 14},
            "barcode": {"show": True, "height_mm": 10.0, "size": 12}
        })

        w_px = int(cfg.get("paper_width_mm", 80.0) * px_per_mm)
        margin = int(2 * px_per_mm)
        print_w = w_px - (margin * 2)
        
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

        if cfg["header"]["show"]:
            f_head = get_font(cfg["header"]["size"], bold=True)
            current_y = draw_text(cfg["header"]["text"], current_y, f_head, cfg["header"]["align"])
            current_y += 10
            
        draw.line([(margin, current_y), (w_px-margin, current_y)], fill=0, width=2)
        current_y += 10

        f_info = get_font(cfg["info"]["size"])
        invoice_id = invoice_data.get('id', 'FCT-000')
        draw_text(f"Facture: #{invoice_id}", current_y, f_info)
        current_y += cfg["info"]["size"] + 4
        
        if cfg["info"]["show_date"]:
            draw_text(f"Date: {invoice_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M'))}", current_y, f_info)
            current_y += cfg["info"]["size"] + 4
        if cfg["info"]["show_client"]:
            client_name = invoice_data.get('client', '').strip()
            if client_name and client_name.lower() != 'passager' and client_name.lower() != 'vente comptoir':
                draw_text(f"Client: {client_name}", current_y, f_info)
                current_y += cfg["info"]["size"] + 4
        if cfg["info"]["show_cashier"]:
            draw_text(f"Caissier: {invoice_data.get('cashier', 'Admin')}", current_y, f_info)
            current_y += cfg["info"]["size"] + 4

        current_y += 5
        draw.line([(margin, current_y), (w_px-margin, current_y)], fill=0, width=1)
        current_y += 10

        f_table = get_font(cfg["table"]["size"])
        if cfg["table"]["show_header"]:
            draw_text("Article", margin, f_table)
            draw_text("Qte", margin + int(print_w * 0.5), f_table)
            draw_text("Prix", margin + int(print_w * 0.7), f_table)
            draw_text("Total", w_px - margin - 40, f_table)
            current_y += cfg["table"]["size"] + 4
            draw.line([(margin, current_y), (w_px-margin, current_y)], fill=0, width=1)
            current_y += 10

        for item in invoice_data.get('items', []):
            name, q, p, t = item.get('name', ''), str(item.get('qty', 0)), str(item.get('price', 0)), str(item.get('total', 0))
            draw_text(name, margin, f_table)
            draw_text(q, margin + int(print_w * 0.5), f_table)
            draw_text(p, margin + int(print_w * 0.7), f_table)
            draw_text(t, w_px - margin - 40, f_table)
            current_y += cfg["table"]["size"] + 6

        draw.line([(margin, current_y), (w_px-margin, current_y)], fill=0, width=2)
        current_y += 10

        f_tot = get_font(cfg["totals"]["size"], bold=cfg["totals"].get("bold", True))
        f_sub = get_font(max(10, cfg["totals"]["size"] - 2))
        
        subtotal_ht = float(invoice_data.get('subtotal_ht', 0))
        remise_total = float(invoice_data.get('remise_total', 0))
        tva_total = float(invoice_data.get('tva_total', 0))
        total_ttc = float(invoice_data.get('total', 0))
        
        if remise_total > 0 or tva_total > 0:
            draw_text("Sous-total HT:", margin + int(print_w * 0.2), f_sub)
            current_y = draw_text(f"{subtotal_ht:.2f} DA", current_y, f_sub, align="right")
            current_y += 5
            
        if remise_total > 0:
            draw_text("Remise:", margin + int(print_w * 0.2), f_sub)
            current_y = draw_text(f"-{remise_total:.2f} DA", current_y, f_sub, align="right")
            current_y += 5
            
        if tva_total > 0:
            draw_text("TVA:", margin + int(print_w * 0.2), f_sub)
            current_y = draw_text(f"+{tva_total:.2f} DA", current_y, f_sub, align="right")
            current_y += 5
            
        if remise_total > 0 or tva_total > 0:
            draw.line([(margin + int(print_w * 0.2), current_y), (w_px-margin, current_y)], fill=0, width=1)
            current_y += 10
            
        draw_text("TOTAL A PAYER:", margin + int(print_w * 0.2), f_tot)
        current_y = draw_text(f"{total_ttc:.2f} DA", current_y, f_tot, align="right")
        current_y += 20
        
        if cfg["footer"]["show"]:
            f_foot = get_font(cfg["footer"]["size"])
            current_y = draw_text(cfg["footer"]["text"], current_y, f_foot, align="center")
            current_y += 20
            
        if cfg["barcode"]["show"]:
            try:
                bc_class = barcode.get_barcode_class('code128') 
                writer = ImageWriter()
                opts = {"module_width": 0.4, "module_height": 8.0, "quiet_zone": 1.0, "write_text": False}
                
                fp = io.BytesIO()
                bc_obj = bc_class(invoice_id, writer=writer)
                bc_obj.write(fp, options=opts)
                fp.seek(0)
                bc_img = Image.open(fp).convert("L")
                
                target_w = int(print_w * 0.8)
                target_h = int(cfg["barcode"]["height_mm"] * px_per_mm)
                bc_img = bc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                
                bc_x = (w_px - target_w) // 2
                img.paste(bc_img, (bc_x, current_y))
                current_y += target_h + 5
                
                f_bc = get_font(cfg["barcode"]["size"])
                current_y = draw_text(invoice_id, current_y, f_bc, align="center")
                current_y += 20
            except Exception as e:
                logging.error(f"Error drawing barcode: {e}")

        img = img.crop((0, 0, w_px, current_y + margin))
        return img.convert('1')

    def _create_receipt_image(self, invoice_data, config_override=None):
        return self._create_professional_receipt_image(invoice_data, config_override)

    def _create_professional_receipt_image(self, invoice_data, config_override=None):
        """Render a readable, data-rich thermal receipt image."""
        from datetime import datetime

        px_per_mm = 8.0  # 203 dpi thermal printers
        defaults = {
            "paper_width_mm": 80.0,
            "header": {
                "show": True,
                "text": f"{get_app_name()}\nAdresse\nTel: 000000000",
                "align": "center",
                "size": 20,
            },
            "logo": {
                "show": True,
                "path": "",
                "max_width_mm": 42.0,
                "max_height_mm": 18.0,
                "align": "center",
            },
            "font": {
                "family": "Segoe UI",
                "regular_path": "",
                "bold_path": "",
            },
            "info": {
                "show_date": True,
                "show_client": True,
                "show_cashier": True,
                "size": 14,
            },
            "table": {
                "size": 13,
                "show_header": True,
                "show_unit_price": True,
                "show_price_before": True,
                "show_discount": True,
                "show_tva": True,
            },
            "totals": {"size": 18, "bold": True},
            "footer": {
                "show": True,
                "text": "Merci pour votre visite!",
                "align": "center",
                "size": 14,
            },
            "barcode": {"show": True, "height_mm": 10.0, "size": 12},
        }

        def merge_config(base, override):
            result = {}
            for key, value in base.items():
                result[key] = dict(value) if isinstance(value, dict) else value
            if isinstance(override, dict):
                for key, value in override.items():
                    if isinstance(value, dict) and isinstance(result.get(key), dict):
                        result[key].update(value)
                    else:
                        result[key] = value
            return result

        cfg_source = config_override
        if cfg_source is None:
            active_template = self.config.get("active_receipt_template", "Standard")
            if self.db:
                try:
                    from .template_manager import TemplateManager
                    cfg_source = TemplateManager(self.db).get_template_by_name("receipt", active_template)
                except Exception as e:
                    logging.error(f"Error fetching receipt template for printing: {e}")
            if not cfg_source:
                cfg_source = self.config.get("receipt_settings", {})
        cfg = merge_config(defaults, cfg_source or {})

        w_px = int(float(cfg.get("paper_width_mm", 80.0)) * px_per_mm)
        margin = int(2.5 * px_per_mm)
        print_w = max(1, w_px - (margin * 2))
        img = Image.new("L", (w_px, 5000), 255)
        draw = ImageDraw.Draw(img)
        current_y = margin

        font_cfg = cfg.get("font", {}) or {}
        family = str(font_cfg.get("family", "Segoe UI")).strip().lower()
        family_paths = {
            "segoe ui": (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
            "arial": (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
            "calibri": (r"C:\Windows\Fonts\calibri.ttf", r"C:\Windows\Fonts\calibrib.ttf"),
            "tahoma": (r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\tahomabd.ttf"),
        }

        def get_font(size, bold=False):
            size = max(9, int(size or 12))
            custom_key = "bold_path" if bold else "regular_path"
            candidates = []
            custom_path = str(font_cfg.get(custom_key) or "").strip()
            if custom_path:
                candidates.append(os.path.expandvars(os.path.expanduser(custom_path)))
            candidates.extend(family_paths.get(family, ()))
            candidates.extend(
                [
                    r"C:\Windows\Fonts\segoeui.ttf" if not bold else r"C:\Windows\Fonts\segoeuib.ttf",
                    "arial.ttf" if not bold else "arialbd.ttf",
                    "DejaVuSans.ttf" if not bold else "DejaVuSans-Bold.ttf",
                ]
            )
            for path in candidates:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
            return ImageFont.load_default()

        def text_width(text, font):
            bbox = draw.textbbox((0, 0), str(text), font=font)
            return bbox[2] - bbox[0]

        def wrap_text(text, font, max_width):
            max_width = max(20, int(max_width))
            output = []
            for raw_line in str(text or "").splitlines() or [""]:
                words = raw_line.split()
                if not words:
                    output.append("")
                    continue
                line = ""
                for word in words:
                    candidate = word if not line else f"{line} {word}"
                    if text_width(candidate, font) <= max_width:
                        line = candidate
                        continue
                    if line:
                        output.append(line)
                    line = word
                    while text_width(line, font) > max_width and len(line) > 1:
                        split_at = max(1, len(line) - 1)
                        output.append(line[:split_at])
                        line = line[split_at:]
                output.append(line)
            return output or [""]

        def draw_text(text, y, font, align="left", max_width=None):
            max_width = max_width or print_w
            lines = wrap_text(text, font, max_width)
            new_y = y
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                line_height = max(12, bbox[3] - bbox[1] + 5)
                if align == "center":
                    x = (w_px - line_width) // 2
                elif align == "right":
                    x = w_px - margin - line_width
                else:
                    x = margin
                draw.text((x, new_y), line, font=font, fill=0)
                new_y += line_height
            return new_y

        def draw_pair(label, value, font, y):
            left_y = draw_text(label, y, font, max_width=int(print_w * 0.58))
            right_y = draw_text(value, y, font, align="right", max_width=int(print_w * 0.40))
            return max(left_y, right_y)

        def format_money(value):
            currency = invoice_data.get("currency", "DA")
            return f"{float(value or 0):,.2f} {currency}"

        def format_qty(value):
            number = float(value or 0)
            return str(int(number)) if number.is_integer() else f"{number:.2f}".rstrip("0").rstrip(".")

        # 1. Logo and business header
        logo_cfg = cfg.get("logo", {}) or {}
        logo_path = (
            logo_cfg.get("path")
            or invoice_data.get("logo_path")
            or self.config.get("receipt_logo_path")
            or get_logo_path()
        )
        if logo_cfg.get("show", True) and logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                max_w = int(float(logo_cfg.get("max_width_mm", 42.0)) * px_per_mm)
                max_h = int(float(logo_cfg.get("max_height_mm", 18.0)) * px_per_mm)
                logo.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                background = Image.new("RGBA", logo.size, "white")
                background.alpha_composite(logo)
                logo_gray = ImageOps.grayscale(background)
                if logo_cfg.get("align", "center") == "left":
                    logo_x = margin
                elif logo_cfg.get("align") == "right":
                    logo_x = w_px - margin - logo_gray.width
                else:
                    logo_x = (w_px - logo_gray.width) // 2
                img.paste(logo_gray, (logo_x, current_y))
                current_y += logo_gray.height + 8
            except Exception as e:
                logging.warning(f"Receipt logo could not be rendered: {e}")

        company = invoice_data.get("company") or {}
        header_text = cfg.get("header", {}).get("text") or company.get("name") or get_app_name()
        if cfg.get("header", {}).get("show", True):
            f_header = get_font(cfg["header"].get("size", 20), bold=True)
            current_y = draw_text(header_text, current_y, f_header, cfg["header"].get("align", "center"))
            company_extra = " | ".join(
                str(company.get(key)).strip()
                for key in ("address", "nif", "rc")
                if str(company.get(key) or "").strip()
            )
            if company_extra:
                current_y = draw_text(company_extra, current_y, get_font(10), "center")
            current_y += 8

        draw.line([(margin, current_y), (w_px - margin, current_y)], fill=0, width=2)
        current_y += 9

        # 2. Invoice information
        f_info = get_font(cfg["info"].get("size", 14))
        invoice_id = str(invoice_data.get("id", "FCT-000"))
        current_y = draw_pair("Facture", f"#{invoice_id}", f_info, current_y)
        current_y += 3
        if cfg["info"].get("show_date", True):
            current_y = draw_pair(
                "Date",
                invoice_data.get("date", datetime.now().strftime("%Y-%m-%d %H:%M")),
                f_info,
                current_y,
            )
            current_y += 3
        if cfg["info"].get("show_client", True):
            current_y = draw_pair("Client", invoice_data.get("client", "Passager"), f_info, current_y)
            current_y += 3
        if cfg["info"].get("show_cashier", True):
            current_y = draw_pair("Caissier", invoice_data.get("cashier", "Admin"), f_info, current_y)
            current_y += 3

        current_y += 3
        draw.line([(margin, current_y), (w_px - margin, current_y)], fill=0, width=1)
        current_y += 8

        # 3. Detailed products and prices
        table_cfg = cfg.get("table", {}) or {}
        f_item = get_font(table_cfg.get("size", 13), bold=True)
        f_detail = get_font(max(10, int(table_cfg.get("size", 13)) - 2))
        f_detail_bold = get_font(max(11, int(table_cfg.get("size", 13)) - 1), bold=True)
        if table_cfg.get("show_header", True):
            current_y = draw_pair("PRODUIT", "TOTAL TTC", f_item, current_y)
            current_y += 4
            draw.line([(margin, current_y), (w_px - margin, current_y)], fill=0, width=1)
            current_y += 7

        for item in invoice_data.get("items", []):
            name = item.get("name") or "Produit"
            current_y = draw_text(name, current_y, f_item, max_width=print_w)
            current_y += 2

            qty = format_qty(item.get("qty", 0))
            unit_price = float(item.get("unit_price_ht", item.get("price", 0)) or 0)
            price_before = float(item.get("price_before", float(item.get("qty", 0) or 0) * unit_price) or 0)
            discount_amount = float(item.get("discount_amount", 0) or 0)
            net_ht = float(item.get("net_ht", price_before - discount_amount) or 0)
            tva_percent = float(item.get("tva_percent", 0) or 0)
            tva_amount = float(item.get("tva_amount", net_ht * tva_percent / 100.0) or 0)
            total_ttc = float(item.get("total", net_ht + tva_amount) or 0)

            if table_cfg.get("show_unit_price", True):
                left_detail = f"{qty} x {format_money(unit_price)} HT"
            else:
                left_detail = f"Qte: {qty}"
            right_detail = f"Avant {format_money(price_before)}" if table_cfg.get("show_price_before", True) else ""
            if right_detail:
                current_y = draw_pair(left_detail, right_detail, f_detail, current_y)
            else:
                current_y = draw_text(left_detail, current_y, f_detail)

            tags = []
            if table_cfg.get("show_discount", True) and discount_amount > 0:
                discount_percent = float(item.get("discount_percent", 0) or 0)
                tags.append(f"Remise -{format_money(discount_amount)} ({discount_percent:g}%)")
            if table_cfg.get("show_tva", True) and tva_amount > 0:
                tags.append(f"TVA {tva_percent:g}% +{format_money(tva_amount)}")
            if tags:
                current_y = draw_text(" | ".join(tags), current_y, f_detail, max_width=print_w)

            current_y = draw_pair(
                f"Net HT {format_money(net_ht)}",
                f"TTC {format_money(total_ttc)}",
                f_detail_bold,
                current_y,
            )
            current_y += 5
            draw.line([(margin, current_y), (w_px - margin, current_y)], fill=0, width=1)
            current_y += 7

        # 4. Totals
        draw.line([(margin, current_y), (w_px - margin, current_y)], fill=0, width=2)
        current_y += 8
        f_total = get_font(cfg["totals"].get("size", 18), bold=cfg["totals"].get("bold", True))
        f_total_detail = get_font(max(10, int(cfg["totals"].get("size", 18)) - 3))
        subtotal_ht = float(invoice_data.get("subtotal_ht", 0) or 0)
        remise_total = float(invoice_data.get("remise_total", 0) or 0)
        net_ht_total = float(invoice_data.get("net_ht", subtotal_ht - remise_total) or 0)
        tva_total = float(invoice_data.get("tva_total", 0) or 0)
        total_ttc = float(invoice_data.get("total", net_ht_total + tva_total) or 0)
        show_discount = table_cfg.get("show_discount", True) and remise_total > 0
        show_tva = table_cfg.get("show_tva", True) and tva_total > 0

        current_y = draw_pair("Sous-total HT", format_money(subtotal_ht), f_total_detail, current_y)
        current_y += 3
        if show_discount:
            current_y = draw_pair("Remise", f"-{format_money(remise_total)}", f_total_detail, current_y)
            current_y += 3
        if show_discount:
            current_y = draw_pair("Net HT", format_money(net_ht_total), f_total_detail, current_y)
            current_y += 3
        if show_tva:
            current_y = draw_pair("TVA", f"+{format_money(tva_total)}", f_total_detail, current_y)
            current_y += 3
        draw.line([(margin, current_y), (w_px - margin, current_y)], fill=0, width=1)
        current_y += 7
        current_y = draw_pair("TOTAL TTC", format_money(total_ttc), f_total, current_y)
        current_y += 12

        # 5. Footer and invoice barcode
        if cfg["footer"].get("show", True):
            f_footer = get_font(cfg["footer"].get("size", 14))
            current_y = draw_text(
                cfg["footer"].get("text", "Merci pour votre visite!"),
                current_y,
                f_footer,
                cfg["footer"].get("align", "center"),
            )
            current_y += 12

        if cfg["barcode"].get("show", True):
            try:
                barcode_value = invoice_id.replace("#", "") or "FCT-000"
                bc_class = barcode.get_barcode_class("code128")
                fp = io.BytesIO()
                bc_class(barcode_value, writer=ImageWriter()).write(
                    fp,
                    options={"module_width": 0.4, "module_height": 8.0, "quiet_zone": 1.0, "write_text": False},
                )
                fp.seek(0)
                bc_img = Image.open(fp).convert("L")
                target_w = int(print_w * 0.8)
                target_h = int(float(cfg["barcode"].get("height_mm", 10.0)) * px_per_mm)
                bc_img = bc_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                img.paste(bc_img, ((w_px - target_w) // 2, current_y))
                current_y += target_h + 4
                current_y = draw_text(barcode_value, current_y, get_font(cfg["barcode"].get("size", 12)), "center")
                current_y += 12
            except Exception as e:
                logging.error(f"Error drawing receipt barcode: {e}")

        return img.crop((0, 0, w_px, current_y + margin)).convert("1")

    def print_receipt(self, invoice_data):
        self.reload_settings()
        printer_name = self.config.get('selected_receipt_printer') or self.config.get('selected_printer')
        if not printer_name:
            return False, "Aucune imprimante sélectionnée."

        try:
            img = self._create_receipt_image(invoice_data)
            
            # Simple ESC/POS conversion for raster image
            width, height = img.size
            width_bytes = (width + 7) // 8
            
            # ESC/POS raster print command
            header = b'\x1d\x76\x30\x00' + width_bytes.to_bytes(2, 'little') + height.to_bytes(2, 'little')
            
            data = bytearray()
            pixels = img.load()
            for y in range(height):
                for x in range(0, width, 8):
                    byte = 0
                    for bit in range(8):
                        if x + bit < width and pixels[x + bit, y] == 0:  # Black pixel = 1
                            byte |= (1 << (7 - bit))
                    data.append(byte)
            
            footer = b'\n\n\n\n\x1d\x56\x41\x00' # Cut paper
            
            raw_data = header + data + footer

            hprinter = win32print.OpenPrinter(printer_name)
            try:
                job_info = ("Facture Thermique", None, "RAW")
                win32print.StartDocPrinter(hprinter, 1, job_info)
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, raw_data)
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
            
            return True, "Facture imprimée avec succès."
        except Exception as e:
            logging.error(f"Receipt print error: {e}")
            return False, f"Erreur d'impression : {e}"
