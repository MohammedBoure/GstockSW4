# database/pos_terminal_manager.py

import logging
import os
import socket
from typing import Dict, Optional


class POSTerminalManager:
    """Manage local POS terminal identity for multi-caisse sales."""

    _schema_checked = False

    def __init__(self, db_instance):
        self.db = db_instance
        self._ensure_schema()

    def _ensure_schema(self):
        if POSTerminalManager._schema_checked:
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
            """
        ]
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                for query in queries:
                    cursor.execute(query)
                POSTerminalManager._schema_checked = True
        except Exception as e:
            logging.error(f"POS terminal schema check failed: {e}", exc_info=True)

    def get_default_terminal_code(self) -> str:
        configured = os.getenv("POS_TERMINAL_CODE")
        raw = configured or socket.gethostname() or "POS-DEFAULT"
        cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw.strip())
        return (cleaned or "POS-DEFAULT")[:100]

    def get_or_create_default_terminal(self) -> Optional[Dict]:
        code = self.get_default_terminal_code()
        name = os.getenv("POS_TERMINAL_NAME") or f"Caisse {code}"
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT * FROM POS_Terminals WHERE Terminal_Code = %s",
                    (code,),
                )
                terminal = cursor.fetchone()
                if terminal:
                    return terminal

                cursor.execute(
                    """
                    INSERT INTO POS_Terminals (Terminal_Code, Terminal_Name)
                    VALUES (%s, %s)
                    """,
                    (code, name[:150]),
                )
                terminal_id = cursor.lastrowid
                return {
                    "Terminal_ID": terminal_id,
                    "Terminal_Code": code,
                    "Terminal_Name": name[:150],
                    "Is_Active": True,
                }
        except Exception as e:
            logging.error(f"Could not get/create POS terminal: {e}", exc_info=True)
            return None
