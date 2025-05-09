# mon_bot_social/gui/main_window.py
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QTabWidget, 
    QPushButton, QMessageBox, QLineEdit, QFormLayout, 
    QTextEdit, QHBoxLayout, QSpinBox, QComboBox,  
    QPlainTextEdit, QCheckBox, QStatusBar, 
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, 
    QFileDialog, QGroupBox
)
from PyQt6.QtCore import pyqtSlot, Qt, QCoreApplication # Qt pour AlignmentFlag, QCoreApplication pour clipboard
from PyQt6.QtGui import QIcon # Optionnel pour icônes

# Importer les widgets personnalisés et le logger
from utils.logger import get_logger, qt_log_handler
from .settings_widget import SettingsWidget
from .exclusion_widget import ExclusionWidget
from .whitelist_widget import WhitelistWidget
from .stats_widget import StatsWidget

class MainWindow(QMainWindow):
    def __init__(self, app_manager, parent=None):
        super().__init__(parent)
        self.app_manager = app_manager
        self.logger = get_logger()
        
        self.setWindowTitle("Mon Bot Social Pro")
        self.setGeometry(100, 100, 950, 800) # Légèrement agrandi

        # Tâches actives
        self.task_widgets = {} # clé=task_name, valeur={'start_btn': btn, 'stop_btn': btn, 'status_label': lbl}

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        self._create_tabs()
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("Prêt.") 

        if qt_log_handler:
             qt_log_handler.log_message_signal.connect(self.append_log_message)
             self.logger.info("Interface principale initialisée et connectée au logger.")
        else:
             self.logger.error("Handler de log Qt non trouvé. Logs UI désactivés.")
        
        # Optionnel: Connecter le changement d'onglet pour rafraîchir les stats
        # self.tab_widget.currentChanged.connect(self._handle_tab_changed)


    def _create_task_controls(self, parent_layout, task_name, friendly_task_name="Tâche"):
        """Helper pour créer les boutons Start/Stop et le label de statut."""
        control_layout = QHBoxLayout()
        start_button = QPushButton(f"🚀 Démarrer {friendly_task_name}")
        stop_button = QPushButton(f"🛑 Arrêter {friendly_task_name}")
        status_label = QLabel("Prêt")
        status_label.setStyleSheet("font-style: italic; color: gray;")
        status_label.setMinimumWidth(100) # Pour éviter que le layout change trop

        # Connecter au handler spécifique pour cette tâche
        if task_name == "auto_follow": start_button.clicked.connect(self.handle_start_follow)
        elif task_name == "auto_unfollow": start_button.clicked.connect(self.handle_start_unfollow)
        elif task_name == "auto_like": start_button.clicked.connect(self.handle_start_like)
        elif task_name == "auto_comment": start_button.clicked.connect(self.handle_start_comment)
        elif task_name == "auto_view_stories": start_button.clicked.connect(self.handle_start_view_stories)
        elif task_name == "auto_accept_requests": start_button.clicked.connect(self.handle_start_accept_requests)
        elif task_name == "check_new_followers": start_button.clicked.connect(self.handle_start_check_new_followers)
        else: self.logger.warning(f"Pas de handler de démarrage spécifique défini pour la tâche: {task_name}")

        stop_button.clicked.connect(lambda checked=False, t=task_name: self.stop_task(t))
        
        self.task_widgets[task_name] = {'start_btn': start_button, 'stop_btn': stop_button, 'status_label': status_label}
        
        control_layout.addWidget(start_button); control_layout.addWidget(stop_button)
        control_layout.addWidget(status_label); control_layout.addStretch(1)
        parent_layout.addLayout(control_layout)
        self.update_task_status_indicator(task_name, False)

    def _create_tabs(self):
        # Onglet Logs
        self.logs_tab = QWidget(); self.tab_widget.addTab(self.logs_tab, "📜 Logs")
        logs_layout = QVBoxLayout(self.logs_tab)
        self.log_display_area = QPlainTextEdit(); self.log_display_area.setReadOnly(True); self.log_display_area.setMaximumBlockCount(5000)
        logs_layout.addWidget(self.log_display_area)
        clear_log_button = QPushButton("Vider l'Affichage des Logs"); clear_log_button.clicked.connect(self.log_display_area.clear)
        logs_layout.addWidget(clear_log_button)

        # Onglet Stats
        self.stats_tab = StatsWidget(app_manager=self.app_manager, parent=self)
        self.tab_widget.addTab(self.stats_tab, "📊 Statistiques")

        # Onglet Actions / Compte
        self.account_action_tab = QWidget(); self.tab_widget.addTab(self.account_action_tab, "🚀 Actions / Compte")
        account_action_layout = QVBoxLayout(self.account_action_tab)
        login_group = QGroupBox("Connexion Manuelle"); login_group_layout = QFormLayout(login_group)
        self.target_url_input = QLineEdit("https://www.instagram.com"); login_group_layout.addRow("URL de connexion:", self.target_url_input)
        self.manual_login_button = QPushButton("🌐 Ouvrir pour Login Manuel"); self.manual_login_button.clicked.connect(self.handle_manual_login)
        login_group_layout.addRow(self.manual_login_button); account_action_layout.addWidget(login_group)
        
        new_follower_check_group = QGroupBox("Vérification Nouveaux Abonnés (en arrière-plan)")
        new_follower_check_layout = QVBoxLayout(new_follower_check_group)
        self._create_task_controls(new_follower_check_layout, "check_new_followers", "Vérif. Nouveaux Abonnés")
        account_action_layout.addWidget(new_follower_check_group)
        account_action_layout.addStretch(1)

        # Onglet Gather
        self.gather_tab = QWidget(); self.tab_widget.addTab(self.gather_tab, "📊 Gather")
        gather_layout = QVBoxLayout(self.gather_tab)
        gather_options_group = QGroupBox("Options Collecte Hashtags"); gather_options_form = QFormLayout(gather_options_group)
        self.hashtags_input = QTextEdit(); self.hashtags_input.setPlaceholderText("tag1, tag2\ntag3"); self.hashtags_input.setFixedHeight(80); gather_options_form.addRow("Hashtags:", self.hashtags_input)
        self.gather_limit_spinbox = QSpinBox(); self.gather_limit_spinbox.setRange(0, 50000); self.gather_limit_spinbox.setValue(1000); self.gather_limit_spinbox.setSpecialValueText("Illimité (0)"); gather_options_form.addRow("Limite/tâche:", self.gather_limit_spinbox)
        self.max_users_per_hashtag_spinbox = QSpinBox(); self.max_users_per_hashtag_spinbox.setRange(5, 1000); self.max_users_per_hashtag_spinbox.setValue(50); gather_options_form.addRow("Max/hashtag:", self.max_users_per_hashtag_spinbox)
        self.scroll_count_spinbox = QSpinBox(); self.scroll_count_spinbox.setRange(1, 50); self.scroll_count_spinbox.setValue(3); gather_options_form.addRow("Nb scrolls/page:", self.scroll_count_spinbox)
        gather_layout.addWidget(gather_options_group)
        self.start_gather_button = QPushButton("🚀 Démarrer Collecte"); self.start_gather_button.clicked.connect(self.handle_start_gather_users)
        gather_status_label = QLabel("Prêt."); gather_control_layout = QHBoxLayout(); gather_control_layout.addWidget(self.start_gather_button); gather_control_layout.addWidget(gather_status_label); gather_control_layout.addStretch()
        gather_layout.addLayout(gather_control_layout); self.task_widgets['gather_users'] = {'start_btn': self.start_gather_button, 'stop_btn': None, 'status_label': gather_status_label}
        gather_layout.addWidget(QLabel("Utilisateurs collectés:"))
        self.gathered_table_widget = QTableWidget(); self.gathered_table_widget.setColumnCount(1); self.gathered_table_widget.setHorizontalHeaderLabels(["Nom d'utilisateur"]); self.gathered_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch); self.gathered_table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.gathered_table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.gathered_table_widget.setAlternatingRowColors(True);
        gather_layout.addWidget(self.gathered_table_widget)
        list_manage_layout = QGridLayout(); save_g = QPushButton("💾 Sauver"); save_g.clicked.connect(self.save_gathered_list); load_g = QPushButton("📂 Charger"); load_g.clicked.connect(self.load_gathered_list); clear_g = QPushButton("🗑️ Vider"); clear_g.clicked.connect(self.clear_gathered_display_and_memory); copy_g = QPushButton("📋 Copier"); copy_g.clicked.connect(self.copy_gathered_list); send_f = QPushButton("➡️ Vers Follow"); send_f.clicked.connect(self.send_gathered_to_follow)
        list_manage_layout.addWidget(save_g,0,0); list_manage_layout.addWidget(load_g,0,1); list_manage_layout.addWidget(clear_g,0,2); list_manage_layout.addWidget(copy_g,1,0); list_manage_layout.addWidget(send_f,1,1,1,2);
        gather_layout.addLayout(list_manage_layout)

        # Onglet Auto-Follow
        self.follow_tab = QWidget(); self.tab_widget.addTab(self.follow_tab, "➕ Follow")
        follow_layout = QVBoxLayout(self.follow_tab)
        follow_options_group = QGroupBox("Options d'Auto-Follow"); follow_options_form = QFormLayout(follow_options_group)
        self.follow_source_combo = QComboBox(); self.follow_source_combo.addItems(["Liste collectée", "Liste manuelle"]); self.follow_source_combo.currentIndexChanged.connect(self.toggle_manual_follow_list_visibility)
        follow_options_form.addRow("Source utilisateurs:", self.follow_source_combo)
        self.manual_follow_list_label = QLabel("Liste manuelle (un/ligne):"); self.manual_follow_list_input = QTextEdit(); self.manual_follow_list_input.setFixedHeight(100); self.manual_follow_list_label.hide(); self.manual_follow_list_input.hide();
        follow_options_form.addRow(self.manual_follow_list_label); follow_options_form.addRow(self.manual_follow_list_input)
        follow_layout.addWidget(follow_options_group)
        self._create_task_controls(follow_layout, "auto_follow", "Auto-Follow")
        follow_layout.addStretch(1)

        # Onglet Auto-Unfollow
        self.unfollow_tab = QWidget(); self.tab_widget.addTab(self.unfollow_tab, "➖ Unfollow")
        unfollow_layout = QVBoxLayout(self.unfollow_tab)
        unfollow_layout.addWidget(QLabel("Options configurables dans Settings > Filtres Unfollow."))
        self._create_task_controls(unfollow_layout, "auto_unfollow", "Auto-Unfollow")
        unfollow_layout.addStretch(1)

        # Onglet Auto-Like
        self.like_tab = QWidget(); self.tab_widget.addTab(self.like_tab, "❤️ Like")
        like_layout = QVBoxLayout(self.like_tab); like_options_group = QGroupBox("Options d'Auto-Like"); like_options_form = QFormLayout(like_options_group)
        self.like_source_main_combo = QComboBox(); self.like_source_main_combo.addItems(["Feed", "X derniers posts d'utilisateurs", "Monitorer une Localisation"]); self.like_source_main_combo.currentIndexChanged.connect(self.toggle_like_options_visibility)
        like_options_form.addRow("Source:", self.like_source_main_combo)
        self.like_user_source_group = QGroupBox("Source Utilisateurs (pour 'X derniers posts')"); self.like_user_source_group.setVisible(False); like_user_source_layout = QFormLayout(self.like_user_source_group)
        self.like_user_source_combo = QComboBox(); self.like_user_source_combo.addItems(["Liste collectée", "Liste manuelle"]); self.like_user_source_combo.currentIndexChanged.connect(self.toggle_manual_like_user_list_visibility)
        like_user_source_layout.addRow("Utilisateurs:", self.like_user_source_combo); self.manual_like_user_list_label = QLabel("Liste manuelle:"); self.manual_like_user_list_input = QTextEdit(); self.manual_like_user_list_label.hide(); self.manual_like_user_list_input.hide(); like_user_source_layout.addRow(self.manual_like_user_list_label); like_user_source_layout.addRow(self.manual_like_user_list_input)
        self.num_posts_to_like_per_user_spinbox = QSpinBox(); self.num_posts_to_like_per_user_spinbox.setRange(1,10);self.num_posts_to_like_per_user_spinbox.setValue(1); like_user_source_layout.addRow("Nb posts/user:", self.num_posts_to_like_per_user_spinbox)
        self.max_users_to_process_like_spinbox = QSpinBox(); self.max_users_to_process_like_spinbox.setRange(1,100);self.max_users_to_process_like_spinbox.setValue(5); like_user_source_layout.addRow("Max users/tâche:", self.max_users_to_process_like_spinbox)
        like_options_form.addRow(self.like_user_source_group)
        self.like_location_source_group = QGroupBox("Source Localisation"); self.like_location_source_group.setVisible(False); like_location_layout = QFormLayout(self.like_location_source_group)
        self.like_location_input = QLineEdit(); self.like_location_input.setPlaceholderText("ID ou Nom exact"); like_location_layout.addRow("Localisation:", self.like_location_input)
        self.like_location_monitor_interval_spinbox = QSpinBox(); self.like_location_monitor_interval_spinbox.setRange(1,1440);self.like_location_monitor_interval_spinbox.setValue(30);self.like_location_monitor_interval_spinbox.setSuffix(" min"); like_location_layout.addRow("Vérifier toutes les:", self.like_location_monitor_interval_spinbox)
        self.like_location_max_age_minutes_spinbox = QSpinBox(); self.like_location_max_age_minutes_spinbox.setRange(1,1440);self.like_location_max_age_minutes_spinbox.setValue(60);self.like_location_max_age_minutes_spinbox.setSuffix(" min"); like_location_layout.addRow("Aimer posts <:", self.like_location_max_age_minutes_spinbox)
        like_options_form.addRow(self.like_location_source_group)
        self.num_likes_per_run_label = QLabel("Limite likes/tâche:"); self.num_likes_per_run_spinbox = QSpinBox(); self.num_likes_per_run_spinbox.setRange(1,50);self.num_likes_per_run_spinbox.setValue(5); like_options_form.addRow(self.num_likes_per_run_label, self.num_likes_per_run_spinbox)
        like_layout.addWidget(like_options_group)
        post_like_actions_group = QGroupBox("Actions après Like"); post_like_layout = QVBoxLayout(post_like_actions_group);
        self.like_then_follow_cb = QCheckBox("Suivre propriétaire"); post_like_layout.addWidget(self.like_then_follow_cb)
        self.like_then_view_story_cb = QCheckBox("Voir story propriétaire"); post_like_layout.addWidget(self.like_then_view_story_cb)
        like_layout.addWidget(post_like_actions_group)
        self._create_task_controls(like_layout, "auto_like", "Auto-Like")
        like_layout.addStretch(1); self.toggle_like_options_visibility(0)

        # Onglet Auto-Comment
        self.comment_tab = QWidget(); self.tab_widget.addTab(self.comment_tab, "💬 Comment") #... (UI comme like tab avec comment_texts_input, comment_then_like_cb etc.)
        # ... construction UI Auto-Comment avec ses options spécifiques ...
        # self.comment_texts_input = QTextEdit() ...
        # self.comment_then_like_cb = QCheckBox(...)
        # self.comment_then_follow_cb = QCheckBox(...)
        # self.comment_then_view_story_cb = QCheckBox(...)
        # self._create_task_controls(comment_layout, "auto_comment", "Auto-Comment")
        
        # Onglet Auto-View Stories
        self.view_stories_tab = QWidget(); self.tab_widget.addTab(self.view_stories_tab, "👀 View Stories") #... (UI comme défini avant avec partial view etc.)
        # ... construction UI View Stories avec options de visionnage partiel ...
        # self.story_partial_view_cb = QCheckBox(...)
        # self.story_partial_min_segments_spinbox = QSpinBox(...)
        # self._create_task_controls(view_stories_layout, "auto_view_stories", "Auto-View Stories")

        # Onglet Auto-Accept
        self.accept_tab = QWidget(); self.tab_widget.addTab(self.accept_tab, "✔️ Accept") #... (UI avec profile private cb, num requests spinbox)
        # self.profile_private_checkbox = QCheckBox(...)
        # self._create_task_controls(accept_layout, "auto_accept_requests", "Auto-Accept")

        # Onglet Settings
        self.settings_content_widget = SettingsWidget(app_manager=self.app_manager, parent=self)
        self.tab_widget.addTab(self.settings_content_widget, "⚙️ Settings")
        exclusion_btn_group = QGroupBox("Listes de Contrôle"); exclusion_btn_layout = QVBoxLayout()
        manage_exclusion_button = QPushButton("🚫 Gérer Liste d'Exclusion..."); manage_exclusion_button.clicked.connect(self.open_exclusion_manager); exclusion_btn_layout.addWidget(manage_exclusion_button)
        manage_whitelist_button = QPushButton("👍 Gérer Whitelist..."); manage_whitelist_button.clicked.connect(self.open_whitelist_manager); exclusion_btn_layout.addWidget(manage_whitelist_button)
        exclusion_btn_group.setLayout(exclusion_btn_layout)
        self.settings_content_widget.add_control_widget(exclusion_btn_group)
        
        # Charger les textes des commentaires ici pour affichage au démarrage
        if hasattr(self, 'comment_texts_input'): # S'assurer qu'il est créé
            dm_texts = self.app_manager.current_settings.get("dm_after_follow_texts", []) # Réutiliser la même clé ? Ou en créer une nouvelle
            self.comment_texts_input.setPlainText("\n".join(self.app_manager.generic_comment_list or dm_texts))


    @pyqtSlot(str) 
    def append_log_message(self, message): self.log_display_area.appendPlainText(message.strip())

    def update_task_status_indicator(self, task_name, is_running):
        widgets = self.task_widgets.get(task_name)
        if widgets:
            if widgets['start_btn']: widgets['start_btn'].setEnabled(not is_running)
            if widgets['stop_btn']: widgets['stop_btn'].setEnabled(is_running)
            status_text = "En cours..." if is_running else "Prêt"
            status_color = "green" if is_running else "gray"
            widgets['status_label'].setText(status_text); widgets['status_label'].setStyleSheet(f"font-style: italic; color: {status_color};")

    # --- Méthodes de mise à jour UI spécifiques ---
    def update_gathered_list_display(self, gathered_list): # ... (logique pour QTableWidget comme avant)
    def copy_gathered_list(self): # ... (logique pour QTableWidget comme avant)
    def save_gathered_list(self): # ... (logique QFileDialog, app_manager.save_list_to_file)
    def load_gathered_list(self): # ... (logique QFileDialog, app_manager.load_list_from_file)
    def clear_gathered_display_and_memory(self): # ... (vider table et app_manager.last_gathered_users)
    def send_gathered_to_follow(self): # ... (copier vers onglet Follow)

    # --- Handlers de démarrage ---
    # (Déjà existants, s'assurer qu'ils passent les bonnes options)
    def handle_start_follow(self): 
        options = {'source_type': "gathered_list" if self.follow_source_combo.currentText() == "Liste collectée" else "manual_list"}
        if options['source_type'] == "manual_list": options['manual_user_list'] = [u.strip() for u in self.manual_follow_list_input.toPlainText().split('\n') if u.strip()]
        self.start_task("auto_follow", options)
    
    def handle_start_unfollow(self): self.start_task("auto_unfollow", {}) 
    
    def handle_start_like(self):
        options = {'like_then_follow': self.like_then_follow_cb.isChecked(), 'like_then_view_story': self.like_then_view_story_cb.isChecked()}
        main_source = self.like_source_main_combo.currentText()
        options['num_likes_per_run'] = self.num_likes_per_run_spinbox.value()
        if main_source == "Aimer les posts du Feed": options['like_source'] = "feed"
        elif main_source == "Aimer les X derniers posts d'utilisateurs":
            options['like_source'] = "users_last_posts"
            options['num_posts_to_like_per_user'] = self.num_posts_to_like_per_user_spinbox.value()
            options['max_users_to_process_this_run'] = self.max_users_to_process_like_spinbox.value()
            user_source_text = self.like_user_source_combo.currentText()
            if user_source_text == "Liste collectée": options['user_source_for_like'] = "gathered_list"
            elif user_source_text == "Liste manuelle": 
                options['user_source_for_like'] = "manual_list"
                options['manual_user_list_for_like'] = [u.strip() for u in self.manual_like_user_list_input.toPlainText().split('\n') if u.strip()]
        elif main_source == "Monitorer une Localisation":
            options['like_source'] = "location"
            options['location_target'] = self.like_location_input.text().strip()
            options['location_monitor_interval_minutes'] = self.like_location_monitor_interval_spinbox.value()
            options['location_max_post_age_minutes'] = self.like_location_max_age_minutes_spinbox.value()
        else: self.show_message("Auto-Like", "Source non supportée.", "warning"); return
        self.start_task("auto_like", options)

    def handle_start_comment(self):
        # Recréer la logique pour comment car le code pour l'onglet a été omis dans le prompt précédent
        # Supposons que les widgets pour l'onglet Comment sont:
        # self.comment_source_main_combo, self.comment_user_source_group, self.comment_user_source_combo, 
        # self.manual_comment_user_list_input, self.num_posts_to_comment_per_user_spinbox,
        # self.max_users_to_process_comment_spinbox, self.num_comments_per_run_spinbox,
        # self.comment_texts_input, self.comment_then_like_cb, self.comment_then_follow_cb, self.comment_then_view_story_cb
        
        options = {
            'comment_then_like': self.comment_then_like_cb.isChecked() if hasattr(self, 'comment_then_like_cb') else False,
            'comment_then_follow': self.comment_then_follow_cb.isChecked() if hasattr(self, 'comment_then_follow_cb') else False,
            'comment_then_view_story': self.comment_then_view_story_cb.isChecked() if hasattr(self, 'comment_then_view_story_cb') else False,
        }
        comment_texts_list = [c.strip() for c in self.comment_texts_input.toPlainText().split('\n') if c.strip()]
        if not comment_texts_list: self.show_message("Auto-Comment", "Liste commentaires vide.", "warning"); return
        options['comment_texts'] = comment_texts_list # Passé à AppManager qui va le stocker/utiliser

        main_source = self.comment_source_main_combo.currentText()
        options['num_comments_per_run'] = self.num_comments_per_run_spinbox.value()

        if main_source == "Commenter les posts du Feed": options['comment_source'] = "feed"
        elif main_source == "Commenter les X derniers posts d'utilisateurs":
            options['comment_source'] = "users_last_posts"
            options['num_posts_to_comment_per_user'] = self.num_posts_to_comment_per_user_spinbox.value()
            options['max_users_to_process_comment_run'] = self.max_users_to_process_comment_spinbox.value()
            user_source_text = self.comment_user_source_combo.currentText()
            if user_source_text == "Liste collectée": options['user_source_for_comment'] = "gathered_list"
            elif user_source_text == "Liste manuelle":
                options['user_source_for_comment'] = "manual_list"
                options['manual_user_list_for_comment'] = [u.strip() for u in self.manual_comment_user_list_input.toPlainText().split('\n') if u.strip()]
        else: self.show_message("Auto-Comment", "Source non supportée.", "warning"); return
        
        self.start_task("auto_comment", options)

    def handle_start_view_stories(self): # (comme défini avant, avec les options partial view)
        options = {'skip_users_viewed_less_than_x_days': self.skip_viewed_days_spinbox.value()}
        options['partial_view_enabled'] = self.story_partial_view_cb.isChecked()
        options['partial_view_min_segments'] = self.story_partial_min_segments_spinbox.value()
        options['partial_view_max_segments'] = self.story_partial_max_segments_spinbox.value()
        # ... (récupérer source principale, listes users etc.)
        self.start_task("auto_view_stories", options)

    def handle_start_accept_requests(self):
        options = {'num_requests_to_accept_per_run': self.num_requests_to_accept_spinbox.value()}
        self.start_task("auto_accept_requests", options)

    def handle_start_check_new_followers(self): # Pour le bouton dans "Actions / Compte"
        self.start_task("check_new_followers", {}) # Pas d'options spécifiques depuis l'UI ici

    # --- Start/Stop Tâche générique ---
    def start_task(self, task_name, task_options):
        self.logger.info(f"UI: Demande démarrage tâche '{task_name}'")
        self.update_task_status_indicator(task_name, True) # MàJ UI optimiste
        if not self.app_manager.start_main_task(task_name, task_options):
            self.update_task_status_indicator(task_name, False) # Rollback UI si échec immédiat
            # self.show_message("Erreur", f"Impossible de démarrer '{task_name}'. Vérifiez logs/settings.", "error") # Message déjà dans AppManager

    def stop_task(self, task_name):
        self.logger.info(f"UI: Demande arrêt tâche '{task_name}'")
        self.app_manager.stop_main_task(task_name) # AppManager notifiera l'UI via update_task_status_indicator

    # --- Gestion des fenêtres/dialogues externes ---
    def open_exclusion_manager(self): self.exclusion_window = ExclusionWidget(self.app_manager); self.exclusion_window.show() 
    def open_whitelist_manager(self): self.whitelist_window = WhitelistWidget(self.app_manager); self.whitelist_window.show()
    
    # --- Callbacks depuis AppManager (pour logs spécifiques onglet si gardé, ou autre) ---
    # (Ces méthodes sont maintenant remplacées par des appels directs à self.logger.info(...) depuis AppManager)
    # def log_follow_action(self, username, success): ...
    # def log_unfollow_action(self, username, success): ...
    # etc.
    
    def update_status(self, message, is_error=False, duration=5000): #... (comme avant)

    def show_message(self, title, message, level="info"): #... (comme avant)
    
    def closeEvent(self, event): #... (comme avant)

    # --- Méthodes de gestion de visibilité UI (pour ComboBoxes) ---
    def toggle_manual_follow_list_visibility(self, index): #... (comme avant)
    def toggle_like_options_visibility(self, index): #... (comme avant, gère user group et location group)
    def toggle_manual_like_user_list_visibility(self, index): #... (comme avant)
    def toggle_comment_options_visibility(self, index): # Similaire à like
        source_text = self.comment_source_main_combo.currentText()
        is_users_last_posts = source_text == "Commenter les X derniers posts d'utilisateurs"
        self.comment_user_source_group.setVisible(is_users_last_posts)
        if is_users_last_posts: self.toggle_manual_comment_user_list_visibility(self.comment_user_source_combo.currentIndex())
        self.num_comments_per_run_label.setVisible(True) # Toujours pertinent
        self.num_comments_per_run_spinbox.setVisible(True)
    
    def toggle_manual_comment_user_list_visibility(self, index): # Similaire à like
        is_manual = self.comment_user_source_combo.currentText() == "Utiliser une liste manuelle"
        self.manual_comment_user_list_label.setVisible(is_manual)
        self.manual_comment_user_list_input.setVisible(is_manual)

    def toggle_story_view_options_visibility(self, index): #... (comme avant)
    def toggle_manual_story_view_user_list_visibility(self, index): #... (comme avant)
    def toggle_partial_view_spinboxes(self, checked): #... (comme avant)
    
    # def _handle_tab_changed(self, index): # Si on veut rafraîchir stats sur sélection onglet
    #     if self.tab_widget.widget(index) == self.stats_tab:
    #         self.stats_tab.refresh_stats()