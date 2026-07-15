import os

filepath = r"d:\git\GstockSW4\database\printer_manager.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = """    def _create_label_image(self, product_name, barcode_data, lot_number, expiry_date):
        \"\"\" 
        تصميم 40x20 ملم مع تصغير تلقائي لاسم المنتج ليناسب العرض.
        \"\"\"
        w_px = 320 # 40mm
        h_px = 160 # 20mm"""

# We'll split the content to replace the entire _create_label_image function
parts = content.split("    # ----------------------------------------------------------------\n    # 2. CONVERSION DE L'IMAGE EN COMMANDES TSPL")

new_method = """    def _create_label_image(self, product_name, barcode_data, lot_number, expiry_date):
        \"\"\" 
        تصميم الملصق بناءً على الإعدادات المرئية من config.json 
        \"\"\"
        px_per_mm = 8.0 # 203 dpi
        
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
"""
new_content = parts[0].split("    def _create_label_image")[0] + new_method + "\n    # ----------------------------------------------------------------\n    # 2. CONVERSION DE L'IMAGE EN COMMANDES TSPL" + parts[1]

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Updated printer_manager.py to use dynamic config.")
