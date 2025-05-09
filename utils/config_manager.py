# mon_bot_social/utils/config_manager.py
import json
import os
from utils.logger import get_logger # Utiliser notre logger

logger = get_logger("ConfigManager") # Logger spécifique pour ce module

# Utiliser BASE_PROJECT_DIR pour construire le chemin
# S'assurer que BASE_PROJECT_DIR est défini. Il devrait l'être dans les fichiers principaux ou ici.
# Pour la portabilité de ce module, on peut le calculer relativement s'il est dans utils/
try:
    # Si ce fichier est dans mon_bot_social/utils/
    BASE_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
except NameError: # Au cas où __file__ n'est pas défini (ex: exécution interactive très spécifique)
    BASE_PROJECT_DIR = os.getcwd() # Fallback (moins robuste)

DEFAULT_SETTINGS_PATH = os.path.join(BASE_PROJECT_DIR, "data_files", "settings.json")

class ConfigManager:
    def __init__(self, settings_path=None):
        self.settings_path = settings_path or DEFAULT_SETTINGS_PATH
        self._ensure_data_files_directory_exists()
        logger.debug(f"ConfigManager initialisé avec le chemin: {self.settings_path}")

    def _ensure_data_files_directory_exists(self):
        """Crée le répertoire data_files à la racine du projet s'il n'existe pas."""
        dir_name = os.path.dirname(self.settings_path) # data_files
        if dir_name and not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name)
                logger.info(f"Répertoire '{dir_name}' créé pour les fichiers de données.")
            except OSError as e:
                logger.error(f"Erreur lors de la création du répertoire '{dir_name}': {e}")
                # Optionnel: lever une exception si la création est critique
                # raise IOError(f"Impossible de créer le répertoire de données: {dir_name}") from e

    def load_settings(self):
        """Charge les paramètres depuis le fichier JSON. Retourne un dictionnaire vide si échec."""
        self._ensure_data_files_directory_exists() # Assurer que le dossier est là avant de lire
        
        if not os.path.exists(self.settings_path):
            logger.warning(f"Fichier de configuration '{os.path.basename(self.settings_path)}' non trouvé. "
                           "Utilisation des valeurs par défaut (définies dans l'UI/code). "
                           "Un fichier sera créé à la première sauvegarde.")
            return {} 
            
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            logger.info(f"Paramètres chargés avec succès depuis '{os.path.basename(self.settings_path)}'.")
            return settings if isinstance(settings, dict) else {} # S'assurer que c'est un dict
        except json.JSONDecodeError:
            logger.error(f"Erreur de décodage JSON dans '{os.path.basename(self.settings_path)}'. Fichier potentiellement corrompu ou vide. "
                         "Sauvegardez les paramètres depuis l'UI pour recréer un fichier valide.")
            return {} 
        except Exception as e:
            logger.error(f"Erreur inattendue lors du chargement des paramètres '{os.path.basename(self.settings_path)}': {e}", exc_info=True)
            return {}

    def save_settings(self, settings_data):
        """Sauvegarde le dictionnaire de paramètres dans le fichier JSON. Retourne True si succès."""
        if not isinstance(settings_data, dict):
            logger.error("Tentative de sauvegarde de données non-dictionnaire. Opération annulée.")
            return False
            
        self._ensure_data_files_directory_exists() # Assurer que le dossier est là avant d'écrire
        
        try:
            # Créer une copie pour éviter de modifier l'original si on filtre plus tard
            # data_to_save = dict(settings_data) 
            
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=4, ensure_ascii=False) # ensure_ascii=False pour accents
            logger.info(f"Paramètres sauvegardés avec succès dans '{os.path.basename(self.settings_path)}'.")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des paramètres dans '{os.path.basename(self.settings_path)}': {e}", exc_info=True)
            return False

# Test isolé
if __name__ == '__main__':
    # S'assurer que le logger est un peu configuré pour ce test
    # Cette partie est principalement pour le test direct de CE fichier.
    # Dans l'application complète, le logger est initialisé une fois dans logger.py.
    
    # Pour éviter de reconfigurer si déjà fait (par ex. si utils.logger a été importé et initialisé)
    # On vérifie si le logger spécifique a déjà des handlers ou si le root logger en a.
    main_test_logger_instance = get_logger("ConfigManagerTest") # Utiliser un nom distinct pour le test
    if not main_test_logger_instance.handlers and not logging.getLogger().handlers: # Simple check
        import logging # Importer logging seulement pour le test
        logging.basicConfig(level=logging.DEBUG, 
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            handlers=[logging.StreamHandler()]) # S'assurer que ça loggue sur la console
        main_test_logger_instance = get_logger("ConfigManagerTest") # Ré-obtenir après config


    main_test_logger_instance.info("--- Test de ConfigManager ---")
    
    test_settings_file = os.path.join(BASE_PROJECT_DIR, "data_files", "test_settings.json")
    if os.path.exists(test_settings_file):
        try: os.remove(test_settings_file)
        except OSError as e_rem: main_test_logger_instance.warning(f"Impossible de supprimer test_settings.json avant test: {e_rem}")


    manager = ConfigManager(settings_path=test_settings_file)
    
    main_test_logger_instance.info("Test 1: Chargement fichier inexistant")
    loaded_settings = manager.load_settings()
    assert loaded_settings == {}, f"Chargement fichier inexistant devrait retourner dict vide, obtenu: {loaded_settings}"
    main_test_logger_instance.info(f"Résultat Test 1 (devrait être {{}}): {loaded_settings}")

    main_test_logger_instance.info("\nTest 2: Sauvegarde et rechargement")
    test_data = {"delay_min": 10, "delay_max": 30, "feature_x_enabled": True, "username_list": ["user1", "user2"], "description": "Test avec caractères français éàçù€"}
    save_success = manager.save_settings(test_data)
    assert save_success, "La sauvegarde aurait dû réussir."
    
    reloaded_settings = manager.load_settings()
    assert reloaded_settings == test_data, f"Données rechargées ne correspondent pas.\nAttendu: {test_data}\nObtenu: {reloaded_settings}"
    main_test_logger_instance.info(f"Résultat Test 2 - Données rechargées: {reloaded_settings}")

    main_test_logger_instance.info("\nTest 3: Chargement fichier JSON malformé")
    with open(test_settings_file, 'w', encoding='utf-8') as f:
        f.write("{'bad_json': True,") 
    malformed_settings = manager.load_settings()
    assert malformed_settings == {}, f"Chargement fichier malformé devrait retourner dict vide, obtenu: {malformed_settings}"
    main_test_logger_instance.info(f"Résultat Test 3 (devrait être {{}}): {malformed_settings}")

    main_test_logger_instance.info("\nTest 4: Sauvegarde données non-dictionnaire")
    save_fail = manager.save_settings(["ceci", "nest", "pas", "un", "dict"])
    assert not save_fail, "Sauvegarde de non-dict devrait échouer."
    main_test_logger_instance.info(f"Résultat Test 4 - Succès sauvegarde non-dict: {save_fail} (Attendu: False)")

    if os.path.exists(test_settings_file):
        try: os.remove(test_settings_file)
        except OSError as e_rem_fin: main_test_logger_instance.warning(f"Impossible de supprimer test_settings.json après test: {e_rem_fin}")
    main_test_logger_instance.info("\n--- Fin Tests ConfigManager ---")