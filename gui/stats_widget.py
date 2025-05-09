# gui/stats_widget.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QGroupBox, 
                             QPushButton, QComboBox, QApplication) # QApplication pour le test
from PyQt6.QtCore import Qt
from utils.logger import get_logger # Import get_logger
import datetime # Nécessaire pour le mock dans __main__

class StatsWidget(QWidget):
    def __init__(self, app_manager, parent=None):
        super().__init__(parent)
        self.app_manager = app_manager
        self.logger = get_logger() # Initialiser le logger
        self.init_ui()
        self.refresh_stats() # Charger les stats initiales

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Sélection de la période
        period_layout = QHBoxLayout()
        period_layout.addWidget(QLabel("Afficher les stats pour:"))
        self.period_combo = QComboBox()
        self.period_combo.addItems(["Aujourd'hui", "Hier", "7 derniers jours", "30 derniers jours"]) # Ajouté 30 jours
        self.period_combo.currentTextChanged.connect(self.refresh_stats) 
        period_layout.addWidget(self.period_combo)
        
        self.refresh_button = QPushButton("🔄 Rafraîchir")
        self.refresh_button.clicked.connect(self.refresh_stats)
        period_layout.addWidget(self.refresh_button)
        period_layout.addStretch()
        main_layout.addLayout(period_layout)

        # Affichage des stats
        stats_group = QGroupBox("Statistiques d'Actions Effectuées par le Bot")
        stats_grid = QGridLayout(stats_group)
        stats_grid.setColumnStretch(0, 1) # Label prend moins de place
        stats_grid.setColumnStretch(1, 0) # Valeur

        row = 0
        self.stat_labels = {} # Pour stocker les QLabels des valeurs
        action_types_labels = [ # Clé DB, Label UI
            ('follows', "✅ Utilisateurs Suivis (Follows)"), 
            ('unfollows', "❌ Désabonnements (Unfollows)"), 
            ('likes', "❤️ Likes Donnés"), 
            ('comments', "💬 Commentaires Postés"), 
            ('story_views', "👀 Stories Visionnées"),
            ('dms_sent', "✉️ DMs Envoyés (Tentatives)"), # Ajouté si vous l'implémentez
            # ('new_followers_checked', "🔔 Nouveaux Abonnés Vérifiés") # Une autre stat possible
        ]
        
        for key, label_text in action_types_labels:
             text_label = QLabel(f"{label_text} :") # Le " :" est ajouté ici pour alignement
             text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
             value_label = QLabel("0")
             value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
             value_label.setStyleSheet("font-weight: bold; font-size: 14pt; padding-right: 20px;") # Un peu plus grand
             
             stats_grid.addWidget(text_label, row, 0)
             stats_grid.addWidget(value_label, row, 1)
             self.stat_labels[key] = value_label
             row += 1
             
        main_layout.addWidget(stats_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def refresh_stats(self):
        if not self.app_manager:
            self.logger.warning("StatsWidget: AppManager non disponible.")
            for label_widget in self.stat_labels.values():
                label_widget.setText("N/A")
            return
            
        period_text = self.period_combo.currentText()
        period_key = "today" 
        if period_text == "Hier": period_key = "yesterday"
        elif period_text == "7 derniers jours": period_key = "last7days"
        elif period_text == "30 derniers jours": period_key = "last30days" # Nouvelle période
             
        self.logger.info(f"Rafraîchissement des stats pour la période: {period_key}")
        stats = self.app_manager.get_action_stats(period=period_key) # Doit être créé dans AppManager
        
        if stats:
            for key, label_widget in self.stat_labels.items():
                label_widget.setText(str(stats.get(key, 0)))
        else: 
            self.logger.error("Impossible de récupérer les statistiques depuis AppManager ou DB.")
            for label_widget in self.stat_labels.values():
                label_widget.setText("Erreur")
                
    # Rafraîchir quand l'onglet devient visible
    def showEvent(self, event):
        self.refresh_stats()
        super().showEvent(event)

# Test isolé (doit être exécuté dans un contexte où get_logger est défini)
if __name__ == '__main__':
    import sys
    # Pour le test isolé, on a besoin de définir get_logger minimalement
    # Dans une vraie exécution, il vient de utils.logger
    if 'get_logger' not in globals():
        import logging
        def get_logger(name=None): return logging.getLogger(name or "TestStats")
        logging.basicConfig(level=logging.DEBUG) # Configurer logging pour le test

    class MockAppManager:
        def __init__(self): 
            self.logger = get_logger("MockAppManager") # Utiliser notre get_logger défini localement
        def get_action_stats(self, period="today"):
            self.logger.info(f"MockAppManager: get_action_stats pour {period}")
            if period == "today": return {'follows': 5, 'unfollows': 1, 'likes': 25, 'comments': 2, 'story_views': 50, 'dms_sent': 1}
            elif period == "yesterday": return {'follows': 8, 'unfollows': 3, 'likes': 40, 'comments': 4, 'story_views': 80, 'dms_sent': 0}
            elif period == "last7days": return {'follows': 50, 'unfollows': 15, 'likes': 200, 'comments': 15, 'story_views': 400, 'dms_sent': 5}
            elif period == "last30days": return {'follows': 200, 'unfollows': 60, 'likes': 800, 'comments': 50, 'story_views': 1500, 'dms_sent': 20}
            return {'follows': 0, 'unfollows': 0, 'likes': 0, 'comments': 0, 'story_views': 0, 'dms_sent': 0} # Default
            
    app = QApplication(sys.argv)
    mock_manager = MockAppManager()
    
    # Créer une fenêtre principale pour héberger le widget de test
    main_test_window = QWidget()
    layout = QVBoxLayout(main_test_window)
    stats_widget_instance = StatsWidget(app_manager=mock_manager)
    layout.addWidget(stats_widget_instance)
    
    main_test_window.setWindowTitle("Test Stats Widget")
    main_test_window.resize(400, 300)
    main_test_window.show()
    
    sys.exit(app.exec())