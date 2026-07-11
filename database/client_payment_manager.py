# database/client_payment_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class ClientPaymentManager:
    """إدارة عمليات مدفوعات العملاء (Client Payments)."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_payment(self, client_id, payment_date, amount, payment_method='Espèce', reference=None, notes=None, invoice_id=None, user_id=None):
        """
        إضافة دفعة مالية جديدة من عميل.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Client_Payments 
                    (Client_ID, Invoice_ID, Payment_Date, Amount, Payment_Method, Reference, Notes, Created_By) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (client_id, invoice_id, payment_date, amount, payment_method, reference, notes, user_id)
                cursor.execute(query, params)
                payment_id = cursor.lastrowid
                logging.info(f"Payment of {amount} added for Client {client_id} (ID: {payment_id}).")
                
                # إذا كانت الدفعة مرتبطة بفاتورة محددة، يمكن التحقق من اكتمال الدفع وتحديث حالة الفاتورة
                if invoice_id:
                    self._check_and_update_invoice_status(cursor, invoice_id)
                    
                return payment_id
        except mysql.connector.Error as err:
            logging.error(f"Database error while adding payment: {err}")
            return None

    def _check_and_update_invoice_status(self, cursor, invoice_id):
        """
        التحقق من إجمالي المدفوعات لفاتورة محددة وتحديث حالتها إلى Paid إذا تم سدادها بالكامل.
        """
        try:
            # إجمالي الفاتورة
            cursor.execute("SELECT Total_Amount_TTC, Status FROM Sales_Invoices WHERE Invoice_ID = %s", (invoice_id,))
            invoice_data = cursor.fetchone()
            if not invoice_data:
                return
            
            total_ttc, current_status = invoice_data
            if current_status == 'Paid':
                return
                
            # إجمالي المدفوعات للفاتورة
            cursor.execute("SELECT SUM(Amount) FROM Client_Payments WHERE Invoice_ID = %s", (invoice_id,))
            total_paid = cursor.fetchone()[0] or 0.00
            
            if total_paid >= total_ttc:
                cursor.execute("UPDATE Sales_Invoices SET Status = 'Paid' WHERE Invoice_ID = %s", (invoice_id,))
                logging.info(f"Invoice {invoice_id} status auto-updated to Paid.")
        except mysql.connector.Error as e:
            logging.error(f"Error checking invoice payment status: {e}")

    def get_payments_by_client(self, client_id):
        """
        جلب جميع المدفوعات الخاصة بعميل محدد.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Client_Payments WHERE Client_ID = %s ORDER BY Payment_Date DESC"
                cursor.execute(query, (client_id,))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching payments for client {client_id}: {e}")
            raise

    def get_all_payments(self):
        """
        جلب جميع المدفوعات لجميع العملاء.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT p.*, c.Client_Name 
                    FROM Client_Payments p
                    JOIN Clients c ON p.Client_ID = c.Client_ID
                    ORDER BY p.Payment_Date DESC, p.Payment_ID DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching all payments: {e}")
            raise
