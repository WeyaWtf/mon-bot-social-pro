# mon_bot_social/utils/logger.py
import logging
import os
import sys # Pour sys.excepthook
from logging.handlers import RotatingFileHandler
from PyQt6.QtCore import QObject, pyqtSignal

# --- Configuration du Path de Log ---
try:
    # Si ce fichier est dans mon_bot_social/utils/
    BASE_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
except NameError: 
    BASE_PROJECT_DIR = os.getcwd()

LOG_DIR = os.path.join(BASE_PROJECT_DIR, "data_files", "logs") # Mettre les logs dans un sous-dossier
LOG_FILE_NAME = "app_activity.log"
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

# --- Niveaux de Log ---
# DEBUG: Informations détaillées, typiquement utiles seulement lors du débogage.
# INFO: Confirmation que les choses fonctionnent comme prévu.
# WARNING: Indication que quelque chose d'inattendu s'est produit, ou indication d'un problème potentiel dans un futur proche (ex: 'espace disque bas'). Le logiciel fonctionne toujours comme prévu.
# ERROR: A cause d'un problème plus sérieux, le logiciel n'a pas pu effectuer certaines fonctions.
# CRITICAL: Une erreur sérieuse, indiquant que le programme lui-même pourrait être incapable de continuer à tourner.

DEFAULT_CONSOLE_LEVEL = logging.INFO
DEFAULT_FILE_LEVEL = logging.DEBUG
DEFAULT_QT_HANDLER_LEVEL = logging.INFO

# --- Handler Qt Personnalisé ---
class QtLogHandler(logging.Handler, QObject):
    # Définir le signal dans __init__ pour une meilleure compatibilité avec QObject
    def __init__(self, parent=None):
        QObject.__init__(self, parent) # Initialiser QObject
        logging.Handler.__init__(self) # Initialiser Handler
        self.log_message_signal = pyqtSignal(str) # Maintenant, définir le signal

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_message_signal.emit(msg)
        except Exception:
            self.handleError(record)

# --- Formateur ---
log_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)-8s - %(name)-15s - %(module)-15s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Création et Configuration du Logger Principal de l'Application ---
app_logger = logging.getLogger("MonBotSocialApp") # Un nom unique pour le logger principal
app_logger.setLevel(logging.DEBUG) # Capture tous les messages à partir de DEBUG
app_logger.propagate = False # Important pour éviter la duplication avec le root logger

# Variable globale pour le handler Qt, pour y accéder depuis l'UI
qt_log_handler = None

def setup_logger():
    global qt_log_handler # Utiliser la variable globale

    # Si le logger a déjà des handlers, ne pas les rajouter (utile si cette fonction est appelée plusieurs fois)
    if app_logger.hasHandlers():
        # On pourrait vouloir reconfigurer les niveaux ici si nécessaire
        # print("Logger déjà configuré.") # Log bas niveau si logger pas prêt
        return app_logger

    # Créer le dossier de logs s'il n'existe pas
    try:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
            print(f"Répertoire de logs créé: {LOG_DIR}") # Log bas niveau car logger pas encore prêt
    except OSError as e:
        print(f"ERREUR CRITIQUE: Impossible de créer le répertoire de logs {LOG_DIR}: {e}. Les logs fichiers seront désactivés.")
        # Optionnel: sortie ou mode dégradé

    # 1. Handler Console
    console_handler = logging.StreamHandler(sys.stdout) # Sortie standard
    console_handler.setLevel(DEFAULT_CONSOLE_LEVEL)
    console_handler.setFormatter(log_formatter)
    app_logger.addHandler(console_handler)

    # 2. Handler Fichier (Rotatif)
    try:
        # 5 fichiers de 2MB max chacun
        file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=2*1024*1024, backupCount=4, encoding='utf-8')
        file_handler.setLevel(DEFAULT_FILE_LEVEL)
        file_handler.setFormatter(log_formatter)
        app_logger.addHandler(file_handler)
    except Exception as e:
        app_logger.error(f"Impossible de configurer le file handler pour les logs: {e}. Logs fichiers désactivés.", exc_info=True)


    # 3. Handler Qt (pour l'UI)
    # L'instance est créée au niveau du module pour être accessible
    if qt_log_handler is None:
        qt_log_handler = QtLogHandler()
        qt_log_handler.setLevel(DEFAULT_QT_HANDLER_LEVEL)
        qt_log_handler.setFormatter(log_formatter)
        app_logger.addHandler(qt_log_handler)
    
    app_logger.info("Logger principal 'MonBotSocialApp' configuré avec les handlers Console, Fichier et Qt.")
    return app_logger

# --- Fonction d'Accès au Logger ---
_initialized_logger = None
def get_logger(name="Default"): # Donner un nom par défaut
    """Retourne une instance du logger principal ou un logger enfant."""
    global _initialized_logger
    if _initialized_logger is None:
        _initialized_logger = setup_logger()

    # Optionnel: Si 'name' est fourni et différent du logger principal, créer un logger enfant
    # Cela aide à identifier la source du log plus facilement
    if name and name != "MonBotSocialApp" and name != "Default":
        return logging.getLogger(f"MonBotSocialApp.{name}")
    return _initialized_logger


# Appel initial pour configurer le logger principal dès l'import du module
# Si l'application est multi-threadée et que setup_logger() est appelé depuis différents threads
# sans protection, il pourrait y avoir des conditions de course. 
# Pour une application PyQt, c'est généralement initialisé dans le thread principal avant que les autres ne démarrent.
if _initialized_logger is None: # Assurer l'appel unique au démarrage
    _initialized_logger = setup_logger()


# --- Test et exemple d'utilisation ---
if __name__ == '__main__':
    # Configuration de base pour le test si exécuté directement
    # (dans l'app principale, get_logger() renverra le logger déjà configuré)
    if not get_logger().hasHandlers(): # Si get_logger n'a pas déclenché setup_logger via import
        test_logger_setup = setup_logger()
    else:
        test_logger_setup = get_logger("LoggerTestMain")

    test_logger_setup.debug("Message de DEBUG du test logger.py.")
    test_logger_setup.info("Message INFO du test logger.py.")
    test_logger_setup.warning("Message WARNING du test logger.py.")
    test_logger_setup.error("Message ERROR du test logger.py.")
    test_logger_setup.critical("Message CRITICAL du test logger.py.")

    # Test d'un logger enfant
    child_logger = get_logger("ModuleTestEnfant")
    child_logger.info("Message INFO depuis le logger enfant.")

    # Simuler la connexion du handler Qt à un slot
    # (Cette partie sera dans MainWindow dans l'application réelle)
    print("\n--- Simulation de la connexion au signal Qt ---")
    if qt_log_handler: # Vérifier que le handler a été créé
        test_slot_messages = []
        def my_test_slot(message_from_signal):
            print(f"[SLOT QT SIMULÉ REÇU] {message_from_signal.strip()}")
            test_slot_messages.append(message_from_signal)

        # Connecter
        qt_log_handler.log_message_signal.connect(my_test_slot)
        
        test_logger_setup.info("Ce message devrait apparaître dans le slot Qt simulé.")
        child_logger.error("Cette erreur devrait aussi apparaître dans le slot.")
        
        # Déconnecter pour éviter des problèmes si ce script est ré-exécuté
        try:
            qt_log_handler.log_message_signal.disconnect(my_test_slot)
        except TypeError: pass # Peut arriver si déjà déconnecté ou si le slot n'était pas valide

        print(f"Messages reçus par le slot simulé: {len(test_slot_messages)}")
        assert len(test_slot_messages) >= 2, "Le signal Qt n'a pas émis correctement."
    else:
        print("qt_log_handler n'a pas été initialisé (problème dans setup_logger).")

    print("--- Test du Logger terminé. Vérifiez app_activity.log et la console. ---")