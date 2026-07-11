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

    def remove_invoice_detail(self, detail_id, batch_manager=None, user_id=None):
        """
        حذف تفصيلة من الفاتورة واسترجاع المخزون (إلغاء جزئي).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # جلب رقم الفاتورة أولاً والكمية والباتش
                cursor.execute("SELECT Invoice_ID, Batch_ID, Qty_Sold FROM Sales_Details WHERE Detail_ID = %s", (detail_id,))
                result = cursor.fetchone()
                if not result:
                    return False
                
                invoice_id = result['Invoice_ID']
                batch_id = result['Batch_ID']
                qty_sold = result['Qty_Sold']
                
                # استرجاع المخزون
                if batch_manager and batch_id and qty_sold > 0:
                    batch_manager.adjust_batch_quantity(
                        batch_id=batch_id, 
                        quantity_change=qty_sold, 
                        movement_type='Sale_Return', 
                        user_id=user_id
                    )
                
                cursor.execute("DELETE FROM Sales_Details WHERE Detail_ID = %s", (detail_id,))
                
                # تحديث إجماليات الفاتورة
                self._update_invoice_totals(cursor, invoice_id)
                conn.commit()
                
                logging.info(f"Detail {detail_id} removed from Invoice {invoice_id} and stock returned.")
                return True
        except mysql.connector.Error as err:
            logging.error(f"Database error while removing invoice detail {detail_id}: {err}")
            return False

    def cancel_invoice(self, invoice_id, batch_manager=None, user_id=None):
        """
        إلغاء فاتورة بالكامل وإرجاع المخزون.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. Fetch all details to refund
                cursor.execute("SELECT Batch_ID, Qty_Sold FROM Sales_Details WHERE Invoice_ID = %s", (invoice_id,))
                details = cursor.fetchall()
                
                # 2. Refund stock
                if batch_manager:
                    for d in details:
                        if d['Batch_ID'] and d['Qty_Sold'] > 0:
                            batch_manager.adjust_batch_quantity(
                                batch_id=d['Batch_ID'], 
                                quantity_change=d['Qty_Sold'], 
                                movement_type='Sale_Return', 
                                user_id=user_id
                            )
                
                # 3. Update Invoice status
                cursor.execute("""
                    UPDATE Sales_Invoices 
                    SET Status = 'Cancelled', Total_Amount_HT = 0, Total_Amount_TTC = 0, 
                        Total_Discount = 0, Total_TVA = 0, Updated_At = NOW() 
                    WHERE Invoice_ID = %s
                """, (invoice_id,))
                
                conn.commit()
                logging.info(f"Invoice {invoice_id} successfully cancelled and stock returned.")
                return True
        except mysql.connector.Error as err:
            logging.error(f"Database error while cancelling invoice {invoice_id}: {err}")
            return False

    def update_invoice_detail_qty(self, detail_id, new_qty, batch_manager=None, user_id=None):
        """
        تعديل الكمية المباعة لعنصر محدد. إذا زادت الكمية، نسحب من المخزون. وإذا نقصت، نرجع للمخزون.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                cursor.execute("""
                    SELECT Invoice_ID, Batch_ID, Qty_Sold, Unit_Price_HT, Discount_Percent, TVA_Percent 
                    FROM Sales_Details 
                    WHERE Detail_ID = %s
                """, (detail_id,))
                result = cursor.fetchone()
                if not result:
                    return False
                    
                old_qty = result['Qty_Sold']
                batch_id = result['Batch_ID']
                invoice_id = result['Invoice_ID']
                unit_price = result['Unit_Price_HT']
                discount = result['Discount_Percent']
                tva = result['TVA_Percent']
                
                diff = int(new_qty) - int(old_qty)
                if diff == 0:
                    return True # لا يوجد تغيير
                    
                # تعديل المخزون أولاً
                if batch_manager and batch_id:
                    if diff > 0:
                        # زيادة في المبيعات -> سحب من المخزون
                        success = batch_manager.adjust_batch_quantity(
                            batch_id=batch_id, 
                            quantity_change=-diff, 
                            movement_type='Sale', 
                            user_id=user_id
                        )
                        if not success:
                            return False # فشل السحب (الكمية غير متوفرة)
                    elif diff < 0:
                        # نقصان في المبيعات -> إرجاع للمخزون
                        batch_manager.adjust_batch_quantity(
                            batch_id=batch_id, 
                            quantity_change=abs(diff), 
                            movement_type='Sale_Return', 
                            user_id=user_id
                        )
                        
                # حساب الإجماليات الجديدة
                line_total_ht = float(new_qty) * float(unit_price) * (1 - float(discount)/100)
                line_total_ttc = line_total_ht * (1 + float(tva)/100)
                
                # تحديث العنصر
                cursor.execute("""
                    UPDATE Sales_Details 
                    SET Qty_Sold = %s, Line_Total_HT = %s, Line_Total_TTC = %s 
                    WHERE Detail_ID = %s
                """, (new_qty, line_total_ht, line_total_ttc, detail_id))
                
                # تحديث إجماليات الفاتورة
                self._update_invoice_totals(cursor, invoice_id)
                conn.commit()
                
                logging.info(f"Detail {detail_id} updated: qty changed from {old_qty} to {new_qty}.")
                return True
        except mysql.connector.Error as err:
            logging.error(f"Database error while updating detail {detail_id}: {err}")
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
        
        if isinstance(totals, dict):
            total_ht = totals.get('total_ht') or 0.00
            total_ttc = totals.get('total_ttc') or 0.00
            total_discount = totals.get('total_discount') or 0.00
            total_tva = totals.get('total_tva') or 0.00
        else:
            total_ht = totals[0] if totals and totals[0] else 0.00
            total_ttc = totals[1] if totals and totals[1] else 0.00
            total_discount = totals[2] if totals and totals[2] else 0.00
            total_tva = totals[3] if totals and totals[3] else 0.00
        
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
                        i.Total_Discount, i.Total_TVA,
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
