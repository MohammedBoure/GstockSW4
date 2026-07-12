# ui/widgets/sales/sales_history_tab.py

import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QHeaderView, QPushButton,
    QHBoxLayout, QLabel, QComboBox, QDateEdit, QDialog, QFormLayout, 
    QGroupBox, QAbstractItemView, QStyle, QTableWidgetItem, QSpinBox, QMessageBox,
    QFileDialog
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush, QFont
from ui.widgets.inventory.dialogs import BarcodeLineEdit
from ui.formatting import format_money, format_quantity

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

def export_invoice_to_pdf(data_manager, invoice_data, parent_widget):
    print("\n" + "🚀" * 10 + " PDF EXPORT START " + "🚀" * 10)

    if not HAS_REPORTLAB:
        QMessageBox.warning(parent_widget, "Erreur", "La bibliothèque 'reportlab' est manquante.")
        return

    try:
        settings = data_manager.company_settings.get_settings()
        if os.path.exists("config.json"):
            import json
            with open("config.json", "r", encoding="utf-8") as f:
                local_settings = json.load(f)
                for k, v in local_settings.items():
                    if k not in settings or not settings[k]:
                        settings[k] = v
    except Exception as e:
        QMessageBox.critical(parent_widget, "Erreur", f"Configuration error: {str(e)}")
        return

    try:
        invoice_id = invoice_data['Invoice_ID']
        details_data = data_manager.sales.get_invoice_details_with_profit(invoice_id)
        client_name = invoice_data.get('Client_Name') or 'Vente comptoir'
    except Exception as e:
        QMessageBox.critical(parent_widget, "Erreur BD", str(e))
        return

    document_title = "FACTURE"
    
    try:
        raw_date = str(invoice_data.get('Invoice_Date', ''))
        year_val = raw_date.split('-')[0] if '-' in raw_date else str(datetime.now().year)
        formatted_ref = invoice_data.get('Invoice_No') or f"{year_val}/{int(invoice_id):03d}"
    except:
        formatted_ref = str(invoice_id)

    client_clean = str(client_name).replace(" ", "_")
    safe_ref_for_filename = formatted_ref.replace("/", "-")
    default_name = f"Facture_{client_clean}_{safe_ref_for_filename}.pdf"

    path, _ = QFileDialog.getSaveFileName(parent_widget, "Enregistrer PDF", default_name, "PDF Files (*.pdf)")
    if not path: return

    try:
        PAGE_WIDTH, PAGE_HEIGHT = A4
        default_color = settings.get('theme_color', '#0b666a')
        primary_color = colors.HexColor(default_color)
        banner_h_cm = settings.get('banner_height_cm', 4.8)
        table_start_y_cm = settings.get('table_start_y_cm', 9.5)

        doc = SimpleDocTemplate(
            path, pagesize=A4, rightMargin=40, leftMargin=40,
            topMargin=table_start_y_cm * cm, bottomMargin=50
        )

        elements = []
        styles = getSampleStyleSheet()
        current_time = datetime.now().strftime('%d/%m/%Y %H:%M')

        lab_name = settings.get('lab_name', 'Laboratoire')
        lab_addr = settings.get('lab_address', '')
        lab_nif = settings.get('lab_nif', '')
        lab_rc = settings.get('lab_rc', '')

        lab_info_lines = [
            f"<font size=14 color='{default_color}'><b>{document_title} N°: {formatted_ref}</b></font><br/>",
            f"<font size=10><b>{lab_name}</b></font>"
        ]
        
        def clean_str(val):
            if not val: return ""
            v = str(val).replace('\n', '').replace('\r', '').strip()
            if v.lower() in ["none", "n/a", "null", "nan", "-", "", "."]:
                return ""
            return v

        if clean_str(lab_addr): lab_info_lines.append(f"<font size=9>{clean_str(lab_addr)}</font>")
        if clean_str(lab_nif): lab_info_lines.append(f"<font size=9>NIF : {clean_str(lab_nif)}</font>")
        if clean_str(lab_rc): lab_info_lines.append(f"<font size=9>RC : {clean_str(lab_rc)}</font>")

        bank_name = settings.get('bank_name', '')
        bank_acc = settings.get('bank_acc', '')

        if clean_str(bank_name): lab_info_lines.append(f"<font size=9>Banque : {clean_str(bank_name)}</font>")
        if clean_str(bank_acc): lab_info_lines.append(f"<font size=9>RIB : {clean_str(bank_acc)}</font>")

        bon_date = raw_date
        lab_info_lines.append("")
        if bon_date:
            lab_info_lines.append(f"<font size=9>Date : {bon_date}</font>")
        lab_info_lines.append(f"<font size=9>Date d'édition : {current_time}</font>")

        left_text_top = "<br/>".join(lab_info_lines)

        dest_label = 'Client :'
        p_name_clean = str(client_name).replace('\n', '').replace('\r', '').strip()
        right_text_lines = [
            f"<b>{dest_label}</b>",
            "",
            f"<font size=11><b>{p_name_clean}</b></font>",
        ]

        right_text = "<br/>".join(right_text_lines)

        def draw_header_compact(canvas, doc):
            canvas.saveState()
            img_x = settings.get('banner_img_x_cm', 0.0) * cm
            img_w = settings.get('banner_img_w_cm', 21.0) * cm
            img_h = settings.get('banner_img_h_cm', 4.8) * cm
            y_offset = settings.get('banner_img_y_cm', 0.2) * cm
            img_y = PAGE_HEIGHT - img_h - y_offset

            img_bytes = data_manager.company_settings.get_banner_image()
            if img_bytes:
                from reportlab.lib.utils import ImageReader
                import io
                img = ImageReader(io.BytesIO(img_bytes))
                canvas.drawImage(img, img_x, img_y, width=img_w, height=img_h)
            else:
                canvas.setStrokeColor(colors.red)
                canvas.rect(img_x, img_y, img_w, img_h, stroke=1)

            total_h_cm = settings.get('banner_height_cm', 4.8) * cm
            top_y = PAGE_HEIGHT - total_h_cm - 0.5*cm

            left_p = Paragraph(left_text_top, styles["Normal"])
            left_w, left_h = left_p.wrap(9.5*cm, 10.0*cm)
            left_p.drawOn(canvas, doc.leftMargin, top_y - left_h)

            dest_x = settings.get('dest_box_x_cm', 11.5) * cm
            dest_y_abs = PAGE_HEIGHT - settings.get('dest_box_y_cm', 6.0) * cm
            dest_w = settings.get('dest_box_w_cm', 8.0) * cm

            right_p = Paragraph(right_text, styles["Normal"])
            right_w, right_h = right_p.wrap(dest_w - 0.5*cm, 10.0*cm)
            box_h = max(right_h + 1.0 * cm, 2.5 * cm)

            canvas.setFillColor(colors.HexColor("#f8f9fa"))
            canvas.setStrokeColor(colors.lightgrey)
            canvas.setLineWidth(0.5)
            canvas.rect(dest_x, dest_y_abs - box_h, dest_w, box_h, fill=1, stroke=1)

            right_p.drawOn(canvas, dest_x + 0.25*cm, dest_y_abs - right_h - 0.5*cm)
            canvas.restoreState()

        has_remise = any(float(item.get('Discount_Percent', 0)) > 0 for item in details_data)
        has_tva = any(float(item.get('TVA_Percent', 0)) > 0 for item in details_data)
        
        header_row = ["Désignation", "Qté", "Prix U. HT"]
        if has_remise: header_row.append("Remise")
        if has_tva: header_row.append("TVA")
        header_row.append("Total TTC")
        
        table_data = [header_row]
        
        for item in details_data:
            qty = float(item.get('Qty_Sold', 0))
            price = float(item.get('Unit_Price_HT', 0))
            remise = float(item.get('Discount_Percent', 0))
            tva = float(item.get('TVA_Percent', 0))
            line_val_ttc = float(item.get('Line_Total_TTC', 0))
            
            p_info = f"<b>{item.get('Product_Name', '-')}</b>"
            
            row = [
                Paragraph(p_info, styles["Normal"]),
                format_quantity(qty),
                f"{price:,.2f}"
            ]
            
            if has_remise:
                row.append(f"{remise}%" if remise > 0 else "-")
            if has_tva:
                row.append(f"{tva}%" if tva > 0 else "-")
                
            row.append(f"{line_val_ttc:,.2f}")
            table_data.append(row)

        col_widths = [8.0*cm, 1.5*cm, 2.5*cm]
        if has_remise: col_widths.append(1.5*cm)
        else: col_widths[0] += 1.5*cm
        
        if has_tva: col_widths.append(1.5*cm)
        else: col_widths[0] += 1.5*cm
        col_widths.append(3.0*cm)

        items_table = Table(table_data, colWidths=col_widths)
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('ALIGN', (1,0), (len(header_row)-1, -1), 'CENTER'),
            ('ALIGN', (len(header_row)-1, 0), (len(header_row)-1, -1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(items_table)
        
        tot_ht_net = float(invoice_data.get('Total_Amount_HT', 0))
        tot_discount = float(invoice_data.get('Total_Discount', 0))
        tot_tva = float(invoice_data.get('Total_TVA', 0))
        tot_ttc = float(invoice_data.get('Total_Amount_TTC', 0))
        
        tot_ht_gross = tot_ht_net + tot_discount
        
        tot_data = [
            ["Total HT :", f"{tot_ht_gross:,.2f} DA"],
        ]
        
        if has_remise or tot_discount > 0:
            tot_data.append(["Remise :", f"{tot_discount:,.2f} DA"])
        if has_tva or tot_tva > 0:
            tot_data.append(["Total TVA :", f"{tot_tva:,.2f} DA"])
            
        tot_data.append(["TOTAL TTC À PAYER :", f"{tot_ttc:,.2f} DA"])

        tot_table = Table(tot_data, colWidths=[14.0*cm, 4.0*cm])
        
        tot_style = [
            ('ALIGN', (0,0), (0,-1), 'RIGHT'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('FONTNAME', (0,len(tot_data)-1), (1,len(tot_data)-1), 'Helvetica-Bold'),
            ('BACKGROUND', (0,len(tot_data)-1), (1,len(tot_data)-1), colors.HexColor("#f4f6f6")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('PADDING', (0,0), (-1,-1), 6),
        ]
        
        tot_table.setStyle(TableStyle(tot_style))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(tot_table)

        doc.build(elements, onFirstPage=draw_header_compact, onLaterPages=draw_header_compact)

        if os.name == 'nt': os.startfile(path)
        else: os.system(f'xdg-open "{path}"')

    except Exception as e:
        QMessageBox.critical(parent_widget, "Erreur PDF", f"Échec de création du PDF: {str(e)}")

    print("="*50 + " PDF EXPORT END " + "="*50)

class SaleDetailsDialog(QDialog):
    def __init__(self, data_manager, invoice_data, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.invoice_data = invoice_data
        self.parent_tab = parent # To trigger refresh
        sale_ref = invoice_data.get('Invoice_No') or f"#{invoice_data['Invoice_ID']}"
        self.setWindowTitle(f"Détails de la Vente {sale_ref}")
        self.resize(850, 500)
        self.details_list = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Invoice summary
        summary_group = QGroupBox("Résumé de la Facture")
        form = QFormLayout(summary_group)
        
        client_name = self.invoice_data.get('Client_Name')
        if not client_name:
            client_name = "Vente comptoir"
            
        form.addRow("<b>Client :</b>", QLabel(client_name))
        form.addRow("<b>Date :</b>", QLabel(str(self.invoice_data.get('Invoice_Date'))))
        form.addRow("<b>Statut :</b>", QLabel(self.invoice_data.get('Status', '')))
        
        self.lbl_total = QLabel(format_money(self.invoice_data.get('Total_Amount_TTC', 0)) + " DA")
        form.addRow("<b>Total TTC :</b>", self.lbl_total)
        
        profit = float(self.invoice_data.get('Total_Profit') or 0)
        self.lbl_profit = QLabel(format_money(profit) + " DA")
        self.lbl_profit.setStyleSheet("color: #27ae60; font-weight: bold;" if profit > 0 else "color: #e74c3c; font-weight: bold;")
        form.addRow("<b>Fayda (Profit) :</b>", self.lbl_profit)
        
        layout.addWidget(summary_group)

        # Table for products
        self.table = QTableWidget()
        cols = ["Produit", "Lot", "Qté", "Prix Vente HT", "Remise %", "TVA %", "Total Ligne TTC", "Profit", "Actions"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        
        self.btn_cancel_sale = QPushButton("🔴 Annuler la Facture")
        self.btn_cancel_sale.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 5px;")
        self.btn_cancel_sale.clicked.connect(self.cancel_sale)
        
        if self.invoice_data.get('Status') == 'Cancelled':
            self.btn_cancel_sale.setEnabled(False)
            
        self.btn_save = QPushButton("💾 Sauvegarder les modifications")
        self.btn_save.clicked.connect(self.save_changes)
        
        self.btn_pdf = QPushButton("🖨️ Imprimer Facture")
        self.btn_pdf.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 5px;")
        self.btn_pdf.clicked.connect(self.print_pdf)

        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        
        btn_row.addWidget(self.btn_cancel_sale)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_pdf)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(btn_close)
        
        layout.addLayout(btn_row)

        self.load_details()

    def load_details(self):
        self.details_list = self.data_manager.sales.get_invoice_details_with_profit(self.invoice_data['Invoice_ID'])
        self.table.setRowCount(0)
        
        for r, d in enumerate(self.details_list):
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(d.get('Product_Name', '---')))
            self.table.setItem(r, 1, QTableWidgetItem(d.get('Lot_Number', '---')))
            
            # Editable Qty SpinBox
            qty_spin = QSpinBox()
            qty_spin.setRange(1, 99999)
            qty_spin.setValue(int(d.get('Qty_Sold', 1)))
            qty_spin.setAlignment(Qt.AlignCenter)
            qty_spin.setProperty("detail_id", d['Detail_ID'])
            qty_spin.setProperty("old_qty", int(d.get('Qty_Sold', 1)))
            qty_spin.setStyleSheet("min-height: 25px;")
            
            qty_container = QWidget()
            qty_container.setStyleSheet("background: transparent;")
            qty_layout = QHBoxLayout(qty_container)
            qty_layout.setContentsMargins(2, 2, 2, 2)
            qty_layout.addWidget(qty_spin, alignment=Qt.AlignCenter)
            
            self.table.setCellWidget(r, 2, qty_container)
            
            self.table.setItem(r, 3, QTableWidgetItem(format_money(d.get('Unit_Price_HT', 0))))
            
            remise = float(d.get('Discount_Percent', 0))
            tva = float(d.get('TVA_Percent', 0))
            
            remise_item = QTableWidgetItem(f"{remise}%")
            if remise > 0: remise_item.setForeground(Qt.darkGreen)
            self.table.setItem(r, 4, remise_item)
            
            tva_item = QTableWidgetItem(f"{tva}%")
            self.table.setItem(r, 5, tva_item)
            
            self.table.setItem(r, 6, QTableWidgetItem(format_money(d.get('Line_Total_TTC', 0))))
            
            profit = float(d.get('Line_Profit') or 0)
            profit_item = QTableWidgetItem(format_money(profit))
            profit_item.setForeground(Qt.darkGreen if profit > 0 else Qt.red)
            profit_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(r, 7, profit_item)
            
            # Actions
            btn_del = QPushButton("🗑️")
            btn_del.setFixedSize(30, 30)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet("padding: 0; margin: 2px; border-radius: 5px;")
            btn_del.clicked.connect(lambda checked=False, d_id=d['Detail_ID']: self.delete_detail(d_id))
            
            if self.invoice_data.get('Status') == 'Cancelled':
                qty_spin.setEnabled(False)
                btn_del.setEnabled(False)
                self.btn_save.setEnabled(False)
                
            # Wrapper for centering the delete button
            action_container = QWidget()
            action_container.setStyleSheet("background: transparent;")
            action_layout = QHBoxLayout(action_container)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.addWidget(btn_del, alignment=Qt.AlignCenter)
            
            self.table.setCellWidget(r, 8, action_container)
            
        has_remise = any(float(d.get('Discount_Percent', 0)) > 0 for d in self.details_list)
        has_tva = any(float(d.get('TVA_Percent', 0)) > 0 for d in self.details_list)
        self.table.setColumnHidden(4, not has_remise)
        self.table.setColumnHidden(5, not has_tva)

    def save_changes(self):
        changes_made = False
        for r in range(self.table.rowCount()):
            container = self.table.cellWidget(r, 2)
            if container:
                spin = container.layout().itemAt(0).widget()
                detail_id = spin.property("detail_id")
                old_qty = spin.property("old_qty")
                new_qty = spin.value()
                
                if old_qty != new_qty:
                    success = self.data_manager.sales.update_invoice_detail_qty(
                        detail_id, new_qty, self.data_manager.batches
                    )
                    if not success:
                        QMessageBox.warning(self, "Erreur", "Échec de la mise à jour pour la ligne. Vérifiez le stock disponible.")
                    else:
                        changes_made = True
                        
        if changes_made:
            QMessageBox.information(self, "Succès", "Les modifications ont été sauvegardées avec succès.")
            if hasattr(self.parent_tab, 'load_sales_data'):
                self.parent_tab.load_sales_data()
            self.accept()

    def delete_detail(self, detail_id):
        reply = QMessageBox.question(self, "Confirmation", "Voulez-vous vraiment supprimer ce produit de la facture ? Le stock sera restitué.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success = self.data_manager.sales.remove_invoice_detail(detail_id, self.data_manager.batches)
            if success:
                QMessageBox.information(self, "Succès", "Produit supprimé et stock restitué.")
                if hasattr(self.parent_tab, 'load_sales_data'):
                    self.parent_tab.load_sales_data()
                self.accept()
            else:
                QMessageBox.warning(self, "Erreur", "Échec de la suppression.")

    def cancel_sale(self):
        reply = QMessageBox.question(self, "Annuler la Vente", "Voulez-vous annuler complètement cette vente ? Tous les produits seront remis en stock.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            success = self.data_manager.sales.cancel_invoice(self.invoice_data['Invoice_ID'], self.data_manager.batches)
            if success:
                QMessageBox.information(self, "Succès", "Vente annulée et stock restitué.")
                if hasattr(self.parent_tab, 'load_sales_data'):
                    self.parent_tab.load_sales_data()
                self.accept()
            else:
                QMessageBox.warning(self, "Erreur", "Échec de l'annulation.")

    def print_pdf(self):
        export_invoice_to_pdf(self.data_manager, self.invoice_data, self)


class SalesHistoryTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.raw_data = []
        self.init_ui()
        self.load_filters()
        self.load_sales_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # --- 1. Filter Section ---
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(5)
        
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setFixedWidth(120)
        self.date_from.dateChanged.connect(self.apply_filter_local)
        
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setFixedWidth(120)
        self.date_to.dateChanged.connect(self.apply_filter_local)
        
        self.cb_client = QComboBox()
        self.cb_client.setMinimumWidth(200)
        self.cb_client.addItem("Tous les Clients", None)
        self.cb_client.currentIndexChanged.connect(self.load_sales_data)
        
        self.search_input = BarcodeLineEdit()
        self.search_input.setPlaceholderText("Rechercher par ID, Client, Caisse ou Utilisateur...")
        self.search_input.textChanged.connect(self.apply_filter_local)
        
        btn_refresh = QPushButton()
        btn_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        btn_refresh.setFixedSize(30, 30)
        btn_refresh.clicked.connect(self.load_sales_data)
        
        self.btn_print_selected = QPushButton("🖨️ Imprimer Facture")
        self.btn_print_selected.setEnabled(False)
        self.btn_print_selected.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 5px 15px;")
        self.btn_print_selected.clicked.connect(self.print_selected_invoice)
        
        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(QLabel("Client:"))
        filter_layout.addWidget(self.cb_client)
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(self.btn_print_selected)
        filter_layout.addWidget(btn_refresh)
        
        layout.addLayout(filter_layout)
        
        # --- 2. Table Section ---
        self.table = QTableWidget()
        cols = [
            "ID", "Date", "Operation", "Client / Details", "Statut",
            "Caisse", "Utilisateur", "Paiement", "Montant saisi",
            "Total TTC", "Fayda (Profit)"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        f = self.table.font()
        f.setPointSize(9)
        self.table.setFont(f)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.show_full_details)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        
        layout.addWidget(self.table)
        
        # --- 3. Summary Section ---
        summary_layout = QHBoxLayout()
        summary_layout.addStretch()
        self.lbl_total_period_profit = QLabel("Bénéfice Total Période : 0.00 DA")
        self.lbl_total_period_profit.setObjectName("ProfitLabel")
        self.lbl_total_period_profit.setStyleSheet("font-size: 18px; padding: 10px; background-color: #eafaf1; border-radius: 8px; border: 1px solid #2ecc71;")
        summary_layout.addWidget(self.lbl_total_period_profit)
        
        layout.addLayout(summary_layout)

    def load_filters(self):
        clients = self.data_manager.clients.get_all_clients()
        for client in clients:
            self.cb_client.addItem(client['Client_Name'], client['Client_ID'])

    def load_sales_data(self):
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")
        client_id = self.cb_client.currentData()
        
        self.raw_data = self.data_manager.sales.get_sales_operations_history(d_from, d_to, client_id)
        self.apply_filter_local()

    def apply_filter_local(self):
        txt = self.search_input.text().lower().strip()
        
        filtered = []
        for inv in self.raw_data:
            full_text = (
                f"{inv.get('Operation_ID','')} #{inv.get('Invoice_ID','')} "
                f"{inv.get('Invoice_No','')} {inv.get('Operation_Label','')} "
                f"{inv.get('Client_Name','')} {inv.get('Status','')} "
                f"{inv.get('Caisse_Label','')} {inv.get('Terminal_Name','')} "
                f"{inv.get('User_Name','')} {inv.get('Session_No','')}"
            ).lower()
            if txt and txt not in full_text: continue
            filtered.append(inv)
            
        self._populate_table(filtered)

    def _populate_table(self, data):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        total_profit_period = 0.0
        
        for r, inv in enumerate(data):
            self.table.insertRow(r)
            
            def item(text, align=Qt.AlignCenter, color=None, font=None):
                val = str(text) if text is not None else "-"
                it = QTableWidgetItem(val)
                it.setTextAlignment(align)
                if color: it.setForeground(QBrush(QColor(color)))
                if font: it.setFont(font)
                return it

            row_type = inv.get('Row_Type', 'Sale')
            is_cash_row = row_type in {'Cash_Open', 'Cash_Close'}
            row_bg = QColor("#eef6ff") if row_type == 'Cash_Open' else QColor("#fff7e6") if row_type == 'Cash_Close' else None
            row_font = QFont("Segoe UI", 9, QFont.Bold) if is_cash_row else None

            # Store row data in first item
            invoice_label = inv.get('Invoice_No') or inv.get('Operation_ID') or f"#{inv.get('Invoice_ID')}"
            id_item = item(invoice_label)
            id_item.setData(Qt.UserRole, inv)
            self.table.setItem(r, 0, id_item)
            
            self.table.setItem(r, 1, item(str(inv.get('Event_Date') or inv.get('Invoice_Date') or "-")))
            self.table.setItem(r, 2, item(inv.get('Operation_Label') or "Vente", font=row_font))
            
            client_name = inv.get('Client_Name')
            if not client_name:
                client_name = "Vente comptoir"
            self.table.setItem(r, 3, item(client_name, Qt.AlignLeft | Qt.AlignVCenter, font=QFont("Segoe UI", 9, QFont.Bold)))
            
            status_item = item(inv['Status'])
            self.table.setItem(r, 4, status_item)
            
            self.table.setItem(r, 5, item(inv.get('Caisse_Label') or inv.get('Terminal_Name') or "-"))
            self.table.setItem(r, 6, item(inv.get('User_Name') or "-"))
            self.table.setItem(r, 7, item(inv.get('Payment_Method') or "-"))

            amount_entered = inv.get('Amount_Entered')
            self.table.setItem(r, 8, item(format_money(amount_entered) if amount_entered is not None else "-"))
            self.table.setItem(r, 9, item(format_money(inv.get('Total_Amount_TTC', 0))))
            
            profit = float(inv.get('Total_Profit') or 0)
            if row_type == 'Sale':
                total_profit_period += profit
            profit_item = item(format_money(profit), Qt.AlignCenter, "#27ae60" if profit > 0 else "#c0392b", QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(r, 10, profit_item)

            if row_bg:
                for col in range(self.table.columnCount()):
                    cell = self.table.item(r, col)
                    if cell:
                        cell.setBackground(QBrush(row_bg))
                        cell.setFont(row_font)
            
        self.table.setSortingEnabled(True)
        self.lbl_total_period_profit.setText(f"Bénéfice Total Période : {format_money(total_profit_period)} DA")

    def show_full_details(self):
        row = self.table.currentRow()
        if row < 0: return
        data = self.table.item(row, 0).data(Qt.UserRole)
        if data and data.get('Row_Type') == 'Sale':
            dlg = SaleDetailsDialog(self.data_manager, data, self)
            dlg.exec()

    def on_selection_changed(self):
        row = self.table.currentRow()
        data = self.table.item(row, 0).data(Qt.UserRole) if row >= 0 and self.table.item(row, 0) else None
        has_selection = bool(data and data.get('Row_Type') == 'Sale')
        self.btn_print_selected.setEnabled(has_selection)

    def print_selected_invoice(self):
        row = self.table.currentRow()
        if row < 0: return
        data = self.table.item(row, 0).data(Qt.UserRole)
        if data and data.get('Row_Type') == 'Sale':
            export_invoice_to_pdf(self.data_manager, data, self)
