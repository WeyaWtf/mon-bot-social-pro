# mon_bot_social/automation_engine/actions/view_story_action.py
import time
import random
from urllib.parse import urlparse # Pour extraire username des liens (moins critique ici)

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

from automation_engine.element_selectors import HomePageLocators, StoryViewLocators, ProfilePageLocators, ErrorAndBlockLocators

class ViewStoryAction:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.driver = None
        self.logger = self.app_manager.logger
        self.viewed_users_this_session = set() # Pour ne pas re-traiter le même user DANS CE RUN de la tâche

    def _click_element_if_exists(self, by_method, selector_value, description="element", timeout=1.0):
        """Tente de cliquer sur un élément, avec fallback JS. Gère le timeout."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by_method, selector_value))
            )
            try: 
                element.click()
                # self.logger.debug(f"Clic normal sur '{description}' réussi.")
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", element)
                # self.logger.debug(f"Clic JS sur '{description}' après interception.")
            return True
        except TimeoutException:
            # self.logger.debug(f"'{description}' non trouvé ou non cliquable (timeout {timeout}s).")
            return False
        except Exception as e:
            self.logger.warning(f"Erreur clic sur '{description}': {e}")
            return False
            
    def _get_current_story_username(self):
        """Tente de récupérer le nom de l'utilisateur de la story active."""
        try:
            user_link_element = WebDriverWait(self.driver, 1).until( # Attente très courte
                EC.presence_of_element_located((By.XPATH, StoryViewLocators.STORY_VIEWER_USERNAME_XPATH))
            )
            href = user_link_element.get_attribute('href')
            if href and "instagram.com/" in href:
                username = urlparse(href).path.strip('/')
                parts = [p for p in username.split('/') if p and p not in ['p','reel','tv','stories']] # Nettoyer
                return parts[0].lower() if parts else None
        except: pass # Ignorer si pas trouvé rapidement
        return None

    def _check_for_block_popup(self): # Helper
        try: #... (logique identique à FollowAction/LikeAction)
            block_xpaths = [ErrorAndBlockLocators.ACTION_BLOCKED_TEXT_XPATH, ErrorAndBlockLocators.TRY_AGAIN_LATER_TEXT_XPATH]
            for i, xpath_tuple in enumerate(block_xpaths): #... (chercher, retourner si trouvé)
        except: pass
        return None


    def view_single_user_story_segments(self, initial_username, max_segments_to_watch=None):
        """Boucle de visionnage des segments pour l'utilisateur courant."""
        viewed_segments_for_this_user = 0
        
        if max_segments_to_watch is None or max_segments_to_watch == 0 : # 0 = illimité
            max_segments_to_watch = float('inf') 
            self.logger.debug(f"Visionnage de tous les segments pour {initial_username}.")
        else:
             self.logger.debug(f"Visionnage partiel: max {max_segments_to_watch} segments pour {initial_username}.")
             
        # Pause initiale pour que la première story se charge
        time.sleep(random.uniform(1.5, 3.0))

        while viewed_segments_for_this_user < max_segments_to_watch:
            current_story_user_in_viewer = self._get_current_story_username()
            
            # Log pour le débug
            # self.logger.debug(f"Segment {viewed_segments_for_this_user + 1}. Initial: {initial_username}, Current viewer: {current_story_user_in_viewer}")

            if current_story_user_in_viewer and current_story_user_in_viewer != initial_username.lower():
                self.logger.info(f"Fin des stories pour {initial_username} (passage à {current_story_user_in_viewer}).")
                break # Passé aux stories d'un autre utilisateur

            if not current_story_user_in_viewer and viewed_segments_for_this_user > 0: # Si on a perdu le user en cours de route
                self.logger.warning(f"Impossible de confirmer l'utilisateur de la story en cours après {viewed_segments_for_this_user} segments (était {initial_username}). Fin anticipée.")
                break

            # Simuler le temps de visionnage d'un segment
            segment_play_time = random.uniform(2, 6) # Entre 2 et 6 secondes par segment
            # self.logger.debug(f"Visionnage segment {viewed_segments_for_this_user + 1} de {initial_username} pendant {segment_play_time:.1f}s...")
            time.sleep(segment_play_time)
            
            viewed_segments_for_this_user += 1

            # Vérifier si c'est le dernier segment autorisé pour cet utilisateur
            if viewed_segments_for_this_user >= max_segments_to_watch:
                self.logger.info(f"Limite de visionnage ({max_segments_to_watch} segments) atteinte pour {initial_username}.")
                break

            # Essayer de passer au segment suivant
            clicked_next = self._click_element_if_exists(By.XPATH, StoryViewLocators.NEXT_STORY_BUTTON_XPATH, "Next Story Segment", timeout=0.7)
            
            if not clicked_next:
                self.logger.info(f"Pas de bouton 'Next' trouvé. Fin des stories pour {initial_username} après {viewed_segments_for_this_user} segments.")
                break # Fin des stories de cet utilisateur
            
            time.sleep(random.uniform(0.5, 1.2)) # Courte pause entre les segments cliqués

        return viewed_segments_for_this_user


    def view_user_stories_logic(self, username_to_view, skip_if_recent_days=1, partial_view_enabled=False, partial_min=2, partial_max=5):
        if self.app_manager.has_viewed_story_recently(username_to_view, days_limit=skip_if_recent_days):
            return "skipped_recent", f"Stories de {username_to_view} vues récemment."
        if self.app_manager.is_excluded(username_to_view):
             return "skipped_excluded", f"{username_to_view} est exclu."

        self.logger.info(f"Tentative de visionnage des stories de {username_to_view}.")
        
        profile_url = f"https://www.instagram.com/{username_to_view}/"
        if not self.driver.current_url.replace("www.","").startswith(profile_url.replace("www.","")):
            if not self.app_manager.browser_handler.navigate_to(profile_url): return "nav_fail", f"Echec nav profil {username_to_view}"
            time.sleep(random.uniform(2.5, 4.0))
        
        # Trouver et cliquer sur l'avatar avec story active
        try:
            # Le sélecteur doit être suffisamment précis pour ne pas cliquer si pas de story
            story_avatar_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, ProfilePageLocators.ACTIVE_STORY_RING_ON_PROFILE_XPATH))
            )
            story_avatar_button.click()
            self.logger.debug(f"Clic sur avatar story de {username_to_view}.")
            time.sleep(random.uniform(1.5, 3.0)) # Laisser la story s'ouvrir
        except (TimeoutException, NoSuchElementException):
            return "no_story_found", f"Pas de story active (ou bouton non trouvé) pour {username_to_view}."
        except ElementClickInterceptedException as e_click:
            return "click_intercepted", f"Clic sur avatar story de {username_to_view} intercepté: {e_click}"
        
        max_segments = None
        if partial_view_enabled and partial_max >= partial_min:
             max_segments = random.randint(partial_min, partial_max)

        viewed_count = self.view_single_user_story_segments(username_to_view, max_segments_to_watch=max_segments)
        
        # Fermer la vue des stories (si elle est toujours ouverte)
        if not self._click_element_if_exists(By.XPATH, StoryViewLocators.CLOSE_STORY_BUTTON_XPATH, "Close Story Viewer", timeout=2):
             self.logger.warning("N'a pas pu fermer la vue des stories, tentative de retour ou navigation.")
             try: self.driver.back(); time.sleep(1) # Essayer 'back'
             except: self.driver.get("https://www.instagram.com/"); time.sleep(1) # Fallback: page d'accueil

        if viewed_count > 0:
            self.app_manager.mark_story_as_viewed(username_to_view)
            self.viewed_users_this_session.add(username_to_view)
            return "success", username_to_view # Retourner username si au moins 1 segment vu
        else: # 0 segments vus (peut-être juste ouvert et fermé)
            return "no_segments_viewed", f"Stories de {username_to_view} ouvertes mais 0 segments confirmés vus."


    def view_stories_from_feed_logic(self, num_users_to_view, skip_if_recent_days, 
                                 partial_view_enabled, partial_min, partial_max):
        self.logger.info("Visionnage stories depuis le Feed.")
        # ... (Navigation vers le feed) ...
        if not (self.driver.current_url.endswith("instagram.com/") or self.driver.current_url.endswith("instagram.com") ): # Simple check
            self.driver.get("https://www.instagram.com/"); time.sleep(random.uniform(3, 5))

        users_successfully_viewed_list = []
        try:
            # Sélecteur pour la barre de stories en haut
            story_bar_rings = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, HomePageLocators.ACTIVE_STORY_BUTTON_ON_FEED_XPATH))
            )
            self.logger.info(f"Trouvé {len(story_bar_rings)} cercles de story potentiels sur le feed.")
            
            # Limiter aux X premiers pour ce run
            for ring_element in story_bar_rings[:num_users_to_view + 5]: # Prendre un peu plus pour filtrer
                if len(users_successfully_viewed_list) >= num_users_to_view: break

                username_from_ring = None
                try: # Extraire le username
                    aria_label = ring_element.get_attribute("aria-label")
                    if aria_label and ("'s story" in aria_label.lower() or "story de" in aria_label.lower()):
                        parts = aria_label.lower().split("'s story")[0].split("story de")
                        username_from_ring = parts[0].strip()
                except: pass
                
                if not username_from_ring: self.logger.debug("Impossible d'extraire le nom d'un cercle de story."); continue
                if username_from_ring in self.viewed_users_this_session: continue # Déjà vu dans cette session de tâche
                if self.app_manager.has_viewed_story_recently(username_from_ring, skip_if_recent_days): continue
                if self.app_manager.is_excluded(username_from_ring): continue

                self.logger.debug(f"Feed: Clic sur story de {username_from_ring}.")
                try: ring_element.click(); time.sleep(random.uniform(1.5, 3))
                except: self.logger.warning(f"Échec clic sur story de {username_from_ring} depuis feed."); continue

                max_segments = None
                if partial_view_enabled and partial_max >= partial_min: max_segments = random.randint(partial_min, partial_max)
                
                viewed_count = self.view_single_user_story_segments(username_from_ring, max_segments_to_watch=max_segments)
                
                # Fermer la vue des stories si toujours ouverte
                if not self._click_element_if_exists(By.XPATH, StoryViewLocators.CLOSE_STORY_BUTTON_XPATH, "Close Story Viewer (feed)", timeout=1):
                     # Essayer de revenir en arrière si le bouton fermer échoue
                     try: self.driver.back(); time.sleep(0.5)
                     except: pass # Si back échoue aussi, on espère que la prochaine action réinitialise l'état
                
                if viewed_count > 0:
                    self.app_manager.mark_story_as_viewed(username_from_ring)
                    users_successfully_viewed_list.append(username_from_ring)
                    self.viewed_users_this_session.add(username_from_ring)
                    time.sleep(self.app_manager.get_setting("delay_between_user_story_view", 5)) # Pause entre users

                if len(users_successfully_viewed_list) >= num_users_to_view: break
            
        except TimeoutException: self.logger.info("Pas de cercles de story actifs trouvés sur le feed (ou timeout).")
        except Exception as e: self.logger.error(f"Erreur visionnage stories du feed: {e}", exc_info=True)
        
        return True, {'viewed_users': users_successfully_viewed_list}


    def execute(self, options):
        self.driver = self.app_manager.browser_handler.driver
        if not self.driver: return False, {"message": "Navigateur non dispo.", "viewed_users": []}
        
        self.viewed_users_this_session.clear() # Reset pour chaque exécution de la tâche principale
        view_source = options.get("view_source", "feed")
        skip_days = options.get("skip_users_viewed_less_than_x_days", 1)
        partial_enabled = options.get("partial_view_enabled", True) # Supposer True par défaut
        partial_min = options.get("partial_view_min_segments", 2)
        partial_max = options.get("partial_view_max_segments", 5)
        if partial_max < partial_min: partial_max = partial_min

        overall_success = True
        final_viewed_users = []

        if view_source == "feed":
            num_users = options.get("num_users_to_view_on_feed", 3)
            success, result_data = self.view_stories_from_feed_logic(num_users, skip_days, partial_enabled, partial_min, partial_max)
            overall_success &= success
            if success and result_data and result_data.get('viewed_users'): final_viewed_users = result_data['viewed_users']

        elif view_source == "users_list":
            target_users = options.get("target_users_list", [])
            max_to_process = options.get("max_users_to_process_stories_run", 5)
            processed_count = 0
            for username in target_users:
                if processed_count >= max_to_process: self.logger.info(f"Limite de {max_to_process} utilisateurs atteinte pour ce run de View Stories."); break
                if username in self.viewed_users_this_session : continue # Déjà fait dans ce run

                status, username_or_msg = self.view_user_stories_logic(username, skip_days, partial_enabled, partial_min, partial_max)
                if status == "success": 
                    final_viewed_users.append(username_or_msg)
                    processed_count +=1
                elif status == "blocked" or status == "nav_fail" or status == "click_intercepted":
                     overall_success = False; # Erreur bloquante pour cet utilisateur
                
                # Délai entre les utilisateurs (si on a fait quelque chose)
                if status not in ["skipped_recent", "skipped_excluded", "no_story_found"]:
                     time.sleep(self.app_manager.get_setting("delay_between_user_story_view", 10))
            
        elif view_source == "single_user_after_interaction": # Utilisé par post-like/comment
            target_user = options.get('target_user')
            if not target_user: return False, {"message": "User cible manquant pour vue post-interaction.", "viewed_users": []}
            status, username_or_msg = self.view_user_stories_logic(target_user, skip_days, partial_enabled, partial_min, partial_max)
            if status == "success": final_viewed_users.append(username_or_msg)
            elif status != "skipped_recent" and status != "no_story_found": overall_success = False

        else: 
            return False, {"message": f"Source inconnue: {view_source}", "viewed_users": []}

        # Notifier AppManager (pour déclencher like après story) est fait par TaskScheduler après le retour
        final_message = f"Auto-View Stories terminé. {len(final_viewed_users)} utilisateurs vus: {', '.join(final_viewed_users[:5])}{'...' if len(final_viewed_users)>5 else ''}"
        self.logger.info(final_message)
        # La structure de retour doit être cohérente pour TaskScheduler
        return overall_success, {'message': final_message, 'viewed_users': final_viewed_users, 'original_options': options}