# core/app_manager.py
import json
import os
import datetime
import time # For timestamps
import random # For random user agent

from utils.config_manager import ConfigManager
from utils.logger import get_logger
from .session_manager import SessionManager
from .task_scheduler import TaskScheduler
from automation_engine.browser_handler import BrowserHandler
from data_layer.database import (
    record_action, get_stats_for_period,
    add_or_update_followed_user, remove_followed_user,
    get_followed_user_details, get_all_followed_usernames,
    add_liked_post_db, has_liked_post_db,
    add_commented_post_db, has_commented_post_db,
    add_or_update_viewed_story_user, get_last_story_view_ts,
    update_following_back_status_db # Pour Unfollow filter
)

# Chemins vers les fichiers JSON (pour listes non encore en DB ou comme fallback/import)
EXCLUSION_FILE_PATH = os.path.join("data_files", "exclusion_list.json")
WHITELIST_FILE_PATH = os.path.join("data_files", "whitelist.json")
PROXY_LIST_FILE = os.path.join("data_files", "proxy_list.json")
PROCESSED_NEW_FOLLOWERS_FILE = os.path.join("data_files", "processed_new_followers.json")

class AppManager:
    def __init__(self, main_window_ref=None):
        self.logger = get_logger("AppManager")
        self.logger.info("Initialisation de AppManager...")
        
        self.main_window = main_window_ref # Référence à la fenêtre principale pour callbacks UI
        
        self.config_manager = ConfigManager()
        self.current_settings = self.config_manager.load_settings() # Charger les settings globaux

        # Initialiser les gestionnaires principaux
        self.browser_handler = BrowserHandler(self)
        self.session_manager = SessionManager(self) # SessionManager a besoin d'AppManager pour settings
        self.task_scheduler = TaskScheduler(self)   # TaskScheduler aussi

        # Listes et états gérés par AppManager
        self.last_gathered_users = []
        self.users_to_process_for_follow = []
        self.processed_users_for_follow = set() # Utilisateurs traités DANS la session de tâche Follow actuelle
        self.users_to_process_for_unfollow = []

        self.exclusion_list = set(); self._load_exclusion_list()
        self.whitelist = set(); self._load_whitelist()
        
        self.proxy_list = []; self.current_proxy_index = -1; self._load_proxy_list()
        self.proxy_usage_enabled = self.get_setting("proxy_enabled", False)

        self.processed_new_followers = set(); self._load_processed_new_followers()
        
        self.available_user_agents = []; self._load_available_user_agents()
        self.generic_comment_list = []; self.contextual_comment_map = {}; self._parse_comment_settings()
        
        self.active_task_names = set() # Pour suivre les tâches actives

        if not self.current_settings:
            self.logger.warning("Aucun fichier settings.json trouvé ou vide. Utilisation des valeurs par défaut.")
        else:
            self.logger.info("Settings chargés avec succès.")
        self.logger.info("AppManager initialisé et prêt.")

    def set_main_window(self, main_window):
        self.main_window = main_window
        self.logger.debug("Référence MainWindow définie dans AppManager.")

    def get_setting(self, key, default=None):
        return self.current_settings.get(key, default)

    def update_settings(self):
        self.logger.info("AppManager: Rechargement des paramètres globaux...")
        self.current_settings = self.config_manager.load_settings()
        
        self.proxy_usage_enabled = self.get_setting("proxy_enabled", False)
        self._load_available_user_agents()
        self._parse_comment_settings()
        
        if self.session_manager:
            self.session_manager.on_settings_updated(self.current_settings) # Notifier SessionManager
        
        self.logger.info("AppManager: Paramètres mis à jour et propagés.")
        if self.main_window: self.main_window.update_status("Paramètres mis à jour.")


    # --- Gestion Listes JSON (Exclusion, Whitelist, Proxy, Processed Followers) ---
    def _load_json_list_as_set(self, file_path, list_name="liste"):
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
                return set(item.lower() for item in data if isinstance(item, str))
            except Exception as e: self.logger.error(f"Erreur chargement {file_path} ({list_name}): {e}")
        return set()

    def _save_set_as_json_list(self, data_set, file_path, list_name="liste"):
        try:
            dir_name = os.path.dirname(file_path); #... (créer dossier si besoin)
            if dir_name and not os.path.exists(dir_name): os.makedirs(dir_name)
            with open(file_path, 'w', encoding='utf-8') as f: json.dump(sorted(list(data_set)), f, indent=4)
        except Exception as e: self.logger.error(f"Erreur sauvegarde {file_path} ({list_name}): {e}")

    def _load_exclusion_list(self): self.exclusion_list = self._load_json_list_as_set(EXCLUSION_FILE_PATH, "exclusion")
    def _save_exclusion_list(self): self._save_set_as_json_list(self.exclusion_list, EXCLUSION_FILE_PATH, "exclusion")
    def add_to_exclusion_list(self, item): #... (logique add et save)
    def remove_from_exclusion_list(self, item): #... (logique remove et save)
    def clear_exclusion_list(self): self.exclusion_list.clear(); self._save_exclusion_list()
    def is_excluded(self, item): return str(item).lower() in self.exclusion_list if item else False
    def import_exclusion_list(self, file_path): #... (logique import et save)
    def export_exclusion_list(self, file_path): #... (logique export)

    def _load_whitelist(self): self.whitelist = self._load_json_list_as_set(WHITELIST_FILE_PATH, "whitelist")
    def _save_whitelist(self): self._save_set_as_json_list(self.whitelist, WHITELIST_FILE_PATH, "whitelist")
    def add_to_whitelist(self, item): #...
    def remove_from_whitelist(self, item): #...
    def clear_whitelist(self): self.whitelist.clear(); self._save_whitelist()
    def is_whitelisted(self, item): return str(item).lower() in self.whitelist if item else False
    def import_whitelist(self, file_path): #...
    def export_whitelist(self, file_path): #...

    def _load_proxy_list(self): #... (comme avant, charge depuis PROXY_LIST_FILE)
    def _save_proxy_list(self): #... (comme avant)
    def add_proxy(self, proxy_data): #... (comme avant)
    def update_proxy(self, index, proxy_data): #... (comme avant)
    def remove_proxy(self, index): #... (comme avant)
    def get_next_proxy(self): #... (comme avant)
    def get_current_proxy_for_browser(self): #... (comme avant)

    def _load_processed_new_followers(self): self.processed_new_followers = self._load_json_list_as_set(PROCESSED_NEW_FOLLOWERS_FILE, "processed_followers")
    def _save_processed_new_followers(self): self._save_set_as_json_list(self.processed_new_followers, PROCESSED_NEW_FOLLOWERS_FILE, "processed_followers")
    def has_processed_new_follower(self, username): return username.lower() in self.processed_new_followers
    def mark_new_follower_as_processed(self, username):
        if username: self.processed_new_followers.add(username.lower()); self._save_processed_new_followers()

    def _load_available_user_agents(self): #... (comme avant, avec defaults)
    def get_random_user_agent(self): #... (comme avant)
    def _parse_comment_settings(self): #... (comme avant)
    def get_contextual_comment(self, text_content): #... (comme avant)
    def get_random_generic_comment(self): #... (comme avant)

    # --- Gestion des Actions / Interactions avec la DB ---
    def mark_user_as_followed(self, username, success=True):
        if username:
            uname_lower = username.lower()
            if success: 
                add_or_update_followed_user(uname_lower, status="followed_by_bot")
                record_action('follows') 
            self.processed_users_for_follow.add(uname_lower) 
            if self.main_window: self.main_window.log_follow_action(username, success) # log_... à supprimer dans MainWindow
    
    def mark_user_as_unfollowed(self, username, success=True): # ... (appelle remove_followed_user, record_action)
    def add_liked_post(self, post_id, like_count=None, comment_count=None): # ... (appelle add_liked_post_db, record_action)
    def has_liked_post(self, post_id): return has_liked_post_db(post_id)
    def add_commented_post(self, post_id, comment_text="", like_count=None, comment_count=None): # ... (appelle add_commented_post_db, record_action)
    def has_commented_post(self, post_id): return has_commented_post_db(post_id)
    def mark_story_as_viewed(self, username): # ... (appelle add_or_update_viewed_story_user, record_action)
    def has_viewed_story_recently(self, username, days_limit=1): # ... (appelle get_last_story_view_ts)
    def update_db_following_back_status(self, username, follows_back_status): update_following_back_status_db(username.lower(), follows_back_status)
    def get_db_followed_user_details(self, username): return get_followed_user_details(username.lower())


    # --- Démarrage / Arrêt des Tâches Principales ---
    def start_main_task(self, task_name, task_options):
        self.logger.info(f"AppManager: Demande démarrage tâche '{task_name}'...")
        if not self.current_settings: self.logger.error("Params non chargés."); return False
        if not self.browser_handler.driver and task_name not in ["manual_login_internal_command"]: # Sauf si c'est une cmd interne pour ouvrir le navigateur
            if self.get_setting("manual_login", True):
                 self.logger.error("Login manuel configuré, navigateur non ouvert. Utilisez 'Login Manuel' UI."); return False
            else: 
                 self.logger.info("Démarrage navigateur pour tâche (login auto présumé)...")
                 if not self.browser_handler.start_browser(): self.logger.error("Échec démarrage navigateur."); return False
        
        if not self.active_task_names and not self.session_manager.is_on_block_cooldown: # Si c'est la 1ere tâche active
            self.session_manager.start_logical_session()
        if self.session_manager.session_action_limit_reached_flag:
            self.logger.warning(f"Limite actions session atteinte, '{task_name}' non démarrée.")
            if self.main_window: self.main_window.show_message("Limite Session", "Limite d'actions/session atteinte.", "warning")
            return False
        
        # --- Préparation options spécifiques ---
        if task_name == "auto_follow": # ... (comme avant)
        elif task_name == "auto_unfollow":
             self.users_to_process_for_unfollow = get_all_followed_usernames() # Depuis DB
             task_options['use_app_manager_queue'] = True
             if not self.users_to_process_for_unfollow: self.logger.info("Aucun user à unfollow (DB vide)."); # ... (return False si main_window existe)
        elif task_name == "auto_like": # ... (options like_source etc.)
        elif task_name == "auto_comment": # ... (options comment_source etc.)
        elif task_name == "auto_view_stories": # ...
        elif task_name == "check_new_followers": # ...
        elif task_name == "auto_accept_requests": # ... (check profile_is_private)
        elif task_name in ["like_latest_post", "follow_single_user", "view_single_user_story", "auto_send_dm", "like_single_post"]: # Tâches uniques
             if not task_options.get('target_user') and task_name not in ["like_single_post"]: # like_single_post a target_post_id
                  if not task_options.get('target_post_id') and task_name == "like_single_post":
                     self.logger.error(f"Données manquantes pour tâche unique '{task_name}'."); return False
             self.logger.debug(f"Préparation tâche unique {task_name} OK.")
        # ... (Gather)

        if self.task_scheduler:
            success = self.task_scheduler.start_task(task_name, task_options)
            if success: self.active_task_names.add(task_name)
            if self.main_window: self.main_window.update_task_status_indicator(task_name, success) #...
            return success
        self.logger.error("TaskScheduler non disponible."); return False

    def stop_main_task(self, task_name): # ... (logique pour retirer de active_task_names, appeler session_manager.end_logical_session si vide)
        self.logger.info(f"AppManager: Demande arrêt tâche '{task_name}'...") #...

    def stop_all_active_tasks(self): # Helper si on veut un bouton "tout arrêter"
        self.logger.warning("Tentative d'arrêt de toutes les tâches actives.")
        for task_name in list(self.active_task_names): self.stop_main_task(task_name)


    # --- Handlers pour retour d'actions ---
    def on_gather_task_completed(self, success, data_or_message): # ... (met à jour last_gathered_users, UI)
    def handle_post_story_view_interaction(self, username): # ... (déclenche like_latest_post)
    def handle_post_like_interaction(self, result_data): # ... (déclenche follow_single_user, view_single_user_story)
    def handle_post_comment_interaction(self, result_data): # ... (déclenche like_single_post, follow, view)
    def handle_new_followers(self, new_follower_usernames): # ... (déclenche like_latest_post pour chaque)

    # --- Utilitaires ---
    def get_action_stats(self, period="today"): # ... (appelle get_stats_for_period)
    def save_list_to_file(self, data_list, file_path): # ... (comme avant)
    def load_list_from_file(self, file_path): # ... (comme avant)

    def perform_manual_login(self, login_url="https://www.instagram.com"): # Pour le bouton UI
        self.logger.info(f"Tentative de login manuel sur {login_url}...")
        task_options = {'url': login_url} # Peut être passé à une "action" d'ouverture de page
        # Simuler le démarrage d'une tâche interne pour que browser_handler soit appelé correctement
        # si le login manuel est activé dans les settings.
        if not self.browser_handler.driver: # Démarrer le navigateur s'il n'est pas déjà ouvert
             if not self.browser_handler.start_browser():
                  self.logger.error("Échec démarrage navigateur pour login manuel.")
                  return False
        return self.browser_handler.navigate_to(login_url)


    def shutdown(self):
        self.logger.info("Arrêt de AppManager et sauvegarde des données...")
        self._save_exclusion_list(); self._save_whitelist(); self._save_proxy_list(); self._save_processed_new_followers()
        if self.task_scheduler: self.task_scheduler.shutdown()
        if self.session_manager: self.session_manager.end_logical_session(); # Appeler end ici aussi
        if self.browser_handler: self.browser_handler.close_browser()
        self.logger.info("AppManager arrêté.")


# --- Réimplémentation des fonctions de gestion de listes JSON ---
# (Il faut s'assurer que add_to_exclusion_list, remove..., import..., export... sont bien ici)
# Par exemple:
    def add_to_exclusion_list(self, item):
        item_lower = item.lower()
        if item_lower not in self.exclusion_list:
            self.exclusion_list.add(item_lower); self._save_exclusion_list()
            self.logger.info(f"'{item}' ajouté à exclusion."); return True
        return False
    # ... et ainsi de suite pour les autres méthodes de gestion de listes.
    # Assurez-vous qu'elles appellent _save_..._list() après modification.