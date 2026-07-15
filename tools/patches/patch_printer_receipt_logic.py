import os

filepath = r"d:\git\GstockSW4\database\printer_manager.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the info block to hide client if passager
target_info = """        if cfg["info"]["show_date"]:
            draw_text(f"Date: {invoice_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M'))}", current_y, f_info)
            current_y += cfg["info"]["size"] + 4
        if cfg["info"]["show_client"]:
            draw_text(f"Client: {invoice_data.get('client', 'Passager')}", current_y, f_info)
            current_y += cfg["info"]["size"] + 4
        if cfg["info"]["show_cashier"]:
            draw_text(f"Caissier: {invoice_data.get('cashier', 'Admin')}", current_y, f_info)
            current_y += cfg["info"]["size"] + 4"""

replacement_info = """        if cfg["info"]["show_date"]:
            draw_text(f"Date: {invoice_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M'))}", current_y, f_info)
            current_y += cfg["info"]["size"] + 4
        if cfg["info"]["show_client"]:
            client_name = invoice_data.get('client', '').strip()
            if client_name and client_name.lower() != 'passager' and client_name.lower() != 'vente comptoir':
                draw_text(f"Client: {client_name}", current_y, f_info)
                current_y += cfg["info"]["size"] + 4
        if cfg["info"]["show_cashier"]:
            draw_text(f"Caissier: {invoice_data.get('cashier', 'Admin')}", current_y, f_info)
            current_y += cfg["info"]["size"] + 4"""

# Replace the totals block to show Remise and TVA only if present
target_totals = """        f_tot = get_font(cfg["totals"]["size"], bold=cfg["totals"].get("bold", True))
        draw_text("TOTAL A PAYER:", margin + int(print_w * 0.2), f_tot)
        current_y = draw_text(f"{invoice_data.get('total', 0)} DA", current_y, f_tot, align="right")
        current_y += 20"""

replacement_totals = """        f_tot = get_font(cfg["totals"]["size"], bold=cfg["totals"].get("bold", True))
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
        current_y += 20"""

if target_info in content:
    content = content.replace(target_info, replacement_info)
    content = content.replace(target_totals, replacement_totals)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated printer_manager.py for dynamic client, remise, and tva.")
else:
    print("Could not find target strings in printer_manager.py. Perhaps already updated.")
