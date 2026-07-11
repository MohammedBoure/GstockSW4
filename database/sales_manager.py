# database/sales_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class SalesManager:
    """إدارة فواتير المبيعات وتفاصيلها (Sales Invoices & Details)."""

    def __init__(self, db_instance):
        self.db = db_instance

    def create_invoice(self, client_id, invoice_date, status='Draft', notes=None, user_id=None):
        """
        إنشاء فاتورة مبيعات جديدة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Sales_Invoices 
                    (Client_ID, Invoice_Date, Status, Notes, Created_By) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                params = (client_id, invoice_date, status, notes, user_id)
                cursor.execute(query, params)
                invoice_id = cursor.lastrowid
                logging.info(f"Sales Invoice created with ID {invoice_id} for Client {client_id}.")
                return invoice_id
        except mysql.connector.Error as err:
            logging.error(f"Database error while creating sales invoice: {err}")
            return None

    def add_invoice_detail(self, invoice_id, product_id, batch_id, qty_sold, unit_price_ht, discount_percent=0.00, tva_percent=0.00):
        """
        إضافة عنصر تفصيلي لفاتورة المبيعات.
        """
        line_total_ht = float(qty_sold) * float(unit_price_ht) * (1 - float(discount_percent)/100)
        line_total_ttc = line_total_ht * (1 + float(tva_percent)/100)
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Sales_Details 
                    (Invoice_ID, Product_ID, Batch_ID, Qty_Sold, Unit_Price_HT, Discount_Percent, TVA_Percent, Line_Total_HT, Line_Total_TTC) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (invoice_id, product_id, batch_id, qty_sold, unit_price_ht, discount_percent, tva_percent, line_total_ht, line_total_ttc)
                cursor.execute(query, params)
                detail_id = cursor.lastrowid
                
                # تحديث إجماليات الفاتورة
                self._update_invoice_totals(cursor, invoice_id)
                
                logging.info(f"Detail added to Invoice {invoice_id} for Product {product_id}.")
                return detail_id
        except mysql.connector.Error as err:
            logging.error(f"Database error while adding invoice detail: {err}")
            return None

    def remove_invoice_detail(self, detail_id):
        """
        حذف تفصيلة من الفاتورة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # جلب رقم الفاتورة أولاً
                cursor.execute("SELECT Invoice_ID FROM Sales_Details WHERE Detail_ID = %s", (detail_id,))
                result = cursor.fetchone()
                if not result:
                    return False
                invoice_id = result[0]
                
                cursor.execute("DELETE FROM Sales_Details WHERE Detail_ID = %s", (detail_id,))
                
                # تحديث إجماليات الفاتورة
                self._update_invoice_totals(cursor, invoice_id)
                
                logging.info(f"Detail {detail_id} removed from Invoice {invoice_id}.")
                return True
        except mysql.connector.Error as err:
            logging.error(f"Database error while removing invoice detail {detail_id}: {err}")
            return False

    def _update_invoice_totals(self, cursor, invoice_id):
        """
        وظيفة داخلية لتحديث إجماليات الفاتورة بعد أي تغيير في التفاصيل.
        """
        query_totals = """
            SELECT 
                SUM(Line_Total_HT) as total_ht,
                SUM(Line_Total_TTC) as total_ttc,
                SUM((Qty_Sold * Unit_Price_HT) * (Discount_Percent/100)) as total_discount,
                SUM(Line_Total_TTC - Line_Total_HT) as total_tva
            FROM Sales_Details
            WHERE Invoice_ID = %s
        """
        cursor.execute(query_totals, (invoice_id,))
        totals = cursor.fetchone()
        
        total_ht = totals[0] or 0.00
        total_ttc = totals[1] or 0.00
        total_discount = totals[2] or 0.00
        total_tva = totals[3] or 0.00
        
        update_query = """
            UPDATE Sales_Invoices 
            SET Total_Amount_HT = %s, Total_Discount = %s, Total_TVA = %s, Total_Amount_TTC = %s, Updated_At = NOW()
            WHERE Invoice_ID = %s
        """
        cursor.execute(update_query, (total_ht, total_discount, total_tva, total_ttc, invoice_id))

    def update_invoice_status(self, invoice_id, status):
        """
        تحديث حالة الفاتورة (Draft, Validated, Paid, Cancelled).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "UPDATE Sales_Invoices SET Status = %s, Updated_At = NOW() WHERE Invoice_ID = %s"
                cursor.execute(query, (status, invoice_id))
                if cursor.rowcount > 0:
                    logging.info(f"Invoice {invoice_id} status updated to {status}.")
                    return True
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating invoice {invoice_id} status: {e}")
            return False

    def get_invoice_by_id(self, invoice_id):
        """
        جلب فاتورة محددة مع تفاصيلها.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # الفاتورة
                query = "SELECT * FROM Sales_Invoices WHERE Invoice_ID = %s"
                cursor.execute(query, (invoice_id,))
                invoice = cursor.fetchone()
                
                if invoice:
                    # التفاصيل
                    detail_query = """
                        SELECT sd.*, p.Product_Name, b.Lot_Number, b.Expiry_Date
                        FROM Sales_Details sd
                        JOIN Products_Master p ON sd.Product_ID = p.Product_ID
                        JOIN Inventory_Batches b ON sd.Batch_ID = b.Batch_ID
                        WHERE sd.Invoice_ID = %s
                    """
                    cursor.execute(detail_query, (invoice_id,))
                    invoice['details'] = cursor.fetchall()
                    
                return invoice
        except mysql.connector.Error as e:
            logging.error(f"Error fetching invoice {invoice_id}: {e}")
            raise

    def get_all_invoices(self):
        """
        جلب جميع الفواتير.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT i.*, c.Client_Name 
                    FROM Sales_Invoices i
                    LEFT JOIN Clients c ON i.Client_ID = c.Client_ID
                    ORDER BY i.Invoice_Date DESC, i.Invoice_ID DESC
                """
                cursor.execute(query)
                invoices = cursor.fetchall()
                return invoices
        except mysql.connector.Error as e:
            logging.error(f"Error fetching invoices: {e}")
            raise

    def get_sales_with_profit(self, start_date=None, end_date=None, client_id=None):
        """
        جلب الفواتير مع حساب الفائدة (الربح) لكل فاتورة وللفترة المحددة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = """
                    SELECT 
                        i.Invoice_ID, i.Invoice_Date, i.Status, i.Total_Amount_HT, i.Total_Amount_TTC,
                        c.Client_Name,
                        SUM(sd.Line_Total_HT - (sd.Qty_Sold * b.Unit_Price_Received)) AS Total_Profit
                    FROM Sales_Invoices i
                    LEFT JOIN Clients c ON i.Client_ID = c.Client_ID
                    LEFT JOIN Sales_Details sd ON i.Invoice_ID = sd.Invoice_ID
                    LEFT JOIN Inventory_Batches b ON sd.Batch_ID = b.Batch_ID
                    WHERE 1=1
                """
                params = []
                
                if start_date:
                    query += " AND i.Invoice_Date >= %s"
                    params.append(start_date)
                if end_date:
                    query += " AND i.Invoice_Date <= %s"
                    params.append(end_date)
                if client_id:
                    query += " AND i.Client_ID = %s"
                    params.append(client_id)
                    
                query += """
                    GROUP BY i.Invoice_ID
                    ORDER BY i.Invoice_Date DESC, i.Invoice_ID DESC
                """
                
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching sales with profit: {e}")
            return []

    def get_invoice_details_with_profit(self, invoice_id):
        """
        جلب تفاصيل فاتورة مع حساب الربح لكل عنصر.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        sd.*, 
                        p.Product_Name, 
                        b.Lot_Number, 
                        b.Unit_Price_Received,
                        (sd.Line_Total_HT - (sd.Qty_Sold * b.Unit_Price_Received)) AS Line_Profit
                    FROM Sales_Details sd
                    JOIN Products_Master p ON sd.Product_ID = p.Product_ID
                    JOIN Inventory_Batches b ON sd.Batch_ID = b.Batch_ID
                    WHERE sd.Invoice_ID = %s
                """
                cursor.execute(query, (invoice_id,))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching invoice details with profit: {e}")
            return []
            logging.error(f"Error fetching invoices: {e}")
            raise
