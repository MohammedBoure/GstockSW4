import json
import logging

class TemplateManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_templates(self, template_type):
        """ Fetch all templates for a specific type (e.g. 'receipt', 'label') """
        query = "SELECT id, name, settings_json FROM Print_Templates WHERE template_type = %s ORDER BY name ASC"
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (template_type,))
                results = cursor.fetchall()
                
            templates = []
            for row in results:
                templates.append({
                    "id": row['id'],
                    "name": row['name'],
                    "settings": json.loads(row['settings_json']) if row['settings_json'] else {}
                })
            return templates
        except Exception as e:
            logging.error(f"Erreur get_templates: {e}")
            return []

    def get_template_by_name(self, template_type, name):
        """ Fetch a specific template by name """
        query = "SELECT settings_json FROM Print_Templates WHERE template_type = %s AND name = %s"
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, (template_type, name))
                results = cursor.fetchall()
                
            if results and results[0]['settings_json']:
                return json.loads(results[0]['settings_json'])
            return None
        except Exception as e:
            logging.error(f"Erreur get_template_by_name: {e}")
            return None

    def save_template(self, template_type, name, settings_dict):
        """ Create or Update a template by name """
        existing = self.get_template_by_name(template_type, name)
        settings_json = json.dumps(settings_dict)
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                if existing is not None:
                    query = "UPDATE Print_Templates SET settings_json = %s WHERE template_type = %s AND name = %s"
                    cursor.execute(query, (settings_json, template_type, name))
                else:
                    query = "INSERT INTO Print_Templates (template_type, name, settings_json) VALUES (%s, %s, %s)"
                    cursor.execute(query, (template_type, name, settings_json))
                conn.commit()
            return True, "Modèle enregistré avec succès."
        except Exception as e:
            logging.error(f"Erreur save_template: {e}")
            return False, f"Erreur lors de l'enregistrement: {e}"

    def rename_template(self, template_type, old_name, new_name):
        """ Rename an existing template """
        try:
            # Check if new name already exists
            if self.get_template_by_name(template_type, new_name) is not None:
                return False, "Un modèle avec ce nom existe déjà."
                
            query = "UPDATE Print_Templates SET name = %s WHERE template_type = %s AND name = %s"
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (new_name, template_type, old_name))
                conn.commit()
            return True, "Renommé avec succès."
        except Exception as e:
            logging.error(f"Erreur rename_template: {e}")
            return False, f"Erreur de renommage: {e}"

    def delete_template(self, template_type, name):
        """ Delete a template """
        try:
            query = "DELETE FROM Print_Templates WHERE template_type = %s AND name = %s"
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (template_type, name))
                conn.commit()
            return True, "Supprimé avec succès."
        except Exception as e:
            logging.error(f"Erreur delete_template: {e}")
            return False, f"Erreur de suppression: {e}"
