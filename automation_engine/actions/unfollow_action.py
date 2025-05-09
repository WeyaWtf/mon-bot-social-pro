# mon_bot_social/automation_engine/actions/unfollow_action.py
import time
import random
import datetime
import re # Pour parser les counts dans le scraping
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    ElementClickInterceptedException, StaleElementReferenceException
)

from automation_engine.element_selectors import ProfilePageLocators, PostLocators, ErrorAndBlockLocators

class UnfollowAction:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.driver = None
        self.logger = self.app_manager.logger

    def _check_if_still_following(self, timeout=2):
        """Vérifie si le bouton "Following" ou "Requested" est présent."""
        try:
            combined_xpath = f"{ProfilePageLocators.CURRENTLY_FOLLOWING_BUTTON_XPATH} | {ProfilePageLocators.REQUESTED_BUTTON_XPATH}"
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, combined_xpath))
            )
            return True # Toujours en train de suivre ou demande en cours
        except TimeoutException:
            return False # Bouton "Following/Requested" non trouvé, on ne suit probablement plus

    def _parse_count_string(self, count_str): # Helper pour parser "1.5k", "2M", etc.
        if not count_str: return None
        text = str(count_str).lower().replace(',', '').replace(' ', '')
        num_part_match = re.search(r'([\d\.]+)', text); num_str = ""
        if num_part_match: num_str = num_part_match.group(1)
        else:
            if not any(char.isdigit() for char in text) and ('k' in text or 'm' in text or 'b' in text): num_str = text
        val = 0
        if 'k' in num_str: val = float(num_str.replace('k', '')) * 1000
        elif 'm' in num_str: val = float(num_str.replace('m', '')) * 1000000
        elif 'b' in num_str: val = float(num_str.replace('b', '')) * 1000000000
        elif num_str:
            try: val = float(num_str)
            except ValueError: self.logger.warning(f"Impossible de parser count_str: '{count_str}' -> '{num_str}'"); return None
        else: return None
        return int(val)

    def _get_profile_info_for_unfollow_filtering(self, username, check_activity=False, check_counts_for_ratio=False, check_min_followers_to_protect=0):
        self.logger.info(f"Récupération infos (A:{check_activity}, Cts:{check_counts_for_ratio}, ProtFol:{check_min_followers_to_protect}) pour unfollow de {username}...")
        profile_info = {'last_post_date': None, 'follower_count': None, 'following_count': None, 'is_private': False}
        
        settings = self.app_manager.current_settings
        needs_activity_check = check_activity and settings.get("unfollow_inactive_days_threshold", 0) > 0
        needs_ratio_check = check_counts_for_ratio and (settings.get("unfollow_filter_ratio_min", 0.0) > 0 or settings.get("unfollow_filter_ratio_max", 0.0) > 0)
        needs_follower_protect_check = check_min_followers_to_protect > 0
        needs_counts_for_any_reason = needs_ratio_check or needs_follower_protect_check

        if not needs_activity_check and not needs_counts_for_any_reason:
            self.logger.debug(f"Pas de scraping d'infos publiques requis pour {username} (filtres inactifs).")
            # On a quand même besoin de savoir si le profil est privé pour la logique `_check_follows_you_status`
            # et pour savoir si on peut scraper la date du dernier post si `check_activity` est True mais le filtre est à 0
            profile_url_temp = f"https://www.instagram.com/{username}/" # Pas de navigation si déjà dessus
            if not self.driver.current_url.replace("www.","").startswith(profile_url_temp.replace("www.","")):
                if not self.app_manager.browser_handler.navigate_to(profile_url_temp): return None
                time.sleep(random.uniform(1.5, 2.5))
            try:
                if self.driver.find_elements(By.XPATH, ProfilePageLocators.PRIVATE_ACCOUNT_INDICATOR_XPATH):
                    profile_info['is_private'] = True
            except: pass
            return profile_info

        profile_url = f"https://www.instagram.com/{username}/"
        if not self.driver.current_url.replace("www.","").startswith(profile_url.replace("www.","")):
            if not self.app_manager.browser_handler.navigate_to(profile_url): return None
            time.sleep(random.uniform(2.5, 4.0))
        
        try:
            wait = WebDriverWait(self.driver, 5)
            if self.driver.find_elements(By.XPATH, ProfilePageLocators.PRIVATE_ACCOUNT_INDICATOR_XPATH):
                profile_info['is_private'] = True; self.logger.info(f"Profil {username} est privé. Scraping limité pour unfollow.")
                # Si privé, on ne peut pas scraper counts ou last_post_date
                return profile_info

            # Scraper Followers/Following SI NÉCESSAIRE
            if needs_counts_for_any_reason:
                try:
                    follower_el = wait.until(EC.visibility_of_element_located((By.XPATH, ProfilePageLocators.FOLLOWERS_COUNT_VALUE_XPATH)))
                    profile_info['follower_count'] = self._parse_count_string(follower_el.get_attribute("title") or follower_el.text)
                    self.logger.debug(f"Scraped Followers Unfollow: {profile_info['follower_count']} for {username}")
                except: self.logger.warning(f"Échec scrape Followers unfollow pour {username}")
                try:
                    following_el = wait.until(EC.visibility_of_element_located((By.XPATH, ProfilePageLocators.FOLLOWING_COUNT_VALUE_XPATH)))
                    profile_info['following_count'] = self._parse_count_string(following_el.get_attribute("title") or following_el.text)
                    self.logger.debug(f"Scraped Following Unfollow: {profile_info['following_count']} for {username}")
                except: self.logger.warning(f"Échec scrape Following unfollow pour {username}")

            # Scraper Date Dernier Post SI NÉCESSAIRE
            if needs_activity_check:
                try:
                    first_post_link_el = wait.until(EC.presence_of_element_located((By.XPATH, ProfilePageLocators.FIRST_POST_THUMBNAIL_ON_PROFILE_XPATH)))
                    first_post_url = first_post_link_el.get_attribute('href')
                    if self.app_manager.browser_handler.navigate_to(first_post_url):
                        time.sleep(random.uniform(2,3)); ts_el = wait.until(EC.presence_of_element_located((By.XPATH, PostLocators.POST_TIMESTAMP_XPATH)))
                        dt_str = ts_el.get_attribute('datetime'); profile_info['last_post_date'] = datetime.datetime.fromisoformat(dt_str.replace('Z','+00:00'))
                        self.logger.debug(f"Scraped Date dernier post unfollow: {profile_info['last_post_date']} for {username}")
                        self.app_manager.browser_handler.navigate_to(profile_url); time.sleep(random.uniform(1,2)) # Retour au profil
                except Exception as e_lp: self.logger.warning(f"Échec scrape Date dernier post unfollow pour {username}: {e_lp}")
            return profile_info
        except Exception as e_global: self.logger.error(f"Erreur globale scraping infos unfollow {username}: {e_global}", exc_info=True); return None


    def _check_follows_you_status(self, username):
        """Vérifie si l'indicateur 'Follows you' est présent. S'assure d'être sur le profil."""
        profile_url = f"https://www.instagram.com/{username}/"
        if not self.driver.current_url.replace("www.","").startswith(profile_url.replace("www.","")):
            if not self.app_manager.browser_handler.navigate_to(profile_url):
                 self.logger.error(f"Échec navigation vers {username} pour vérifier 'Follows You'.")
                 return False # Ne peut pas vérifier
            time.sleep(random.uniform(1.5, 2.5))
        try:
            indicator = self.driver.find_elements(By.XPATH, ProfilePageLocators.FOLLOWS_YOU_INDICATOR_XPATH)
            if indicator: self.logger.debug(f"'Follows you' trouvé pour {username}."); return True
            else: self.logger.debug(f"'Follows you' NON trouvé pour {username}."); return False
        except Exception as e: self.logger.warning(f"Erreur vérif 'Follows you' pour {username}: {e}. Supposer False."); return False

    def _apply_unfollow_filters(self, username, user_db_details):
        settings = self.app_manager.current_settings; now_ts = time.time(); logger = self.logger

        if self.app_manager.is_whitelisted(username): return False, "Protégé par whitelist"
        if self.app_manager.is_excluded(username): return False, "Exclu globalement"

        if user_db_details is None: # Devrait seulement arriver si on l'a suivi manuellement sans l'enregistrer
             logger.warning(f"Filtre Unfollow: {username} non trouvé dans DB suivis. Impossible d'appliquer filtre ancienneté. Skip par sécurité.")
             return False, "Non trouvé en DB des suivis"

        # 1. Ancienneté Suivi (DB)
        min_days_setting = settings.get("unfollow_min_days_before", 7)
        if min_days_setting > 0:
            followed_at_ts = user_db_details.get("followed_at_ts", 0)
            if followed_at_ts: days_followed = (now_ts - followed_at_ts) / (24*60*60)
            else: days_followed = float('inf') # Si pas de ts, considérer comme suivi depuis longtemps
            if days_followed < min_days_setting: return False, f"Suivi depuis {days_followed:.1f}j (< {min_days_setting}j)"
        
        # Récupérer les settings des filtres qui nécessitent du scraping
        unfollow_ratio_min = settings.get("unfollow_filter_ratio_min", 0.0)
        unfollow_ratio_max = settings.get("unfollow_filter_ratio_max", 0.0)
        unfollow_inactive_days = settings.get("unfollow_inactive_days_threshold", 0)
        unfollow_protect_followers = settings.get("unfollow_protect_min_followers", 0)
        only_non_followers_setting = settings.get("unfollow_only_non_followers", True)
        
        needs_scrape_for_public_info = (unfollow_ratio_min > 0 or unfollow_ratio_max > 0 or \
                                       unfollow_inactive_days > 0 or unfollow_protect_followers > 0 or \
                                       only_non_followers_setting) # Si on check "follows you", on doit être sur le profil

        profile_scraped_info = None
        if needs_scrape_for_public_info:
            profile_scraped_info = self._get_profile_info_for_unfollow_filtering(
                username, 
                check_activity=(unfollow_inactive_days > 0), 
                check_counts_for_ratio=(unfollow_ratio_min > 0 or unfollow_ratio_max > 0),
                check_min_followers_to_protect=unfollow_protect_followers
            )
            if profile_scraped_info is None: return False, "Échec scraping infos profil pour filtre"
        
        # 2. Filtre Non-Followers (Check UI)
        if only_non_followers_setting:
            if profile_scraped_info and profile_scraped_info.get('is_private'):
                logger.info(f"Filtre Unfollow: {username} privé, impossible de vérifier 'follows you' de manière fiable sans envoyer une requête. Skip filtre 'non-follower'.")
            elif self._check_follows_you_status(username): # Coûteux, s'assure d'être sur la page
                # Optionnel : mettre à jour DB
                self.app_manager.update_db_following_back_status(username, True)
                return False, "Suit en retour (vérifié)"
            else: # Ne suit pas ou erreur vérif
                self.app_manager.update_db_following_back_status(username, False)

        # Appliquer filtres qui dépendent de profile_scraped_info
        if profile_scraped_info:
            is_private = profile_scraped_info.get('is_private', False) # Si is_private, les counts et date ne sont pas dispos
            if not is_private:
                # 3. Filtre Inactivité
                if unfollow_inactive_days > 0:
                    last_post_date = profile_scraped_info.get('last_post_date')
                    if last_post_date:
                        days_since_lp = (datetime.datetime.now(datetime.timezone.utc) - last_post_date).days
                        if days_since_lp < unfollow_inactive_days: return False, f"Actif récemment ({days_since_lp}j < {unfollow_inactive_days}j)"
                    elif last_post_date is None and needs_scrape_for_public_info: # N'a pas pu scraper
                        return False, "Activité récente inconnue (scraping date échoué)"
                
                # 4. Filtre Ratio (NE PAS Unfollow si ratio dans la plage "safe")
                if unfollow_ratio_min > 0 or unfollow_ratio_max > 0:
                    followers = profile_scraped_info.get('follower_count'); following = profile_scraped_info.get('following_count')
                    if followers is not None and following is not None:
                        if following > 0: ratio = followers / following
                        else: ratio = float('inf') # Pour le cas following=0
                        
                        # NE PAS unfollow si le ratio est bon (entre min et max)
                        is_safe_ratio = True # Default to true if max is 0 (no upper limit)
                        if unfollow_ratio_min > 0 and ratio < unfollow_ratio_min: is_safe_ratio = False
                        if unfollow_ratio_max > 0 and ratio > unfollow_ratio_max: is_safe_ratio = False
                        # Cas spécial: si min et max sont 0, le filtre n'est pas actif.
                        # Si min > 0 et max=0, alors ratio doit être >= min_ratio
                        # Si min = 0 et max>0, alors ratio doit être <= max_ratio
                        # Notre logique : on skippe si ratio DANS la plage min-max (si min ou max > 0)
                        if (unfollow_ratio_min > 0 or unfollow_ratio_max > 0) and \
                            (ratio >= unfollow_ratio_min if unfollow_ratio_min > 0 else True) and \
                            (ratio <= unfollow_ratio_max if unfollow_ratio_max > 0 else True) :
                                return False, f"Ratio ({ratio:.2f}) dans la plage de protection [{unfollow_ratio_min}-{unfollow_ratio_max}]"
                    elif (unfollow_ratio_min > 0 or unfollow_ratio_max > 0): return False, "Ratio inconnu (scraping counts échoué)"

                # 5. Filtre Protection Followers (NE PAS unfollow si a TROP de followers)
                if unfollow_protect_followers > 0:
                    followers = profile_scraped_info.get('follower_count')
                    if followers is not None:
                        if followers > unfollow_protect_followers: return False, f"Followers ({followers}) > Seuil protection ({unfollow_protect_followers})"
                    elif followers is None: return False, "Nb Followers inconnu (protection active)"

        return True, "Passe tous les filtres d'unfollow"


    def execute(self, options):
        self.driver = self.app_manager.browser_handler.driver; #... (check driver)
        target_user_to_unfollow = None
        if options.get('use_app_manager_queue', False):
            target_user_to_unfollow = self.app_manager.get_next_user_for_unfollow()
            if not target_user_to_unfollow: return True, "File unfollow vide."
        else: target_user_to_unfollow = options.get('target_user')
        if not target_user_to_unfollow: return False, "User cible non défini."
        
        self.logger.info(f"UnfollowAction: Traitement de '{target_user_to_unfollow}'.")
        user_db_details = self.app_manager.get_db_followed_user_details(target_user_to_unfollow)

        can_unfollow, filter_reason = self._apply_unfollow_filters(target_user_to_unfollow, user_db_details)
        if not can_unfollow:
            self.logger.info(f"UnfollowAction: '{target_user_to_unfollow}' filtré. Raison: {filter_reason}")
            # On ne marque pas comme "unfollowed" mais comme "traité pour unfollow (skip)"
            # C'est pour que le compteur d'actions avance.
            # On ne modifie pas la DB 'followed_users' ici car pas d'action réelle d'unfollow.
            return True, filter_reason # Succès de l'évaluation, mais pas d'unfollow

        # Si filtres OK, procéder à l'unfollow
        self.logger.info(f"UnfollowAction: Tous filtres passés pour '{target_user_to_unfollow}'. Tentative d'unfollow réel.")
        # Assurer d'être sur la page de profil AVANT les clics d'unfollow
        profile_url = f"https://www.instagram.com/{target_user_to_unfollow}/"
        if not self.driver.current_url.replace("www.","").startswith(profile_url.replace("www.","")):
             if not self.app_manager.browser_handler.navigate_to(profile_url):
                 self.logger.error(f"Échec re-navigation vers profil {target_user_to_unfollow} AVANT tentative d'unfollow.")
                 return False, f"Échec re-navigation {target_user_to_unfollow}"
             time.sleep(random.uniform(1,2.5))
        
        try:
            wait = WebDriverWait(self.driver, 10)
            # 1. Cliquer sur le bouton "Following" (ou "Requested")
            unfollow_trigger_button_xpath = f"{ProfilePageLocators.CURRENTLY_FOLLOWING_BUTTON_XPATH} | {ProfilePageLocators.REQUESTED_BUTTON_XPATH}"
            trigger_button = wait.until(EC.element_to_be_clickable((By.XPATH, unfollow_trigger_button_xpath)))
            self.driver.execute_script("arguments[0].scrollIntoViewIfNeeded(true);", trigger_button)
            time.sleep(0.3)
            try: trigger_button.click()
            except ElementClickInterceptedException: self.driver.execute_script("arguments[0].click();", trigger_button); self.logger.debug("Clic JS sur Following/Requested.")
            time.sleep(random.uniform(1.0, 2.0)) # Attendre la popup

            # 2. Cliquer sur le bouton de confirmation "Unfollow"
            confirm_button = wait.until(EC.element_to_be_clickable((By.XPATH, ProfilePageLocators.UNFOLLOW_CONFIRM_BUTTON_XPATH)))
            try: confirm_button.click()
            except ElementClickInterceptedException: self.driver.execute_script("arguments[0].click();", confirm_button); self.logger.debug("Clic JS sur Confirm Unfollow.")
            time.sleep(random.uniform(2.0, 3.5)) # Attendre la mise à jour de l'UI

            block_msg = self._check_for_block_popup() # Check après les actions
            if block_msg:
                self.app_manager.mark_user_as_unfollowed(target_user_to_unfollow, success=False)
                return False, block_msg

            # 3. Vérifier que le bouton n'est PLUS "Following/Requested"
            if not self._check_if_still_following(timeout=5):
                 msg = f"Utilisateur '{target_user_to_unfollow}' désabonné avec succès."
                 self.logger.info(f"UnfollowAction: {msg}")
                 self.app_manager.mark_user_as_unfollowed(target_user_to_unfollow, success=True)
                 return True, msg
            else:
                 msg = f"Statut bouton non changé après tentative unfollow pour {target_user_to_unfollow}. Potentiel échec ou blocage."
                 self.logger.warning(f"UnfollowAction: {msg}")
                 self.app_manager.mark_user_as_unfollowed(target_user_to_unfollow, success=False)
                 return False, msg

        except TimeoutException:
            # Si le bouton "Following/Requested" n'est pas trouvé initialement,
            # cela signifie qu'on ne le suivait plus (ou jamais).
            # C'est un "succès" d'unfollow si on le considère comme "n'est plus suivi".
            if not self._check_if_still_following(timeout=1):
                self.logger.info(f"Ne suivait déjà plus (ou jamais) {target_user_to_unfollow} (bouton 'Following' non trouvé initialement).")
                self.app_manager.mark_user_as_unfollowed(target_user_to_unfollow, success=True) # Marquer comme "traité avec succès"
                return True, f"Ne suivait déjà plus {target_user_to_unfollow}."
            else: # Autre Timeout
                msg = f"Timeout lors de l'action unfollow sur {target_user_to_unfollow} (ex: confirmation non trouvée)."
                self.logger.warning(msg); self.app_manager.mark_user_as_unfollowed(target_user_to_unfollow, success=False); return False, msg
        except Exception as e:
            msg = f"Erreur inattendue unfollow {target_user_to_unfollow}: {e}"
            self.logger.error(msg, exc_info=True)
            block_msg = self._check_for_block_popup()
            final_msg = block_msg if block_msg else msg
            self.app_manager.mark_user_as_unfollowed(target_user_to_unfollow, success=False); return False, final_msg
            
    def _check_for_block_popup(self): # Dupliqué depuis FollowAction, idéalement un helper partagé
        try:
            block_texts = [ErrorAndBlockLocators.ACTION_BLOCKED_TEXT_XPATH, ErrorAndBlockLocators.TRY_AGAIN_LATER_TEXT_XPATH]
            for i, block_xpath_tuple in enumerate(block_texts):
                if not block_xpath_tuple or not block_xpath_tuple[1]: continue
                elements = self.driver.find_elements(block_xpath_tuple[0], block_xpath_tuple[1])
                if elements: return f"BLOCKED: Popup détecté (Pattern {i+1})."
        except: pass
        return None