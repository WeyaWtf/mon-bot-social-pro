# gui/exclusion_widget.py
import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from utils.logger import get_logger

logger = get_logger()

class ExclusionWidget(QWidget):
    def __init__(self, app_manager, parent=None):
        super().__init__(parent)
        self.app_manager = app_manager
        self.setWindowTitle("Gestion de la Liste d'Exclusion")
        self.setMinimumSize(450, 350) # Légèrement plus grand
        self.init_ui()
        self._load_exclusion_list_from_appmanager()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Les utilisateurs/IDs dans cette liste ne seront JAMAIS ciblés par AUCUNE action."))

        # Liste des exclus
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # Permettre multi-selection pour suppression
        main_layout.addWidget(QLabel("Utilisateurs/IDs exclus :"))
        main_layout.addWidget(self.list_widget)

        # Champs et boutons d'ajout
        add_group = QGroupBox("Ajouter à la liste")
        add_layout = QHBoxLayout(add_group)
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("Entrer un nom d'utilisateur ou ID (ou plusieurs séparés par virgule/espace)")
        self.add_button = QPushButton("➕ Ajouter")
        self.add_button.clicked.connect(self.add_items) # Modifié pour gérer plusieurs ajouts
        add_layout.addWidget(self.add_input)
        add_layout.addWidget(self.add_button)
        main_layout.addWidget(add_group)

        # Boutons de gestion de liste
        manage_buttons_layout = QHBoxLayout()
        self.delete_button = QPushButton("➖ Supprimer Sélectionné(s)")
        self.delete_button.clicked.connect(self.delete_selected_items) # Modifié pour gérer plusieurs
        manage_buttons_layout.addWidget(self.delete_button)

        self.clear_button = QPushButton("🗑️ Vider Toute la Liste")
        self.clear_button.clicked.connect(self.clear_list)
        manage_buttons_layout.addWidget(self.clear_button)
        manage_buttons_layout.addStretch()
        main_layout.addLayout(manage_buttons_layout)
        
        # Boutons Import/Export
        file_buttons_layout = QHBoxLayout()
        self.import_button = QPushButton("📂 Importer depuis Fichier Texte (.txt)")
        self.import_button.clicked.connect(self.import_from_file)
        file_buttons_layout.addWidget(self.import_button)

        self.export_button = QPushButton("💾 Exporter vers Fichier Texte (.txt)")
        self.export_button.clicked.connect(self.export_to_file)
        file_buttons_layout.addWidget(self.export_button)
        main_layout.addLayout(file_buttons_layout)
        
        self.setLayout(main_layout)


    def _populate_list_widget(self):
        self.list_widget.clear()
        if self.app_manager and hasattr(self.app_manager, 'exclusion_list'):
            sorted_list = sorted(list(self.app_manager.exclusion_list))
            self.list_widget.addItems(sorted_list)
            self.list_widget.sortItems(Qt.SortOrder.AscendingOrder)
        self.update_status_label()


    def update_status_label(self):
        count = self.list_widget.count()
        # Ce widget n'a pas de label de statut propre pour l'instant,
        # mais on pourrait l'ajouter ou mettre à jour le titre de la fenêtre
        self.setWindowTitle(f"Liste d'Exclusion ({count} éléments)")


    def _load_exclusion_list_from_appmanager(self):
        if self.app_manager:
            self._populate_list_widget()
        else:
            logger.warning("ExclusionWidget: AppManager non disponible pour charger la liste.")

    def add_items(self): # Modifié pour gérer multiples
        input_text = self.add_input.text().strip().lower()
        if not input_text:
             QMessageBox.warning(self, "Entrée Vide", "Veuillez entrer au moins un nom d'utilisateur ou ID.")
             return

        # Séparer par virgule ou espace, nettoyer chaque item
        items_to_add = set()
        for part in input_text.split(','):
            for item in part.split(): # Sépare par espaces restants
                cleaned_item = item.strip()
                if cleaned_item:
                    items_to_add.add(cleaned_item)
        
        if not items_to_add:
            QMessageBox.warning(self, "Entrée Vide", "Aucun nom d'utilisateur ou ID valide détecté après nettoyage.")
            return

        added_count = 0
        already_exist_count = 0
        if self.app_manager:
            for item_text in items_to_add:
                if self.app_manager.add_to_exclusion_list(item_text):
                    added_count +=1
                else:
                    already_exist_count +=1
            
            if added_count > 0:
                self._populate_list_widget() # Met à jour l'affichage
                self.add_input.clear()
                logger.info(f"{added_count} utilisateur(s) ajouté(s) à la liste d'exclusion.")
            
            message = ""
            if added_count > 0: message += f"{added_count} élément(s) ajouté(s).\n"
            if already_exist_count > 0: message += f"{already_exist_count} élément(s) étai(en)t déjà dans la liste."
            if not message: message = "Aucun changement (éléments invalides ou déjà présents)."
            
            if added_count > 0 or already_exist_count == len(items_to_add): # Afficher info si qqch ajouté ou si tous étaient doublons
                QMessageBox.information(self, "Ajout Terminé", message.strip())
            elif added_count == 0 and already_exist_count == 0: # Rien n'a été ajouté, rien n'existait déjà (donc entrée invalide?)
                QMessageBox.warning(self, "Ajout", "Aucun élément valide n'a pu être ajouté.")


    def delete_selected_items(self): # Modifié pour gérer multiples
        selected_items_widgets = self.list_widget.selectedItems()
        if not selected_items_widgets:
            QMessageBox.warning(self, "Aucune Sélection", "Veuillez sélectionner le(s) élément(s) à supprimer.")
            return
            
        items_to_delete = [item.text() for item in selected_items_widgets]
        
        if self.app_manager:
            reply = QMessageBox.question(self, "Confirmation de Suppression", 
                                         f"Voulez-vous vraiment supprimer {len(items_to_delete)} élément(s) de la liste d'exclusion ?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                deleted_count = 0
                for item_text in items_to_delete:
                    if self.app_manager.remove_from_exclusion_list(item_text):
                        deleted_count +=1
                
                if deleted_count > 0:
                    self._populate_list_widget()
                    logger.info(f"{deleted_count} utilisateur(s) retiré(s) de la liste d'exclusion.")
                QMessageBox.information(self, "Suppression", f"{deleted_count} élément(s) supprimé(s).")


    def clear_list(self):
        if self.app_manager and self.app_manager.exclusion_list:
            count = len(self.app_manager.exclusion_list)
            reply = QMessageBox.question(self, "Vider la Liste", 
                                         f"Voulez-vous vraiment vider TOUTE la liste d'exclusion ({count} éléments) ?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.app_manager.clear_exclusion_list()
                self._populate_list_widget()
                logger.info("Liste d'exclusion vidée.")
                QMessageBox.information(self, "Liste Vidée", "La liste d'exclusion a été vidée.")
        else:
             QMessageBox.information(self, "Info", "La liste d'exclusion est déjà vide.")

    def import_from_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Importer Liste d'Exclusion (.txt)", "",
                                                   "Fichiers Texte (*.txt);;Tous les Fichiers (*)", options=options)
        if file_path and self.app_manager:
            # Confirmer avant d'écraser/fusionner ? Pour l'instant, fusionne.
            added_count = self.app_manager.import_exclusion_list(file_path) # Appelle la méthode de AM
            if added_count >= 0: # 0 est un succès si le fichier était vide ou que tout était doublon
                 QMessageBox.information(self, "Importation Réussie", f"{added_count} nouveaux éléments uniques ajoutés depuis '{os.path.basename(file_path)}'.")
                 self._populate_list_widget()
            else: # Erreur pendant import (-1)
                 QMessageBox.critical(self, "Erreur d'Importation", "Erreur lors de la lecture ou du traitement du fichier. Vérifiez la console.")

    def export_to_file(self):
        if not self.app_manager or not self.app_manager.exclusion_list:
            QMessageBox.information(self, "Exportation", "La liste d'exclusion est vide, rien à exporter.")
            return
            
        options = QFileDialog.Options()
        default_filename = "ma_liste_exclusion.txt"
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporter Liste d'Exclusion (.txt)", default_filename,
                                                  "Fichiers Texte (*.txt);;Tous les Fichiers (*)", options=options)
        if file_path and self.app_manager:
             if not file_path.lower().endswith(".txt"): file_path += ".txt" # Assurer extension
             if self.app_manager.export_exclusion_list(file_path): # Appelle la méthode de AM
                  QMessageBox.information(self, "Exportation Réussie", f"Liste ({len(self.app_manager.exclusion_list)} éléments) exportée vers '{os.path.basename(file_path)}'.")
             else:
                  QMessageBox.critical(self, "Erreur d'Exportation", "Erreur lors de l'écriture du fichier.")

    # S'assurer que la liste est rafraîchie si la fenêtre est montrée à nouveau
    def showEvent(self, event):
        self._load_exclusion_list_from_appmanager()
        super().showEvent(event)