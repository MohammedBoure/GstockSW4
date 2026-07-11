# database/client_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class ClientManager:
    """إدارة عمليات جدول العملاء (Clients)."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_client(self, name, contact_person=None, phone=None, email=None, address=None, city=None, tax_id=None, commercial_reg=None):
        """
        إضافة عميل جديد.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Clients 
                    (Client_Name, Contact_Person, Phone, Email, Address, City, Tax_ID_Number, Commercial_Reg_No) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (name, contact_person, phone, email, address, city, tax_id, commercial_reg)
                cursor.execute(query, params)
                client_id = cursor.lastrowid
                logging.info(f"Client '{name}' added with ID {client_id}.")
                return client_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Client '{name}' already exists (Duplicate entry).")
            else:
                logging.error(f"Database error while adding client '{name}': {err}")
            return None

    def update_client(self, client_id, **kwargs):
        """
        تحديث معلومات العميل بشكل ديناميكي.
        الوسائط المتاحة: name, contact_person, phone, email, address, city, tax_id, commercial_reg
        """
        field_map = {
            'name': 'Client_Name',
            'contact_person': 'Contact_Person',
            'phone': 'Phone',
            'email': 'Email',
            'address': 'Address',
            'city': 'City',
            'tax_id': 'Tax_ID_Number',
            'commercial_reg': 'Commercial_Reg_No'
        }
        
        updates = []
        params = []
        
        for kw, db_field in field_map.items():
            if kw in kwargs and kwargs[kw] is not None:
                updates.append(f"{db_field} = %s")
                params.append(kwargs[kw])
                
        if not updates:
            logging.warning(f"No fields provided for client update (ID: {client_id}).")
            return False

        params.append(client_id)
        query = f"UPDATE Clients SET {', '.join(updates)} WHERE Client_ID = %s AND Deleted_At IS NULL"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                if cursor.rowcount > 0:
                    logging.info(f"Client {client_id} updated successfully.")
                    return True
                logging.warning(f"No active client found with ID {client_id} for update.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating client {client_id}: {e}")
            raise

    def get_all_clients(self, include_deleted=False):
        """
        جلب جميع العملاء.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = "SELECT * FROM Clients"
                if not include_deleted:
                    query += " WHERE Deleted_At IS NULL"
                query += " ORDER BY Client_Name"
                
                cursor.execute(query)
                clients = cursor.fetchall()
                logging.info(f"Fetched {len(clients)} clients.")
                return clients
        except mysql.connector.Error as e:
            logging.error(f"Error fetching clients: {e}")
            raise

    def get_client_by_id(self, client_id):
        """
        جلب عميل محدد باستخدام ID.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Clients WHERE Client_ID = %s"
                cursor.execute(query, (client_id,))
                client = cursor.fetchone()
                return client
        except mysql.connector.Error as e:
            logging.error(f"Error fetching client {client_id}: {e}")
            raise

    def soft_delete_client(self, client_id):
        """
        حذف منطقي (Soft Delete) لعميل.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # التحقق مما إذا كان العميل مرتبطاً بفواتير
                cursor.execute("SELECT COUNT(*) FROM Sales_Invoices WHERE Client_ID = %s", (client_id,))
                if cursor.fetchone()[0] > 0:
                    logging.error(f"Cannot soft delete client {client_id}. They have associated sales invoices.")
                    return False
                
                query = "UPDATE Clients SET Deleted_At = %s WHERE Client_ID = %s AND Deleted_At IS NULL"
                params = (datetime.now(), client_id)
                cursor.execute(query, params)
                
                if cursor.rowcount > 0:
                    logging.info(f"Client {client_id} soft deleted successfully.")
                    return True
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while soft deleting client {client_id}: {e}")
            return False
