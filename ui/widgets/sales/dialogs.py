# ui/widgets/sales/dialogs.py

from PySide6.QtWidgets import (QFormLayout, QLineEdit, QWidget, QMessageBox)
from ui.widgets.master_data.dialogs import BaseDialog

class ClientDialog(BaseDialog):
    """Fenêtre pour ajouter ou modifier un client."""
    def __init__(self, parent=None, data=None):
        title = "Modifier le Client" if data else "Ajouter un Client"
        super().__init__(title, parent)
        self.resize(500, 450)
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nom de l'entreprise ou du client *")
        
        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Personne à contacter")
        
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Numéro de téléphone")
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Adresse Email")
        
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Adresse")
        
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Ville")
        
        self.tax_id_input = QLineEdit()
        self.tax_id_input.setPlaceholderText("NIF / N° d'identification fiscale")
        
        self.commercial_reg_input = QLineEdit()
        self.commercial_reg_input.setPlaceholderText("RC / Registre de Commerce")

        layout.addRow("Nom du Client * :", self.name_input)
        layout.addRow("Contact :", self.contact_input)
        layout.addRow("Téléphone :", self.phone_input)
        layout.addRow("Email :", self.email_input)
        layout.addRow("Adresse :", self.address_input)
        layout.addRow("Ville :", self.city_input)
        layout.addRow("NIF :", self.tax_id_input)
        layout.addRow("RC :", self.commercial_reg_input)

        if self.data:
            self.name_input.setText(self.data.get('Client_Name', ''))
            self.contact_input.setText(self.data.get('Contact_Person', ''))
            self.phone_input.setText(self.data.get('Phone', ''))
            self.email_input.setText(self.data.get('Email', ''))
            self.address_input.setText(self.data.get('Address', ''))
            self.city_input.setText(self.data.get('City', ''))
            self.tax_id_input.setText(self.data.get('Tax_ID_Number', ''))
            self.commercial_reg_input.setText(self.data.get('Commercial_Reg_No', ''))

    def get_data(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom du client est obligatoire.")
            return None
            
        return {
            'name': name,
            'contact_person': self.contact_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'email': self.email_input.text().strip(),
            'address': self.address_input.text().strip(),
            'city': self.city_input.text().strip(),
            'tax_id': self.tax_id_input.text().strip(),
            'commercial_reg': self.commercial_reg_input.text().strip()
        }
