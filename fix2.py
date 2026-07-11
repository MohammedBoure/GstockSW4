with open('database/stock_movement_log_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()
import re
start_idx = content.find('    def _ensure_schema(self):')
end_idx = content.find('            # 2. حساب وتثبيت المخزون المتبقي (Snapshot) في الخانة الخاصة')
if start_idx != -1 and end_idx != -1:
    correct_block = '''    def _ensure_schema(self):
        \"\"\"تأكد من وجود عمود Stock_After لتسجيل القيم بشكل صحيح وجديد\"\"\"
        if StockMovementLogManager._schema_checked:
            return
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(\"SHOW COLUMNS FROM Stock_Movement_Log LIKE 'Stock_After'\")
                if not cursor.fetchone():
                    logging.info(\"Adding Stock_After column to Stock_Movement_Log...\")
                    cursor.execute(\"ALTER TABLE Stock_Movement_Log ADD COLUMN Stock_After DECIMAL(15, 2) NULL;\")
                StockMovementLogManager._schema_checked = True
        except Exception as e:
            logging.error(f\"Schema check error: {e}\")

    def create_movement_log(self, product_id: int, movement_type: str, qty_change: Decimal, unit_used: str, 
                    batch_id: int = None, container_id: int = None, 
                    reason_id: int = None, notes: str = None, 
                    user_id: int = None, 
                    external_cursor=None) -> int:
        valid_movements = [
            'Purchase_Receive', 'Open_Pack', 'Patient_Test', 'QC_Run', 
            'Calibration', 'Adjustment', 'Waste', 'Transfer', 
            'External_Transfer', 'Return_To_Supplier', 'Sale', 'Sale_Return'
        ]
        
        if movement_type not in valid_movements:
            logging.error(f\"⚠️ Type de mouvement invalide: {movement_type}\")
            return None

        # 1. إدخال الحركة أولاً
        query_insert = \"\"\"
            INSERT INTO Stock_Movement_Log 
            (Product_ID, Batch_ID, Container_ID, Movement_Type, Reason_ID, 
            Qty_Change, Unit_Used, Notes, User_ID, Transaction_Date) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        \"\"\"
        params = (product_id, batch_id, container_id, movement_type, reason_id, 
                qty_change, unit_used, notes, user_id)
        
        conn = None
        try:
            # إذا كان هناك مؤشر خارجي (جزء من معاملة أكبر)
            cursor_to_use = external_cursor
            
            if not cursor_to_use:
                conn = self.db.get_raw_connection()
                cursor_to_use = conn.cursor()

            cursor_to_use.execute(query_insert, params)
            movement_id = cursor_to_use.lastrowid

'''
    new_content = content[:start_idx] + correct_block + content[end_idx:]
    with open('database/stock_movement_log_manager.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Fixed successfully')
else:
    print('Failed to find indices', start_idx, end_idx)
