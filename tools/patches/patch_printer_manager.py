import os

filepath = r"d:\git\GstockSW4\database\printer_manager.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

new_methods = """
    # ----------------------------------------------------------------
    # 4. IMPRESSION FACTURE (TICKET THERMIQUE)
    # ----------------------------------------------------------------
    def _create_receipt_image(self, invoice_data):
        from datetime import datetime
        px_per_mm = 8.0 # 203 dpi
        
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
            lines = text.split('\\n')
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
            draw_text(f"Client: {invoice_data.get('client', 'Passager')}", current_y, f_info)
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
        draw_text("TOTAL A PAYER:", margin + int(print_w * 0.2), f_tot)
        current_y = draw_text(f"{invoice_data.get('total', 0)} DA", current_y, f_tot, align="right")
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

    def print_receipt(self, invoice_data):
        self.reload_settings()
        printer_name = self.config.get('selected_printer')
        if not printer_name:
            return False, "Aucune imprimante sélectionnée."

        try:
            img = self._create_receipt_image(invoice_data)
            
            # Simple ESC/POS conversion for raster image
            width, height = img.size
            width_bytes = (width + 7) // 8
            
            # ESC/POS raster print command
            header = b'\\x1d\\x76\\x30\\x00' + width_bytes.to_bytes(2, 'little') + height.to_bytes(2, 'little')
            
            data = bytearray()
            pixels = img.load()
            for y in range(height):
                for x in range(0, width, 8):
                    byte = 0
                    for bit in range(8):
                        if x + bit < width and pixels[x + bit, y] == 0:  # Black pixel = 1
                            byte |= (1 << (7 - bit))
                    data.append(byte)
            
            footer = b'\\n\\n\\n\\n\\x1d\\x56\\x41\\x00' # Cut paper
            
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
"""

if "def _create_receipt_image" not in content:
    content += new_methods
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added receipt methods to printer_manager.py")
else:
    print("Methods already exist.")
