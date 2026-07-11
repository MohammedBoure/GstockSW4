# database/client_credit_note_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class ClientCreditNoteManager:
    """إدارة عمليات الإشعارات الدائنة للعملاء ومرتجعات المبيعات (Client Credit Notes)."""

    def __init__(self, db_instance):
        self.db = db_instance

    def create_credit_note(self, client_id, return_date, invoice_id=None, status='Draft', notes=None, user_id=None):
        """
        إنشاء إشعار دائن (مرتجع مبيعات) جديد.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Client_Credit_Notes 
                    (Client_ID, Invoice_ID, Return_Date, Status, Notes, Created_By) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                params = (client_id, invoice_id, return_date, status, notes, user_id)
                cursor.execute(query, params)
                credit_note_id = cursor.lastrowid
                logging.info(f"Credit Note created with ID {credit_note_id} for Client {client_id}.")
                return credit_note_id
        except mysql.connector.Error as err:
            logging.error(f"Database error while creating client credit note: {err}")
            return None

    def add_credit_note_detail(self, credit_note_id, product_id, batch_id, qty_returned, unit_price_ht, tva_percent=0.00):
        """
        إضافة عنصر تفصيلي للمرتجعات.
        """
        line_total_ht = float(qty_returned) * float(unit_price_ht)
        line_total_ttc = line_total_ht * (1 + float(tva_percent)/100)
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Client_Credit_Note_Details 
                    (Credit_Note_ID, Product_ID, Batch_ID, Qty_Returned, Unit_Price_HT, TVA_Percent, Line_Total_HT, Line_Total_TTC) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (credit_note_id, product_id, batch_id, qty_returned, unit_price_ht, tva_percent, line_total_ht, line_total_ttc)
                cursor.execute(query, params)
                detail_id = cursor.lastrowid
                
                # تحديث إجماليات الإشعار
                self._update_credit_note_totals(cursor, credit_note_id)
                
                logging.info(f"Detail added to Credit Note {credit_note_id} for Product {product_id}.")
                return detail_id
        except mysql.connector.Error as err:
            logging.error(f"Database error while adding credit note detail: {err}")
            return None

    def _update_credit_note_totals(self, cursor, credit_note_id):
        """
        تحديث الإجماليات للإشعار الدائن.
        """
        query_totals = """
            SELECT 
                SUM(Line_Total_HT) as total_ht,
                SUM(Line_Total_TTC) as total_ttc,
                SUM(Line_Total_TTC - Line_Total_HT) as total_tva
            FROM Client_Credit_Note_Details
            WHERE Credit_Note_ID = %s
        """
        cursor.execute(query_totals, (credit_note_id,))
        totals = cursor.fetchone()
        
        total_ht = totals[0] or 0.00
        total_ttc = totals[1] or 0.00
        total_tva = totals[2] or 0.00
        
        update_query = """
            UPDATE Client_Credit_Notes 
            SET Total_Amount_HT = %s, Total_TVA = %s, Total_Amount_TTC = %s
            WHERE Credit_Note_ID = %s
        """
        cursor.execute(update_query, (total_ht, total_tva, total_ttc, credit_note_id))

    def validate_credit_note(self, credit_note_id, user_id):
        """
        اعتماد الإشعار الدائن: سيقوم هذا الإجراء بإرجاع الكميات إلى المخزون كحركة Sale_Return
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # التحقق من الحالة
                cursor.execute("SELECT Status FROM Client_Credit_Notes WHERE Credit_Note_ID = %s", (credit_note_id,))
                result = cursor.fetchone()
                if not result or result[0] != 'Draft':
                    logging.warning(f"Credit Note {credit_note_id} cannot be validated (not in Draft status).")
                    return False
                    
                # جلب التفاصيل لتحديث المخزون
                cursor.execute("SELECT Product_ID, Batch_ID, Qty_Returned FROM Client_Credit_Note_Details WHERE Credit_Note_ID = %s", (credit_note_id,))
                details = cursor.fetchall()
                
                for detail in details:
                    product_id, batch_id, qty_returned = detail
                    if batch_id:
                        # زيادة الكمية في الـ Batch
                        cursor.execute("UPDATE Inventory_Batches SET Quantity_Current = Quantity_Current + %s WHERE Batch_ID = %s", (qty_returned, batch_id))
                        
                        # تسجيل حركة في Stock Movement
                        cursor.execute("SELECT Quantity_Current, Stock_Unit FROM Inventory_Batches b JOIN Products_Master p ON b.Product_ID = p.Product_ID WHERE Batch_ID = %s", (batch_id,))
                        batch_info = cursor.fetchone()
                        stock_after = batch_info[0]
                        stock_unit = batch_info[1]
                        
                        move_query = """
                            INSERT INTO Stock_Movement_Log 
                            (User_ID, Product_ID, Batch_ID, Movement_Type, Qty_Change, Unit_Used, Notes, Stock_After)
                            VALUES (%s, %s, %s, 'Sale_Return', %s, %s, %s, %s)
                        """
                        move_notes = f"مرتجع مبيعات إشعار دائن رقم {credit_note_id}"
                        cursor.execute(move_query, (user_id, product_id, batch_id, float(qty_returned), stock_unit, move_notes, stock_after))
                
                # تغيير الحالة
                cursor.execute("UPDATE Client_Credit_Notes SET Status = 'Validated' WHERE Credit_Note_ID = %s", (credit_note_id,))
                
                logging.info(f"Credit Note {credit_note_id} validated successfully.")
                return True
        except mysql.connector.Error as err:
            logging.error(f"Database error while validating credit note: {err}")
            return False

    def get_credit_note_by_id(self, credit_note_id):
        """
        جلب إشعار محدد وتفاصيله.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = "SELECT * FROM Client_Credit_Notes WHERE Credit_Note_ID = %s"
                cursor.execute(query, (credit_note_id,))
                credit_note = cursor.fetchone()
                
                if credit_note:
                    detail_query = """
                        SELECT d.*, p.Product_Name, b.Lot_Number 
                        FROM Client_Credit_Note_Details d
                        JOIN Products_Master p ON d.Product_ID = p.Product_ID
                        LEFT JOIN Inventory_Batches b ON d.Batch_ID = b.Batch_ID
                        WHERE d.Credit_Note_ID = %s
                    """
                    cursor.execute(detail_query, (credit_note_id,))
                    credit_note['details'] = cursor.fetchall()
                    
                return credit_note
        except mysql.connector.Error as e:
            logging.error(f"Error fetching credit note {credit_note_id}: {e}")
            raise
