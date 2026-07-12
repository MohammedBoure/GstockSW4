# database/cash_session_manager.py

import logging
from datetime import date
from typing import Dict, Optional, Tuple


class CashSessionManager:
    """Open/close POS cash sessions and summarize session takings."""

    _schema_checked = False

    def __init__(self, db_instance):
        self.db = db_instance
        self._ensure_schema()

    def _ensure_schema(self):
        if CashSessionManager._schema_checked:
            return
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
        ]
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                for query in queries:
                    cursor.execute(query)
                CashSessionManager._schema_checked = True
        except Exception as e:
            logging.error(f"Cash session schema check failed: {e}", exc_info=True)

    def get_open_session(self, terminal_id: int) -> Optional[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT s.*, t.Terminal_Code, t.Terminal_Name
                    FROM POS_Cash_Sessions s
                    JOIN POS_Terminals t ON s.Terminal_ID = t.Terminal_ID
                    WHERE s.Terminal_ID = %s AND s.Status = 'Open'
                    ORDER BY s.Opened_At DESC
                    LIMIT 1
                    """,
                    (terminal_id,),
                )
                return cursor.fetchone()
        except Exception as e:
            logging.error(f"Could not fetch open cash session: {e}", exc_info=True)
            return None

    def open_session(self, terminal_id: int, user_id: Optional[int], opening_amount=0.0, notes=None) -> Tuple[bool, Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT * FROM POS_Cash_Sessions
                    WHERE Terminal_ID = %s AND Status = 'Open'
                    ORDER BY Opened_At DESC
                    LIMIT 1
                    """,
                    (terminal_id,),
                )
                existing = cursor.fetchone()
                if existing:
                    return True, existing

                today = date.today().strftime("%Y%m%d")
                cursor.execute(
                    """
                    SELECT COUNT(*) AS Cnt
                    FROM POS_Cash_Sessions
                    WHERE Terminal_ID = %s AND DATE(Opened_At) = CURDATE()
                    """,
                    (terminal_id,),
                )
                count_row = cursor.fetchone() or {}
                seq = int(count_row.get("Cnt") or 0) + 1
                session_no = f"CS-{int(terminal_id):02d}-{today}-{seq:02d}"
                cursor.execute(
                    """
                    INSERT INTO POS_Cash_Sessions
                    (Session_No, Terminal_ID, Opened_By, Opening_Amount, Notes)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (session_no, terminal_id, user_id, opening_amount, notes),
                )
                session_id = cursor.lastrowid
                return True, {
                    "Cash_Session_ID": session_id,
                    "Session_No": session_no,
                    "Terminal_ID": terminal_id,
                    "Opened_By": user_id,
                    "Opening_Amount": opening_amount,
                    "Status": "Open",
                    "Next_Invoice_Seq": 1,
                }
        except Exception as e:
            logging.error(f"Could not open cash session: {e}", exc_info=True)
            return False, {"message": str(e)}

    def get_session_summary(self, cash_session_id: int) -> Dict:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN Payment_Method = 'Cash' THEN Total_Amount_TTC ELSE 0 END), 0) AS Expected_Cash,
                        COALESCE(SUM(CASE WHEN Payment_Method = 'Card' THEN Total_Amount_TTC ELSE 0 END), 0) AS Expected_Card,
                        COALESCE(SUM(CASE WHEN Payment_Method = 'Transfer' THEN Total_Amount_TTC ELSE 0 END), 0) AS Expected_Transfer,
                        COALESCE(SUM(Total_Amount_TTC), 0) AS Expected_Total,
                        COUNT(*) AS Invoice_Count
                    FROM Sales_Invoices
                    WHERE Cash_Session_ID = %s AND Status <> 'Cancelled'
                    """,
                    (cash_session_id,),
                )
                return cursor.fetchone() or {}
        except Exception as e:
            logging.error(f"Could not summarize cash session: {e}", exc_info=True)
            return {}

    def close_session(self, cash_session_id: int, user_id: Optional[int], counted_cash=0.0, notes=None) -> Tuple[bool, Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                conn.start_transaction()
                cursor.execute(
                    """
                    SELECT * FROM POS_Cash_Sessions
                    WHERE Cash_Session_ID = %s AND Status = 'Open'
                    FOR UPDATE
                    """,
                    (cash_session_id,),
                )
                session = cursor.fetchone()
                if not session:
                    conn.rollback()
                    return False, {"message": "Aucune session ouverte a cloturer."}

                summary = self.get_session_summary(cash_session_id)
                expected_cash = float(summary.get("Expected_Cash") or 0)
                expected_card = float(summary.get("Expected_Card") or 0)
                expected_transfer = float(summary.get("Expected_Transfer") or 0)
                opening_amount = float(session.get("Opening_Amount") or 0)
                cash_difference = float(counted_cash) - (opening_amount + expected_cash)

                cursor.execute(
                    """
                    UPDATE POS_Cash_Sessions
                    SET Status = 'Closed',
                        Closed_By = %s,
                        Closed_At = NOW(),
                        Expected_Cash = %s,
                        Expected_Card = %s,
                        Expected_Transfer = %s,
                        Counted_Cash = %s,
                        Cash_Difference = %s,
                        Notes = %s
                    WHERE Cash_Session_ID = %s
                    """,
                    (
                        user_id, expected_cash, expected_card, expected_transfer,
                        counted_cash, cash_difference, notes, cash_session_id,
                    ),
                )
                conn.commit()
                summary.update({
                    "Opening_Amount": opening_amount,
                    "Counted_Cash": float(counted_cash),
                    "Cash_Difference": cash_difference,
                })
                return True, summary
        except Exception as e:
            logging.error(f"Could not close cash session: {e}", exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
            return False, {"message": str(e)}
