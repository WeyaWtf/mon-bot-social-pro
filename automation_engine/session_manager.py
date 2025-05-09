# mon_bot_social/core/session_manager.py
import time
import random
import datetime 
from PyQt6.QtCore import QTime # Nécessaire pour la comparaison des plages horaires
from utils.logger import get_logger

class SessionManager:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = self.app_manager.logger # Utiliser le logger de AppManager

        self.is_bot_globally_active = False # Indique si une tâche est censée tourner

        self.current_session_config = {} # Sera chargé par load_session_config
        self.activity_time_ranges = [] # Liste de tuples (QTime start, QTime end)

        # Grosses Pauses (Breaks)
        self.actions_since_last_break = 0
        self.is_on_break = False
        self.break_end_time = None # Timestamp Unix (float)

        # Micro-Pauses (Distractions)
        self.is_on_distraction_pause = False
        self.distraction_pause_end_time = None # Timestamp Unix
        self.actions_since_last_distraction = 0
        self.next_distraction_action_count_target = 0 

        # Limite d'actions par "session logique" de l'application
        self.current_session_total_actions = 0 
        self.session_action_limit_reached_flag = False 

        # Cooldown suite à un blocage détecté
        self.is_on_block_cooldown = False
        self.block_cooldown_end_time = None # Timestamp Unix

        # Simulation de déconnexion réseau
        self.is_on_network_sim_pause = False
        self.network_sim_pause_end_time = None # Timestamp Unix
        self.next_network_sim_trigger_time = None # Timestamp Unix

        self.logger.info("SessionManager initialisé.")
        self.load_session_config() # Charger la configuration initiale

    def _set_next_distraction_target(self):
        if not self.current_session_config.get("enable_distractions", False):
            self.next_distraction_action_count_target = -1 # Désactivé
            return

        min_act = self.current_session_config.get("distraction_actions_min", 10)
        max_act = self.current_session_config.get("distraction_actions_max", 25)
        if min_act > 0 and max_act >= min_act:
            self.next_distraction_action_count_target = random.randint(min_act, max_act)
        else:
            self.next_distraction_action_count_target = -1
        self.logger.debug(f"Prochaine micro-pause possible après {self.next_distraction_action_count_target} actions.")

    def _set_next_network_sim_trigger(self):
        if not self.current_session_config.get("enable_network_disconnect_sim", False):
            self.next_network_sim_trigger_time = None; return

        min_interval = self.current_session_config.get("net_disconnect_interval_min_min", 30)
        max_interval = self.current_session_config.get("net_disconnect_interval_max_min", 90)
        if min_interval <= 0 or max_interval < min_interval:
            self.next_network_sim_trigger_time = None; return
        
        interval_minutes = random.randint(min_interval, max_interval)
        self.next_network_sim_trigger_time = time.time() + interval_minutes * 60
        self.logger.info(f"Prochaine simulation de déconnexion réseau possible dans ~{interval_minutes} min.")


    def load_session_config(self):
        settings = self.app_manager.current_settings
        self.logger.info("SessionManager: Rechargement de la configuration de session...")
        self.current_session_config = {
            "enable_activity_times": settings.get("enable_activity_times", False),
            "time_slots_str": [ # Stocker les strings pour reconstruction facile
                (settings.get("time1_start", "08:00"), settings.get("time1_end", "11:00")),
                (settings.get("time2_start", "13:00"), settings.get("time2_end", "16:00")),
                (settings.get("time3_start", "19:00"), settings.get("time3_end", "22:30")),
            ],
            "enable_target_timezone": settings.get("enable_target_timezone", False),
            "target_timezone_str": settings.get("target_timezone", "UTC"),

            "max_actions_per_session": settings.get("max_actions_per_session", 0),

            "actions_before_break": settings.get("actions_before_break", 40),
            "break_duration_min": settings.get("break_duration_min", 5),
            "break_duration_max": settings.get("break_duration_max", 15),

            "enable_distractions": settings.get("enable_distractions", False),
            "distraction_actions_min": settings.get("distraction_actions_min", 10),
            "distraction_actions_max": settings.get("distraction_actions_max", 25),
            "distraction_duration_min_sec": settings.get("distraction_duration_min_sec", 60),
            "distraction_duration_max_sec": settings.get("distraction_duration_max_sec", 180),
            
            "fatigue_threshold": settings.get("fatigue_threshold", 0),
            "fatigue_pause_multiplier": settings.get("fatigue_pause_multiplier", 1.0),

            "enable_network_disconnect_sim": settings.get("enable_network_disconnect_sim", False),
            "net_disconnect_interval_min_min": settings.get("net_disconnect_interval_min_min", 30),
            "net_disconnect_interval_max_min": settings.get("net_disconnect_interval_max_min", 90),
            "net_disconnect_duration_min_sec": settings.get("net_disconnect_duration_min_sec", 60),
            "net_disconnect_duration_max_sec": settings.get("net_disconnect_duration_max_sec", 120),
        }
        
        self.activity_time_ranges = []
        if self.current_session_config["enable_activity_times"]:
            for start_str, end_str in self.current_session_config["time_slots_str"]:
                t_start = QTime.fromString(start_str, "HH:mm"); t_end = QTime.fromString(end_str, "HH:mm")
                if t_start.isValid() and t_end.isValid() and t_start != t_end : 
                    self.activity_time_ranges.append((t_start, t_end))
            self.logger.info(f"Plages horaires configurées: {[(t1.toString(), t2.toString()) for t1,t2 in self.activity_time_ranges]}")

        self.target_timezone_obj = None
        if self.current_session_config["enable_target_timezone"]:
            tz_str = self.current_session_config["target_timezone_str"]
            try:
                self.target_timezone_obj = pytz.timezone(tz_str)
                self.logger.info(f"Fuseau horaire cible activé: {tz_str}")
            except Exception as e_tz:
                 self.logger.error(f"Erreur init fuseau horaire {tz_str}: {e_tz}. Utilisation UTC."); self.target_timezone_obj = pytz.utc
            
        self._set_next_distraction_target()
        if not self.is_on_network_sim_pause: self._set_next_network_sim_trigger() # Ne pas reset si une pause est en cours

        # Réévaluer la limite de session
        self.session_action_limit_reached_flag = False 
        if self.current_session_total_actions > 0 and \
           self.current_session_config["max_actions_per_session"] > 0 and \
           self.current_session_total_actions >= self.current_session_config["max_actions_per_session"]:
            self.session_action_limit_reached_flag = True
            self.logger.warning("Limite d'actions/session toujours atteinte après rechargement config.")


    def _is_within_activity_time(self):
        if not self.current_session_config.get("enable_activity_times") or not self.activity_time_ranges:
            return True 

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        current_qtime_for_comparison = QTime(now_utc.hour, now_utc.minute, now_utc.second) # Par défaut UTC

        if self.target_timezone_obj: # Si adaptation TZ activée
            try:
                current_dt_in_target_tz = now_utc.astimezone(self.target_timezone_obj)
                current_qtime_for_comparison = QTime(current_dt_in_target_tz.hour, current_dt_in_target_tz.minute, current_dt_in_target_tz.second)
            except Exception as e_tz_conv: # Erreur pendant conversion (rare avec pytz)
                 self.logger.error(f"Erreur conversion heure vers TZ cible {self.target_timezone_obj}: {e_tz_conv}. Comparaison en UTC.")
        # else: On utilise l'heure locale de la machine si pas de target_timezone_obj, ce qui n'est pas idéal
        # Il faudrait un QTime.currentTime() si enable_target_timezone est False, mais la logique de UTC+target est plus propre
        # Pour l'instant, si enable_target_timezone=False, on compare avec QTime.currentTime() qui est l'heure locale
        
        if not self.current_session_config.get("enable_target_timezone"): # Si pas d'adaptation, utiliser l'heure locale de la machine
            current_qtime_for_comparison = QTime.currentTime()
        
        # logger.debug(f"Heure pour comparaison: {current_qtime_for_comparison.toString('HH:mm:ss')}")

        for start_time_q, end_time_q in self.activity_time_ranges:
            if start_time_q <= end_time_q: 
                if start_time_q <= current_qtime_for_comparison < end_time_q: return True
            else: 
                if start_time_q <= current_qtime_for_comparison or current_qtime_for_comparison < end_time_q: return True
        
        # self.logger.debug(f"Hors des plages horaires: {[(s.toString(), e.toString()) for s,e in self.activity_time_ranges]}")
        return False

    def start_logical_session(self): 
        self.logger.info("Démarrage d'une session logique d'activité (Bot START).")
        self.is_bot_globally_active = True 
        self.current_session_total_actions = 0 
        self.session_action_limit_reached_flag = False 
        self.actions_since_last_break = 0
        self.actions_since_last_distraction = 0
        self._set_next_distraction_target()
        self._set_next_network_sim_trigger() # Programmer la 1ere sim déconnexion
        self.is_on_break = False; self.break_end_time = None
        self.is_on_distraction_pause = False; self.distraction_pause_end_time = None
        # Ne pas reset is_on_block_cooldown ici
        self.load_session_config() # S'assurer que les dernières options sont chargées


    def end_logical_session(self): 
        self.logger.info("Fin de la session logique d'activité (Bot STOP).")
        self.is_bot_globally_active = False
        self.next_network_sim_trigger_time = None # Annuler les futures sim déconnexions
        
    def can_perform_action(self):
        if not self.is_bot_globally_active: return False 

        now_ts = time.time()

        if self.is_on_block_cooldown:
            if self.block_cooldown_end_time and now_ts < self.block_cooldown_end_time: return False
            else: self.logger.info("Fin Cooldown Blocage."); self.is_on_block_cooldown = False; self.block_cooldown_end_time = None;
        
        if self.session_action_limit_reached_flag: return False
        if not self._is_within_activity_time(): return False

        if self.is_on_network_sim_pause: # D'abord check la pause réseau
            if self.network_sim_pause_end_time and now_ts < self.network_sim_pause_end_time: return False
            else: self.logger.info("Fin sim. déconnexion réseau."); self.is_on_network_sim_pause = False; self.network_sim_pause_end_time = None; self._set_next_network_sim_trigger();

        if self.is_on_break: 
            if self.break_end_time and now_ts < self.break_end_time: return False
            else: self.logger.info(f"Fin grosse pause."); self.is_on_break = False; self.break_end_time = None; self.actions_since_last_break = 0;
        
        if self.is_on_distraction_pause: 
            if self.distraction_pause_end_time and now_ts < self.distraction_pause_end_time: return False
            else: self.logger.info(f"Fin micro-pause."); self.is_on_distraction_pause = False; self.distraction_pause_end_time = None; self.actions_since_last_distraction = 0; self._set_next_distraction_target();

        return True

    def increment_action_count(self):
        # Cette fonction est appelée APRÈS qu'une action a été tentée et a réussi (ou échoué mais compte quand même comme une tentative)
        if not self.is_bot_globally_active: return # Ne rien faire si le bot est globalement arrêté

        # Incrémenter seulement si on n'est PAS dans une pause qui vient de se terminer DANS CE CYCLE `can_perform_action`
        # `can_perform_action` devrait s'occuper de ne pas laisser l'action se faire si en pause.
        
        self.actions_since_last_break += 1
        self.current_session_total_actions += 1
        
        if self.current_session_config.get("enable_distractions"):
             self.actions_since_last_distraction += 1
        
        self.logger.debug(f"Compteurs actions: Break={self.actions_since_last_break}, Distraction={self.actions_since_last_distraction}/{self.next_distraction_action_count_target}, SessionTotal={self.current_session_total_actions}")

        session_limit = self.current_session_config.get("max_actions_per_session", 0)
        if session_limit > 0 and self.current_session_total_actions >= session_limit:
             self.logger.warning(f"LIMITE DE {session_limit} ACTIONS/SESSION ATTEINTE. Fin de session logique.")
             self.session_action_limit_reached_flag = True
             if self.app_manager and self.app_manager.main_window:
                 self.app_manager.main_window.update_status(f"Limite Actions ({session_limit}) atteinte. Pause session.", is_error=True, duration=300000) # 5 min
             # AppManager doit être notifié pour stopper les tâches actives
             if self.app_manager: self.app_manager.stop_all_active_tasks_due_to_session_limit()


    def should_take_break(self): 
        limit = self.current_session_config.get("actions_before_break", 0)
        return limit > 0 and self.actions_since_last_break >= limit and \
               not self.is_on_break and not self.is_on_block_cooldown and not self.is_on_network_sim_pause

    def take_break(self): 
        min_d = self.current_session_config.get("break_duration_min", 5); max_d = self.current_session_config.get("break_duration_max", 15);
        duration_m = random.randint(min_d, max_d); now_ts = time.time(); self.break_end_time = now_ts + duration_m * 60;
        self.is_on_break = True; self.actions_since_last_break = 0;
        self.logger.info(f"Début GROSSE pause ({duration_m} min). Fin ~ {datetime.datetime.fromtimestamp(self.break_end_time).strftime('%H:%M:%S')}.")
        if self.app_manager.main_window: self.app_manager.main_window.update_status(f"En pause ({duration_m} min)...", duration=duration_m * 60 * 1000);


    def should_take_distraction_pause(self):
        if not self.current_session_config.get("enable_distractions"): return False
        if self.next_distraction_action_count_target <= 0: return False
        return self.actions_since_last_distraction >= self.next_distraction_action_count_target and \
               not self.is_on_distraction_pause and not self.is_on_break and \
               not self.is_on_block_cooldown and not self.is_on_network_sim_pause

    def take_distraction_pause(self): 
        min_s = self.current_session_config.get("distraction_duration_min_sec", 60)
        max_s = self.current_session_config.get("distraction_duration_max_sec", 180)
        duration_s = random.randint(min_s, max_s)
        fatigue_info = ""; fatigue_threshold = self.current_session_config.get("fatigue_threshold",0)
        if fatigue_threshold > 0 and self.current_session_total_actions >= fatigue_threshold:
            multiplier = self.current_session_config.get("fatigue_pause_multiplier",1.0)
            if multiplier > 1.0: original_duration = duration_s; duration_s = int(duration_s * multiplier); fatigue_info = f" (Fatigué: {original_duration}s*{multiplier:.1f})"
        
        now_ts = time.time(); self.distraction_pause_end_time = now_ts + duration_s;
        self.is_on_distraction_pause = True; self.actions_since_last_distraction = 0 # Reset pour prochaine micro-pause
        # self._set_next_distraction_target() # Est appelé à la FIN de la pause
        
        self.logger.info(f"Début MICRO-pause ({duration_s} sec){fatigue_info}. Fin ~ {datetime.datetime.fromtimestamp(self.distraction_pause_end_time).strftime('%H:%M:%S')}.")
        if self.app_manager.main_window: self.app_manager.main_window.update_status(f"Micro-pause ({duration_s}s){fatigue_info}...", duration=duration_s*1000)

    def should_simulate_network_disconnect(self):
        if not self.current_session_config.get("enable_network_disconnect_sim", False) or \
           any([self.is_on_network_sim_pause, self.is_on_block_cooldown, self.is_on_break, self.is_on_distraction_pause]):
            return False
        return self.next_network_sim_trigger_time and time.time() >= self.next_network_sim_trigger_time

    def simulate_network_disconnect(self):
        min_s = self.current_session_config.get("net_disconnect_duration_min_sec", 60)
        max_s = self.current_session_config.get("net_disconnect_duration_max_sec", 120)
        duration_s = random.randint(min_s, max_s); now_ts = time.time();
        self.network_sim_pause_end_time = now_ts + duration_s
        self.is_on_network_sim_pause = True
        # Prochain trigger sera programmé à la fin de cette pause via can_perform_action
        self.logger.warning(f"SIM. DÉCONNEXION RÉSEAU ({duration_s} sec). Fin ~ {datetime.datetime.fromtimestamp(self.network_sim_pause_end_time).strftime('%H:%M:%S')}.")
        if self.app_manager.main_window: self.app_manager.main_window.update_status(f"🔌 Sim. Déco. ({duration_s}s)...", duration=duration_s*1000, is_error=True)


    def start_block_cooldown(self):
        # ... (comme avant, s'assurer qu'il met is_on_block_cooldown et is_on_break à True)
        cooldown_minutes = self.app_manager.get_setting("stop_on_block_delay", 10); #...
        if cooldown_minutes <= 0: self.logger.warning("Détection blocage, mais cooldown <=0."); return
        now_ts = time.time(); self.block_cooldown_end_time = now_ts + cooldown_minutes * 60
        self.is_on_block_cooldown = True; self.is_on_break = True; self.break_end_time = self.block_cooldown_end_time
        self.actions_since_last_break = 0; self.actions_since_last_distraction = 0; self._set_next_distraction_target();
        end_time_str = datetime.datetime.fromtimestamp(self.block_cooldown_end_time).strftime('%H:%M:%S')
        self.logger.critical(f"BLOCAGE DÉTECTÉ! Cooldown ({cooldown_minutes} min). Fin ~ {end_time_str}.")
        if self.app_manager.main_window: self.app_manager.main_window.update_status(f"🚫 Blocage! Cooldown ({cooldown_minutes} min) ~{end_time_str}", is_error=True, duration=cooldown_minutes*60*1000)


    def on_settings_updated(self, new_settings=None): # new_settings est optionnel maintenant car AM lit les settings
        self.logger.info("SessionManager: Réception notification MàJ paramètres.")
        self.load_session_config() # Recharge TOUTE la config