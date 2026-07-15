import logging
import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QPushButton, QFrame, QDoubleSpinBox, QCompleter, QCheckBox, QMessageBox, QLineEdit,
    QGridLayout, QGroupBox
)
from PySide6.QtCore import Qt, QDate, QLocale
from PySide6.QtGui import QFont

from ui.widgets.procurement.reception_dialog.auto_select_widgets import (
    AutoSelectSpinBox, AutoSelectDoubleSpinBox, AutoSelectLineEdit
)
from ui.widgets.inventory.location_tree_combo import LocationTreeComboBox

class QuickAddDialog(QDialog):
    def __init__(self, manager, parent=None, batch_data=None):
        super().__init__(parent)
        self.manager = manager
        self.batch_data = batch_data
        
        if batch_data:
            self.setWindowTitle("Modification Rapide (Détaillée)")
        else:
            self.setWindowTitle("Ajout Rapide au Stock (Détaillé)")
            
        self.setMinimumWidth(800)
        
        self.product_defaults = {}
        
        self._build_ui()
        self._setup_connections()
        self._load_products()
        
        if batch_data:
            self.btn_add.setText(" Enregistrer")
            self.chk_print.setChecked(False)
            self._prefill_data()

    def _prefill_data(self):
        d = self.batch_data
        
        # Product
        for i in range(self.cb_product.count()):
            p = self.cb_product.itemData(i)
            if p and p['Product_ID'] == d.get('Product_ID'):
                self.cb_product.setCurrentIndex(i)
                break
                
        # Location
        self.cb_location.select_location_id(d.get('Location_ID'))
        
        # Supplier
        supp_id = d.get('Supplier_ID')
        if supp_id:
            for i in range(self.cb_supplier.count()):
                if self.cb_supplier.itemData(i) == supp_id:
                    self.cb_supplier.setCurrentIndex(i)
                    break
        
        # Qty
        self.inp_qty.setValue(float(d.get('Quantity_Initial', 1)))
        
        # Lot, Exp
        self.inp_lot.setText(d.get('Lot_Number', ''))
        
        exp = d.get('Expiry_Date')
        from PySide6.QtCore import QDate
        if exp and str(exp).strip() and str(exp) != 'None':
            # handle str or date obj
            if isinstance(exp, str):
                parts = exp.split('-')
                if len(parts) == 3:
                    self.inp_expiry.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
            else:
                self.inp_expiry.setDate(QDate(exp.year, exp.month, exp.day))
                
        # Prices
        self.inp_price.setValue(float(d.get('Unit_Price_Received') or 0))
        self.inp_remise.setValue(float(d.get('Discount_Percent') or 0))
        self.cb_remise_type.setCurrentText('%')
        self.chk_tva.setChecked(float(d.get('Tax_Rate_Percent') or 0) > 0)
        
        self.inp_sell_price.setValue(float(d.get('Selling_Price_HT') or 0))
        self.inp_sell_price_2.setValue(float(d.get('Selling_Price_HT_2') or 0))
        self.inp_sell_price_3.setValue(float(d.get('Selling_Price_HT_3') or 0))
        self.inp_sell_price_4.setValue(float(d.get('Selling_Price_HT_4') or 0))
        self.chk_sell_tva.setChecked(float(d.get('Selling_TVA_Percent') or 0) > 0)
        
        self.inp_observation.setText(d.get('Reception_Note') or d.get('Batch_Note') or '')
        self.inp_barcode.setText(d.get('External_Barcode') or '')
        
        self.calculate_live_item_ttc()
        self.calculate_live_sell_ttc()
        
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        lbl_header = QLabel("Ajout Rapide d'un Produit")
        lbl_header.setFont(QFont("Arial", 14, QFont.Bold))
        lbl_header.setStyleSheet("color: #2980b9; padding-bottom: 5px;")
        lbl_header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(lbl_header)

        # ---------------------------------------------------------
        # Product & Location Group
        # ---------------------------------------------------------
        grp_prod = QGroupBox("Produit et Emplacement")
        grp_prod.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #bdc3c7; border-radius: 4px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }")
        lay_prod = QGridLayout(grp_prod)
        lay_prod.setSpacing(10)
        
        self.cb_product = QComboBox()
        self.cb_product.setEditable(True)
        self.cb_product.completer().setFilterMode(Qt.MatchContains)
        self.cb_product.completer().setCompletionMode(QCompleter.PopupCompletion)
        
        self.cb_unit_type = QComboBox()
        self.cb_unit_type.setMinimumWidth(100)
        
        self.cb_location = LocationTreeComboBox(self.manager.locations)
        self.cb_supplier = QComboBox()
        self.cb_supplier.setEditable(True)
        self.cb_supplier.completer().setFilterMode(Qt.MatchContains)
        self.cb_supplier.setLineEdit(AutoSelectLineEdit())
        
        self.cb_product.setLineEdit(AutoSelectLineEdit())
        
        lay_prod.addWidget(QLabel("Produit:"), 0, 0)
        lay_prod.addWidget(self.cb_product, 0, 1, 1, 3)
        lay_prod.addWidget(QLabel("Unité:"), 0, 4)
        lay_prod.addWidget(self.cb_unit_type, 0, 5)
        
        lay_prod.addWidget(QLabel("Emplacement:"), 1, 0)
        lay_prod.addWidget(self.cb_location, 1, 1, 1, 2)
        
        lay_prod.addWidget(QLabel("Fournisseur:"), 1, 3)
        lay_prod.addWidget(self.cb_supplier, 1, 4, 1, 2)
        
        main_layout.addWidget(grp_prod)

        # ---------------------------------------------------------
        # Quantities & Dates Group
        # ---------------------------------------------------------
        grp_qty = QGroupBox("Quantité, Lot et Validité")
        grp_qty.setStyleSheet(grp_prod.styleSheet())
        lay_qty = QHBoxLayout(grp_qty)
        lay_qty.setSpacing(15)
        
        self.inp_qty = AutoSelectSpinBox()
        self.inp_qty.setRange(1, 999999)
        self.inp_qty.setValue(1)
        
        self.inp_lot = AutoSelectLineEdit()
        self.inp_lot.setPlaceholderText("N/A")
        
        self.inp_expiry = QDateEdit(QDate.currentDate().addYears(2))
        self.inp_expiry.setCalendarPopup(True)
        
        self.inp_barcode = AutoSelectLineEdit()
        self.inp_barcode.setPlaceholderText("Scanner ou saisir (Optionnel)")
        
        lay_qty.addWidget(QLabel("Quantité:"))
        lay_qty.addWidget(self.inp_qty)
        lay_qty.addWidget(QLabel("Lot:"))
        lay_qty.addWidget(self.inp_lot)
        lay_qty.addWidget(QLabel("Exp:"))
        lay_qty.addWidget(self.inp_expiry)
        lay_qty.addWidget(QLabel("Code Barre Ext:"))
        lay_qty.addWidget(self.inp_barcode)
        
        main_layout.addWidget(grp_qty)

        # ---------------------------------------------------------
        # Purchase Prices Group
        # ---------------------------------------------------------
        grp_achat = QGroupBox("Prix d'Achat")
        grp_achat.setStyleSheet(grp_prod.styleSheet())
        lay_achat = QGridLayout(grp_achat)
        lay_achat.setSpacing(10)
        
        self.inp_price = AutoSelectDoubleSpinBox()
        self.inp_price.setRange(0, 99999999.99)
        self.inp_price.setDecimals(2)
        self.inp_price.setGroupSeparatorShown(True)
        
        self.inp_price_ttc = AutoSelectDoubleSpinBox()
        self.inp_price_ttc.setRange(0, 99999999.99)
        self.inp_price_ttc.setDecimals(2)
        self.inp_price_ttc.setGroupSeparatorShown(True)
        
        self.inp_remise = AutoSelectDoubleSpinBox()
        self.inp_remise.setRange(0, 99999999.99)
        self.inp_remise.setDecimals(2)
        
        self.cb_remise_type = QComboBox()
        self.cb_remise_type.addItems(["%", "DA"])
        
        self.chk_tva = QCheckBox("TVA 19%")
        
        self.lbl_item_ttc = QLabel("TTC : 0.00 DA")
        self.lbl_item_ttc.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
        
        lay_achat.addWidget(QLabel("Prix HT:"), 0, 0)
        lay_achat.addWidget(self.inp_price, 0, 1)
        lay_achat.addWidget(QLabel("Prix TTC:"), 0, 2)
        lay_achat.addWidget(self.inp_price_ttc, 0, 3)
        
        lay_achat.addWidget(QLabel("Remise:"), 1, 0)
        lay_rem = QHBoxLayout()
        lay_rem.addWidget(self.inp_remise)
        lay_rem.addWidget(self.cb_remise_type)
        lay_achat.addLayout(lay_rem, 1, 1)
        
        lay_achat.addWidget(self.chk_tva, 1, 2)
        lay_achat.addWidget(self.lbl_item_ttc, 1, 3, alignment=Qt.AlignRight)
        
        main_layout.addWidget(grp_achat)

        # ---------------------------------------------------------
        # Selling Prices Group
        # ---------------------------------------------------------
        grp_vente = QGroupBox("Prix de Vente")
        grp_vente.setStyleSheet(grp_prod.styleSheet())
        lay_vente = QGridLayout(grp_vente)
        lay_vente.setSpacing(10)
        
        self.inp_sell_price = AutoSelectDoubleSpinBox()
        self.inp_sell_price_2 = AutoSelectDoubleSpinBox()
        self.inp_sell_price_3 = AutoSelectDoubleSpinBox()
        self.inp_sell_price_4 = AutoSelectDoubleSpinBox()
        
        for sp in [self.inp_sell_price, self.inp_sell_price_2, self.inp_sell_price_3, self.inp_sell_price_4]:
            sp.setRange(0, 99999999.99)
            sp.setDecimals(2)
            sp.setGroupSeparatorShown(True)
            
        self.chk_sell_tva = QCheckBox("TVA Vente 19%")
        
        self.lbl_sell_ttc = QLabel("TTC Vente : 0.00 DA")
        self.lbl_sell_ttc.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 14px;")
        
        lay_vente.addWidget(QLabel("Vente 1 HT:"), 0, 0)
        lay_vente.addWidget(self.inp_sell_price, 0, 1)
        lay_vente.addWidget(QLabel("Vente 2 HT:"), 0, 2)
        lay_vente.addWidget(self.inp_sell_price_2, 0, 3)
        
        lay_vente.addWidget(QLabel("Vente 3 HT:"), 1, 0)
        lay_vente.addWidget(self.inp_sell_price_3, 1, 1)
        lay_vente.addWidget(QLabel("Vente 4 HT:"), 1, 2)
        lay_vente.addWidget(self.inp_sell_price_4, 1, 3)
        
        lay_vente.addWidget(self.chk_sell_tva, 2, 0, 1, 2)
        lay_vente.addWidget(self.lbl_sell_ttc, 2, 2, 1, 2, alignment=Qt.AlignRight)
        
        main_layout.addWidget(grp_vente)

        # ---------------------------------------------------------
        # Observation & Actions
        # ---------------------------------------------------------
        lay_obs = QHBoxLayout()
        self.inp_observation = AutoSelectLineEdit()
        self.inp_observation.setPlaceholderText("Observation (Optionnel)")
        lay_obs.addWidget(QLabel("Observation:"))
        lay_obs.addWidget(self.inp_observation)
        main_layout.addLayout(lay_obs)
        
        self.chk_print = QCheckBox("Imprimer l'étiquette après l'ajout")
        self.chk_print.setChecked(True)
        self.chk_print.setStyleSheet("color: #8e44ad; font-weight: bold;")
        main_layout.addWidget(self.chk_print)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)
        
        btns = QHBoxLayout()
        btns.addStretch()
        
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_add = QPushButton(" Ajouter")
        self.btn_add.setIcon(qta.icon('fa5s.plus', color='white'))
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white; font-weight: bold; padding: 6px 15px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_add.clicked.connect(self.validate_and_accept)
        
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_add)
        main_layout.addLayout(btns)

    def _setup_connections(self):
        self.cb_product.currentIndexChanged.connect(self.on_product_selected)
        
        # Calculate TTC for purchase
        self.inp_price.valueChanged.connect(lambda: self.on_price_changed('ht'))
        self.inp_price_ttc.valueChanged.connect(lambda: self.on_price_changed('ttc'))
        self.inp_remise.valueChanged.connect(self.calculate_live_item_ttc)
        self.cb_remise_type.currentIndexChanged.connect(self.calculate_live_item_ttc)
        self.chk_tva.toggled.connect(self.calculate_live_item_ttc)
        self.inp_qty.valueChanged.connect(self.calculate_live_item_ttc)
        
        # Calculate TTC for sell
        self.inp_sell_price.valueChanged.connect(self.calculate_live_sell_ttc)
        self.chk_sell_tva.toggled.connect(self.calculate_live_sell_ttc)

        self.cb_unit_type.currentIndexChanged.connect(self.on_unit_type_changed)

    def _load_products(self):
        all_products = self.manager.products.get_all_products()
        self.cb_product.addItem("--- Sélectionnez un produit ---", None)
        for p in all_products:
            brand = p.get('Manuf_Name') or "---"
            ref = p.get('Manuf_Cat_No') or "---"
            self.cb_product.addItem(f"{p['Product_Name']} | Réf: {ref} | {brand}", p)
            
        # Load Suppliers
        self.cb_supplier.addItem("--- Sans Fournisseur ---", None)
        try:
            conn = self.manager.db.get_raw_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT Supplier_ID, Supplier_Name FROM Suppliers WHERE Deleted_At IS NULL ORDER BY Supplier_Name")
            for row in cursor.fetchall():
                self.cb_supplier.addItem(row['Supplier_Name'], row['Supplier_ID'])
            conn.close()
        except:
            pass

    def on_product_selected(self):
        p = self.cb_product.currentData()
        self.cb_unit_type.clear()
        
        if not p:
            self.inp_price.setValue(0)
            self.inp_sell_price.setValue(0)
            return
            
        # Units
        self.cb_unit_type.addItem(p.get('Base_Unit_Name', 'Unité'), 1)
        if p.get('Package_Unit_Name') and p.get('Units_per_Package'):
            self.cb_unit_type.addItem(p['Package_Unit_Name'], int(p['Units_per_Package']))
            
        self.chk_tva.setChecked(bool(float(p.get('Tax_Rate_Percent') or 0) > 0))
        self.chk_sell_tva.setChecked(bool(float(p.get('Selling_TVA_Percent') or 0) > 0))
        
        self.inp_sell_price.setValue(float(p.get('Default_Selling_Price_HT', 0)))
        
        self.calculate_live_item_ttc()
        self.calculate_live_sell_ttc()

    def on_unit_type_changed(self):
        pass

    def on_price_changed(self, source='ht'):
        if not self.cb_product.currentData(): return
        self.inp_price.blockSignals(True)
        self.inp_price_ttc.blockSignals(True)
        
        tva = 1.19 if self.chk_tva.isChecked() else 1.0
        if source == 'ht':
            ht = self.inp_price.value()
            self.inp_price_ttc.setValue(ht * tva)
        else:
            ttc = self.inp_price_ttc.value()
            self.inp_price.setValue(ttc / tva)
            
        self.inp_price.blockSignals(False)
        self.inp_price_ttc.blockSignals(False)
        self.calculate_live_item_ttc()

    def calculate_live_item_ttc(self):
        ht = self.inp_price.value()
        remise = self.inp_remise.value()
        
        if self.cb_remise_type.currentText() == '%':
            ht = ht * (1 - remise / 100.0)
        else:
            ht = ht - remise
            
        if ht < 0: ht = 0
            
        tva = 1.19 if self.chk_tva.isChecked() else 1.0
        ttc = ht * tva
        qty = self.inp_qty.value()
        
        factor = self.cb_unit_type.currentData() or 1
        total = ttc * (qty * factor)
        
        self.lbl_item_ttc.setText(f"TTC Total : {total:,.2f} DA")

    def calculate_live_sell_ttc(self):
        ht = self.inp_sell_price.value()
        tva = 1.19 if self.chk_sell_tva.isChecked() else 1.0
        ttc = ht * tva
        self.lbl_sell_ttc.setText(f"TTC Vente : {ttc:,.2f} DA")

    def validate_and_accept(self):
        p_data = self.cb_product.currentData()
        loc_id = self.cb_location.get_current_location_id()
        
        if not p_data:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un produit.")
            self.cb_product.setFocus()
            return
            
        if loc_id is None:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un emplacement.")
            self.cb_location.setFocus()
            return
            
        qty = self.inp_qty.value()
        if qty <= 0:
            QMessageBox.warning(self, "Erreur", "La quantité doit être supérieure à zéro.")
            self.inp_qty.setFocus()
            return
            
        self.accept()
        
    def get_data(self):
        p_data = self.cb_product.currentData()
        factor = self.cb_unit_type.currentData() or 1
        effective_qty = self.inp_qty.value() * factor
        
        remise = self.inp_remise.value()
        if self.cb_remise_type.currentText() == 'DA':
            # convert DA to percentage relative to price
            base_price = self.inp_price.value()
            discount_pct = (remise / base_price * 100) if base_price > 0 else 0
        else:
            discount_pct = remise
            
        return {
            'Product_ID': p_data['Product_ID'],
            'Product_Name': p_data['Product_Name'],
            'Location_ID': self.cb_location.get_current_location_id(),
            'Quantity': effective_qty,
            'Lot_Number': self.inp_lot.text().strip() or "N/A",
            'Expiry_Date': self.inp_expiry.date().toPyDate(),
            'Unit_Price_HT': self.inp_price.value(),
            'Discount_Percent': discount_pct,
            'Tax_Rate_Percent': 19.0 if self.chk_tva.isChecked() else 0.0,
            
            'Selling_Price_HT': self.inp_sell_price.value(),
            'Selling_Price_HT_2': self.inp_sell_price_2.value(),
            'Selling_Price_HT_3': self.inp_sell_price_3.value(),
            'Selling_Price_HT_4': self.inp_sell_price_4.value(),
            'Selling_TVA_Percent': 19.0 if self.chk_sell_tva.isChecked() else 0.0,
            
            'Batch_Note': self.inp_observation.text().strip(),
            'External_Barcode': self.inp_barcode.text().strip(),
            
            'Supplier_ID': self.cb_supplier.currentData(),
            'Print_Label': self.chk_print.isChecked(),
        }
