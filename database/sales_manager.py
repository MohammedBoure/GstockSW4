# database/sales_manager.py

import mysql.connector
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from .system_logger import active_user_id, log_methods
from .stock_movement_log_manager import StockMovementLogManager

@log_methods()
class SalesManager:
    """إدارة فواتير المبيعات وتفاصيلها (Sales Invoices & Details)."""

    def __init__(self, db_instance):
        self.db = db_instance
        self.stock_movement_log = StockMovementLogManager(db_instance)
        self._ensure_sales_pos_schema()

    def _ensure_sales_pos_schema(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS POS_Terminals (
                Terminal_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Terminal_Code VARCHAR(100) NOT NULL UNIQUE,
                Terminal_Name VARCHAR(150) NOT NULL,
                Is_Active BOOLEAN DEFAULT TRUE,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Cash_Sessions (
                Cash_Session_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Session_No VARCHAR(100) NOT NULL UNIQUE,
                Terminal_ID INT UNSIGNED NOT NULL,
                Opened_By INT UNSIGNED NULL,
                Closed_By INT UNSIGNED NULL,
                Status ENUM('Open', 'Closed', 'Cancelled') NOT NULL DEFAULT 'Open',
                Opening_Amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Expected_Cash DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Expected_Card DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Expected_Transfer DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Counted_Cash DECIMAL(15, 2) NULL,
                Cash_Difference DECIMAL(15, 2) NULL,
                Notes TEXT NULL,
                Opened_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                Closed_At DATETIME NULL,
                Next_Invoice_Seq INT UNSIGNED NOT NULL DEFAULT 1,
                FOREIGN KEY (Terminal_ID) REFERENCES POS_Terminals(Terminal_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Opened_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
                FOREIGN KEY (Closed_By) REFERENCES Users(User_ID) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS Sales_Invoice_Sequences (
                Year_Num INT UNSIGNED NOT NULL PRIMARY KEY,
                Next_Seq INT UNSIGNED NOT NULL DEFAULT 1,
                Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            "ALTER TABLE Sales_Invoices ADD COLUMN Invoice_No VARCHAR(100) NULL;",
            "ALTER TABLE Sales_Invoices ADD COLUMN Terminal_ID INT UNSIGNED NULL;",
            "ALTER TABLE Sales_Invoices ADD COLUMN Cash_Session_ID BIGINT UNSIGNED NULL;",
            "ALTER TABLE Sales_Invoices ADD COLUMN Sale_UUID VARCHAR(64) NULL;",
            "ALTER TABLE Sales_Invoices ADD COLUMN Payment_Method ENUM('Cash', 'Card', 'Transfer', 'Versement', 'Other') DEFAULT 'Cash';",
            "CREATE UNIQUE INDEX uq_sales_invoice_no ON Sales_Invoices(Invoice_No);",
            "CREATE UNIQUE INDEX uq_sales_sale_uuid ON Sales_Invoices(Sale_UUID);",
            "CREATE INDEX idx_sales_terminal ON Sales_Invoices(Terminal_ID);",
            "CREATE INDEX idx_sales_cash_session ON Sales_Invoices(Cash_Session_ID);",
            "CREATE INDEX idx_sales_invoice_sequences_updated ON Sales_Invoice_Sequences(Updated_At);",
            "ALTER TABLE Sales_Invoices ADD CONSTRAINT fk_sales_terminal FOREIGN KEY (Terminal_ID) REFERENCES POS_Terminals(Terminal_ID) ON DELETE SET NULL;",
            "ALTER TABLE Sales_Invoices ADD CONSTRAINT fk_sales_cash_session FOREIGN KEY (Cash_Session_ID) REFERENCES POS_Cash_Sessions(Cash_Session_ID) ON DELETE SET NULL;",
        ]
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                for query in queries:
                    try:
                        cursor.execute(query)
                    except mysql.connector.Error as err:
                        if err.errno in (1060, 1061, 1826):
                            continue
                        logging.warning(f"Sales POS schema warning: {err}")
        except Exception as e:
            logging.error(f"Sales POS schema check failed: {e}", exc_info=True)

    def _invoice_year_from_date(self, invoice_date):
        try:
            return int(datetime.strptime(str(invoice_date), "%Y-%m-%d").year)
        except Exception:
            try:
                return int(str(invoice_date)[:4])
            except Exception:
                return datetime.now().year

    def _next_invoice_no(self, cursor, invoice_date):
        year_num = self._invoice_year_from_date(invoice_date)
        cursor.execute(
            """
            SELECT MAX(CAST(SUBSTRING_INDEX(Invoice_No, '/', -1) AS UNSIGNED)) AS MaxSeq
            FROM Sales_Invoices
            WHERE Invoice_No LIKE %s
            """,
            (f"{year_num}/%",),
        )
        row = cursor.fetchone() or {}
        next_seq = int(row.get('MaxSeq') or 0) + 1
        cursor.execute(
            """
            INSERT INTO Sales_Invoice_Sequences (Year_Num, Next_Seq)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE Year_Num = Year_Num
            """,
            (year_num, next_seq),
        )
        cursor.execute(
            "SELECT Next_Seq FROM Sales_Invoice_Sequences WHERE Year_Num = %s FOR UPDATE",
            (year_num,),
        )
        seq_row = cursor.fetchone() or {}
        seq = int(seq_row.get('Next_Seq') or 1)
        cursor.execute(
            "UPDATE Sales_Invoice_Sequences SET Next_Seq = %s WHERE Year_Num = %s",
            (seq + 1, year_num),
        )
        return f"{year_num}/{seq:04d}"

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

    def create_validated_sale(
        self, client_id, invoice_date, cart_items, terminal_id, cash_session_id,
        payment_method='Cash', user_id=None, request_id=None, notes=None
    ):
        """
        Create a validated sale atomically: invoice, details, stock deduction and
        stock movement logs are committed together. Returns (success, payload).
        """
        request_id = request_id or str(uuid.uuid4())
        valid_payment_methods = {'Cash', 'Card', 'Transfer', 'Versement', 'Other'}
        if payment_method not in valid_payment_methods:
            payment_method = 'Cash'
        if not terminal_id or not cash_session_id:
            return False, {"message": "Aucune caisse ouverte pour cette vente."}
        if not cart_items:
            return False, {"message": "Le panier est vide."}

        normalized_items = []
        batch_totals = {}
        try:
            for raw in cart_items:
                batch_id = int(raw['batch_id'])
                qty = Decimal(str(raw['qty_sold']))
                if qty <= 0:
                    return False, {"message": "Quantite invalide dans le panier."}
                item = {
                    "product_id": int(raw['product_id']),
                    "batch_id": batch_id,
                    "qty_sold": qty,
                    "unit_price_ht": Decimal(str(raw.get('unit_price_ht') or 0)),
                    "discount_percent": Decimal(str(raw.get('discount_percent') or 0)),
                    "tva_percent": Decimal(str(raw.get('tva_percent') or 0)),
                }
                normalized_items.append(item)
                batch_totals[batch_id] = batch_totals.get(batch_id, Decimal('0')) + qty
        except (KeyError, ValueError, TypeError) as e:
            return False, {"message": f"Panier invalide: {e}"}

        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT Invoice_ID, Invoice_No
                FROM Sales_Invoices
                WHERE Sale_UUID = %s
                LIMIT 1
                """,
                (request_id,),
            )
            existing = cursor.fetchone()
            if existing:
                conn.commit()
                return True, {
                    "invoice_id": existing['Invoice_ID'],
                    "invoice_no": existing.get('Invoice_No') or f"#{existing['Invoice_ID']}",
                    "duplicate": True,
                }

            cursor.execute(
                """
                SELECT s.*, t.Terminal_Code
                FROM POS_Cash_Sessions s
                JOIN POS_Terminals t ON s.Terminal_ID = t.Terminal_ID
                WHERE s.Cash_Session_ID = %s
                  AND s.Terminal_ID = %s
                  AND s.Status = 'Open'
                FOR UPDATE
                """,
                (cash_session_id, terminal_id),
            )
            session = cursor.fetchone()
            if not session:
                conn.rollback()
                return False, {"message": "La session de caisse est fermee ou introuvable."}

            locked_batches = {}
            for batch_id in sorted(batch_totals):
                cursor.execute(
                    """
                    SELECT b.Batch_ID, b.Product_ID, b.Quantity_Current, b.Status, p.Stock_Unit
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Batch_ID = %s
                    FOR UPDATE
                    """,
                    (batch_id,),
                )
                batch = cursor.fetchone()
                needed = batch_totals[batch_id]
                if not batch:
                    conn.rollback()
                    return False, {"message": f"Lot introuvable: {batch_id}"}
                available = Decimal(str(batch.get('Quantity_Current') or 0))
                if available < needed:
                    conn.rollback()
                    return False, {
                        "message": f"Stock insuffisant pour le lot {batch_id}. Disponible: {available}, demande: {needed}"
                    }
                locked_batches[batch_id] = batch

            invoice_no = self._next_invoice_no(cursor, invoice_date)

            cursor.execute(
                """
                INSERT INTO Sales_Invoices
                (Invoice_No, Client_ID, Invoice_Date, Status, Notes, Created_By,
                 Terminal_ID, Cash_Session_ID, Sale_UUID, Payment_Method)
                VALUES (%s, %s, %s, 'Validated', %s, %s, %s, %s, %s, %s)
                """,
                (
                    invoice_no, client_id, invoice_date, notes, user_id,
                    terminal_id, cash_session_id, request_id, payment_method,
                ),
            )
            invoice_id = cursor.lastrowid

            for item in normalized_items:
                line_total_ht = item['qty_sold'] * item['unit_price_ht'] * (
                    Decimal('1') - (item['discount_percent'] / Decimal('100'))
                )
                line_total_ttc = line_total_ht * (Decimal('1') + (item['tva_percent'] / Decimal('100')))
                cursor.execute(
                    """
                    INSERT INTO Sales_Details
                    (Invoice_ID, Product_ID, Batch_ID, Qty_Sold, Unit_Price_HT,
                     Discount_Percent, TVA_Percent, Line_Total_HT, Line_Total_TTC)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invoice_id, item['product_id'], item['batch_id'], item['qty_sold'],
                        item['unit_price_ht'], item['discount_percent'], item['tva_percent'],
                        line_total_ht, line_total_ttc,
                    ),
                )

            for batch_id, qty_needed in batch_totals.items():
                batch = locked_batches[batch_id]
                new_qty = Decimal(str(batch.get('Quantity_Current') or 0)) - qty_needed
                cursor.execute(
                    """
                    UPDATE Inventory_Batches
                    SET Quantity_Current = %s,
                        Status = CASE
                            WHEN %s <= 0 THEN 'Depleted'
                            WHEN Status = 'Depleted' AND %s > 0 THEN 'Available'
                            ELSE Status
                        END
                    WHERE Batch_ID = %s
                    """,
                    (new_qty, new_qty, new_qty, batch_id),
                )
                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=batch['Product_ID'],
                    movement_type='Sale',
                    qty_change=-qty_needed,
                    unit_used=batch.get('Stock_Unit') or 'Unit',
                    batch_id=batch_id,
                    user_id=user_id,
                    notes=f"Vente {invoice_no}",
                    external_cursor=cursor,
                )
                if not movement_id:
                    conn.rollback()
                    return False, {"message": "Echec de journalisation du mouvement de stock."}

            self._update_invoice_totals(cursor, invoice_id)
            conn.commit()
            return True, {
                "invoice_id": invoice_id,
                "invoice_no": invoice_no,
                "request_id": request_id,
            }
        except mysql.connector.Error as err:
            if conn:
                conn.rollback()
            if getattr(err, 'errno', None) == 1062:
                try:
                    with self.db.get_db_connection() as lookup_conn:
                        lookup = lookup_conn.cursor(dictionary=True)
                        lookup.execute(
                            "SELECT Invoice_ID, Invoice_No FROM Sales_Invoices WHERE Sale_UUID = %s",
                            (request_id,),
                        )
                        existing = lookup.fetchone()
                        if existing:
                            return True, {
                                "invoice_id": existing['Invoice_ID'],
                                "invoice_no": existing.get('Invoice_No') or f"#{existing['Invoice_ID']}",
                                "duplicate": True,
                            }
                except Exception:
                    pass
            logging.error(f"Atomic sale error: {err}", exc_info=True)
            return False, {"message": str(err)}
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Atomic sale error: {e}", exc_info=True)
            return False, {"message": str(e)}
        finally:
            if conn and conn.is_connected():
                conn.close()

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

    def _invoice_allows_edit(self, cursor, invoice_id, allow_closed_session_override=False):
        cursor.execute(
            """
            SELECT i.Invoice_ID, i.Status, i.Cash_Session_ID, s.Status AS Cash_Session_Status
            FROM Sales_Invoices i
            LEFT JOIN POS_Cash_Sessions s ON i.Cash_Session_ID = s.Cash_Session_ID
            WHERE i.Invoice_ID = %s
            FOR UPDATE
            """,
            (invoice_id,),
        )
        invoice = cursor.fetchone()
        if not invoice:
            return False, "Facture introuvable.", None
        if invoice.get('Status') == 'Cancelled':
            return False, "Facture deja annulee.", invoice
        if invoice.get('Cash_Session_ID') and invoice.get('Cash_Session_Status') != 'Open' and not allow_closed_session_override:
            return False, "La session de caisse est fermee. Modification refusee.", invoice
        return True, "", invoice

    def cancel_invoice_atomic(self, invoice_id, user_id=None, reason=None, allow_closed_session_override=False):
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            allowed, msg, invoice = self._invoice_allows_edit(cursor, invoice_id, allow_closed_session_override)
            if not allowed:
                conn.rollback()
                return False

            cursor.execute(
                "SELECT Detail_ID, Product_ID, Batch_ID, Qty_Sold FROM Sales_Details WHERE Invoice_ID = %s",
                (invoice_id,),
            )
            details = cursor.fetchall()
            for detail in sorted(details, key=lambda d: int(d['Batch_ID'])):
                qty = Decimal(str(detail.get('Qty_Sold') or 0))
                if qty <= 0:
                    continue
                cursor.execute(
                    """
                    SELECT b.Batch_ID, b.Product_ID, b.Quantity_Current, p.Stock_Unit
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Batch_ID = %s
                    FOR UPDATE
                    """,
                    (detail['Batch_ID'],),
                )
                batch = cursor.fetchone()
                if not batch:
                    conn.rollback()
                    return False
                new_qty = Decimal(str(batch.get('Quantity_Current') or 0)) + qty
                cursor.execute(
                    """
                    UPDATE Inventory_Batches
                    SET Quantity_Current = %s,
                        Status = CASE WHEN %s > 0 AND Status = 'Depleted' THEN 'Available' ELSE Status END
                    WHERE Batch_ID = %s
                    """,
                    (new_qty, new_qty, detail['Batch_ID']),
                )
                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=detail['Product_ID'],
                    movement_type='Sale_Return',
                    qty_change=qty,
                    unit_used=batch.get('Stock_Unit') or 'Unit',
                    batch_id=detail['Batch_ID'],
                    user_id=user_id,
                    notes=reason or f"Annulation vente #{invoice_id}",
                    external_cursor=cursor,
                )
                if not movement_id:
                    conn.rollback()
                    return False

            cursor.execute(
                """
                UPDATE Sales_Invoices
                SET Status = 'Cancelled',
                    Total_Amount_HT = 0,
                    Total_Amount_TTC = 0,
                    Total_Discount = 0,
                    Total_TVA = 0,
                    Updated_At = NOW()
                WHERE Invoice_ID = %s
                """,
                (invoice_id,),
            )
            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Atomic cancel invoice error: {e}", exc_info=True)
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

    def update_invoice_detail_qty_atomic(self, detail_id, new_qty, user_id=None, allow_closed_session_override=False):
        conn = None
        try:
            new_qty = Decimal(str(new_qty))
            if new_qty <= 0:
                return self.remove_invoice_detail_atomic(detail_id, user_id, allow_closed_session_override)

            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT Invoice_ID FROM Sales_Details WHERE Detail_ID = %s",
                (detail_id,),
            )
            detail_ref = cursor.fetchone()
            if not detail_ref:
                conn.rollback()
                return False

            allowed, msg, invoice = self._invoice_allows_edit(cursor, detail_ref['Invoice_ID'], allow_closed_session_override)
            if not allowed:
                conn.rollback()
                return False
            cursor.execute(
                "SELECT * FROM Sales_Details WHERE Detail_ID = %s FOR UPDATE",
                (detail_id,),
            )
            detail = cursor.fetchone()
            if not detail:
                conn.rollback()
                return False

            old_qty = Decimal(str(detail.get('Qty_Sold') or 0))
            diff = new_qty - old_qty
            cursor.execute(
                """
                SELECT b.Batch_ID, b.Product_ID, b.Quantity_Current, p.Stock_Unit
                FROM Inventory_Batches b
                JOIN Products_Master p ON b.Product_ID = p.Product_ID
                WHERE b.Batch_ID = %s
                FOR UPDATE
                """,
                (detail['Batch_ID'],),
            )
            batch = cursor.fetchone()
            if not batch:
                conn.rollback()
                return False
            current_qty = Decimal(str(batch.get('Quantity_Current') or 0))
            if diff > 0 and current_qty < diff:
                conn.rollback()
                return False

            new_stock = current_qty - diff
            cursor.execute(
                """
                UPDATE Inventory_Batches
                SET Quantity_Current = %s,
                    Status = CASE
                        WHEN %s <= 0 THEN 'Depleted'
                        WHEN Status = 'Depleted' AND %s > 0 THEN 'Available'
                        ELSE Status
                    END
                WHERE Batch_ID = %s
                """,
                (new_stock, new_stock, new_stock, detail['Batch_ID']),
            )
            if diff != 0:
                movement_type = 'Sale' if diff > 0 else 'Sale_Return'
                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=detail['Product_ID'],
                    movement_type=movement_type,
                    qty_change=-diff,
                    unit_used=batch.get('Stock_Unit') or 'Unit',
                    batch_id=detail['Batch_ID'],
                    user_id=user_id,
                    notes=f"Modification quantite facture #{detail['Invoice_ID']}",
                    external_cursor=cursor,
                )
                if not movement_id:
                    conn.rollback()
                    return False

            unit_price = Decimal(str(detail.get('Unit_Price_HT') or 0))
            discount = Decimal(str(detail.get('Discount_Percent') or 0))
            tva = Decimal(str(detail.get('TVA_Percent') or 0))
            line_total_ht = new_qty * unit_price * (Decimal('1') - discount / Decimal('100'))
            line_total_ttc = line_total_ht * (Decimal('1') + tva / Decimal('100'))
            cursor.execute(
                """
                UPDATE Sales_Details
                SET Qty_Sold = %s, Line_Total_HT = %s, Line_Total_TTC = %s
                WHERE Detail_ID = %s
                """,
                (new_qty, line_total_ht, line_total_ttc, detail_id),
            )
            self._update_invoice_totals(cursor, detail['Invoice_ID'])
            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Atomic update invoice detail error: {e}", exc_info=True)
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

    def remove_invoice_detail_atomic(self, detail_id, user_id=None, allow_closed_session_override=False):
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT Invoice_ID FROM Sales_Details WHERE Detail_ID = %s",
                (detail_id,),
            )
            detail_ref = cursor.fetchone()
            if not detail_ref:
                conn.rollback()
                return False
            allowed, msg, invoice = self._invoice_allows_edit(cursor, detail_ref['Invoice_ID'], allow_closed_session_override)
            if not allowed:
                conn.rollback()
                return False
            cursor.execute(
                "SELECT * FROM Sales_Details WHERE Detail_ID = %s FOR UPDATE",
                (detail_id,),
            )
            detail = cursor.fetchone()
            if not detail:
                conn.rollback()
                return False

            qty = Decimal(str(detail.get('Qty_Sold') or 0))
            cursor.execute(
                """
                SELECT b.Batch_ID, b.Product_ID, b.Quantity_Current, p.Stock_Unit
                FROM Inventory_Batches b
                JOIN Products_Master p ON b.Product_ID = p.Product_ID
                WHERE b.Batch_ID = %s
                FOR UPDATE
                """,
                (detail['Batch_ID'],),
            )
            batch = cursor.fetchone()
            if not batch:
                conn.rollback()
                return False
            new_stock = Decimal(str(batch.get('Quantity_Current') or 0)) + qty
            cursor.execute(
                """
                UPDATE Inventory_Batches
                SET Quantity_Current = %s,
                    Status = CASE WHEN %s > 0 AND Status = 'Depleted' THEN 'Available' ELSE Status END
                WHERE Batch_ID = %s
                """,
                (new_stock, new_stock, detail['Batch_ID']),
            )
            movement_id = self.stock_movement_log.create_movement_log(
                product_id=detail['Product_ID'],
                movement_type='Sale_Return',
                qty_change=qty,
                unit_used=batch.get('Stock_Unit') or 'Unit',
                batch_id=detail['Batch_ID'],
                user_id=user_id,
                notes=f"Suppression ligne facture #{detail['Invoice_ID']}",
                external_cursor=cursor,
            )
            if not movement_id:
                conn.rollback()
                return False
            cursor.execute("DELETE FROM Sales_Details WHERE Detail_ID = %s", (detail_id,))
            self._update_invoice_totals(cursor, detail['Invoice_ID'])
            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Atomic remove invoice detail error: {e}", exc_info=True)
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

    def remove_invoice_detail(self, detail_id, batch_manager=None, user_id=None):
        return self.remove_invoice_detail_atomic(detail_id, user_id=user_id or active_user_id.get())
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
        return self.cancel_invoice_atomic(invoice_id, user_id=user_id or active_user_id.get())
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
        return self.update_invoice_detail_qty_atomic(detail_id, new_qty, user_id=user_id or active_user_id.get())
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
                        i.Invoice_ID, i.Invoice_No, i.Invoice_Date, i.Status, i.Total_Amount_HT, i.Total_Amount_TTC,
                        i.Total_Discount, i.Total_TVA, i.Payment_Method, i.Terminal_ID, i.Cash_Session_ID, i.Created_By,
                        t.Terminal_Name, s.Session_No,
                        c.Client_Name,
                        COALESCE(u.Full_Name, u.Username) AS User_Name,
                        SUM(sd.Line_Total_HT - (sd.Qty_Sold * b.Unit_Price_Received)) AS Total_Profit
                    FROM Sales_Invoices i
                    LEFT JOIN Clients c ON i.Client_ID = c.Client_ID
                    LEFT JOIN POS_Terminals t ON i.Terminal_ID = t.Terminal_ID
                    LEFT JOIN POS_Cash_Sessions s ON i.Cash_Session_ID = s.Cash_Session_ID
                    LEFT JOIN Users u ON i.Created_By = u.User_ID
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

    def get_sales_operations_history(self, start_date=None, end_date=None, client_id=None):
        rows = []
        invoices = self.get_sales_with_profit(start_date, end_date, client_id)
        for inv in invoices:
            inv['Row_Type'] = 'Sale'
            inv['Event_Date'] = inv.get('Invoice_Date')
            inv['Operation_Label'] = 'Vente'
            inv['Amount_Entered'] = None
            inv['Caisse_Label'] = inv.get('Terminal_Name') or "-"
            rows.append(inv)

        if client_id:
            return rows

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT
                        s.Cash_Session_ID, s.Session_No, s.Status,
                        s.Opening_Amount, s.Expected_Cash, s.Expected_Card, s.Expected_Transfer,
                        s.Counted_Cash, s.Cash_Difference, s.Opened_At, s.Closed_At,
                        COALESCE(tot.Expected_Total, 0) AS Expected_Total,
                        t.Terminal_Name, t.Terminal_Code,
                        COALESCE(open_user.Full_Name, open_user.Username) AS Opened_By_Name,
                        COALESCE(close_user.Full_Name, close_user.Username) AS Closed_By_Name
                    FROM POS_Cash_Sessions s
                    LEFT JOIN POS_Terminals t ON s.Terminal_ID = t.Terminal_ID
                    LEFT JOIN Users open_user ON s.Opened_By = open_user.User_ID
                    LEFT JOIN Users close_user ON s.Closed_By = close_user.User_ID
                    LEFT JOIN (
                        SELECT Cash_Session_ID, SUM(Total_Amount_TTC) AS Expected_Total
                        FROM Sales_Invoices
                        WHERE Status <> 'Cancelled'
                        GROUP BY Cash_Session_ID
                    ) tot ON s.Cash_Session_ID = tot.Cash_Session_ID
                    WHERE 1=1
                """
                params = []
                if start_date:
                    query += " AND (DATE(s.Opened_At) >= %s OR DATE(s.Closed_At) >= %s)"
                    params.extend([start_date, start_date])
                if end_date:
                    query += " AND (DATE(s.Opened_At) <= %s OR DATE(s.Closed_At) <= %s)"
                    params.extend([end_date, end_date])
                cursor.execute(query, tuple(params))
                sessions = cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching sales operation history: {e}")
            sessions = []

        def event_in_range(value):
            if not value:
                return False
            date_text = str(value)[:10]
            if start_date and date_text < str(start_date):
                return False
            if end_date and date_text > str(end_date):
                return False
            return True

        for session in sessions:
            caisse_label = session.get('Terminal_Name') or session.get('Terminal_Code') or "-"
            if event_in_range(session.get('Opened_At')):
                rows.append({
                    'Row_Type': 'Cash_Open',
                    'Operation_ID': f"OPEN-{session['Cash_Session_ID']}",
                    'Invoice_No': session.get('Session_No'),
                    'Invoice_ID': None,
                    'Invoice_Date': session.get('Opened_At'),
                    'Event_Date': session.get('Opened_At'),
                    'Operation_Label': 'Ouverture caisse',
                    'Client_Name': f"Session {session.get('Session_No')}",
                    'Status': 'Open',
                    'Total_Amount_HT': 0,
                    'Total_Amount_TTC': 0,
                    'Total_Profit': 0,
                    'Payment_Method': '-',
                    'Terminal_Name': caisse_label,
                    'Caisse_Label': caisse_label,
                    'Session_No': session.get('Session_No'),
                    'User_Name': session.get('Opened_By_Name') or "-",
                    'Amount_Entered': session.get('Opening_Amount'),
                    'Opening_Amount': session.get('Opening_Amount'),
                    'Counted_Cash': None,
                    'Cash_Difference': None,
                })
            if event_in_range(session.get('Closed_At')):
                expected_total = session.get('Expected_Total') or 0
                rows.append({
                    'Row_Type': 'Cash_Close',
                    'Operation_ID': f"CLOSE-{session['Cash_Session_ID']}",
                    'Invoice_No': session.get('Session_No'),
                    'Invoice_ID': None,
                    'Invoice_Date': session.get('Closed_At'),
                    'Event_Date': session.get('Closed_At'),
                    'Operation_Label': 'Cloture caisse',
                    'Client_Name': (
                        f"Comptage cash: {session.get('Counted_Cash') or 0} | "
                        f"Ecart: {session.get('Cash_Difference') or 0}"
                    ),
                    'Status': 'Closed',
                    'Total_Amount_HT': 0,
                    'Total_Amount_TTC': expected_total,
                    'Total_Profit': 0,
                    'Payment_Method': '-',
                    'Terminal_Name': caisse_label,
                    'Caisse_Label': caisse_label,
                    'Session_No': session.get('Session_No'),
                    'User_Name': session.get('Closed_By_Name') or "-",
                    'Amount_Entered': session.get('Counted_Cash'),
                    'Opening_Amount': session.get('Opening_Amount'),
                    'Counted_Cash': session.get('Counted_Cash'),
                    'Cash_Difference': session.get('Cash_Difference'),
                })

        def sort_key(row):
            value = row.get('Event_Date') or row.get('Invoice_Date') or ""
            return str(value)

        rows.sort(key=sort_key, reverse=True)
        return rows

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
