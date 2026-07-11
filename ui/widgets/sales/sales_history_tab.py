# ui/widgets/sales/sales_history_tab.py

import logging
from datetime import date
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QComboBox, QDateEdit, QFrame, QSplitter)
from PySide6.QtCore import Qt, QDate
from ui.formatting import format_money

class SalesHistoryTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        
        self.init_ui()
        self.load_filters()
        self.load_sales_data()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            #FilterFrame, #MainFrame, #DetailFrame {
                background-color: #ffffff;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
            QTableWidget {
                border: none;
                gridline-color: #f1f2f6;
                selection-background-color: #e3f2fd;
                selection-color: #2c3e50;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #2c3e50;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #e0e0e0;
            }
            QLabel {
                font-size: 13px;
                font-weight: 600;
            }
            QComboBox, QDateEdit {
                padding: 6px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: #f8f9fa;
            }
            QPushButton {
                background-color: #3498db; 
                color: white; 
                font-weight: bold; 
                border-radius: 4px; 
                padding: 8px 15px;
            }
            QPushButton:hover { background-color: #2980b9; }
            #ProfitLabel {
                color: #27ae60;
                font-weight: bold;
            }
            #TitleLabel {
                font-size: 16px;
                font-weight: 800;
                color: #2c3e50;
                margin-bottom: 5px;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # --- Filter Section ---
        filter_frame = QFrame()
        filter_frame.setObjectName("FilterFrame")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(15, 10, 15, 10)
        
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addMonths(-1)) # Default 1 month ago
        
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        
        self.cb_client = QComboBox()
        self.cb_client.setMinimumWidth(200)
        self.cb_client.addItem("Tous les Clients", None)
        
        btn_search = QPushButton("🔍 Rechercher")
        btn_search.clicked.connect(self.load_sales_data)
        
        filter_layout.addWidget(QLabel("Du :"))
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(QLabel("Au :"))
        filter_layout.addWidget(self.date_end)
        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("Client :"))
        filter_layout.addWidget(self.cb_client)
        filter_layout.addStretch()
        filter_layout.addWidget(btn_search)
        
        main_layout.addWidget(filter_frame)
        
        # --- Splitter for Tables ---
        splitter = QSplitter(Qt.Vertical)
        
        # Invoices Table
        main_frame = QFrame()
        main_frame.setObjectName("MainFrame")
        main_frame_layout = QVBoxLayout(main_frame)
        
        title_invoices = QLabel("📄 Liste des Ventes")
        title_invoices.setObjectName("TitleLabel")
        main_frame_layout.addWidget(title_invoices)
        
        self.table_invoices = QTableWidget()
        self.table_invoices.setColumnCount(8)
        self.table_invoices.setHorizontalHeaderLabels(["ID", "Date", "Client", "Statut", "Total HT", "Total TTC", "Fayda (Profit HT)", "Actions"])
        header = self.table_invoices.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_invoices.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_invoices.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_invoices.setShowGrid(False)
        self.table_invoices.setAlternatingRowColors(True)
        self.table_invoices.itemSelectionChanged.connect(self.on_invoice_selected)
        
        main_frame_layout.addWidget(self.table_invoices)
        splitter.addWidget(main_frame)
        
        # Details Table
        detail_frame = QFrame()
        detail_frame.setObjectName("DetailFrame")
        detail_frame_layout = QVBoxLayout(detail_frame)
        
        title_details = QLabel("📦 Détails de la Vente")
        title_details.setObjectName("TitleLabel")
        detail_frame_layout.addWidget(title_details)
        
        self.table_details = QTableWidget()
        self.table_details.setColumnCount(8)
        self.table_details.setHorizontalHeaderLabels(["Produit", "Lot", "Qté", "Prix Vente HT", "Prix Achat", "Total Ligne", "Fayda (Profit)", "TVA (%)"])
        self.table_details.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_details.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_details.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_details.setShowGrid(False)
        self.table_details.setAlternatingRowColors(True)
        
        detail_frame_layout.addWidget(self.table_details)
        splitter.addWidget(detail_frame)
        
        main_layout.addWidget(splitter)
        
        # Total Profit Summary
        summary_layout = QHBoxLayout()
        summary_layout.addStretch()
        self.lbl_total_period_profit = QLabel("Bénéfice Total Période : 0.00 DA")
        self.lbl_total_period_profit.setStyleSheet("font-size: 20px; font-weight: bold; color: #27ae60; background-color: #eafaf1; padding: 10px; border-radius: 8px;")
        summary_layout.addWidget(self.lbl_total_period_profit)
        
        main_layout.addLayout(summary_layout)

    def load_filters(self):
        clients = self.data_manager.clients.get_all_clients()
        for client in clients:
            self.cb_client.addItem(client['Client_Name'], client['Client_ID'])

    def load_sales_data(self):
        start_date = self.date_start.date().toString("yyyy-MM-dd")
        end_date = self.date_end.date().toString("yyyy-MM-dd")
        client_id = self.cb_client.currentData()
        
        invoices = self.data_manager.sales.get_sales_with_profit(start_date, end_date, client_id)
        
        self.table_invoices.setRowCount(0)
        total_profit_period = 0.0
        
        for inv in invoices:
            row = self.table_invoices.rowCount()
            self.table_invoices.insertRow(row)
            
            # Store ID in first item
            id_item = QTableWidgetItem(f"#{inv['Invoice_ID']}")
            id_item.setData(Qt.UserRole, inv['Invoice_ID'])
            self.table_invoices.setItem(row, 0, id_item)
            
            self.table_invoices.setItem(row, 1, QTableWidgetItem(str(inv['Invoice_Date'])))
            self.table_invoices.setItem(row, 2, QTableWidgetItem(inv['Client_Name'] or "---"))
            
            status_item = QTableWidgetItem(inv['Status'])
            self.table_invoices.setItem(row, 3, status_item)
            
            self.table_invoices.setItem(row, 4, QTableWidgetItem(format_money(inv.get('Total_Amount_HT', 0))))
            self.table_invoices.setItem(row, 5, QTableWidgetItem(format_money(inv.get('Total_Amount_TTC', 0))))
            
            profit = float(inv.get('Total_Profit') or 0)
            total_profit_period += profit
            profit_item = QTableWidgetItem(format_money(profit))
            profit_item.setForeground(Qt.darkGreen if profit > 0 else Qt.red)
            profit_item.setFont(self._bold_font())
            self.table_invoices.setItem(row, 6, profit_item)
            
            btn_view = QPushButton("👀")
            btn_view.setFixedSize(30, 30)
            btn_view.setCursor(Qt.PointingHandCursor)
            self.table_invoices.setCellWidget(row, 7, btn_view)
            
        self.lbl_total_period_profit.setText(f"Bénéfice Total Période : {format_money(total_profit_period)} DA")
        self.table_details.setRowCount(0)

    def on_invoice_selected(self):
        selected_rows = self.table_invoices.selectedItems()
        if not selected_rows:
            return
            
        invoice_id = self.table_invoices.item(selected_rows[0].row(), 0).data(Qt.UserRole)
        details = self.data_manager.sales.get_invoice_details_with_profit(invoice_id)
        
        self.table_details.setRowCount(0)
        
        for d in details:
            row = self.table_details.rowCount()
            self.table_details.insertRow(row)
            
            self.table_details.setItem(row, 0, QTableWidgetItem(d.get('Product_Name', '---')))
            self.table_details.setItem(row, 1, QTableWidgetItem(d.get('Lot_Number', '---')))
            self.table_details.setItem(row, 2, QTableWidgetItem(str(d.get('Qty_Sold', 0))))
            self.table_details.setItem(row, 3, QTableWidgetItem(format_money(d.get('Unit_Price_HT', 0))))
            self.table_details.setItem(row, 4, QTableWidgetItem(format_money(d.get('Unit_Price_Received', 0))))
            self.table_details.setItem(row, 5, QTableWidgetItem(format_money(d.get('Line_Total_HT', 0))))
            
            profit = float(d.get('Line_Profit') or 0)
            profit_item = QTableWidgetItem(format_money(profit))
            profit_item.setForeground(Qt.darkGreen if profit > 0 else Qt.red)
            profit_item.setFont(self._bold_font())
            self.table_details.setItem(row, 6, profit_item)
            
            self.table_details.setItem(row, 7, QTableWidgetItem(f"{d.get('TVA_Percent', 0)} %"))

    def _bold_font(self):
        from PySide6.QtGui import QFont
        f = QFont()
        f.setBold(True)
        return f
