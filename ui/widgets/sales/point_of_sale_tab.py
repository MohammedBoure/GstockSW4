# ui/widgets/sales/point_of_sale_tab.py

import logging
from datetime import date
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QComboBox, QMessageBox, QDoubleSpinBox, QSpinBox,
                               QDateEdit, QFrame, QCompleter, QAbstractItemView)
from PySide6.QtCore import Qt, QDate, Signal, QStringListModel, QTimer
from ui.formatting import format_money

class RemiseWidget(QWidget):
    valueChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(0, 9999999)
        self.value_spin.setValue(0.0)
        self.value_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.value_spin.setDecimals(2)
        self.value_spin.setAlignment(Qt.AlignCenter)
        self.value_spin.setMinimumWidth(82)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["%", "DA"])
        self.type_combo.setMinimumWidth(58)
        
        layout.addWidget(self.value_spin, 2)
        layout.addWidget(self.type_combo, 1)

        self.value_spin.valueChanged.connect(lambda v: self.valueChanged.emit())
        self.type_combo.currentIndexChanged.connect(lambda idx: self.valueChanged.emit())

    def get_value(self):
        return self.value_spin.value()

    def get_type(self):
        return self.type_combo.currentText()


class BarcodeLineEdit(QLineEdit):
    """Line edit that accepts numeric input from common AZERTY scanner mappings."""
    def keyPressEvent(self, event):
        azerty_map = {
            Qt.Key_Ampersand: "1",
            Qt.Key_Eacute: "2",
            Qt.Key_QuoteDbl: "3",
            Qt.Key_QuoteLeft: "4",
            Qt.Key_ParenLeft: "5",
            Qt.Key_Minus: "6",
            Qt.Key_Egrave: "7",
            Qt.Key_Underscore: "8",
            Qt.Key_Ccedilla: "9",
            Qt.Key_Agrave: "0",
        }
        if event.key() in azerty_map:
            self.insert(azerty_map[event.key()])
            event.accept()
            return
        super().keyPressEvent(event)


class PointOfSaleTab(QWidget):
    """
    Point de Vente (POS) Tab for creating sales.
    """
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        
        self.cart_items = []  # List of dicts representing cart rows
        self.batches_cache = []
        self.search_map = {}
        self.barcode_map = {}
        self.scan_timer = QTimer(self)
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self.process_instant_scan)
        
        self.init_ui()
        self.load_initial_data()

    def init_ui(self):
        pass
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # --- Left Section (Cart Frame) ---
        cart_frame = QFrame()
        cart_frame.setObjectName("CartFrame")
        left_layout = QVBoxLayout(cart_frame)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(15)
        
        # Header controls
        header_layout = QHBoxLayout()
        
        self.cb_client = QComboBox()
        self.cb_client.setMinimumWidth(300)
        self.cb_client.setPlaceholderText("👤 Sélectionner un Client...")
        self.make_combo_searchable(self.cb_client)
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMinimumWidth(150)
        
        header_layout.addWidget(QLabel("Client :"))
        header_layout.addWidget(self.cb_client)
        header_layout.addSpacing(20)
        header_layout.addWidget(QLabel("Date :"))
        header_layout.addWidget(self.date_edit)
        header_layout.addStretch()
        
        left_layout.addLayout(header_layout)
        
        # Product Search / Barcode
        search_layout = QHBoxLayout()
        self.cb_product_search = BarcodeLineEdit()
        self.cb_product_search.setObjectName("ScanSearchInput")
        self.cb_product_search.setMinimumWidth(450)
        self.cb_product_search.setMinimumHeight(44)
        self.cb_product_search.setPlaceholderText("🔍 Scanner code-barres ou chercher un produit...")

        self.product_completer = QCompleter(self)
        self.product_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.product_completer.setFilterMode(Qt.MatchContains)
        self.product_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.cb_product_search.setCompleter(self.product_completer)
        self.product_completer.activated.connect(self.on_product_selected)
        self.cb_product_search.returnPressed.connect(self.handle_search_return)
        self.cb_product_search.textChanged.connect(self.schedule_instant_scan)
        
        self.lbl_scan_hint = QLabel("Scan direct: le produit est ajoute des que le code correspond.")
        self.lbl_scan_hint.setStyleSheet("color: #7f8c8d; font-size: 12px; font-weight: 500;")
        
        search_layout.addWidget(self.cb_product_search)
        search_layout.addWidget(self.lbl_scan_hint)
        search_layout.addStretch()
        
        left_layout.addLayout(search_layout)
        
        # Cart Table
        self.cart_table = QTableWidget()
        self.cart_table.setObjectName("POSCartTable")
        cols = ["Produit", "Lot", "Code-barres", "Stock", "Qté vendue", "Prix vente HT", "Remise", "TVA", "Total TTC", ""]
        self.cart_table.setColumnCount(len(cols))
        self.cart_table.setHorizontalHeaderLabels(cols)
        
        # Adjust column sizing
        header = self.cart_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch) # Produit
        for i in range(1, len(cols)):
            header.setSectionResizeMode(i, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(1, 88)
        self.cart_table.setColumnWidth(2, 122)
        self.cart_table.setColumnWidth(3, 62)
        self.cart_table.setColumnWidth(4, 108)
        self.cart_table.setColumnWidth(5, 162)
        self.cart_table.setColumnWidth(6, 138)
        self.cart_table.setColumnWidth(7, 86)
        self.cart_table.setColumnWidth(8, 118)
        self.cart_table.setColumnWidth(9, 46)
            
        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cart_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.cart_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cart_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.cart_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setShowGrid(False)
        self.cart_table.setWordWrap(False)
        self.cart_table.setFocusPolicy(Qt.NoFocus)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(58)
        self.cart_table.verticalHeader().setMinimumSectionSize(56)
        
        left_layout.addWidget(self.cart_table)
        
        # --- Right Section (Summary Frame) ---
        summary_frame = QFrame()
        summary_frame.setObjectName("SummaryFrame")
        summary_frame.setMinimumWidth(320)
        summary_frame.setMaximumWidth(400)
        
        right_layout = QVBoxLayout(summary_frame)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(10)
        
        summary_title = QLabel("Résumé de la Vente")
        summary_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-bottom: 10px;")
        right_layout.addWidget(summary_title)
        
        self.lbl_total_ht = QLabel("Total HT : 0.00 DA")
        self.lbl_total_ht.setObjectName("SubTotalLabel")
        
        self.lbl_total_tva = QLabel("TVA : 0.00 DA")
        self.lbl_total_tva.setObjectName("SubTotalLabel")
        
        self.lbl_total_remise = QLabel("Remise : 0.00 DA")
        self.lbl_total_remise.setObjectName("SubTotalLabel")
        
        self.lbl_total_ttc = QLabel("TOTAL TTC : 0.00 DA")
        self.lbl_total_ttc.setObjectName("TotalLabel")
        self.lbl_total_ttc.setAlignment(Qt.AlignCenter)
        
        self.btn_validate = QPushButton("✔️ Valider la Vente")
        self.btn_validate.setMinimumHeight(60)
        self.btn_validate.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; 
                color: white; 
                font-size: 18px; 
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #229954; }
        """)
        self.btn_validate.setCursor(Qt.PointingHandCursor)
        self.btn_validate.clicked.connect(self.validate_sale)
        
        self.btn_clear = QPushButton("🗑️ Vider le Panier")
        self.btn_clear.setMinimumHeight(45)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #ffffff; 
                color: #e74c3c; 
                font-weight: bold; 
                font-size: 14px;
                border: 2px solid #e74c3c;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #fdf2f1; }
            QPushButton:pressed { background-color: #fadbd8; }
        """)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_cart)
        
        right_layout.addWidget(self.lbl_total_ht)
        right_layout.addWidget(self.lbl_total_tva)
        right_layout.addWidget(self.lbl_total_remise)
        right_layout.addWidget(self.lbl_total_ttc)
        right_layout.addStretch()
        right_layout.addWidget(self.btn_validate)
        right_layout.addSpacing(10)
        right_layout.addWidget(self.btn_clear)
        
        main_layout.addWidget(cart_frame, stretch=3)
        main_layout.addWidget(summary_frame, stretch=1)

    def make_combo_searchable(self, combo):
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.completer().setFilterMode(Qt.MatchContains)
        combo.completer().setCaseSensitivity(Qt.CaseInsensitive)

    def load_initial_data(self):
        # Load clients
        self.cb_client.clear()
        self.cb_client.addItem("Vente comptoir / sans client", None)
        try:
            clients = self.data_manager.clients.get_all_clients()
            for c in clients:
                self.cb_client.addItem(f"{c['Client_Name']} - {c.get('City', '')}", c)
            self.cb_client.setCurrentIndex(0)
        except Exception as e:
            logging.error(f"Error loading clients for POS: {e}")

        # Load products (Batches with stock > 0)
        self.cb_product_search.blockSignals(True)
        self.cb_product_search.clear()
        self.cb_product_search.blockSignals(False)
        self.batches_cache = []
        self.search_map = {}
        self.barcode_map = {}
        try:
            self.batches_cache = self.data_manager.batches.get_all_batches_with_details()
            suggestions = []
            for batch in self.batches_cache:
                suggestion = self.format_product_suggestion(batch)
                suggestions.append(suggestion)
                self.search_map[suggestion] = batch
                self.register_barcodes(batch)
            self.product_completer.setModel(QStringListModel(suggestions))
        except Exception as e:
            logging.error(f"Error loading batches for POS: {e}")

    def normalize_code(self, value):
        return str(value or "").strip().lower().replace(" ", "").replace("-", "")

    def is_real_code(self, value):
        code = str(value or "").strip()
        return bool(code) and code.lower() not in {"none", "null", "---"}

    def register_barcodes(self, batch):
        for key in ("Internal_Barcode", "External_Barcode", "Barcode"):
            value = batch.get(key)
            if not self.is_real_code(value):
                continue
            normalized = self.normalize_code(value)
            if normalized:
                self.barcode_map[normalized] = batch

    def format_product_suggestion(self, batch):
        internal = batch.get("Internal_Barcode") or "-"
        external = batch.get("External_Barcode")
        ext_text = f" | Ext: {external}" if self.is_real_code(external) else ""
        lot = batch.get("Lot_Number") or "---"
        qty = batch.get("Quantity_Current") or 0
        return f"[{internal}{ext_text}] {batch.get('Product_Name', '')} | Lot: {lot} | Stock: {qty}"

    def on_product_selected(self, text):
        batch = self.search_map.get(text)
        if batch:
            self.add_product_to_cart(batch)

    def schedule_instant_scan(self, text):
        if not text.strip():
            self.scan_timer.stop()
            return
        self.scan_timer.start(120)

    def process_instant_scan(self):
        text = self.cb_product_search.text().strip()
        if not text:
            return
        batch = self.barcode_map.get(self.normalize_code(text))
        if batch:
            self.add_product_to_cart(batch)

    def handle_search_return(self):
        self.add_product_to_cart(self.find_batch_from_search_text(), show_not_found=True)

    def find_batch_from_search_text(self):
        text = self.cb_product_search.text().strip()
        if not text:
            return None

        if text in self.search_map:
            return self.search_map[text]

        exact_code = self.barcode_map.get(self.normalize_code(text))
        if exact_code:
            return exact_code

        lowered = text.lower()
        matches = [
            batch for batch in self.batches_cache
            if lowered in str(batch.get("Product_Name", "")).lower()
            or lowered in str(batch.get("Lot_Number", "")).lower()
        ]
        return matches[0] if len(matches) == 1 else None

    def clear_search_input(self):
        self.cb_product_search.blockSignals(True)
        self.cb_product_search.clear()
        self.cb_product_search.blockSignals(False)
        self.cb_product_search.setFocus()

    def flash_scan_feedback(self, success=True):
        color = "#dff7e8" if success else "#fdecea"
        border = "#27ae60" if success else "#e74c3c"
        self.cb_product_search.setStyleSheet(
            f"border: 2px solid {border}; background-color: {color};"
        )
        QTimer.singleShot(350, lambda: self.cb_product_search.setStyleSheet(""))

    def add_product_to_cart(self, batch=None, show_not_found=False):
        if batch is None:
            batch = self.find_batch_from_search_text()

        if not batch:
            if show_not_found and self.cb_product_search.text().strip() != "":
                self.flash_scan_feedback(False)
                QMessageBox.warning(self, "Attention", "Produit non trouvé.")
                self.clear_search_input()
            return
            
        # If the same lot is scanned again, increase the quantity smoothly.
        for row in range(self.cart_table.rowCount()):
            existing_batch = self.cart_table.item(row, 0).data(Qt.UserRole)
            if existing_batch and existing_batch['Batch_ID'] == batch['Batch_ID']:
                qty_widget = self.cart_table.cellWidget(row, 4)
                if qty_widget and qty_widget.value() < qty_widget.maximum():
                    qty_widget.setValue(qty_widget.value() + 1)
                    self.cart_table.scrollToItem(self.cart_table.item(row, 0))
                    self.flash_scan_feedback(True)
                    self.clear_search_input()
                    return
                QMessageBox.information(self, "Info", "Stock maximum déjà atteint pour ce lot.")
                self.clear_search_input()
                return

        row_idx = self.cart_table.rowCount()
        self.cart_table.insertRow(row_idx)
        self.cart_table.setRowHeight(row_idx, 58)
        
        # Product Name
        name_item = QTableWidgetItem(batch['Product_Name'])
        name_item.setData(Qt.UserRole, batch)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_item.setToolTip(batch['Product_Name'])
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.cart_table.setItem(row_idx, 0, name_item)
        
        # Lot
        lot_item = QTableWidgetItem(batch.get('Lot_Number', '---'))
        lot_item.setFlags(lot_item.flags() & ~Qt.ItemIsEditable)
        lot_item.setToolTip(str(batch.get('Lot_Number', '---')))
        lot_item.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row_idx, 1, lot_item)
        
        # Barcode badge
        bc1 = batch.get('Internal_Barcode')
        bc2 = batch.get('External_Barcode')
        barcode_text = f"BR: {bc1}" if self.is_real_code(bc1) else "---"
        barcode_tip = barcode_text
        if self.is_real_code(bc2):
            barcode_tip = f"{barcode_tip}\nExt: {bc2}"
        barcode_label = QLabel(barcode_text)
        barcode_label.setToolTip(barcode_tip)
        barcode_label.setAlignment(Qt.AlignCenter)
        barcode_label.setStyleSheet("""
            QLabel {
                background-color: #edf7ff;
                color: #0f5f8f;
                border: 1px solid #c7e4fb;
                border-radius: 6px;
                font-weight: 800;
                padding: 6px 8px;
            }
        """)
        self.cart_table.setCellWidget(row_idx, 2, barcode_label)
        
        # Qty Stock
        stock_item = QTableWidgetItem(str(batch['Quantity_Current']))
        stock_item.setFlags(stock_item.flags() & ~Qt.ItemIsEditable)
        stock_item.setTextAlignment(Qt.AlignCenter)
        self.cart_table.setItem(row_idx, 3, stock_item)
        
        # Qty Sold Input
        qty_spin = QDoubleSpinBox()
        qty_spin.setRange(0.01, float(batch['Quantity_Current']))
        qty_spin.setDecimals(2)
        qty_spin.setValue(1.0)
        qty_spin.setAlignment(Qt.AlignCenter)
        qty_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        qty_spin.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row_idx, 4, qty_spin)
        
        # Price Selection Combo (Support 4 prices)
        price_combo = QComboBox()
        price_combo.setMinimumWidth(150)
        p1 = float(batch.get('Selling_Price_HT') or 0)
        p2 = float(batch.get('Selling_Price_HT_2') or 0)
        p3 = float(batch.get('Selling_Price_HT_3') or 0)
        p4 = float(batch.get('Selling_Price_HT_4') or 0)
        
        if p1 > 0: price_combo.addItem(f"Prix 1 - {format_money(p1)} DA", p1)
        if p2 > 0: price_combo.addItem(f"Prix 2 - {format_money(p2)} DA", p2)
        if p3 > 0: price_combo.addItem(f"Prix 3 - {format_money(p3)} DA", p3)
        if p4 > 0: price_combo.addItem(f"Prix 4 - {format_money(p4)} DA", p4)
        
        # If no selling prices defined, fallback to 0.00 (DO NOT SHOW PURCHASE PRICE)
        if price_combo.count() == 0:
            price_combo.addItem("Aucun prix défini", 0.0)
            
        price_combo.currentIndexChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row_idx, 5, price_combo)
        
        # Remise (New custom widget for % or DA, initialized to 0)
        remise_widget = RemiseWidget()
        remise_widget.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row_idx, 6, remise_widget)
        
        # TVA
        tva_spin = QDoubleSpinBox()
        tva_spin.setRange(0, 100)
        tva_spin.setSuffix(" %")
        tva_spin.setAlignment(Qt.AlignCenter)
        tva_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        tva_spin.setValue(float(batch.get('Selling_TVA_Percent') or batch.get('Tax_Rate_Percent') or 0))
        tva_spin.valueChanged.connect(self.calculate_totals)
        self.cart_table.setCellWidget(row_idx, 7, tva_spin)
        
        # Line Total TTC
        total_item = QTableWidgetItem("0.00")
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.cart_table.setItem(row_idx, 8, total_item)
        
        # Action Delete
        btn_del = QPushButton("X")
        btn_del.setFixedSize(30, 30)
        btn_del.setStyleSheet("""
            QPushButton {
                color: #e74c3c;
                border: 1px solid #fecaca;
                border-radius: 15px;
                background: #fff7f7;
                font-weight: 900;
            }
            QPushButton:hover {
                color: #ffffff;
                background: #e74c3c;
                border-color: #e74c3c;
            }
        """)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(lambda _checked=False, button=btn_del: self.remove_cart_row(button))
        action_cell = QWidget()
        action_layout = QHBoxLayout(action_cell)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setAlignment(Qt.AlignCenter)
        action_layout.addWidget(btn_del)
        self.cart_table.setCellWidget(row_idx, 9, action_cell)
        
        self.calculate_totals()
        self.cart_table.scrollToBottom()
        self.flash_scan_feedback(True)
        
        # Clear search input for the next scan
        self.clear_search_input()

    def remove_cart_row(self, button):
        # Must find the real row dynamically because indexes shift
        for r in range(self.cart_table.rowCount()):
            widget = self.cart_table.cellWidget(r, 9)
            if widget == button or (widget and widget.findChild(QPushButton) == button):
                self.cart_table.removeRow(r)
                break
        self.calculate_totals()

    def calculate_totals(self):
        total_ht = 0.0
        total_tva = 0.0
        total_remise = 0.0
        
        for row in range(self.cart_table.rowCount()):
            qty_widget = self.cart_table.cellWidget(row, 4)
            price_widget = self.cart_table.cellWidget(row, 5)
            remise_widget = self.cart_table.cellWidget(row, 6)
            tva_widget = self.cart_table.cellWidget(row, 7)
            total_item = self.cart_table.item(row, 8)
            
            if not all([qty_widget, price_widget, remise_widget, tva_widget, total_item]):
                continue
                
            qty = qty_widget.value()
            price_ht = price_widget.currentData() or 0.0
            tva_pct = tva_widget.value()
            
            line_ht = qty * price_ht
            
            remise_val = remise_widget.get_value()
            remise_type = remise_widget.get_type()
            
            if remise_type == "%":
                remise_amount = line_ht * (remise_val / 100.0)
            else:
                remise_amount = remise_val

            remise_amount = max(0.0, min(remise_amount, line_ht))
                
            net_ht = max(0.0, line_ht - remise_amount)
            tva_val = net_ht * (tva_pct / 100.0)
            line_ttc = net_ht + tva_val
            
            total_ht += net_ht
            total_remise += remise_amount
            total_tva += tva_val
            
            total_item.setText(format_money(line_ttc))
            
        total_ttc = total_ht + total_tva
        
        self.lbl_total_ht.setText(f"Total HT : {format_money(total_ht)} DA")
        self.lbl_total_tva.setText(f"TVA : {format_money(total_tva)} DA")
        self.lbl_total_remise.setText(f"Remise : {format_money(total_remise)} DA")
        self.lbl_total_ttc.setText(f"TOTAL TTC : {format_money(total_ttc)} DA")

    def clear_cart(self):
        self.cart_table.setRowCount(0)
        self.calculate_totals()

    def validate_sale(self):
        if self.cart_table.rowCount() == 0:
            QMessageBox.warning(self, "Erreur", "Le panier est vide.")
            return
            
        client = self.cb_client.currentData()
        client_id = client['Client_ID'] if client else None
        client_name = client['Client_Name'] if client else "Vente comptoir"
            
        invoice_date = self.date_edit.date().toString("yyyy-MM-dd")
        
        # 1. Create Invoice Header
        from database.system_logger import active_user_id
        u_id = active_user_id.get()
        
        invoice_id = self.data_manager.sales.create_invoice(
            client_id=client_id,
            invoice_date=invoice_date,
            status='Validated',
            notes=None if client else "Vente sans client",
            user_id=u_id
        )
        
        if not invoice_id:
            QMessageBox.critical(self, "Erreur", "Impossible de créer la facture.")
            return
            
        # 2. Add Details
        success = True
        for row in range(self.cart_table.rowCount()):
            batch = self.cart_table.item(row, 0).data(Qt.UserRole)
            qty = self.cart_table.cellWidget(row, 4).value()
            price_ht = self.cart_table.cellWidget(row, 5).currentData() or 0.0
            
            remise_val = self.cart_table.cellWidget(row, 6).get_value()
            remise_type = self.cart_table.cellWidget(row, 6).get_type()
            
            line_ht = qty * price_ht
            if remise_type == "%":
                remise_pct = max(0.0, min(remise_val, 100.0))
            else:
                remise_amount = max(0.0, min(remise_val, line_ht))
                remise_pct = (remise_amount / line_ht * 100.0) if line_ht > 0 else 0.0
                
            tva_pct = self.cart_table.cellWidget(row, 7).value()
            
            detail_id = self.data_manager.sales.add_invoice_detail(
                invoice_id=invoice_id,
                product_id=batch['Product_ID'],
                batch_id=batch['Batch_ID'],
                qty_sold=qty,
                unit_price_ht=price_ht,
                discount_percent=remise_pct,
                tva_percent=tva_pct
            )
            
            if not detail_id:
                success = False
                break
                
            # Deduct stock
            # In a real system, you'd use a dedicated function in inventory_batch_manager
            # For now, we rely on the manager if available, or do a direct adjustment
            self.data_manager.batches.stock_movement_log.create_movement_log(
                product_id=batch['Product_ID'],
                movement_type='Sale',
                qty_change=-float(qty),
                unit_used='Unit',
                batch_id=batch['Batch_ID'],
                user_id=u_id,
                notes=f"Vente Facture #{invoice_id} - Client: {client_name}"
            )
            
            # Update Current_Quantity in DB
            with self.data_manager.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current - %s WHERE Batch_ID = %s",
                    (qty, batch['Batch_ID'])
                )
                conn.commit()

        if success:
            QMessageBox.information(self, "Succès", f"Vente enregistrée avec succès ! Facture #{invoice_id}")
            self.clear_cart()
            # Reload inventory data so stock quantities are fresh
            self.load_initial_data()
        else:
            QMessageBox.critical(self, "Erreur", "Une erreur est survenue lors de l'enregistrement des détails.")
