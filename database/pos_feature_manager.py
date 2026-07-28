"""Extended POS persistence and business helpers.

The original GstockSW4 sales tables remain the source of truth for invoices,
details and stock.  This manager adds append-only POS capabilities around that
model and deliberately keeps every migration idempotent so older installations
can be upgraded without rewriting existing sales.
"""

import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from .stock_movement_log_manager import StockMovementLogManager

import mysql.connector


MONEY_QUANTUM = Decimal("0.01")
PAYMENT_METHODS = ("Cash", "Card", "Transfer", "Versement", "Other", "Credit")


def money(value):
    return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class POSFeatureManager:
    """Persistence services for multi-tender POS and related workflows."""

    def __init__(self, db_instance):
        self.db = db_instance
        self.stock_movement_log = StockMovementLogManager(db_instance)
        self.ensure_schema()

    def ensure_schema(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS POS_Sale_Payments (
                Payment_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Invoice_ID BIGINT UNSIGNED NOT NULL,
                Payment_Line_No INT UNSIGNED NOT NULL,
                Payment_Method ENUM('Cash', 'Card', 'Transfer', 'Versement', 'Other', 'Credit') NOT NULL,
                Amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Tendered_Amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Change_Amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Reference VARCHAR(150) NULL,
                Payment_UUID VARCHAR(80) NOT NULL UNIQUE,
                Created_By INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Invoice_ID) REFERENCES Sales_Invoices(Invoice_ID) ON DELETE CASCADE,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
                UNIQUE KEY uq_pos_sale_payment_line (Invoice_ID, Payment_Line_No)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Sale_Drafts (
                Draft_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Draft_Ref VARCHAR(100) NOT NULL UNIQUE,
                Draft_Type ENUM('Held', 'Quote') NOT NULL DEFAULT 'Held',
                Client_ID INT UNSIGNED NULL,
                Invoice_Date DATE NOT NULL,
                Cart_JSON LONGTEXT NOT NULL,
                Total_Amount_TTC DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Status ENUM('Open', 'Converted', 'Cancelled') NOT NULL DEFAULT 'Open',
                Expires_At DATE NULL,
                Converted_Invoice_ID BIGINT UNSIGNED NULL,
                Notes TEXT NULL,
                Created_By INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (Client_ID) REFERENCES Clients(Client_ID) ON DELETE SET NULL,
                FOREIGN KEY (Converted_Invoice_ID) REFERENCES Sales_Invoices(Invoice_ID) ON DELETE SET NULL,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Sale_Returns (
                Return_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Return_No VARCHAR(100) NOT NULL UNIQUE,
                Original_Invoice_ID BIGINT UNSIGNED NULL,
                Client_ID INT UNSIGNED NULL,
                Return_Date DATE NOT NULL,
                Return_Type ENUM('Return', 'Exchange') NOT NULL DEFAULT 'Return',
                Status ENUM('Draft', 'Validated', 'Cancelled') NOT NULL DEFAULT 'Draft',
                Refund_Method ENUM('Cash', 'Card', 'Transfer', 'Versement', 'Other', 'Credit') NULL,
                Refund_Amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Reason VARCHAR(255) NULL,
                Exchange_Invoice_ID BIGINT UNSIGNED NULL,
                Created_By INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (Original_Invoice_ID) REFERENCES Sales_Invoices(Invoice_ID) ON DELETE SET NULL,
                FOREIGN KEY (Client_ID) REFERENCES Clients(Client_ID) ON DELETE SET NULL,
                FOREIGN KEY (Exchange_Invoice_ID) REFERENCES Sales_Invoices(Invoice_ID) ON DELETE SET NULL,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Sale_Return_Details (
                Return_Detail_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Return_ID BIGINT UNSIGNED NOT NULL,
                Original_Detail_ID BIGINT UNSIGNED NULL,
                Product_ID INT UNSIGNED NOT NULL,
                Batch_ID BIGINT UNSIGNED NULL,
                Qty_Returned DECIMAL(10, 2) NOT NULL,
                Unit_Price_HT DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                TVA_Percent DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
                Line_Total_HT DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Line_Total_TTC DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                FOREIGN KEY (Return_ID) REFERENCES POS_Sale_Returns(Return_ID) ON DELETE CASCADE,
                FOREIGN KEY (Original_Detail_ID) REFERENCES Sales_Details(Detail_ID) ON DELETE SET NULL,
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
                FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Cash_Movements (
                Movement_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Cash_Session_ID BIGINT UNSIGNED NOT NULL,
                Movement_Type ENUM('Cash_In', 'Cash_Out', 'Refund') NOT NULL,
                Amount DECIMAL(15, 2) NOT NULL,
                Reason VARCHAR(255) NOT NULL,
                Reference VARCHAR(150) NULL,
                Created_By INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Cash_Session_ID) REFERENCES POS_Cash_Sessions(Cash_Session_ID) ON DELETE CASCADE,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Audit_Log (
                Audit_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Entity_Type VARCHAR(60) NOT NULL,
                Entity_ID BIGINT UNSIGNED NULL,
                Action VARCHAR(80) NOT NULL,
                Details TEXT NULL,
                User_ID INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (User_ID) REFERENCES Users(User_ID) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Promotions (
                Promotion_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Promotion_Code VARCHAR(80) NULL UNIQUE,
                Promotion_Name VARCHAR(150) NOT NULL,
                Promotion_Type ENUM('Percent', 'Fixed', 'BuyXGetY') NOT NULL DEFAULT 'Percent',
                Value DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Buy_Qty DECIMAL(10, 2) NULL,
                Get_Qty DECIMAL(10, 2) NULL,
                Min_Amount DECIMAL(15, 2) NULL,
                Starts_At DATE NULL,
                Ends_At DATE NULL,
                Priority INT NOT NULL DEFAULT 0,
                Is_Stackable BOOLEAN NOT NULL DEFAULT FALSE,
                Is_Active BOOLEAN NOT NULL DEFAULT TRUE,
                Created_By INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Promotion_Products (
                Promotion_ID BIGINT UNSIGNED NOT NULL,
                Product_ID INT UNSIGNED NOT NULL,
                PRIMARY KEY (Promotion_ID, Product_ID),
                FOREIGN KEY (Promotion_ID) REFERENCES POS_Promotions(Promotion_ID) ON DELETE CASCADE,
                FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Loyalty_Accounts (
                Loyalty_Account_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Client_ID INT UNSIGNED NOT NULL UNIQUE,
                Points_Balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Total_Earned DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Total_Redeemed DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
                Is_Active BOOLEAN NOT NULL DEFAULT TRUE,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (Client_ID) REFERENCES Clients(Client_ID) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS POS_Loyalty_Transactions (
                Loyalty_Transaction_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Loyalty_Account_ID BIGINT UNSIGNED NOT NULL,
                Invoice_ID BIGINT UNSIGNED NULL,
                Transaction_Type ENUM('Earn', 'Redeem', 'Adjust', 'Reverse') NOT NULL,
                Points DECIMAL(15, 2) NOT NULL,
                Notes VARCHAR(255) NULL,
                Created_By INT UNSIGNED NULL,
                Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Loyalty_Account_ID) REFERENCES POS_Loyalty_Accounts(Loyalty_Account_ID) ON DELETE CASCADE,
                FOREIGN KEY (Invoice_ID) REFERENCES Sales_Invoices(Invoice_ID) ON DELETE SET NULL,
                FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL
            )
            """,
            "ALTER TABLE Sales_Invoices MODIFY COLUMN Payment_Method ENUM('Cash', 'Card', 'Transfer', 'Versement', 'Other', 'Credit') DEFAULT 'Cash';",
            "ALTER TABLE Clients ADD COLUMN Credit_Limit DECIMAL(15, 2) NOT NULL DEFAULT 0.00;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Expected_Versement DECIMAL(15, 2) NOT NULL DEFAULT 0.00;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Expected_Other DECIMAL(15, 2) NOT NULL DEFAULT 0.00;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Expected_Credit DECIMAL(15, 2) NOT NULL DEFAULT 0.00;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Counted_Card DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Counted_Transfer DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Counted_Versement DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Counted_Other DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Counted_Credit DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Card_Difference DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Transfer_Difference DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Versement_Difference DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Other_Difference DECIMAL(15, 2) NULL;",
            "ALTER TABLE POS_Cash_Sessions ADD COLUMN Credit_Difference DECIMAL(15, 2) NULL;"
        ]
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                for query in queries:
                    try:
                        cursor.execute(query)
                    except mysql.connector.Error as err:
                        if err.errno not in (1050, 1060, 1061, 1091, 1826, 1831):
                            logging.warning("POS schema warning: %s", err)

                indexes = [
                    "CREATE INDEX idx_pos_payment_invoice ON POS_Sale_Payments(Invoice_ID);",
                    "CREATE INDEX idx_pos_payment_method ON POS_Sale_Payments(Payment_Method);",
                    "CREATE INDEX idx_pos_draft_status ON POS_Sale_Drafts(Status, Created_At);",
                    "CREATE INDEX idx_pos_return_invoice ON POS_Sale_Returns(Original_Invoice_ID);",
                    "CREATE INDEX idx_pos_return_status ON POS_Sale_Returns(Status, Return_Date);",
                    "CREATE INDEX idx_pos_cash_movement_session ON POS_Cash_Movements(Cash_Session_ID, Created_At);",
                    "CREATE INDEX idx_pos_audit_entity ON POS_Audit_Log(Entity_Type, Entity_ID, Created_At);",
                    "CREATE INDEX idx_pos_promotion_active_dates ON POS_Promotions(Is_Active, Starts_At, Ends_At);",
                    "CREATE INDEX idx_pos_loyalty_transaction_invoice ON POS_Loyalty_Transactions(Invoice_ID);",
                ]
                for query in indexes:
                    try:
                        cursor.execute(query)
                    except mysql.connector.Error as err:
                        if err.errno not in (1061, 1022):
                            logging.warning("POS index warning: %s", err)

                # Backfill only invoices that have no payment lines.  This is
                # deliberately insert-only and therefore safe for old data.
                cursor.execute(
                    """
                    INSERT INTO POS_Sale_Payments
                        (Invoice_ID, Payment_Line_No, Payment_Method, Amount,
                         Tendered_Amount, Change_Amount, Reference, Payment_UUID)
                    SELECT i.Invoice_ID, 1, i.Payment_Method, i.Total_Amount_TTC,
                           i.Total_Amount_TTC, 0, 'LEGACY_BACKFILL',
                           CONCAT('legacy:', i.Invoice_ID)
                    FROM Sales_Invoices i
                    LEFT JOIN POS_Sale_Payments p ON p.Invoice_ID = i.Invoice_ID
                    WHERE p.Payment_ID IS NULL
                      AND i.Status IN ('Validated', 'Paid')
                    """
                )
        except Exception as exc:
            logging.error("POS feature schema check failed: %s", exc, exc_info=True)

    @staticmethod
    def normalize_payment_lines(total, payment_lines, client_id=None):
        total = money(total)
        if total < 0:
            return False, [], "Montant total invalide."
        if not payment_lines:
            return False, [], "Aucun moyen de paiement fourni."

        normalized = []
        applied_total = Decimal("0.00")
        for raw in payment_lines:
            method = str(raw.get("method") or raw.get("Payment_Method") or "Cash")
            if method not in PAYMENT_METHODS:
                return False, [], f"Moyen de paiement invalide: {method}"
            amount = money(raw.get("amount") or raw.get("Amount"))
            tendered = money(raw.get("tendered") or raw.get("Tendered_Amount") or amount)
            if amount <= 0:
                return False, [], "Le montant d'un paiement doit être positif."
            if tendered < amount:
                return False, [], "Le montant remis est inférieur au montant à payer."
            if method == "Credit" and not client_id:
                return False, [], "Le paiement à crédit nécessite un client."
            change = money(tendered - amount) if method == "Cash" else Decimal("0.00")
            normalized.append({
                "method": method,
                "amount": amount,
                "tendered": tendered,
                "change": change,
                "reference": str(raw.get("reference") or raw.get("Reference") or "").strip() or None,
            })
            applied_total += amount

        if money(applied_total) != total:
            return False, [], f"Paiements incomplets: {money(applied_total)} / {total} DA"
        return True, normalized, ""

    def save_invoice_payments(self, invoice_id, payment_lines, user_id=None, request_id=None, cursor=None):
        own_connection = cursor is None
        conn = None
        try:
            if own_connection:
                conn = self.db.get_raw_connection()
                conn.start_transaction()
                cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT Total_Amount_TTC, Client_ID FROM Sales_Invoices WHERE Invoice_ID = %s", (invoice_id,))
            invoice = cursor.fetchone() or {}
            valid, normalized, error = self.normalize_payment_lines(
                invoice.get("Total_Amount_TTC"), payment_lines, invoice.get("Client_ID")
            )
            if not valid:
                if own_connection:
                    conn.rollback()
                return False, {"message": error}

            cursor.execute("SELECT Payment_ID FROM POS_Sale_Payments WHERE Invoice_ID = %s ORDER BY Payment_Line_No", (invoice_id,))
            if cursor.fetchall():
                if own_connection:
                    conn.commit()
                return True, {"payments": self.get_invoice_payments(invoice_id)}

            request_id = request_id or str(uuid.uuid4())
            for index, payment in enumerate(normalized, start=1):
                cursor.execute(
                    """
                    INSERT INTO POS_Sale_Payments
                        (Invoice_ID, Payment_Line_No, Payment_Method, Amount,
                         Tendered_Amount, Change_Amount, Reference, Payment_UUID, Created_By)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invoice_id, index, payment["method"], payment["amount"],
                        payment["tendered"], payment["change"], payment["reference"],
                        f"{request_id}:{index}", user_id,
                    ),
                )
            if own_connection:
                conn.commit()
            return True, {"payments": normalized}
        except Exception as exc:
            if own_connection and conn:
                conn.rollback()
            logging.error("Could not save POS payments: %s", exc, exc_info=True)
            return False, {"message": str(exc)}
        finally:
            if own_connection and conn and conn.is_connected():
                conn.close()

    def get_invoice_payments(self, invoice_id):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT p.*, COALESCE(u.Full_Name, u.Username) AS User_Name
                    FROM POS_Sale_Payments p
                    LEFT JOIN Users u ON u.User_ID = p.Created_By
                    WHERE p.Invoice_ID = %s
                    ORDER BY p.Payment_Line_No
                    """,
                    (invoice_id,),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Could not load POS payments: %s", exc, exc_info=True)
            return []

    @staticmethod
    def validate_credit_limit(cursor, client_id, credit_amount):
        amount = money(credit_amount)
        if amount <= 0:
            return True, {"Credit_Limit": Decimal("0.00"), "Credit_Balance": Decimal("0.00")}
        if not client_id:
            return False, {"message": "Le crédit nécessite un client."}
        cursor.execute("SELECT Credit_Limit FROM Clients WHERE Client_ID = %s FOR UPDATE", (client_id,))
        client = cursor.fetchone() or {}
        limit = money(client.get("Credit_Limit"))
        if limit <= 0:
            return True, {"Credit_Limit": limit, "Credit_Balance": Decimal("0.00"), "Available_Credit": None}
        cursor.execute(
            """
            SELECT COALESCE(SUM(p.Amount), 0) AS Credit_Sales
            FROM POS_Sale_Payments p
            JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
            WHERE i.Client_ID = %s
              AND i.Status IN ('Validated', 'Paid')
              AND p.Payment_Method = 'Credit'
            """,
            (client_id,),
        )
        credit_sales = money((cursor.fetchone() or {}).get("Credit_Sales"))
        cursor.execute("SELECT COALESCE(SUM(Amount), 0) AS Settled FROM Client_Payments WHERE Client_ID = %s", (client_id,))
        settled = money((cursor.fetchone() or {}).get("Settled"))
        balance = max(Decimal("0.00"), credit_sales - settled)
        available = max(Decimal("0.00"), limit - balance)
        if balance + amount > limit:
            return False, {
                "message": f"Limite de crédit dépassée. Disponible: {available:.2f} DA.",
                "Credit_Limit": limit,
                "Credit_Balance": balance,
                "Available_Credit": available,
            }
        return True, {
            "Credit_Limit": limit,
            "Credit_Balance": balance,
            "Available_Credit": available,
        }
    def get_client_credit_summary(self, client_id):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT Client_ID, Client_Name, Credit_Limit FROM Clients WHERE Client_ID = %s", (client_id,))
                client = cursor.fetchone() or {}
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(p.Amount), 0) AS Credit_Sales
                    FROM POS_Sale_Payments p
                    JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                    WHERE i.Client_ID = %s AND i.Status IN ('Validated', 'Paid') AND p.Payment_Method = 'Credit'
                    """,
                    (client_id,),
                )
                credit_sales = money((cursor.fetchone() or {}).get("Credit_Sales"))
                cursor.execute(
                    "SELECT COALESCE(SUM(Amount), 0) AS Settled FROM Client_Payments WHERE Client_ID = %s",
                    (client_id,),
                )
                settled = money((cursor.fetchone() or {}).get("Settled"))
                balance = max(Decimal("0.00"), credit_sales - settled)
                limit = money(client.get("Credit_Limit"))
                return {
                    "Client_ID": client_id,
                    "Client_Name": client.get("Client_Name"),
                    "Credit_Limit": limit,
                    "Credit_Balance": balance,
                    "Available_Credit": max(Decimal("0.00"), limit - balance) if limit else None,
                }
        except Exception as exc:
            logging.error("Could not load client credit summary: %s", exc, exc_info=True)
            return {"Client_ID": client_id, "Credit_Limit": Decimal("0.00"), "Credit_Balance": Decimal("0.00")}

    def save_draft(self, client_id, invoice_date, cart_items, total_ttc, draft_type="Held", draft_ref=None,
                   expires_at=None, notes=None, user_id=None):
        draft_ref = draft_ref or f"POS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        if draft_type not in {"Held", "Quote"}:
            draft_type = "Held"
        try:
            payload = json.dumps(cart_items, ensure_ascii=False, default=str)
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    INSERT INTO POS_Sale_Drafts
                        (Draft_Ref, Draft_Type, Client_ID, Invoice_Date, Cart_JSON,
                         Total_Amount_TTC, Expires_At, Notes, Created_By)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (draft_ref, draft_type, client_id, invoice_date, payload, money(total_ttc), expires_at, notes, user_id),
                )
                return cursor.lastrowid
        except Exception as exc:
            logging.error("Could not save POS draft: %s", exc, exc_info=True)
            return None

    def list_drafts(self, status="Open", draft_type=None):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT d.*, c.Client_Name, COALESCE(u.Full_Name, u.Username) AS User_Name
                    FROM POS_Sale_Drafts d
                    LEFT JOIN Clients c ON c.Client_ID = d.Client_ID
                    LEFT JOIN Users u ON u.User_ID = d.Created_By
                    WHERE d.Status = %s
                """
                params = [status]
                if draft_type:
                    query += " AND d.Draft_Type = %s"
                    params.append(draft_type)
                query += " ORDER BY d.Updated_At DESC, d.Draft_ID DESC"
                cursor.execute(query, tuple(params))
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Could not list POS drafts: %s", exc, exc_info=True)
            return []

    def get_draft(self, draft_id):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM POS_Sale_Drafts WHERE Draft_ID = %s", (draft_id,))
                row = cursor.fetchone()
                if row:
                    try:
                        row["cart_items"] = json.loads(row.get("Cart_JSON") or "[]")
                    except (TypeError, json.JSONDecodeError):
                        row["cart_items"] = []
                return row
        except Exception as exc:
            logging.error("Could not load POS draft: %s", exc, exc_info=True)
            return None

    def mark_draft_converted(self, draft_id, invoice_id, user_id=None):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE POS_Sale_Drafts
                    SET Status = 'Converted', Converted_Invoice_ID = %s, Updated_At = NOW()
                    WHERE Draft_ID = %s AND Status = 'Open'
                    """,
                    (invoice_id, draft_id),
                )
                changed = cursor.rowcount > 0
                if changed:
                    self.audit("POS_Sale_Draft", draft_id, "Converted", {"invoice_id": invoice_id}, user_id, cursor=cursor)
                return changed
        except Exception as exc:
            logging.error("Could not mark POS draft converted: %s", exc, exc_info=True)
            return False

    def cancel_draft(self, draft_id, user_id=None):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE POS_Sale_Drafts SET Status = 'Cancelled', Updated_At = NOW() WHERE Draft_ID = %s AND Status = 'Open'",
                    (draft_id,),
                )
                changed = cursor.rowcount > 0
                if changed:
                    self.audit("POS_Sale_Draft", draft_id, "Cancelled", None, user_id, cursor=cursor)
                return changed
        except Exception as exc:
            logging.error("Could not cancel POS draft: %s", exc, exc_info=True)
            return False

    def add_cash_movement(self, cash_session_id, movement_type, amount, reason, user_id=None, reference=None):
        if movement_type not in {"Cash_In", "Cash_Out", "Refund"} or money(amount) <= 0 or not str(reason).strip():
            return False
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO POS_Cash_Movements
                        (Cash_Session_ID, Movement_Type, Amount, Reason, Reference, Created_By)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (cash_session_id, movement_type, money(amount), str(reason).strip(), reference, user_id),
                )
                self.audit("POS_Cash_Session", cash_session_id, movement_type, {"amount": str(money(amount)), "reason": reason}, user_id, cursor=cursor)
                return cursor.lastrowid
        except Exception as exc:
            logging.error("Could not record cash movement: %s", exc, exc_info=True)
            return False

    def audit(self, entity_type, entity_id, action, details=None, user_id=None, cursor=None):
        payload = json.dumps(details, ensure_ascii=False, default=str) if details is not None else None
        if cursor is not None:
            cursor.execute(
                "INSERT INTO POS_Audit_Log (Entity_Type, Entity_ID, Action, Details, User_ID) VALUES (%s, %s, %s, %s, %s)",
                (entity_type, entity_id, action, payload, user_id),
            )
            return
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO POS_Audit_Log (Entity_Type, Entity_ID, Action, Details, User_ID) VALUES (%s, %s, %s, %s, %s)",
                    (entity_type, entity_id, action, payload, user_id),
                )
        except Exception as exc:
            logging.error("Could not write POS audit event: %s", exc, exc_info=True)

    def create_sale_return(self, original_invoice_id, return_items, return_type="Return", refund_method=None, reason=None, user_id=None):
        """Validate a partial/full return and restore its original stock atomically."""
        if not original_invoice_id or not return_items:
            return False, {"message": "La facture et les lignes du retour sont obligatoires."}
        if return_type not in {"Return", "Exchange"}:
            return_type = "Return"
        if refund_method and refund_method not in PAYMENT_METHODS:
            return False, {"message": "Moyen de remboursement invalide."}

        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM Sales_Invoices WHERE Invoice_ID = %s FOR UPDATE",
                (original_invoice_id,),
            )
            invoice = cursor.fetchone()
            if not invoice or invoice.get("Status") == "Cancelled":
                conn.rollback()
                return False, {"message": "Facture d'origine introuvable ou annulée."}

            return_no = f"RET-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            cursor.execute(
                """
                INSERT INTO POS_Sale_Returns
                    (Return_No, Original_Invoice_ID, Client_ID, Return_Date,
                     Return_Type, Status, Refund_Method, Reason, Created_By)
                VALUES (%s, %s, %s, %s, %s, 'Validated', %s, %s, %s)
                """,
                (
                    return_no, original_invoice_id, invoice.get("Client_ID"), date.today(),
                    return_type, refund_method, reason, user_id,
                ),
            )
            return_id = cursor.lastrowid
            refund_amount = Decimal("0.00")

            for raw in return_items:
                detail_id = int(raw.get("original_detail_id") or raw.get("Detail_ID"))
                qty = Decimal(str(raw.get("qty_returned") or raw.get("Qty_Returned") or 0))
                if qty <= 0:
                    raise ValueError("Quantité de retour invalide.")
                cursor.execute(
                    """
                    SELECT sd.*, b.Quantity_Current, b.Status AS Batch_Status, p.Stock_Unit
                    FROM Sales_Details sd
                    JOIN Inventory_Batches b ON b.Batch_ID = sd.Batch_ID
                    JOIN Products_Master p ON p.Product_ID = sd.Product_ID
                    WHERE sd.Detail_ID = %s AND sd.Invoice_ID = %s
                    FOR UPDATE
                    """,
                    (detail_id, original_invoice_id),
                )
                detail = cursor.fetchone()
                if not detail:
                    raise ValueError(f"Ligne de vente introuvable: {detail_id}")
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(rd.Qty_Returned), 0) AS Already_Returned
                    FROM POS_Sale_Return_Details rd
                    JOIN POS_Sale_Returns rh ON rh.Return_ID = rd.Return_ID
                    WHERE rd.Original_Detail_ID = %s AND rh.Status = 'Validated'
                    """,
                    (detail_id,),
                )
                already_returned = Decimal(str((cursor.fetchone() or {}).get("Already_Returned") or 0))
                sold_qty = Decimal(str(detail.get("Qty_Sold") or 0))
                if qty > sold_qty - already_returned:
                    raise ValueError(
                        f"Quantité retournée supérieure au disponible pour la ligne {detail_id}."
                    )

                unit_price = Decimal(str(detail.get("Unit_Price_HT") or 0))
                discount = Decimal(str(detail.get("Discount_Percent") or 0))
                tva = Decimal(str(detail.get("TVA_Percent") or 0))
                line_ht = (qty * unit_price * (Decimal("1") - discount / Decimal("100"))).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
                line_ttc = (line_ht * (Decimal("1") + tva / Decimal("100"))).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
                refund_amount += line_ttc

                cursor.execute(
                    """
                    INSERT INTO POS_Sale_Return_Details
                        (Return_ID, Original_Detail_ID, Product_ID, Batch_ID,
                         Qty_Returned, Unit_Price_HT, TVA_Percent, Line_Total_HT, Line_Total_TTC)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        return_id, detail_id, detail["Product_ID"], detail["Batch_ID"],
                        qty, unit_price, tva, line_ht, line_ttc,
                    ),
                )
                current_qty = Decimal(str(detail.get("Quantity_Current") or 0))
                new_qty = current_qty + qty
                cursor.execute(
                    """
                    UPDATE Inventory_Batches
                    SET Quantity_Current = %s,
                        Status = CASE WHEN %s > 0 THEN 'Available' ELSE Status END
                    WHERE Batch_ID = %s
                    """,
                    (new_qty, new_qty, detail["Batch_ID"]),
                )
                movement_id = self.stock_movement_log.create_movement_log(
                    product_id=detail["Product_ID"],
                    movement_type="Sale_Return",
                    qty_change=qty,
                    unit_used=detail.get("Stock_Unit") or "Unit",
                    batch_id=detail["Batch_ID"],
                    user_id=user_id,
                    notes=f"Retour {return_no}",
                    external_cursor=cursor,
                )
                if not movement_id:
                    raise ValueError("Échec de journalisation du retour de stock.")

            cursor.execute(
                "UPDATE POS_Sale_Returns SET Refund_Amount = %s, Updated_At = NOW() WHERE Return_ID = %s",
                (refund_amount, return_id),
            )
            if refund_method == "Cash" and invoice.get("Cash_Session_ID") and refund_amount > 0:
                cursor.execute(
                    """
                    INSERT INTO POS_Cash_Movements
                        (Cash_Session_ID, Movement_Type, Amount, Reason, Reference, Created_By)
                    VALUES (%s, 'Refund', %s, %s, %s, %s)
                    """,
                    (invoice["Cash_Session_ID"], refund_amount, reason or "Retour de vente", return_no, user_id),
                )
            self.audit(
                "POS_Sale_Return", return_id, "Validated",
                {"invoice_id": original_invoice_id, "refund": str(refund_amount), "type": return_type},
                user_id, cursor=cursor,
            )
            conn.commit()
            return True, {
                "return_id": return_id,
                "return_no": return_no,
                "refund_amount": refund_amount,
                "original_invoice_id": original_invoice_id,
            }
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Could not create POS sale return: %s", exc, exc_info=True)
            return False, {"message": str(exc)}
        finally:
            if conn and conn.is_connected():
                conn.close()

    def get_return_by_id(self, return_id):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM POS_Sale_Returns WHERE Return_ID = %s", (return_id,))
                header = cursor.fetchone()
                if header:
                    cursor.execute(
                        "SELECT * FROM POS_Sale_Return_Details WHERE Return_ID = %s ORDER BY Return_Detail_ID",
                        (return_id,),
                    )
                    header["details"] = cursor.fetchall() or []
                return header
        except Exception as exc:
            logging.error("Could not load POS return: %s", exc, exc_info=True)
            return None

    def list_returns(self, start_date=None, end_date=None, status=None, limit=100, offset=0):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT r.*, i.Invoice_No, c.Client_Name,
                           COALESCE(u.Full_Name, u.Username) AS User_Name
                    FROM POS_Sale_Returns r
                    LEFT JOIN Sales_Invoices i ON i.Invoice_ID = r.Original_Invoice_ID
                    LEFT JOIN Clients c ON c.Client_ID = r.Client_ID
                    LEFT JOIN Users u ON u.User_ID = r.Created_By
                    WHERE 1 = 1
                """
                params = []
                if start_date:
                    query += " AND r.Return_Date >= %s"
                    params.append(start_date)
                if end_date:
                    query += " AND r.Return_Date <= %s"
                    params.append(end_date)
                if status:
                    query += " AND r.Status = %s"
                    params.append(status)
                query += " ORDER BY r.Return_Date DESC, r.Return_ID DESC LIMIT %s OFFSET %s"
                params.extend([int(limit), int(offset)])
                cursor.execute(query, tuple(params))
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Could not list POS returns: %s", exc, exc_info=True)
            return []
    def evaluate_promotion(self, code, cart_items):
        """Return the deterministic discount for a coupon/code and cart."""
        promotions = self.get_active_promotions(code=str(code or "").strip())
        if not promotions:
            return False, {"message": "Promotion introuvable ou inactive."}
        promotion = promotions[0]
        product_ids = set(promotion.get("Product_IDs") or [])
        applicable = []
        for item in cart_items or []:
            product_id = item.get("product_id") or item.get("Product_ID")
            if product_ids and product_id not in product_ids:
                continue
            qty = Decimal(str(item.get("qty_sold") or item.get("Qty_Sold") or 0))
            price = money(item.get("unit_price_ht") or item.get("Unit_Price_HT"))
            if qty > 0 and price >= 0:
                applicable.append({"qty": qty, "price": price, "base": money(qty * price)})
        base_amount = sum((row["base"] for row in applicable), Decimal("0.00"))
        min_amount = money(promotion.get("Min_Amount"))
        if base_amount <= 0 or (min_amount > 0 and base_amount < min_amount):
            return False, {"message": "Le panier ne respecte pas le minimum de la promotion."}

        promotion_type = promotion.get("Promotion_Type")
        value = money(promotion.get("Value"))
        discount = Decimal("0.00")
        if promotion_type == "Percent":
            discount = (base_amount * value / Decimal("100")).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        elif promotion_type == "Fixed":
            discount = min(value, base_amount)
        elif promotion_type == "BuyXGetY":
            buy_qty = Decimal(str(promotion.get("Buy_Qty") or 0))
            get_qty = Decimal(str(promotion.get("Get_Qty") or 0))
            if buy_qty <= 0 or get_qty <= 0:
                return False, {"message": "Configuration Buy X Get Y invalide."}
            free_units = sum((row["qty"] for row in applicable), Decimal("0")) // (buy_qty + get_qty) * get_qty
            prices = sorted((row["price"] for row in applicable), reverse=False)
            discount = sum(prices[:int(free_units)], Decimal("0.00"))
        discount = min(discount, base_amount)
        return True, {
            "promotion": promotion,
            "base_amount": base_amount,
            "discount_amount": discount,
            "discount_percent": (discount / base_amount * Decimal("100")) if base_amount else Decimal("0"),
        }
    def get_active_promotions(self, on_date=None, code=None):
        on_date = on_date or date.today()
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT * FROM POS_Promotions
                    WHERE Is_Active = TRUE
                      AND (Starts_At IS NULL OR Starts_At <= %s)
                      AND (Ends_At IS NULL OR Ends_At >= %s)
                """
                params = [on_date, on_date]
                if code:
                    query += " AND Promotion_Code = %s"
                    params.append(code)
                query += " ORDER BY Priority DESC, Promotion_ID"
                cursor.execute(query, tuple(params))
                promotions = cursor.fetchall() or []
                for promotion in promotions:
                    cursor.execute(
                        "SELECT Product_ID FROM POS_Promotion_Products WHERE Promotion_ID = %s",
                        (promotion["Promotion_ID"],),
                    )
                    promotion["Product_IDs"] = [row["Product_ID"] for row in cursor.fetchall()]
                return promotions
        except Exception as exc:
            logging.error("Could not load promotions: %s", exc, exc_info=True)
            return []

    def create_promotion(self, data, product_ids=None, user_id=None):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO POS_Promotions
                        (Promotion_Code, Promotion_Name, Promotion_Type, Value,
                         Buy_Qty, Get_Qty, Min_Amount, Starts_At, Ends_At,
                         Priority, Is_Stackable, Is_Active, Created_By)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data.get("code") or None, data["name"], data.get("type", "Percent"), money(data.get("value")),
                        data.get("buy_qty"), data.get("get_qty"), data.get("min_amount"), data.get("starts_at"),
                        data.get("ends_at"), int(data.get("priority") or 0), bool(data.get("stackable")),
                        bool(data.get("active", True)), user_id,
                    ),
                )
                promotion_id = cursor.lastrowid
                for product_id in product_ids or []:
                    cursor.execute(
                        "INSERT IGNORE INTO POS_Promotion_Products (Promotion_ID, Product_ID) VALUES (%s, %s)",
                        (promotion_id, product_id),
                    )
                self.audit("POS_Promotion", promotion_id, "Created", data, user_id, cursor=cursor)
                return promotion_id
        except Exception as exc:
            logging.error("Could not create promotion: %s", exc, exc_info=True)
            return None

    def get_or_create_loyalty_account(self, client_id, cursor=None):
        own_connection = cursor is None
        conn = None
        try:
            if own_connection:
                conn = self.db.get_raw_connection()
                cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM POS_Loyalty_Accounts WHERE Client_ID = %s", (client_id,))
            account = cursor.fetchone()
            if not account:
                cursor.execute("INSERT INTO POS_Loyalty_Accounts (Client_ID) VALUES (%s)", (client_id,))
                account_id = cursor.lastrowid
                cursor.execute("SELECT * FROM POS_Loyalty_Accounts WHERE Loyalty_Account_ID = %s", (account_id,))
                account = cursor.fetchone()
            if own_connection:
                conn.commit()
            return account
        except Exception as exc:
            if own_connection and conn:
                conn.rollback()
            logging.error("Could not get loyalty account: %s", exc, exc_info=True)
            return None
        finally:
            if own_connection and conn and conn.is_connected():
                conn.close()

    def get_loyalty_account(self, client_id):
        return self.get_or_create_loyalty_account(client_id)

    def record_loyalty_transaction(self, client_id, invoice_id, transaction_type, points, user_id=None, notes=None, cursor=None):
        points = Decimal(str(points or 0))
        if not client_id or points == 0 or transaction_type not in {"Earn", "Redeem", "Adjust", "Reverse"}:
            return False
        own_connection = cursor is None
        conn = None
        try:
            if own_connection:
                conn = self.db.get_raw_connection()
                conn.start_transaction()
                cursor = conn.cursor(dictionary=True)
            account = self.get_or_create_loyalty_account(client_id, cursor=cursor)
            if not account:
                raise ValueError("Compte fidélité introuvable.")
            balance = Decimal(str(account.get("Points_Balance") or 0))
            if transaction_type == "Redeem" and balance < abs(points):
                raise ValueError("Solde de points insuffisant.")
            delta = -abs(points) if transaction_type == "Redeem" else abs(points)
            new_balance = balance + delta
            cursor.execute(
                """
                INSERT INTO POS_Loyalty_Transactions
                    (Loyalty_Account_ID, Invoice_ID, Transaction_Type, Points, Notes, Created_By)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (account["Loyalty_Account_ID"], invoice_id, transaction_type, abs(points), notes, user_id),
            )
            cursor.execute(
                """
                UPDATE POS_Loyalty_Accounts
                SET Points_Balance = %s,
                    Total_Earned = Total_Earned + %s,
                    Total_Redeemed = Total_Redeemed + %s
                WHERE Loyalty_Account_ID = %s
                """,
                (new_balance, abs(points) if transaction_type != "Redeem" else 0, abs(points) if transaction_type == "Redeem" else 0, account["Loyalty_Account_ID"]),
            )
            if own_connection:
                conn.commit()
            return True
        except Exception as exc:
            if own_connection and conn:
                conn.rollback()
            logging.error("Could not record loyalty transaction: %s", exc, exc_info=True)
            return False
        finally:
            if own_connection and conn and conn.is_connected():
                conn.close()
