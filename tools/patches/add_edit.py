import os
filepath = r"d:\git\GstockSW4\ui\widgets\inventory\tabs_batches\_actions.py"
with open(filepath, "a", encoding="utf-8") as f:
    f.write("""
def open_quick_edit(self):
    \"\"\"يفتح نافذة التعديل السريع للحصة المحددة (إذا لم تكن من إيصال استلام رسمي)\"\"\"
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtCore import Qt
    
    selected_rows = set(item.row() for item in self.table.selectedItems())
    if not selected_rows or len(selected_rows) != 1:
        QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un (1) seul lot à modifier.")
        return
        
    row = list(selected_rows)[0]
    batch_data = self.table.item(row, 0).data(Qt.UserRole)
    
    if batch_data.get('BR_ID') is not None:
        QMessageBox.warning(self, "Action non permise", "Ce lot appartient à un Bon de Réception.\\nVeuillez le modifier depuis l'historique des réceptions.")
        return
        
    from .quick_add_dialog import QuickAddDialog
    dialog = QuickAddDialog(self.manager, self, batch_data=batch_data)
    
    if dialog.exec():
        data = dialog.get_data()
        success = self.manager.batches.update_direct_batch(
            batch_data['Batch_ID'],
            data,
            user_id=get_current_user_id(self)
        )
        
        if success:
            self.load_data()
            self.data_changed.emit()
        else:
            QMessageBox.critical(self, "Erreur", "Échec de la modification du stock.")
""")
print("Added open_quick_edit")
