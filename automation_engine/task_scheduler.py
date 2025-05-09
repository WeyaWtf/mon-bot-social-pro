# core/task_scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError
import time
import random
import datetime 

# Importer les classes d'action
from automation_engine.actions.follow_action import FollowAction
from automation_engine.actions.unfollow_action import UnfollowAction
from automation_engine.actions.like_action import LikeAction
from automation_engine.actions.comment_action import CommentAction
from automation_engine.actions.view_story_action import ViewStoryAction
from automation_engine.actions.gather_action import GatherAction
from automation_engine.actions.accept_follow_request_action import AcceptFollowRequestAction
from automation_engine.actions.direct_message_action import DirectMessageAction
from automation_engine.actions.check_new_followers_action import CheckNewFollowersAction


class TaskScheduler:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = self.app_manager.logger # Utiliser le logger de AppManager
        self.scheduler = BackgroundScheduler(daemon=True) 
        self.active_tasks = {} # Clé: task_name (pour répétitives) ou job_id (pour uniques), Valeur: job object ou job_id string
        
        try:
            self.scheduler.start()
            self.logger.info("TaskScheduler: APScheduler démarré avec succès.")
        except Exception as e:
            self.logger.critical(f"TaskScheduler: ERREUR FATALE au démarrage de APScheduler: {e}", exc_info=True)
            self.scheduler = None 

    def _get_random_delay_seconds(self, min_key, max_key, default_min_sec=30, default_max_sec=60, options_override=None):
        """Calcule un délai aléatoire en SECONDES, potentiellement ajusté."""
        if options_override and options_override.get(min_key) is not None and options_override.get(max_key) is not None:
            base_min = options_override.get(min_key)
            base_max = options_override.get(max_key)
            self.logger.debug(f"Délai pour tâche utilisant override d'options: Min={base_min}, Max={base_max}")
        else:
            base_min = self.app_manager.get_setting(min_key, default_min_sec)
            base_max = self.app_manager.get_setting(max_key, default_max_sec)
        
        if base_min >= base_max: base_max = base_min + max(10, int(base_min * 0.1)) # Assurer un intervalle
        
        delay_sec = random.randint(int(base_min), int(base_max))

        # Ajustement dynamique si activé
        dynamic_speed_enabled = self.app_manager.get_setting("enable_dynamic_speed", False)
        if dynamic_speed_enabled:
            # session_manager gère _is_within_activity_time qui inclut la logique TZ
            is_peak_time = self.app_manager.session_manager._is_within_activity_time()
            if not is_peak_time:
                 multiplier = self.app_manager.get_setting("off_peak_delay_multiplier", 1.0)
                 if multiplier > 1.0:
                     original_delay_sec = delay_sec
                     delay_sec = int(delay_sec * multiplier)
                     self.logger.debug(f"Vitesse dynamique: Hors pic. Délai {original_delay_sec}s * {multiplier:.1f}x -> {delay_sec}s")
        
        return max(1, delay_sec) # Minimum 1 seconde


    def _execute_action(self, action_instance, action_name, task_options, is_one_time_task=False):
        self.logger.debug(f"Début _execute_action pour: {action_name}, OneTime: {is_one_time_task}")
        
        # 1. Vérifier simulation déconnexion réseau globale
        if self.app_manager.session_manager.should_simulate_network_disconnect():
             self.app_manager.session_manager.simulate_network_disconnect()
             self.logger.info(f"TaskScheduler: Sim. déconnexion réseau AVANT '{action_name}'. Action non exécutée.")
             return

        # 2. Vérifier les pauses "planifiées" (grosse pause, micro-pause)
        # Uniquement pour les tâches répétitives (is_one_time_task = False)
        if not is_one_time_task:
            if self.app_manager.session_manager.should_take_break():
                self.app_manager.session_manager.take_break()
                self.logger.info(f"TaskScheduler: Grosse pause déclenchée AVANT '{action_name}'. Action non exécutée."); return
            if self.app_manager.session_manager.should_take_distraction_pause():
                 self.app_manager.session_manager.take_distraction_pause()
                 self.logger.info(f"TaskScheduler: Micro-pause déclenchée AVANT '{action_name}'. Action non exécutée."); return

        # 3. Vérification générale si l'action peut être performée (heure, pauses en cours, limites)
        if not self.app_manager.session_manager.can_perform_action():
            self.logger.debug(f"TaskScheduler: Action '{action_name}' sautée (can_perform_action() = False).")
            return

        # Si on arrive ici, l'action peut s'exécuter
        self.logger.info(f"TaskScheduler: Exécution effective de '{action_name}'...")
        action_performed_successfully = False 
        result_data_or_msg_from_action = "Action non initialisée (erreur pré-exécution)."

        try:
            if not self.app_manager.browser_handler.driver and action_name not in ["manual_login_internal_command"]: # Si pas de driver et pas une commande qui l'ouvre
                 self.logger.error(f"Navigateur non disponible pour '{action_name}'.")
                 if not is_one_time_task: self.stop_task(action_name) # Arrêter la tâche répétitive
                 return

            success, result_data_or_msg_from_action = action_instance.execute(task_options)
            action_performed_successfully = success # True si l'action elle-même a réussi
            
            if success:
                self.logger.info(f"TaskScheduler: Action '{action_name}' terminée avec SUCCÈS.")
                # Gestion des retours spécifiques pour interactions en chaîne
                if action_name == "auto_like": self.app_manager.handle_post_like_interaction(result_data_or_msg_from_action)
                elif action_name == "auto_comment": self.app_manager.handle_post_comment_interaction(result_data_or_msg_from_action)
                elif action_name == "auto_view_stories":
                    if isinstance(result_data_or_msg_from_action, dict) and result_data_or_msg_from_action.get('viewed_users'): # Structure de retour modifiée
                        for user in result_data_or_msg_from_action['viewed_users']: self.app_manager.handle_post_story_view_interaction(user)
                elif action_name == "gather_users" and isinstance(result_data_or_msg_from_action, list):
                    self.app_manager.on_gather_task_completed(True, result_data_or_msg_from_action)
                elif action_name == "check_new_followers" and isinstance(result_data_or_msg_from_action, list) and result_data_or_msg_from_action:
                     self.app_manager.handle_new_followers(result_data_or_msg_from_action)
            else: # Échec de l'action
                self.logger.warning(f"TaskScheduler: Action '{action_name}' a ÉCHOUÉ. Message: {result_data_or_msg_from_action}")
                result_str = str(result_data_or_msg_from_action).upper()
                if "BLOCK" in result_str or "LIMIT" in result_str or "TRY AGAIN" in result_str:
                     self.logger.critical(f"BLOCAGE/LIMITE détecté pour '{action_name}'. Démarrage Cooldown.")
                     self.app_manager.session_manager.start_block_cooldown()
                if action_name == "gather_users": self.app_manager.on_gather_task_completed(False, result_data_or_msg_from_action)

        except Exception as e_exec:
            self.logger.exception(f"TaskScheduler: Erreur CRITIQUE pendant _execute_action '{action_name}': {e_exec}")
            if action_name == "gather_users": self.app_manager.on_gather_task_completed(False, f"Erreur critique: {e_exec}")

        finally:
            # Pour les tâches uniques, les retirer de la liste active (TaskScheduler les exécute une fois)
            if is_one_time_task:
                job_id = task_options.get('_job_id_one_time', f"{action_name}_{int(time.time())}") # Fallback
                if job_id in self.active_tasks: del self.active_tasks[job_id]
                self.logger.debug(f"Tâche unique '{action_name}' (job: {job_id}) terminée et retirée du suivi actif.")

            # Incrémenter compteur seulement pour tâches répétitives, et si l'action a VRAIMENT été tentée
            # (c-à-d pas skip par une pause ou une limite DANS CE CYCLE DE _execute_action)
            # Et si on n'est pas dans un état "File vide" qui va stopper la tâche
            if not is_one_time_task:
                # Vérifier si l'action était censée faire qqch (pas juste "file vide")
                was_productive_attempt = not ("File d'attente" in str(result_data_or_msg_from_action) and "vide" in str(result_data_or_msg_from_action))
                
                if was_productive_attempt:
                    # Ré-évaluer can_perform_action car une longue action a pu nous faire sortir d'une plage horaire par exemple
                    if self.app_manager.session_manager.can_perform_action(): # Ne pas incrémenter si une pause a commencé pendant l'action (rare)
                        self.app_manager.session_manager.increment_action_count()
                    else:
                        self.logger.info(f"Non incrémentation du compteur pour '{action_name}' car session/pause est devenue active pendant l'action.")
            
            # Informer l'UI si une tâche répétitive se termine d'elle-même (ex: file vide)
            if not is_one_time_task and not action_performed_successfully and \
               ("File d'attente" in str(result_data_or_msg_from_action) and "vide" in str(result_data_or_msg_from_action)):
                if self.app_manager.main_window:
                    self.app_manager.main_window.update_task_status_indicator(action_name, False) # Indiquer arrêt
                    self.app_manager.main_window.update_status(f"Tâche '{action_name}' terminée (file vide).")
                if action_name in self.active_tasks: del self.active_tasks[action_name] # Retirer du suivi


    def start_task(self, task_name, task_options):
        if not self.scheduler: self.logger.error("TaskScheduler: APScheduler non démarré. Tâche non planifiée."); return False
        
        is_one_time = False
        action_instance = None
        delay_min_key, delay_max_key = None, None
        default_delay_min, default_delay_max = 30, 60 # Secondes par défaut

        # Définition des actions et de leurs types
        if task_name == "auto_follow": action_instance = FollowAction(self.app_manager); delay_min_key, delay_max_key = "follow_delay_min", "follow_delay_max"
        elif task_name == "auto_unfollow": action_instance = UnfollowAction(self.app_manager); delay_min_key, delay_max_key = "unfollow_delay_min", "unfollow_delay_max"
        elif task_name == "auto_like":
            action_instance = LikeAction(self.app_manager)
            if task_options.get("like_source") == "location": # Délais spécifiques pour monitoring location
                 default_delay_min = task_options.get('location_monitor_interval_minutes', 30) * 60
                 default_delay_max = default_delay_min + 60 # Ajouter 1min de variabilité
                 delay_min_key = "_loc_like_min_s"; delay_max_key = "_loc_like_max_s" # Clés virtuelles pour options
                 task_options[delay_min_key] = default_delay_min; task_options[delay_max_key] = default_delay_max
            else: delay_min_key, delay_max_key = "like_delay_min", "like_delay_max"
        elif task_name == "auto_comment": action_instance = CommentAction(self.app_manager); delay_min_key, delay_max_key = "comment_delay_min", "comment_delay_max"
        elif task_name == "auto_view_stories": action_instance = ViewStoryAction(self.app_manager); delay_min_key, delay_max_key = "view_story_delay_min", "view_story_delay_max"
        elif task_name == "check_new_followers": action_instance = CheckNewFollowersAction(self.app_manager); delay_min_key, delay_max_key = "check_followers_delay_min_minutes", "check_followers_delay_max_minutes"; default_delay_min = 15*60; default_delay_max = 45*60 # Minutes converties en sec
        elif task_name == "auto_accept_requests": action_instance = AcceptFollowRequestAction(self.app_manager); delay_min_key, delay_max_key = "accept_request_delay_min", "accept_request_delay_max"
        elif task_name == "gather_users": action_instance = GatherAction(self.app_manager); is_one_time = True
        elif task_name == "auto_send_dm": action_instance = DirectMessageAction(self.app_manager); is_one_time = True
        elif task_name == "like_latest_post": action_instance = LikeAction(self.app_manager); is_one_time = True # options['like_source'] = 'specific_user_latest'
        elif task_name == "follow_single_user": action_instance = FollowAction(self.app_manager); is_one_time = True # options['source'] = 'post_interaction'
        elif task_name == "view_single_user_story": action_instance = ViewStoryAction(self.app_manager); is_one_time = True # options['source'] = 'post_interaction'
        elif task_name == "like_single_post": action_instance = LikeAction(self.app_manager); is_one_time = True # options['like_source'] = 'specific_post'
        else: self.logger.error(f"TaskScheduler: Tâche inconnue '{task_name}'."); return False
        
        if not action_instance: self.logger.error(f"TaskScheduler: Erreur instanciation action pour '{task_name}'."); return False

        # Vérifier si une tâche répétitive est déjà active (sauf pour les tâches uniques qui peuvent être empilées)
        if not is_one_time and task_name in self.active_tasks:
             self.logger.info(f"TaskScheduler: Tâche répétitive '{task_name}' est déjà active. Pas de replanification."); return True


        try:
            if is_one_time:
                delay_seconds = random.uniform(2, 8) # Délai pour les actions uniques
                if task_name == "auto_send_dm": delay_seconds = random.uniform(5, 15)
                run_time = datetime.datetime.now() + datetime.timedelta(seconds=delay_seconds)
                job_id = f"{task_name}_{task_options.get('target_user', task_options.get('target_post_id',''))[:10]}_{int(time.time()*1000)}" # ID unique plus robuste
                task_options['_job_id_one_time'] = job_id # Important pour le suivi dans _execute_action
                
                self.scheduler.add_job(self._execute_action, args=[action_instance, task_name, task_options, True],
                                       trigger='date', run_date=run_time, id=job_id, name=f"OneTime: {task_name[:15]}-{job_id_target[:10] if 'job_id_target' in locals() else '...'}")
                self.active_tasks[job_id] = job_id # Suivre par ID unique
                self.logger.info(f"Tâche unique '{task_name}' planifiée pour {run_time.strftime('%H:%M:%S')} (Job ID: {job_id}).")
            else: # Tâches répétitives
                if not delay_min_key: self.logger.error(f"Clés de délai manquantes pour tâche répétitive '{task_name}'."); return False
                
                # Utiliser les defaults_delay si les clés sont virtuelles (ex: pour location like)
                current_default_min = default_delay_min if '_loc_like' in delay_min_key or 'minutes' in delay_min_key else 30
                current_default_max = default_delay_max if '_loc_like' in delay_max_key or 'minutes' in delay_max_key else 60
                
                interval_seconds = self._get_random_delay_seconds(delay_min_key, delay_max_key, current_default_min, current_default_max, options_override=task_options)
                initial_job_delay = random.randint(2, 5) # Délai avant le tout premier run du job
                
                self.logger.info(f"Planification tâche répétitive '{task_name}' avec intervalle ~{interval_seconds}s (délai initial ~{initial_job_delay}s).")
                job = self.scheduler.add_job(self._execute_action, args=[action_instance, task_name, task_options, False],
                                           trigger=IntervalTrigger(seconds=interval_seconds, jitter=min(10, int(interval_seconds * 0.1))), # Jitter max 10s ou 10%
                                           id=task_name, name=f"Recurring: {task_name}", replace_existing=True,
                                           next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=initial_job_delay))
                self.active_tasks[task_name] = job # Suivre par nom de tâche

            return True
        except Exception as e_planif:
            self.logger.error(f"TaskScheduler: ERREUR lors de la PLANIFICATION de '{task_name}': {e_planif}", exc_info=True)
            # Nettoyer si une référence a été ajoutée par erreur
            if not is_one_time and task_name in self.active_tasks: del self.active_tasks[task_name]
            # Pour one-time, l'ID est unique, moins de risque ici, mais pourrait être vérifié
            return False

    def stop_task(self, task_name_or_job_id):
        if not self.scheduler: self.logger.error("TaskScheduler: APScheduler non dispo."); return False
        
        job_id_to_remove = None
        is_one_time_task_stop = False

        # Vérifier si c'est un ID de tâche unique (elles sont stockées avec leur ID comme clé)
        if task_name_or_job_id in self.active_tasks and isinstance(self.active_tasks[task_name_or_job_id], str):
             job_id_to_remove = self.active_tasks[task_name_or_job_id]
             is_one_time_task_stop = True
        # Sinon, c'est une tâche répétitive (stockée avec son nom comme clé et l'objet job comme valeur)
        elif task_name_or_job_id in self.active_tasks and hasattr(self.active_tasks[task_name_or_job_id], 'id'):
            job_id_to_remove = self.active_tasks[task_name_or_job_id].id # C'est le nom de la tâche
        # Cas où on passe directement un job_id pour une tâche unique (qui n'est pas dans active_tasks car déjà finie)
        elif isinstance(task_name_or_job_id, str) and task_name_or_job_id.startswith(("like_latest_post_","follow_single_user_", "view_single_user_story_", "auto_send_dm_", "gather_users_", "like_single_post_")):
            job_id_to_remove = task_name_or_job_id # C'est déjà un job_id
            is_one_time_task_stop = True # Marquer qu'on essaie d'arrêter un job unique (peut-être déjà fini)

        if job_id_to_remove:
            try:
                self.scheduler.remove_job(job_id_to_remove)
                self.logger.info(f"TaskScheduler: Job '{job_id_to_remove}' retiré du scheduler.")
            except JobLookupError: # Le job n'existe plus (peut-être déjà fini si one-time)
                self.logger.debug(f"Job '{job_id_to_remove}' non trouvé dans APScheduler (déjà fini ou jamais existé?).")
            except Exception as e_rem: 
                self.logger.error(f"Erreur APScheduler remove_job '{job_id_to_remove}': {e_rem}"); return False # Problème plus grave
            
            # Nettoyer self.active_tasks
            key_to_delete_from_active = task_name_or_job_id if is_one_time_task_stop or isinstance(self.active_tasks.get(task_name_or_job_id), str) else task_name_or_job_id
            if key_to_delete_from_active in self.active_tasks:
                 del self.active_tasks[key_to_delete_from_active]
                 self.logger.debug(f"'{key_to_delete_from_active}' retiré de active_tasks.")
            return True
        else:
            self.logger.warning(f"Tâche/Job ID '{task_name_or_job_id}' non trouvé dans active_tasks pour arrêt."); return False

    # La méthode pause_task_on_block est toujours là, mais son appel a été intégré dans SessionManager.start_block_cooldown
    # qui est ensuite appelé par _execute_action si un "BLOCK" est détecté.
    # On pourrait la garder si on veut un mécanisme de pause de TÂCHE spécifique hors blocage global.
    # Pour l'instant, on la commente ou on la supprime si elle n'est plus utilisée.
    # def pause_task_on_block(self, task_name): ... 

    def shutdown(self):
        if self.scheduler and self.scheduler.running:
            self.logger.info("TaskScheduler: Arrêt de APScheduler...")
            try: self.scheduler.shutdown(wait=False); self.logger.info("TaskScheduler: APScheduler arrêté.")
            except Exception as e: self.logger.error(f"TaskScheduler: Erreur arrêt APScheduler: {e}", exc_info=True)