import os

filepath = r"d:\git\GstockSW4\ui\widgets\sales\point_of_sale_tab.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Add Checkbox above Validation button
target_chk = """        self.btn_validate = QPushButton("✔️ Valider la Vente")"""
replacement_chk = """        from PySide6.QtWidgets import QCheckBox
        self.chk_print_receipt = QCheckBox("🖨️ Imprimer la Facture (Thermique)")
        self.chk_print_receipt.setChecked(True)
        self.chk_print_receipt.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        right_layout.addWidget(self.chk_print_receipt)
        
        self.btn_validate = QPushButton("✔️ Valider la Vente")"""

if "self.chk_print_receipt = QCheckBox" not in content:
    content = content.replace(target_chk, replacement_chk)

# Add logic inside validate_sale
target_val = """        if success:
            invoice_label = result.get('invoice_no') or f"#{result.get('invoice_id')}"
            QMessageBox.information(self, "Succès", f"Vente enregistrée avec succès ! Facture {invoice_label}")
            self.clear_cart()
            self.load_initial_data()
        else:"""

replacement_val = """        if success:
            invoice_label = result.get('invoice_no') or f"#{result.get('invoice_id')}"
            
            # Print if enabled
            if self.chk_print_receipt.isChecked():
                total_ht_sum = sum(item["qty_sold"] * item["unit_price_ht"] for item in cart_items)
                total_ttc_sum = result.get('total_ttc', 0)
                remise_sum = sum((item["qty_sold"] * item["unit_price_ht"]) * (item["discount_percent"]/100.0) for item in cart_items)
                tva_sum = total_ttc_sum - total_ht_sum + remise_sum # approximation based on return
                
                receipt_items = []
                for row in range(self.cart_table.rowCount()):
                    batch = self.cart_table.item(row, 0).data(Qt.UserRole)
                    qty = self.cart_table.cellWidget(row, 4).value()
                    price = self.cart_table.cellWidget(row, 5).currentData() or 0.0
                    total = qty * price
                    remise_val = self.cart_table.cellWidget(row, 6).get_value()
                    remise_type = self.cart_table.cellWidget(row, 6).get_type()
                    if remise_type == "%":
                        total -= total * (min(100.0, remise_val) / 100.0)
                    else:
                        total -= remise_val
                    tva_pct = self.cart_table.cellWidget(row, 7).value()
                    total += total * (tva_pct / 100.0)
                    receipt_items.append({
                        'name': batch['Product_Name'],
                        'qty': qty,
                        'price': f"{price:.2f}",
                        'total': f"{total:.2f}"
                    })
                    
                invoice_data = {
                    'id': str(invoice_label),
                    'date': invoice_date,
                    'client': client['Client_Name'] if client else 'Passager',
                    'cashier': self.terminal_label,
                    'items': receipt_items,
                    'subtotal_ht': round(total_ht_sum, 2),
                    'remise_total': round(remise_sum, 2),
                    'tva_total': round(tva_sum, 2),
                    'total': round(total_ttc_sum, 2)
                }
                
                print_success, msg = self.data_manager.printer.print_receipt(invoice_data)
                if not print_success:
                    import logging
                    logging.error(f"Echec impression recu: {msg}")
            
            QMessageBox.information(self, "Succès", f"Vente enregistrée avec succès ! Facture {invoice_label}")
            self.clear_cart()
            self.load_initial_data()
        else:"""

if "if self.chk_print_receipt.isChecked():" not in content:
    content = content.replace(target_val, replacement_val)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated point_of_sale_tab.py with printing integration.")
else:
    print("Already updated.")
