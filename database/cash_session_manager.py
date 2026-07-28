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
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Cash' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Cash,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Card' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Card,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Transfer' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Transfer,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Versement' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Versement,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Other' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Other,
                        COALESCE(SUM(CASE WHEN COALESCE(p.Payment_Method, i.Payment_Method) = 'Credit' THEN COALESCE(p.Amount, i.Total_Amount_TTC) ELSE 0 END), 0) AS Expected_Credit,
                        COALESCE(SUM(COALESCE(p.Amount, i.Total_Amount_TTC)), 0) AS Expected_Total,
                        COUNT(DISTINCT i.Invoice_ID) AS Invoice_Count
                    FROM Sales_Invoices i
                    LEFT JOIN POS_Sale_Payments p ON p.Invoice_ID = i.Invoice_ID
                    WHERE i.Cash_Session_ID = %s AND i.Status <> 'Cancelled'
                    """,
                    (cash_session_id,),
                )
                summary = cursor.fetchone() or {}
                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN Movement_Type = 'Cash_In' THEN Amount ELSE 0 END), 0) AS Cash_In,
                        COALESCE(SUM(CASE WHEN Movement_Type IN ('Cash_Out', 'Refund') THEN Amount ELSE 0 END), 0) AS Cash_Out
                    FROM POS_Cash_Movements
                    WHERE Cash_Session_ID = %s
                    """,
                    (cash_session_id,),
                )
                movements = cursor.fetchone() or {}
                summary['Cash_In'] = movements.get('Cash_In') or 0
                summary['Cash_Out'] = movements.get('Cash_Out') or 0
                summary['Expected_Cash'] = float(summary.get('Expected_Cash') or 0) + float(summary['Cash_In']) - float(summary['Cash_Out'])
                return summary
        except Exception as e:
            logging.error(f"Could not summarize cash session: {e}", exc_info=True)
            return {}

    def close_session(self, cash_session_id: int, user_id: Optional[int], counted_cash=0.0, notes=None, counted_card=None, counted_transfer=None, counted_versement=None, counted_other=None, counted_credit=None) -> Tuple[bool, Dict]:
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
                expected_versement = float(summary.get("Expected_Versement") or 0)
                expected_other = float(summary.get("Expected_Other") or 0)
                expected_credit = float(summary.get("Expected_Credit") or 0)
                opening_amount = float(session.get("Opening_Amount") or 0)
                counted_card = float(counted_card if counted_card is not None else expected_card)
                counted_transfer = float(counted_transfer if counted_transfer is not None else expected_transfer)
                counted_versement = float(counted_versement if counted_versement is not None else expected_versement)
                counted_other = float(counted_other if counted_other is not None else expected_other)
                counted_credit = float(counted_credit if counted_credit is not None else expected_credit)
                cash_difference = float(counted_cash) - (opening_amount + expected_cash)
                card_difference = counted_card - expected_card
                transfer_difference = counted_transfer - expected_transfer
                versement_difference = counted_versement - expected_versement
                other_difference = counted_other - expected_other
                credit_difference = counted_credit - expected_credit

                cursor.execute(
                    """
                    UPDATE POS_Cash_Sessions
                    SET Status = 'Closed',
                        Closed_By = %s,
                        Closed_At = NOW(),
                        Expected_Cash = %s,
                        Expected_Card = %s,
                        Expected_Transfer = %s,
                        Expected_Versement = %s,
                        Expected_Other = %s,
                        Expected_Credit = %s,
                        Counted_Cash = %s,
                        Counted_Card = %s,
                        Counted_Transfer = %s,
                        Counted_Versement = %s,
                        Counted_Other = %s,
                        Counted_Credit = %s,
                        Cash_Difference = %s,
                        Card_Difference = %s,
                        Transfer_Difference = %s,
                        Versement_Difference = %s,
                        Other_Difference = %s,
                        Credit_Difference = %s,
                        Notes = %s
                    WHERE Cash_Session_ID = %s
                    """,
                    (
                        user_id, expected_cash, expected_card, expected_transfer, expected_versement, expected_other, expected_credit,
                        counted_cash, counted_card, counted_transfer, counted_versement, counted_other, counted_credit,
                        cash_difference, card_difference, transfer_difference, versement_difference, other_difference, credit_difference,
                        notes, cash_session_id,
                    ),
                )
                conn.commit()
                summary.update({
                    "Opening_Amount": opening_amount,
                    "Counted_Cash": float(counted_cash),
                    "Counted_Card": counted_card,
                    "Counted_Transfer": counted_transfer,
                    "Counted_Versement": counted_versement,
                    "Counted_Other": counted_other,
                    "Counted_Credit": counted_credit,
                    "Cash_Difference": cash_difference,
                    "Card_Difference": card_difference,
                    "Transfer_Difference": transfer_difference,
                    "Versement_Difference": versement_difference,
                    "Other_Difference": other_difference,
                    "Credit_Difference": credit_difference,
                })
                return True, summary
        except Exception as e:
            logging.error(f"Could not close cash session: {e}", exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
            return False, {"message": str(e)}
