# mon_bot_social/main.py
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QCoreApplication


from gui.main_window import MainWindow
from core.app_manager import AppManager
from utils.logger import get_logger # Importer le logger

logger = get_logger() # Obtenir l'instance du logger global

def main():
    logger.info(" démarrage de l'application Mon Bot Social Pro...")
    
    # Bonne pratique pour les applications Qt modernes
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # Initialiser AppManager SANS la référence à la fenêtre d'abord
    # Car la création de MainWindow pourrait en avoir besoin (indirectement via SettingsWidget)
    app_manager = AppManager()

    # Créer MainWindow en passant app_manager
    window = MainWindow(app_manager=app_manager)
    
    # MAINTENANT, donner à AppManager la référence à la fenêtre principale pour les callbacks UI
    app_manager.set_main_window(window)
    
    window.show()

    exit_code = app.exec()
    
    logger.info("Tentative d'arrêt propre de l'application...")
    app_manager.shutdown() # Appeler la méthode shutdown de AppManager
    logger.info("Application Mon Bot Social Pro terminée.")
    sys.exit(exit_code)

if __name__ == "__main__":
    # Gérer les exceptions non interceptées avec le logger
    def excepthook(exc_type, exc_value, exc_tb):
        logger.critical("Exception non interceptée :", exc_info=(exc_type, exc_value, exc_tb))
        # On peut ajouter ici un QMessageBox pour l'utilisateur si on est dans un contexte GUI déjà lancé
        # Mais si c'est avant que l'app Qt ne soit lancée, il n'y aura pas de pop-up.

    sys.excepthook = excepthook
    
    try:
        main()
    except Exception as e:
        logger.critical(f"Erreur fatale au niveau racine de l'application : {e}", exc_info=True)
        # Afficher un message d'erreur simple à l'utilisateur si possible
        try:
            error_app = QApplication.instance() # Récupérer l'instance si elle existe
            if not error_app: error_app = QApplication(sys.argv) # Créer si n'existe pas
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Erreur Fatale", f"Une erreur critique est survenue et l'application doit fermer.\nConsultez {os.path.join('data_files', 'app_activity.log')} pour les détails.\n\nErreur: {e}")
        except:
            pass # Si même la création de la QMessageBox échoue, ne rien faire de plus
        sys.exit(1) # Quitter avec un code d'erreur