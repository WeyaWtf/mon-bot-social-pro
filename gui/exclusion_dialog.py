# gui/whitelist_widget.py
import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox, QFileDialog, QAbstractItemView
)
from PyQt6.QtCore import Qt
from utils.logger import get_logger

logger = get_logger()

class WhitelistWidget(QWidget):
    def __init__(self, app_manager, parent=None):
        super().__init__(parent)
        self.app_manager = app_manager
        self.setWindowTitle("Gestion de la Whitelist (Protection Unfollow)")
        self.setMinimumSize(450, 350) # Légèrement plus grand
        self.init_ui()
        self._load_whitelist_from_appmanager()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Les utilisateurs dans cette liste NE seront JAMAIS désabonnés par le bot."))

        # Liste
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        main_layout.addWidget(QLabel("Utilisateurs protégés :"))
        main_layout.addWidget(self.list_widget)

        # Ajout
        add_group = QGroupBox("Ajouter à la whitelist")
        add_layout = QHBoxLayout(add_group)
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("Nom d'utilisateur ou ID (ou plusieurs séparés par virgule/espace)")
        self.add_button = QPushButton("➕ Ajouter")
        self.add_button.clicked.connect(self.add_items)
        add_layout.addWidget(self.add_input)
        add_layout.addWidget(self.add_button)
        main_layout.addWidget(add_group)

        # Gestion Liste
        manage_buttons_layout = QHBoxLayout()
        self.delete_button = QPushButton("➖ Retirer Sélectionné(s)")
        self.delete_button.clicked.connect(self.delete_selected_items)
        manage_buttons_layout.addWidget(self.delete_button)

        self.clear_button = QPushButton("🗑️ Vider Toute la Whitelist")
        self.clear_button.clicked.connect(self.clear_list)
        manage_buttons_layout.addWidget(self.clear_button)
        manage_buttons_layout.addStretch()
        main_layout.addLayout(manage_buttons_layout)
        
        # Import/Export
        file_buttons_layout = QHBoxLayout()
        self.import_button = QPushButton("📂 Importer Whitelist (.txt)")
        self.import_button.clicked.connect(self.import_from_file)
        file_buttons_layout.addWidget(self.import_button)

        self.export_button = QPushButton("💾 Exporter Whitelist (.txt)")
        self.export_button.clicked.connect(self.export_to_file)
        file_buttons_layout.addWidget(self.export_button)
        main_layout.addLayout(file_buttons_layout)

        self.setLayout(main_layout)

    def _populate_list_widget(self):
        self.list_widget.clear()
        if self.app_manager and hasattr(self.app_manager, 'whitelist'):
            sorted_list = sorted(list(self.app_manager.whitelist))
            self.list_widget.addItems(sorted_list)
            self.list_widget.sortItems(Qt.SortOrder.AscendingOrder)
        self.update_status_label()

    def update_status_label(self):
        count = self.list_widget.count()
        self.setWindowTitle(f"Whitelist ({count} éléments)")

    def _load_whitelist_from_appmanager(self):
        if self.app_manager:
            self._populate_list_widget()
        else:
            logger.warning("WhitelistWidget: AppManager non disponible.")

    def add_items(self):
        input_text = self.add_input.text().strip().lower()
        if not input_text:
             QMessageBox.warning(self, "Entrée Vide", "Veuillez entrer un nom d'utilisateur."); return

        items_to_add = set()
        for part in input_text.split(','):
            for item in part.split():
                cleaned_item = item.strip()
                if cleaned_item: items_to_add.add(cleaned_item)
        
        if not items_to_add:
            QMessageBox.warning(self, "Entrée Vide", "Aucun nom valide détecté."); return

        added_count = 0; already_exist_count = 0
        if self.app_manager:
            for item_text in items_to_add:
                if self.app_manager.add_to_whitelist(item_text): added_count +=1
                else: already_exist_count +=1
            
            if added_count > 0:
                self._populate_list_widget(); self.add_input.clear()
                logger.info(f"{added_count} utilisateur(s) ajouté(s) à la whitelist.")
            
            message = ""
            if added_count > 0: message += f"{added_count} ajouté(s).\n"
            if already_exist_count > 0: message += f"{already_exist_count} déjà dans la whitelist."
            if not message: message = "Aucun changement."
            QMessageBox.information(self, "Ajout Whitelist", message.strip())
             
    def delete_selected_items(self):
        selected_items_widgets = self.list_widget.selectedItems()
        if not selected_items_widgets: QMessageBox.warning(self, "Sélection", "Sélectionnez élément(s)."); return
            
        items_to_delete = [item.text() for item in selected_items_widgets]
        
        if self.app_manager:
            reply = QMessageBox.question(self, "Confirmation", f"Retirer {len(items_to_delete)} élément(s) de la whitelist ?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                deleted_count = 0
                for item_text in items_to_delete:
                    if self.app_manager.remove_from_whitelist(item_text): deleted_count +=1
                if deleted_count > 0: self._populate_list_widget()
                QMessageBox.information(self, "Suppression", f"{deleted_count} élément(s) retiré(s).")

    def clear_list(self):
        if self.app_manager and self.app_manager.whitelist:
            reply = QMessageBox.question(self, "Vider", f"Vider la Whitelist ({len(self.app_manager.whitelist)} éléments) ?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.app_manager.clear_whitelist(); self._populate_list_widget()
                QMessageBox.information(self, "Liste Vidée", "Whitelist vidée.")
        else: QMessageBox.information(self, "Info", "Whitelist déjà vide.")

    def import_from_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Importer Whitelist (.txt)", "",
                                                   "Fichiers Texte (*.txt);;Tous les Fichiers (*)", options=options)
        if file_path and self.app_manager:
            added_count = self.app_manager.import_whitelist(file_path)
            if added_count >= 0:
                 QMessageBox.information(self, "Importation", f"{added_count} nouveaux éléments uniques ajoutés.")
                 self._populate_list_widget()
            else: QMessageBox.critical(self, "Erreur Importation", "Erreur lecture/traitement fichier.")

    def export_to_file(self):
        if not self.app_manager or not self.app_manager.whitelist:
            QMessageBox.information(self, "Exportation", "Whitelist vide."); return
            
        options = QFileDialog.Options(); default_filename = "ma_whitelist.txt"
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporter Whitelist (.txt)", default_filename,
                                                  "Fichiers Texte (*.txt);;Tous les Fichiers (*)", options=options)
        if file_path and self.app_manager:
             if not file_path.lower().endswith(".txt"): file_path += ".txt"
             if self.app_manager.export_whitelist(file_path):
                  QMessageBox.information(self, "Exportation", f"Whitelist ({len(self.app_manager.whitelist)}) exportée.")
             else: QMessageBox.critical(self, "Erreur Exportation", "Erreur écriture fichier.")

    def showEvent(self, event):
        self._load_whitelist_from_appmanager()
        super().showEvent(event)