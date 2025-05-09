# mon_bot_social/gui/settings_widget.py
import pytz
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QSpinBox,
    QCheckBox, QPushButton, QScrollArea, QFormLayout, QMessageBox, QLineEdit,
    QTimeEdit, QDoubleSpinBox, QComboBox, QTextEdit, QCompleter
)

from utils.config_manager import ConfigManager # Assurez-vous de l'import
from utils.logger import get_logger

class SettingsWidget(QWidget):
    def __init__(self, app_manager, parent=None):
        super().__init__(parent)
        self.app_manager = app_manager
        self.logger = get_logger()
        self.config_manager = ConfigManager()
        self.init_ui()
        self.load_settings()

    def _create_horizontal_spinboxes(self, spinbox1, spinbox2):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(spinbox1)
        layout.addWidget(QLabel(" à "))
        layout.addWidget(spinbox2)
        layout.addStretch(1)
        return widget

    def _create_horizontal_timeedits(self, timeedit1, timeedit2):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(timeedit1)
        layout.addWidget(QLabel(" à "))
        layout.addWidget(timeedit2)
        layout.addStretch(1)
        return widget

    def _get_value_or_default(self, data, key, default_value, widget_type="spinbox"):
        value = data.get(key, default_value)
        try:
            if widget_type == "spinbox": return int(value)
            elif widget_type == "double_spinbox": return float(value)
            elif widget_type == "checkbox": return bool(value)
            elif widget_type == "time": return QTime.fromString(value, "HH:mm")
            return value
        except (ValueError, TypeError):
            self.logger.warning(f"Valeur invalide '{value}' pour clé '{key}' (type {widget_type}). Utilisation de la valeur par défaut '{default_value}'.")
            return default_value


    def init_ui(self):
        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        scroll_content_widget = QWidget()
        scroll_area.setWidget(scroll_content_widget)
        self.content_layout = QVBoxLayout(scroll_content_widget) # Pour y ajouter les groupes

        # --- Section Horaires, Fuseau Horaire & Activité ---
        activity_time_group = QGroupBox("⏲️ Horaires, Fuseau Horaire & Activité")
        activity_time_layout = QFormLayout(activity_time_group)
        self.enable_activity_times_cb = QCheckBox("Restreindre l'activité à des plages horaires")
        activity_time_layout.addRow(self.enable_activity_times_cb)
        time_slots_data = [
            ("Plage 1 (Matin approx.):", "08:00", "11:00", "time1_start", "time1_end"),
            ("Plage 2 (Après-midi approx.):", "13:00", "16:00", "time2_start", "time2_end"),
            ("Plage 3 (Soir approx.):", "19:00", "22:30", "time3_start", "time3_end"),
        ]
        self.time_edits = {} # Stocker les QTimeEdit
        for label, default_start, default_end, start_key, end_key in time_slots_data:
            activity_time_layout.addRow(QLabel(label))
            start_edit = QTimeEdit(QTime.fromString(default_start, "HH:mm")); start_edit.setDisplayFormat("HH:mm")
            end_edit = QTimeEdit(QTime.fromString(default_end, "HH:mm")); end_edit.setDisplayFormat("HH:mm")
            self.time_edits[start_key] = start_edit; self.time_edits[end_key] = end_edit
            activity_time_layout.addRow(" Début - Fin:", self._create_horizontal_timeedits(start_edit, end_edit))
        activity_time_layout.addRow(QLabel("--- Adaptation Fuseau Horaire ---"))
        self.enable_target_timezone_cb = QCheckBox("Adapter aux plages horaires du fuseau cible"); activity_time_layout.addRow(self.enable_target_timezone_cb)
        self.target_timezone_combo = QComboBox(); common_timezones_short = ["UTC", "Europe/Paris", "Europe/London", "America/New_York", "America/Los_Angeles", "Asia/Tokyo"]
        try: # Version complète
            all_tz = sorted([tz for tz in pytz.common_timezones if "Etc/" not in tz and "SystemV" not in tz and "Factory" not in tz])
            self.target_timezone_combo.addItems(all_tz)
            self.target_timezone_combo.setCurrentText("UTC")
        except NameError: # pytz non dispo (rare si bien dans requirements)
            self.target_timezone_combo.addItems(common_timezones_short); self.target_timezone_combo.setCurrentText("UTC")
        self.target_timezone_combo.setEditable(True); self.target_timezone_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); self.target_timezone_combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        activity_time_layout.addRow("Fuseau Horaire Cible:", self.target_timezone_combo)
        self.target_timezone_combo.setEnabled(self.enable_target_timezone_cb.isChecked()); self.enable_target_timezone_cb.toggled.connect(self.target_timezone_combo.setEnabled)
        activity_time_layout.addRow(QLabel("--- Vitesse Dynamique ---"))
        self.enable_dynamic_speed_cb = QCheckBox("Varier vitesse selon plages horaires"); activity_time_layout.addRow(self.enable_dynamic_speed_cb)
        self.off_peak_delay_multiplier_spinbox = QDoubleSpinBox(); self.off_peak_delay_multiplier_spinbox.setRange(1.0, 5.0); self.off_peak_delay_multiplier_spinbox.setValue(1.5); self.off_peak_delay_multiplier_spinbox.setDecimals(1); self.off_peak_delay_multiplier_spinbox.setSuffix("x")
        activity_time_layout.addRow("Ralentissement hors plages:", self.off_peak_delay_multiplier_spinbox)
        self.content_layout.addWidget(activity_time_group)

        # --- Section Micro-Pauses, Fatigue & Sim. Réseau ---
        distraction_group = QGroupBox("🧘 Micro-Pauses, Fatigue & Simulation Réseau")
        distraction_layout = QFormLayout(distraction_group)
        self.enable_distractions_cb = QCheckBox("Activer micro-pauses aléatoires"); distraction_layout.addRow(self.enable_distractions_cb)
        self.distraction_actions_min = QSpinBox(); self.distraction_actions_min.setRange(5, 50); self.distraction_actions_min.setValue(10)
        self.distraction_actions_max = QSpinBox(); self.distraction_actions_max.setRange(10, 100); self.distraction_actions_max.setValue(25)
        distraction_layout.addRow("Nb actions AVANT micro-pause:", self._create_horizontal_spinboxes(self.distraction_actions_min, self.distraction_actions_max))
        self.distraction_duration_min_sec = QSpinBox(); self.distraction_duration_min_sec.setRange(30,300); self.distraction_duration_min_sec.setValue(60)
        self.distraction_duration_max_sec = QSpinBox(); self.distraction_duration_max_sec.setRange(60,600); self.distraction_duration_max_sec.setValue(180)
        distraction_layout.addRow("Durée micro-pause (sec):", self._create_horizontal_spinboxes(self.distraction_duration_min_sec, self.distraction_duration_max_sec))
        distraction_layout.addRow(QLabel("--- Simulation Fatigue ---"))
        self.fatigue_threshold_spinbox = QSpinBox(); self.fatigue_threshold_spinbox.setRange(0,1000); self.fatigue_threshold_spinbox.setValue(100); self.fatigue_threshold_spinbox.setSpecialValueText("Désactivé (0)")
        distraction_layout.addRow("Seuil actions avant fatigue:", self.fatigue_threshold_spinbox)
        self.fatigue_pause_multiplier_spinbox = QDoubleSpinBox(); self.fatigue_pause_multiplier_spinbox.setRange(1.0,5.0); self.fatigue_pause_multiplier_spinbox.setValue(1.8); self.fatigue_pause_multiplier_spinbox.setDecimals(1); self.fatigue_pause_multiplier_spinbox.setSuffix("x")
        distraction_layout.addRow("Multiplicateur durée micro-pause (si fatigué):", self.fatigue_pause_multiplier_spinbox)
        distraction_layout.addRow(QLabel("--- Sim. Déconnexions Réseau ---"))
        self.enable_network_disconnect_sim_cb = QCheckBox("Simuler déconnexions réseau"); distraction_layout.addRow(self.enable_network_disconnect_sim_cb)
        self.net_disconnect_interval_min_min = QSpinBox(); self.net_disconnect_interval_min_min.setRange(5,120); self.net_disconnect_interval_min_min.setValue(30)
        self.net_disconnect_interval_max_min = QSpinBox(); self.net_disconnect_interval_max_min.setRange(10,240); self.net_disconnect_interval_max_min.setValue(90)
        distraction_layout.addRow("Intervalle déconnexions (min):", self._create_horizontal_spinboxes(self.net_disconnect_interval_min_min, self.net_disconnect_interval_max_min))
        self.net_disconnect_duration_min_sec = QSpinBox(); self.net_disconnect_duration_min_sec.setRange(30,300); self.net_disconnect_duration_min_sec.setValue(60)
        self.net_disconnect_duration_max_sec = QSpinBox(); self.net_disconnect_duration_max_sec.setRange(60,600); self.net_disconnect_duration_max_sec.setValue(120)
        distraction_layout.addRow("Durée déconnexion simulée (sec):", self._create_horizontal_spinboxes(self.net_disconnect_duration_min_sec, self.net_disconnect_duration_max_sec))
        self.content_layout.addWidget(distraction_group)

        # --- Section Délais Actions ---
        delays_group = QGroupBox("⏱️ Délais entre Actions (secondes)"); delays_layout = QFormLayout(delays_group)
        delays_actions = [
            ("Follow:", "follow_delay_min", 30, "follow_delay_max", 120),
            ("Unfollow:", "unfollow_delay_min", 30, "unfollow_delay_max", 120),
            ("Like:", "like_delay_min", 20, "like_delay_max", 100),
            ("Comment:", "comment_delay_min", 60, "comment_delay_max", 180),
            ("View Story:", "view_story_delay_min", 10, "view_story_delay_max", 30),
            ("Vérif. Nouveaux Abonnés (min):", "check_followers_delay_min_minutes", 15, "check_followers_delay_max_minutes", 45), # Note: en minutes
            ("Accept Follow Req:", "accept_request_delay_min", 20, "accept_request_delay_max", 90),
            ("DM (après follow):", "dm_after_follow_delay_min", 5, "dm_after_follow_delay_max", 20), # Ajouté
            ("Like (après comment/story):", "post_interaction_like_delay_min", 3, "post_interaction_like_delay_max", 10), # Ajouté
        ]
        self.delay_spinboxes = {}
        for label, key_min, val_min, key_max, val_max in delays_actions:
            min_sb = QSpinBox(); min_sb.setRange(1, 600 if "minutes" not in label else 240); min_sb.setValue(val_min)
            max_sb = QSpinBox(); max_sb.setRange(1, 1200 if "minutes" not in label else 480); max_sb.setValue(val_max)
            if "minutes" in label: min_sb.setSuffix(" min"); max_sb.setSuffix(" min")
            else: min_sb.setSuffix(" s"); max_sb.setSuffix(" s")
            self.delay_spinboxes[key_min] = min_sb; self.delay_spinboxes[key_max] = max_sb
            delays_layout.addRow(label, self._create_horizontal_spinboxes(min_sb, max_sb))
        # Pauses occasionnelles (grosse pause)
        self.actions_before_break = QSpinBox(); self.actions_before_break.setRange(1,500); self.actions_before_break.setValue(40)
        delays_layout.addRow("Actions avant GROSSE pause:", self.actions_before_break)
        self.break_duration_min = QSpinBox(); self.break_duration_min.setRange(1,60); self.break_duration_min.setValue(5); self.break_duration_min.setSuffix(" min")
        self.break_duration_max = QSpinBox(); self.break_duration_max.setRange(1,120); self.break_duration_max.setValue(15); self.break_duration_max.setSuffix(" min")
        delays_layout.addRow("Durée GROSSE pause (min):", self._create_horizontal_spinboxes(self.break_duration_min, self.break_duration_max))
        self.stop_on_block_delay = QSpinBox(); self.stop_on_block_delay.setRange(1,1440); self.stop_on_block_delay.setValue(10); self.stop_on_block_delay.setSuffix(" min")
        delays_layout.addRow("Pause si bloqué (min):", self.stop_on_block_delay)
        self.content_layout.addWidget(delays_group)

        # --- Section Filtres Généraux & Actions Spécifiques ---
        filters_main_group = QGroupBox("🚦 Filtres Généraux & Actions Spécifiques"); filters_main_layout = QVBoxLayout(filters_main_group)
        # Filtres User (Follow)
        user_filters_group = QGroupBox("Filtres Utilisateurs (pour Follow)"); user_filters_layout = QFormLayout(user_filters_group)
        self.filter_min_posts = QSpinBox(); self.filter_min_posts.setRange(0,10000); self.filter_max_posts = QSpinBox(); self.filter_max_posts.setRange(0,50000); self.filter_max_posts.setSpecialValueText("Pas de limite (0)"); user_filters_layout.addRow("Nb Posts:", self._create_horizontal_spinboxes(self.filter_min_posts, self.filter_max_posts))
        self.filter_min_followers = QSpinBox(); self.filter_min_followers.setRange(0,1000000); self.filter_max_followers = QSpinBox(); self.filter_max_followers.setRange(0,50000000); self.filter_max_followers.setSpecialValueText("Pas de limite (0)"); user_filters_layout.addRow("Followers:", self._create_horizontal_spinboxes(self.filter_min_followers, self.filter_max_followers))
        self.filter_min_following = QSpinBox(); self.filter_min_following.setRange(0,10000); self.filter_max_following = QSpinBox(); self.filter_max_following.setRange(0,10000); self.filter_max_following.setSpecialValueText("Pas de limite (0)"); user_filters_layout.addRow("Following:", self._create_horizontal_spinboxes(self.filter_min_following, self.filter_max_following))
        self.filter_min_ratio = QDoubleSpinBox(); self.filter_min_ratio.setRange(0,100); self.filter_min_ratio.setDecimals(2); self.filter_min_ratio.setSuffix(" :1"); self.filter_min_ratio.setSpecialValueText("Pas de limite (0)")
        self.filter_max_ratio = QDoubleSpinBox(); self.filter_max_ratio.setRange(0,500); self.filter_max_ratio.setDecimals(2); self.filter_max_ratio.setSuffix(" :1"); self.filter_max_ratio.setSpecialValueText("Pas de limite (0)")
        user_filters_layout.addRow("Ratio Folr/Folw:", self._create_horizontal_spinboxes(self.filter_min_ratio, self.filter_max_ratio))
        self.filter_max_days_last_post = QSpinBox(); self.filter_max_days_last_post.setRange(0,365); self.filter_max_days_last_post.setSpecialValueText("Pas de filtre (0)"); user_filters_layout.addRow("Post récent < (jours):", self.filter_max_days_last_post)
        self.filter_bio_keywords_include = QLineEdit(); self.filter_bio_keywords_include.setPlaceholderText("voyage, photo"); user_filters_layout.addRow("Bio contient (OU):", self.filter_bio_keywords_include)
        self.filter_bio_keywords_exclude = QLineEdit(); self.filter_bio_keywords_exclude.setPlaceholderText("bot, spam"); user_filters_layout.addRow("Bio NE contient PAS (ET):", self.filter_bio_keywords_exclude)
        self.filter_profile_type_combo = QComboBox(); self.filter_profile_type_combo.addItems(["Tous", "Personnel Seulement", "Pro Seulement"]); user_filters_layout.addRow("Type Profil:", self.filter_profile_type_combo)
        self.filter_must_have_story_cb = QCheckBox("Doit avoir Story Active"); user_filters_layout.addRow(self.filter_must_have_story_cb)
        self.filter_skip_no_profile_pic_cb = QCheckBox("Ignorer si pas de photo profil"); self.filter_skip_no_profile_pic_cb.setChecked(True); user_filters_layout.addRow(self.filter_skip_no_profile_pic_cb)
        private_profile_layout = QHBoxLayout(); self.filter_skip_private_cb = QCheckBox("Ignorer privés"); self.filter_only_private_cb = QCheckBox("Seulement privés"); private_profile_layout.addWidget(self.filter_skip_private_cb); private_profile_layout.addWidget(self.filter_only_private_cb); self.filter_skip_private_cb.toggled.connect(lambda checked: self.filter_only_private_cb.setEnabled(not checked) if checked else None); self.filter_only_private_cb.toggled.connect(lambda checked: self.filter_skip_private_cb.setEnabled(not checked) if checked else None); user_filters_layout.addRow("Profils Privés:", private_profile_layout)
        filters_main_layout.addWidget(user_filters_group)
        # Filtres Photo (Like/Comment)
        photo_filters_group = QGroupBox("Filtres Photos (Like/Comment)"); photo_filters_layout = QFormLayout(photo_filters_group)
        self.photo_filter_min_age_days = QSpinBox(); self.photo_filter_min_age_days.setSpecialValueText("N/A (0)"); self.photo_filter_max_age_days = QSpinBox(); self.photo_filter_max_age_days.setRange(0,90);self.photo_filter_max_age_days.setValue(14); photo_filters_layout.addRow("Âge Photo < (jours):", self.photo_filter_max_age_days) # Simplifié
        self.photo_filter_min_likes_val = QSpinBox(); self.photo_filter_min_likes_val.setRange(0,1000); self.photo_filter_max_likes_val = QSpinBox(); self.photo_filter_max_likes_val.setRange(0,100000);self.photo_filter_max_likes_val.setSpecialValueText("Pas de limite (0)"); photo_filters_layout.addRow("Nb Likes Photo:", self._create_horizontal_spinboxes(self.photo_filter_min_likes_val, self.photo_filter_max_likes_val))
        photo_filters_layout.addRow(QLabel("--- Filtres Mots-Clés Légende (Like) ---"))
        self.like_filter_caption_include = QLineEdit(); self.like_filter_caption_include.setPlaceholderText("nature, food"); photo_filters_layout.addRow("Légende DOIT contenir (OU):", self.like_filter_caption_include)
        self.like_filter_caption_exclude = QLineEdit(); self.like_filter_caption_exclude.setPlaceholderText("concours, politique"); photo_filters_layout.addRow("Légende NE DOIT PAS (ET):", self.like_filter_caption_exclude)
        photo_filters_layout.addRow(QLabel("--- Autres Filtres Like ---"))
        self.like_filter_skip_sponsored_cb = QCheckBox("Ignorer posts sponsorisés"); self.like_filter_skip_sponsored_cb.setChecked(True); photo_filters_layout.addRow(self.like_filter_skip_sponsored_cb)
        filters_main_layout.addWidget(photo_filters_group)
        # Filtres Unfollow
        unfollow_filters_group = QGroupBox("Filtres Auto-Unfollow"); unfollow_filters_layout = QFormLayout(unfollow_filters_group)
        self.unfollow_filter_min_days_val = QSpinBox(); self.unfollow_filter_min_days_val.setRange(0,365); self.unfollow_filter_min_days_val.setValue(7); unfollow_filters_layout.addRow("Ne pas Unfollow si suivi < (j):", self.unfollow_filter_min_days_val)
        self.unfollow_filter_non_followers_cb_val = QCheckBox("Unfollow non-followers"); self.unfollow_filter_non_followers_cb_val.setChecked(True); unfollow_filters_layout.addRow(self.unfollow_filter_non_followers_cb_val)
        self.unfollow_filter_inactive_days_val = QSpinBox(); self.unfollow_filter_inactive_days_val.setRange(0,365); self.unfollow_filter_inactive_days_val.setValue(30); self.unfollow_filter_inactive_days_val.setSpecialValueText("Ne pas filtrer (0)"); unfollow_filters_layout.addRow("Unfollow si inactif > (j):", self.unfollow_filter_inactive_days_val)
        unfollow_filters_layout.addRow(QLabel("--- Filtre Ratio (Ne PAS Unfollow) ---"))
        self.unfollow_filter_ratio_min_val = QDoubleSpinBox(); self.unfollow_filter_ratio_min_val.setRange(0,100); self.unfollow_filter_ratio_min_val.setDecimals(2); self.unfollow_filter_ratio_min_val.setSuffix(" :1"); self.unfollow_filter_ratio_min_val.setSpecialValueText("Pas de limite (0)")
        self.unfollow_filter_ratio_max_val = QDoubleSpinBox(); self.unfollow_filter_ratio_max_val.setRange(0,500); self.unfollow_filter_ratio_max_val.setDecimals(2); self.unfollow_filter_ratio_max_val.setSuffix(" :1"); self.unfollow_filter_ratio_max_val.setSpecialValueText("Pas de limite (0)")
        unfollow_filters_layout.addRow("Si ratio Folr/Folw est entre:", self._create_horizontal_spinboxes(self.unfollow_filter_ratio_min_val, self.unfollow_filter_ratio_max_val))
        unfollow_filters_layout.addRow(QLabel("--- Filtre Protection Comptes Populaires ---"))
        self.unfollow_protect_min_followers_val = QSpinBox(); self.unfollow_protect_min_followers_val.setRange(0,50000000); self.unfollow_protect_min_followers_val.setValue(10000); self.unfollow_protect_min_followers_val.setSpecialValueText("Ne pas protéger (0)"); unfollow_filters_layout.addRow("NE PAS Unfollow si > (followers):", self.unfollow_protect_min_followers_val)
        filters_main_layout.addWidget(unfollow_filters_group)
        self.content_layout.addWidget(filters_main_group)

        # --- Section Options Générales & Interactions ---
        general_options_group = QGroupBox("🔧 Options Générales & Interactions"); general_options_layout = QVBoxLayout(general_options_group)
        # Checkboxes
        checkbox_options_gen = [
            ("skip_followed_before", "Ignorer users déjà suivis par le bot", False),
            ("skip_liked_photos_before", "Ignorer photos déjà likées par le bot", False),
            ("skip_commented_photos_before", "Ignorer photos déjà commentées par le bot", False),
            ("skip_users_already_following_me", "Ignorer users qui me suivent déjà (pour Follow)", False),
            ("profile_is_private", "Mon profil (du bot) est Privé (affecte Auto-Accept)", False), # Note: différent de filtre sur profil privé
            ("only_like_and_comment_photos_not_videos", "Seulement Liker/Commenter Photos (pas Vidéos/Reels)", False),
            ("manual_login", "Se connecter manuellement au démarrage du navigateur", True),
            ("minimize_to_tray", "Minimiser dans la barre des tâches système", False),
            ("auto_launch_on_windows_startup", "Lancer automatiquement au démarrage de Windows", False),
            ("disable_browser_images", "Désactiver images navigateur (perf+)", False),
            ("always_clear_cookies_on_startup", "Toujours vider cookies/cache au démarrage nav.", True),
        ]
        self.general_checkboxes = {}
        for key, label, default in checkbox_options_gen:
            cb = QCheckBox(label); cb.setChecked(default); self.general_checkboxes[key] = cb; general_options_layout.addWidget(cb)
        # Autres options SpinBox / LineEdit
        general_options_form_layout = QFormLayout()
        self.max_actions_per_session_spinbox = QSpinBox(); self.max_actions_per_session_spinbox.setRange(0,1000); self.max_actions_per_session_spinbox.setValue(150); self.max_actions_per_session_spinbox.setSpecialValueText("Illimité (0)"); general_options_form_layout.addRow("Max Actions / Session:", self.max_actions_per_session_spinbox)
        self.monitoring_check_interval_sec = QSpinBox(); self.monitoring_check_interval_sec.setRange(10,300); self.monitoring_check_interval_sec.setValue(60); self.monitoring_check_interval_sec.setSuffix(" s"); general_options_form_layout.addRow("Intervalle vérif. nouveaux posts (monitoring):", self.monitoring_check_interval_sec)
        self.monitoring_process_posts_younger_than_min = QSpinBox(); self.monitoring_process_posts_younger_than_min.setRange(1,1440); self.monitoring_process_posts_younger_than_min.setValue(60); self.monitoring_process_posts_younger_than_min.setSuffix(" min"); general_options_form_layout.addRow("Traiter posts monitoring < (min):", self.monitoring_process_posts_younger_than_min)
        self.custom_user_agent_input = QLineEdit(); self.custom_user_agent_input.setPlaceholderText("Laisser vide pour aléatoire/défaut"); general_options_form_layout.addRow("User-Agent Navigateur Personnalisé:", self.custom_user_agent_input)
        general_options_layout.addLayout(general_options_form_layout)
        # DM Options
        general_options_layout.addWidget(QLabel("--- Messages Directs (Auto-DM après Follow) ---"))
        self.dm_after_follow_cb = QCheckBox("Envoyer DM après Follow"); general_options_layout.addWidget(self.dm_after_follow_cb)
        self.dm_texts_input = QTextEdit(); self.dm_texts_input.setPlaceholderText("Salut {username}!\nSuper profil {username}!"); self.dm_texts_input.setFixedHeight(80); general_options_layout.addWidget(QLabel("Messages DM possibles (un/ligne, {username}):")); general_options_layout.addWidget(self.dm_texts_input)
        # Post-Story Interactions
        general_options_layout.addWidget(QLabel("--- Interactions Post-Story ---"))
        self.like_after_story_cb = QCheckBox("Aimer dernier post après vue Story"); general_options_layout.addWidget(self.like_after_story_cb)
        self.content_layout.addWidget(general_options_group)
        
        # --- Section Commentaires Contextuels ---
        context_comments_group = QGroupBox("💬 Commentaires Contextuels & Génériques")
        context_comments_layout = QVBoxLayout(context_comments_group)
        context_comments_layout.addWidget(QLabel("Commentaires Génériques (utilisés si aucun contextuel ne correspond, un par ligne):"))
        self.generic_comment_texts_input = QTextEdit(); self.generic_comment_texts_input.setFixedHeight(80); self.generic_comment_texts_input.setPlaceholderText("Super! 👍\nCool 😊\nBien vu!"); context_comments_layout.addWidget(self.generic_comment_texts_input)
        context_comments_layout.addWidget(QLabel("Commentaires Contextuels (Format: motclé1,motclé2:comA;comB)"))
        self.context_comments_input = QTextEdit(); self.context_comments_input.setFixedHeight(150); self.context_comments_input.setPlaceholderText("voyage,plage: Super endroit!;Profite bien!\nfood: Miam!😋"); context_comments_layout.addWidget(self.context_comments_input)
        self.content_layout.addWidget(context_comments_group)

        # --- Section Proxy ---
        proxy_group = QGroupBox("🛡️ Gestion des Proxies"); proxy_main_layout = QVBoxLayout(proxy_group)
        self.proxy_enable_cb = QCheckBox("Activer utilisation des proxies"); proxy_main_layout.addWidget(self.proxy_enable_cb)
        self.proxy_table = QTableWidget(); self.proxy_table.setColumnCount(4); self.proxy_table.setHorizontalHeaderLabels(["IP","Port","User","Pass(caché)"]); #... (config table)
        proxy_main_layout.addWidget(self.proxy_table)
        proxy_button_layout = QHBoxLayout(); self.add_proxy_button = QPushButton("➕"); self.add_proxy_button.clicked.connect(self.add_proxy_dialog); self.edit_proxy_button = QPushButton("✏️"); self.edit_proxy_button.clicked.connect(self.edit_proxy_dialog); self.remove_proxy_button = QPushButton("➖"); self.remove_proxy_button.clicked.connect(self.remove_selected_proxy); proxy_button_layout.addWidget(self.add_proxy_button); proxy_button_layout.addWidget(self.edit_proxy_button); proxy_button_layout.addWidget(self.remove_proxy_button); proxy_button_layout.addStretch(); proxy_main_layout.addLayout(proxy_button_layout)
        self.proxy_enable_cb.toggled.connect(self.toggle_proxy_list_enabled); self.toggle_proxy_list_enabled(self.proxy_enable_cb.isChecked())
        self.content_layout.addWidget(proxy_group)

        # Boutons additionnels (Exclusion, Whitelist) et Save/Load
        self.additional_controls_layout = QVBoxLayout()
        self.content_layout.addLayout(self.additional_controls_layout)
        buttons_layout = QGridLayout(); self.save_settings_button = QPushButton("💾 Sauvegarder Paramètres"); self.save_settings_button.clicked.connect(self.save_settings); self.load_settings_button = QPushButton("📂 Recharger Paramètres"); self.load_settings_button.clicked.connect(self.load_settings); buttons_layout.addWidget(self.save_settings_button,0,0); buttons_layout.addWidget(self.load_settings_button,0,1);
        self.content_layout.addLayout(buttons_layout)
        self.content_layout.addStretch(1)

    # --- Méthodes Load/Save (doivent inclure TOUS les nouveaux settings) ---
    def load_settings(self):
        settings_data = self.config_manager.load_settings()
        self.logger.debug("Chargement des paramètres UI...")
        
        # Horaires, TZ, Vitesse Dyn
        self.enable_activity_times_cb.setChecked(self._get_value_or_default(settings_data, "enable_activity_times", False, "checkbox"))
        for key, edit_widget in self.time_edits.items(): edit_widget.setTime(self._get_value_or_default(settings_data, key, QTime(8,0) if "start" in key else QTime(22,0) , "time"))
        self.enable_target_timezone_cb.setChecked(self._get_value_or_default(settings_data, "enable_target_timezone", False, "checkbox"))
        target_tz_str = settings_data.get("target_timezone", "UTC"); tz_idx = self.target_timezone_combo.findText(target_tz_str); self.target_timezone_combo.setCurrentIndex(tz_idx if tz_idx >=0 else self.target_timezone_combo.findText("UTC"))
        self.target_timezone_combo.setEnabled(self.enable_target_timezone_cb.isChecked())
        self.enable_dynamic_speed_cb.setChecked(self._get_value_or_default(settings_data, "enable_dynamic_speed", False, "checkbox"))
        self.off_peak_delay_multiplier_spinbox.setValue(self._get_value_or_default(settings_data, "off_peak_delay_multiplier", 1.5, "double_spinbox"))
        
        # Micro-Pauses, Fatigue, Sim Réseau
        self.enable_distractions_cb.setChecked(self._get_value_or_default(settings_data, "enable_distractions", False, "checkbox")) #... (charger le reste de cette section)
        self.distraction_actions_min.setValue(self._get_value_or_default(settings_data, "distraction_actions_min",10)); #...
        self.fatigue_threshold_spinbox.setValue(self._get_value_or_default(settings_data, "fatigue_threshold", 100)); #...
        self.enable_network_disconnect_sim_cb.setChecked(self._get_value_or_default(settings_data, "enable_network_disconnect_sim", False, "checkbox")); #...

        # Délais
        for key, spinbox in self.delay_spinboxes.items(): spinbox.setValue(self._get_value_or_default(settings_data, key, 30)) # Mettre de bons defaults
        self.actions_before_break.setValue(self._get_value_or_default(settings_data, "actions_before_break",40)); #...

        # Filtres User (Follow)
        self.filter_min_posts.setValue(self._get_value_or_default(settings_data, "filter_min_posts",0)); #... (charger tous les filtres user)
        self.filter_profile_type_combo.setCurrentText(settings_data.get("filter_profile_type", "Tous")); #...
        self.filter_skip_no_profile_pic_cb.setChecked(self._get_value_or_default(settings_data, "filter_skip_no_profile_pic", True, "checkbox")); #...
        
        # Filtres Photo (Like/Comment)
        self.photo_filter_max_age_days.setValue(self._get_value_or_default(settings_data, "photo_filter_max_age_days", 14)); #... (charger le reste)
        self.like_filter_caption_include.setText(settings_data.get("like_filter_caption_include","")); #...
        
        # Filtres Unfollow
        self.unfollow_filter_min_days_val.setValue(self._get_value_or_default(settings_data, "unfollow_min_days_before",7)); #... (charger le reste)
        self.unfollow_protect_min_followers_val.setValue(self._get_value_or_default(settings_data, "unfollow_protect_min_followers",10000)); #...
        
        # Options Générales & Interactions
        for key, cb_widget in self.general_checkboxes.items(): cb_widget.setChecked(self._get_value_or_default(settings_data, key, False, "checkbox")) # Ajuster defaults
        self.general_checkboxes["manual_login"].setChecked(self._get_value_or_default(settings_data, "manual_login", True, "checkbox")) # Défaut spécifique
        self.general_checkboxes["always_clear_cookies_on_startup"].setChecked(self._get_value_or_default(settings_data, "always_clear_cookies_on_startup", True, "checkbox"))
        self.max_actions_per_session_spinbox.setValue(self._get_value_or_default(settings_data, "max_actions_per_session", 150)); #... (charger le reste des options générales)
        self.dm_after_follow_cb.setChecked(self._get_value_or_default(settings_data, "dm_after_follow_enabled", False, "checkbox")); #... (charger dm_texts)
        self.like_after_story_cb.setChecked(self._get_value_or_default(settings_data, "like_after_story_enabled", False, "checkbox"));
        
        # Commentaires Contextuels & Génériques
        self.generic_comment_texts_input.setPlainText(settings_data.get("generic_comment_texts","Super! 👍\nCool 😊")) # Default value here too
        self.context_comments_input.setPlainText(settings_data.get("context_comments_definitions",""))
        
        # Proxy
        self.proxy_enable_cb.setChecked(self._get_value_or_default(settings_data, "proxy_enabled", False, "checkbox"))
        self._populate_proxy_table(); self.toggle_proxy_list_enabled(self.proxy_enable_cb.isChecked())
        
        QMessageBox.information(self, "Chargement", "Paramètres chargés depuis le fichier." if settings_data else "Fichier de config non trouvé/vide. Valeurs par défaut appliquées.")


    def save_settings(self):
        dm_texts_list = [dm.strip() for dm in self.dm_texts_input.toPlainText().split('\n') if dm.strip()]
        # User agents:
        user_agents_text = ""
        if hasattr(self, 'user_agents_input'): # Si le widget a été créé (dans Options Générales)
             user_agents_text = self.user_agents_input.toPlainText()
        user_agents_list = [ua.strip() for ua in user_agents_text.split('\n') if ua.strip()]

        settings_data = {
            "enable_activity_times": self.enable_activity_times_cb.isChecked(),
            # Time Edits (boucle)
            **{key: widget.time().toString("HH:mm") for key, widget in self.time_edits.items()},
            "enable_target_timezone": self.enable_target_timezone_cb.isChecked(),
            "target_timezone": self.target_timezone_combo.currentText(),
            "enable_dynamic_speed": self.enable_dynamic_speed_cb.isChecked(),
            "off_peak_delay_multiplier": self.off_peak_delay_multiplier_spinbox.value(),
            
            "enable_distractions": self.enable_distractions_cb.isChecked(), #... (distractions, fatigue, sim. réseau)
            "distraction_actions_min": self.distraction_actions_min.value(), #...
            "fatigue_threshold": self.fatigue_threshold_spinbox.value(), #...
            "enable_network_disconnect_sim": self.enable_network_disconnect_sim_cb.isChecked(), #...

            # Délais (boucle)
            **{key: widget.value() for key, widget in self.delay_spinboxes.items()},
            "actions_before_break": self.actions_before_break.value(), #...

            # Filtres User (Follow)
            "filter_min_posts": self.filter_min_posts.value(), #... (tous les filtres user)
            "filter_profile_type": self.filter_profile_type_combo.currentText(), #...
            "filter_skip_no_profile_pic": self.filter_skip_no_profile_pic_cb.isChecked(), #...
            
            # Filtres Photo (Like/Comment)
            "photo_filter_max_age_days": self.photo_filter_max_age_days.value(), #... (tous les filtres photo)
            "like_filter_caption_include": self.like_filter_caption_include.text(), #...
            
            # Filtres Unfollow
            "unfollow_min_days_before": self.unfollow_filter_min_days_val.value(), #... (tous les filtres unfollow)
            "unfollow_protect_min_followers": self.unfollow_protect_min_followers_val.value(), #...

            # Options Générales & Interactions (boucle sur self.general_checkboxes)
            **{key: widget.isChecked() for key, widget in self.general_checkboxes.items()},
            "max_actions_per_session": self.max_actions_per_session_spinbox.value(), #... (autres options gen.)
            "custom_user_agent_input": self.custom_user_agent_input.text() if hasattr(self,'custom_user_agent_input') else "",
            "user_agents_list": user_agents_list, # Si user_agents_input est implémenté dans Options Gén.
            "dm_after_follow_enabled": self.dm_after_follow_cb.isChecked(), #...
            "dm_after_follow_texts": dm_texts_list,
            "like_after_story_enabled": self.like_after_story_cb.isChecked(),

            # Commentaires Contextuels & Génériques
            "generic_comment_texts": [c.strip() for c in self.generic_comment_texts_input.toPlainText().split('\n') if c.strip()],
            "context_comments_definitions": self.context_comments_input.toPlainText(),
            
            # Proxy (juste l'état enabled ici, la liste est gérée par AppManager via son propre JSON)
            "proxy_enabled": self.proxy_enable_cb.isChecked(),
        }
        if self.config_manager.save_settings(settings_data):
            self.logger.info("Paramètres sauvegardés avec succès.")
            QMessageBox.information(self, "Sauvegarde", "Paramètres sauvegardés.")
            if self.app_manager: self.app_manager.update_settings() # Notifier AM
        else:
            self.logger.error("Erreur lors de la sauvegarde des paramètres.")
            QMessageBox.warning(self, "Erreur Sauvegarde", "Erreur lors de la sauvegarde.")

    # ... (Autres méthodes : toggle_proxy_list_enabled, add_proxy_dialog, etc. comme avant)
    def add_control_widget(self, widget): #...
    def toggle_proxy_list_enabled(self, enabled): #...
    def _populate_proxy_table(self): #...
    def add_proxy_dialog(self): #...
    def edit_proxy_dialog(self): #...
    def remove_selected_proxy(self): #...