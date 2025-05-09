# mon_bot_social/automation_engine/actions/follow_action.py
import time
import random
import datetime
import math # Pour le ratio
import re # Pour _parse_count_string
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    ElementClickInterceptedException, StaleElementReferenceException
)

from automation_engine.element_selectors import ProfilePageLocators, PostLocators, ErrorAndBlockLocators

class FollowAction:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.driver = None
        self.logger = self.app_manager.logger

    def _check_if_already_following_or_requested(self, timeout=2):
        """Vérifie si le bouton indique 'Following' ou 'Requested'."""
        try:
            # Tenter de trouver soit le bouton "Following", soit "Requested"
            # Utiliser un XPath qui combine les deux ou vérifier séquentiellement
            combined_xpath = f"{ProfilePageLocators.CURRENTLY_FOLLOWING_BUTTON_XPATH} | {ProfilePageLocators.REQUESTED_BUTTON_XPATH}"
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, combined_xpath))
            )
            self.logger.debug("Déjà suivi ou demande envoyée (bouton Following/Requested trouvé).")
            return True
        except TimeoutException:
            self.logger.debug("Pas de bouton Following/Requested trouvé (on ne suit probablement pas).")
            return False # Le bouton n'est pas trouvé, donc on ne suit pas / pas de demande en cours

    def _parse_count_string(self, count_str):
        if not count_str: return None
        
        text = str(count_str).lower().replace(',', '').replace(' ', '')
        # Essayer d'extraire le nombre en premier, car 'title' peut contenir du texte supplémentaire
        # Ex: "1,234 followers" ou "1234"
        num_part_match = re.search(r'([\d\.]+)', text)
        num_str = ""
        if num_part_match:
            num_str = num_part_match.group(1)
        else: # Si aucun chiffre direct, voir si k/m sont seuls
            if not any(char.isdigit() for char in text) and ('k' in text or 'm' in text or 'b' in text):
                 num_str = text # ex: "1.5k" sans chiffres avant

        val = 0
        if 'k' in num_str: val = float(num_str.replace('k', '')) * 1000
        elif 'm' in num_str: val = float(num_str.replace('m', '')) * 1000000
        elif 'b' in num_str: val = float(num_str.replace('b', '')) * 1000000000
        elif num_str: # S'il reste quelque chose qui pourrait être un nombre
            try: val = float(num_str)
            except ValueError: self.logger.warning(f"Impossible de parser la chaîne de comptage: '{count_str}' (après filtrage: '{num_str}')"); return None
        else: # Rien à parser
            return None
            
        return int(val)

    def _get_profile_info_for_filtering(self, username):
        self.logger.info(f"Récupération infos profil pour filtrage: {username}")
        profile_info = {'post_count': None, 'follower_count': None, 'following_count': None, 
                       'last_post_date': None, 'bio': "", 'is_business': False, 
                       'has_active_story': False, 'is_private': False, 
                       'has_profile_pic': True, 'follows_me': False, 'i_am_following': False}

        profile_url = f"https://www.instagram.com/{username}/"
        # Vérifier si on est déjà sur la page avant de naviguer pour éviter rechargement inutile
        # Si on navigue, l'attente est dans navigate_to
        if not self.driver.current_url.replace("www.","").startswith(profile_url.replace("www.","")):
            if not self.app_manager.browser_handler.navigate_to(profile_url):
                self.logger.error(f"Échec navigation vers {profile_url} pour scraping infos.")
                return None # Échec critique de navigation
            time.sleep(random.uniform(2.5, 4.5)) # Pause post-navigation pour chargement dynamique
        else:
            self.logger.debug(f"Déjà sur le profil de {username} pour scraping.")

        try:
            wait = WebDriverWait(self.driver, 5) # Attente par défaut pour les éléments principaux

            # Check Profil Privé (souvent visible même si la page ne charge pas complètement)
            try:
                private_indicators = self.driver.find_elements(By.XPATH, ProfilePageLocators.PRIVATE_ACCOUNT_INDICATOR_XPATH)
                if private_indicators: profile_info['is_private'] = True; self.logger.debug(f"{username} est privé.")
            except Exception as e_priv: self.logger.debug(f"Erreur check profil privé pour {username}: {e_priv} (continuant).")

            # Check Photo Profil (avant de scraper le reste au cas où la page est limitée)
            try:
                profile_pic_img = wait.until(EC.presence_of_element_located((By.XPATH, ProfilePageLocators.PROFILE_PIC_IMG_XPATH)))
                pic_src = profile_pic_img.get_attribute('src')
                # Améliorer le check de la photo par défaut
                default_subs = [ProfilePageLocators.DEFAULT_PROFILE_PIC_SRC_SUBSTRING_1, 
                                ProfilePageLocators.DEFAULT_PROFILE_PIC_SRC_SUBSTRING_2,
                                ProfilePageLocators.DEFAULT_PROFILE_PIC_SRC_SUBSTRING_3]
                if pic_src and any(sub in pic_src for sub in default_subs if sub): # Si sub est non vide
                    profile_info['has_profile_pic'] = False; self.logger.debug(f"Photo profil par défaut pour {username}.")
            except (TimeoutException, NoSuchElementException) as e_pic: self.logger.warning(f"Vérification photo profil {username} échouée: {e_pic}")

            # Check "Follows You" et "I Am Following" (si la page n'est pas privée)
            if not profile_info['is_private']:
                try:
                    if self.driver.find_elements(By.XPATH, ProfilePageLocators.FOLLOWS_YOU_INDICATOR_XPATH):
                        profile_info['follows_me'] = True; self.logger.debug(f"{username} suit le bot.")
                except: pass # Pas critique
                try:
                    if self.driver.find_elements(By.XPATH, ProfilePageLocators.CURRENTLY_FOLLOWING_BUTTON_XPATH) or \
                       self.driver.find_elements(By.XPATH, ProfilePageLocators.REQUESTED_BUTTON_XPATH):
                        profile_info['i_am_following'] = True; self.logger.debug(f"Le bot suit déjà {username} ou a demandé.")
                except: pass # Pas critique

            # Scraper le reste seulement si public ou si on doit le faire
            if not profile_info['is_private']:
                # Posts
                try:
                    post_count_el = wait.until(EC.visibility_of_element_located((By.XPATH, ProfilePageLocators.POST_COUNT_VALUE_XPATH)))
                    profile_info['post_count'] = self._parse_count_string(post_count_el.text or post_count_el.get_attribute("title"))
                    self.logger.debug(f"Posts {username}: {profile_info['post_count']}")
                except: self.logger.debug(f"Posts non trouvés pour {username}")
                # Followers
                try:
                    follower_el = wait.until(EC.visibility_of_element_located((By.XPATH, ProfilePageLocators.FOLLOWERS_COUNT_VALUE_XPATH)))
                    profile_info['follower_count'] = self._parse_count_string(follower_el.get_attribute("title") or follower_el.text)
                    self.logger.debug(f"Followers {username}: {profile_info['follower_count']}")
                except: self.logger.debug(f"Followers non trouvés pour {username}")
                # Following
                try:
                    following_el = wait.until(EC.visibility_of_element_located((By.XPATH, ProfilePageLocators.FOLLOWING_COUNT_VALUE_XPATH)))
                    profile_info['following_count'] = self._parse_count_string(following_el.get_attribute("title") or following_el.text)
                    self.logger.debug(f"Following {username}: {profile_info['following_count']}")
                except: self.logger.debug(f"Following non trouvés pour {username}")
                # Bio
                try:
                    bio_el = self.driver.find_element(By.XPATH, ProfilePageLocators.BIO_TEXT_XPATH)
                    profile_info['bio'] = bio_el.text.lower() if bio_el.text else ""
                except: self.logger.debug(f"Bio non trouvée pour {username}")
                # Type Profil
                try:
                    if self.driver.find_elements(By.XPATH, ProfilePageLocators.BUSINESS_CATEGORY_TEXT_XPATH) or \
                       self.driver.find_elements(By.XPATH, ProfilePageLocators.BUSINESS_ACTION_BUTTON_XPATH):
                        profile_info['is_business'] = True; self.logger.debug(f"Compte Pro/Créateur détecté pour {username}.")
                except: pass
                # Story Active
                try:
                    if self.driver.find_elements(By.XPATH, ProfilePageLocators.ACTIVE_STORY_RING_ON_PROFILE_XPATH):
                        profile_info['has_active_story'] = True; self.logger.debug(f"Story active détectée pour {username}.")
                except: pass
                # Date Dernier Post
                if self.app_manager.get_setting("filter_max_days_last_post", 0) > 0:
                    try:
                        first_post_link_el = wait.until(EC.presence_of_element_located((By.XPATH, ProfilePageLocators.FIRST_POST_THUMBNAIL_ON_PROFILE_XPATH)))
                        first_post_url = first_post_link_el.get_attribute('href')
                        if self.app_manager.browser_handler.navigate_to(first_post_url):
                             time.sleep(random.uniform(2,3)); ts_el = wait.until(EC.presence_of_element_located((By.XPATH, PostLocators.POST_TIMESTAMP_XPATH)))
                             dt_str = ts_el.get_attribute('datetime'); profile_info['last_post_date'] = datetime.datetime.fromisoformat(dt_str.replace('Z','+00:00'))
                             self.logger.debug(f"Date dernier post {username}: {profile_info['last_post_date']}")
                             self.app_manager.browser_handler.navigate_to(profile_url); time.sleep(random.uniform(1,2)) # Retour
                    except Exception as e_lp: self.logger.warning(f"Échec récupération date dernier post {username}: {e_lp}")

            return profile_info
        except Exception as e_global:
            self.logger.error(f"Erreur globale scraping infos {username}: {e_global}", exc_info=True)
            return profile_info # Retourner ce qui a pu être collecté


    def _apply_user_filters(self, username, profile_info):
        settings = self.app_manager.current_settings; logger = self.logger # Utiliser le logger de l'action
        
        # 0. Whitelist / Exclusion
        if self.app_manager.is_whitelisted(username): return False, "Protégé par whitelist"
        if self.app_manager.is_excluded(username): return False, "Exclu globalement"
        
        # 1. Filtres Relation
        if settings.get("filter_skip_followers", False) and profile_info.get('follows_me'):
             return False, "Vous suit déjà"
        if settings.get("filter_skip_following", True) and profile_info.get('i_am_following'):
             return False, "Déjà suivi par le bot"

        # 2. Filtres basiques Profil
        if settings.get("filter_skip_no_profile_pic", True) and not profile_info.get('has_profile_pic'):
             return False, "Pas de photo de profil personnalisée"
        if settings.get("filter_skip_private", False) and profile_info.get('is_private'):
             return False, "Profil privé (ignorer)"
        if settings.get("filter_only_private", False) and not profile_info.get('is_private'):
             return False, "Profil public (seulement privés demandé)"

        # Si profil privé et on continue (ex: only_private=True ou skip_private=False), 
        # alors les filtres suivants (stats, bio, etc.) ne sont pas fiables.
        # On peut choisir de les ignorer ou de skipper par défaut.
        is_private_scraped = profile_info.get('is_private', False)
        can_apply_public_filters = not is_private_scraped
        
        if not can_apply_public_filters and settings.get("filter_only_private", False):
            logger.debug(f"{username} est privé et 'only_private' est actif. Passe les filtres publics par défaut.")
        elif not can_apply_public_filters:
             # Cas où on suit des privés mais certains filtres publics pourraient être actifs.
             # Par prudence, on skippe si des filtres stricts sont en place.
             # Par exemple, si min_posts > 0, on ne peut pas le vérifier sur un privé.
             if settings.get("filter_min_posts", 0) > 0 or settings.get("filter_min_followers", 0) > 0: # etc.
                  logger.info(f"Filtre: {username} privé, impossible de vérifier les stats (filtres stricts actifs). Skip.")
                  return False, "Privé, stats non vérifiables"
        
        # Appliquer les filtres si le profil est public (ou si on décide qu'ils ne s'appliquent pas aux privés)
        if can_apply_public_filters:
            # Type de profil
            pt_filter = settings.get("filter_profile_type", "Tous types")
            is_biz = profile_info.get('is_business') # True, False, ou None
            if pt_filter == "Personnel Seulement" and is_biz: return False, "Compte Pro (requis Perso)"
            if pt_filter == "Professionnel Seulement" and not is_biz: return False, "Compte Perso (requis Pro)"
            # Story Active
            if settings.get("filter_must_have_story", False) and not profile_info.get('has_active_story'): return False, "Pas de story active (requis)"
            
            # Posts
            pc = profile_info.get('post_count'); min_p = settings.get("filter_min_posts",0); max_p = settings.get("filter_max_posts",0)
            if pc is not None:
                if pc < min_p: return False, f"Posts ({pc}) < Min ({min_p})"
                if max_p > 0 and pc > max_p: return False, f"Posts ({pc}) > Max ({max_p})"
            elif min_p > 0: return False, "Nb Posts inconnu (Min requis)"

            # Followers / Following / Ratio
            fols = profile_info.get('follower_count'); foling = profile_info.get('following_count')
            min_fols=settings.get("filter_min_followers",0); max_fols=settings.get("filter_max_followers",0)
            min_foling=settings.get("filter_min_following",0); max_foling=settings.get("filter_max_following",0)
            min_r=settings.get("filter_min_ratio",0.0); max_r=settings.get("filter_max_ratio",0.0)
            if fols is not None:
                if fols < min_fols: return False, f"Followers ({fols}) < Min ({min_fols})"
                if max_fols > 0 and fols > max_fols: return False, f"Followers ({fols}) > Max ({max_fols})"
            elif min_fols > 0 or max_fols > 0: return False, "Nb Followers inconnu (filtre actif)"
            if foling is not None:
                if foling < min_foling: return False, f"Following ({foling}) < Min ({min_foling})"
                if max_foling > 0 and foling > max_foling: return False, f"Following ({foling}) > Max ({max_foling})"
            elif min_foling > 0 or max_foling > 0: return False, "Nb Following inconnu (filtre actif)"
            if fols is not None and foling is not None and foling > 0:
                ratio = fols/foling
                if min_r > 0 and ratio < min_r: return False, f"Ratio ({ratio:.2f}) < Min ({min_r})"
                if max_r > 0 and ratio > max_r: return False, f"Ratio ({ratio:.2f}) > Max ({max_r})"
            elif (min_r > 0 or max_r > 0) and (fols is None or foling is None): return False, "Ratio inconnu (filtre actif)"

            # Date dernier post
            lpd = profile_info.get('last_post_date'); max_days_lp = settings.get("filter_max_days_last_post",0)
            if max_days_lp > 0 and lpd:
                days_since_lp = (datetime.datetime.now(datetime.timezone.utc) - lpd).days
                if days_since_lp > max_days_lp: return False, f"Dernier post > {max_days_lp} jours ({days_since_lp}j)"
            elif max_days_lp > 0 and not lpd: return False, "Date dernier post inconnue (filtre actif)"
            
            # Bio Keywords
            bio = profile_info.get('bio',""); inc_kw_str=settings.get("filter_bio_keywords_include",""); exc_kw_str=settings.get("filter_bio_keywords_exclude","")
            if inc_kw_str:
                inc_kws = [kw.strip().lower() for kw in inc_kw_str.split(',') if kw.strip()]
                if inc_kws and not any(re.search(r'\b'+re.escape(kw)+r'\b', bio) for kw in inc_kws): return False, "Bio manque mots-clés requis"
            if exc_kw_str:
                exc_kws = [kw.strip().lower() for kw in exc_kw_str.split(',') if kw.strip()]
                if exc_kws and any(re.search(r'\b'+re.escape(kw)+r'\b', bio) for kw in exc_kws): return False, "Bio contient mot-clé exclu"

        logger.info(f"{username} passe tous les filtres User.")
        return True, "Passe filtres"


    def execute(self, options):
        self.driver = self.app_manager.browser_handler.driver
        if not self.driver: self.logger.error("Navigateur non dispo pour Follow."); return False, "Navigateur non dispo."
        
        target_user_to_follow = None
        # Gérer si la tâche est pour un user unique (post-interaction) ou depuis la file
        if options.get('source') in ['post_like', 'post_comment', 'new_follower_interaction']: # Convention pour tâches uniques
            target_user_to_follow = options.get('target_user')
            self.logger.info(f"FollowAction (unique) pour {target_user_to_follow} via {options.get('source')}.")
        elif options.get('use_app_manager_queue', False):
            target_user_to_follow = self.app_manager.get_next_user_for_follow() # Lit déjà la liste d'exclusion
            if not target_user_to_follow: return True, "File d'attente Follow vide (après exclusion)."
        else: target_user_to_follow = options.get('target_user') # Cible directe (peu utilisé)
            
        if not target_user_to_follow: return False, "Aucun utilisateur cible valide pour Follow."

        self.logger.info(f"FollowAction: Traitement de '{target_user_to_follow}'.")

        # --- Navigation & Scraping Infos Profil pour Filtres ---
        profile_url = f"https://www.instagram.com/{target_user_to_follow}/"
        if not self.driver.current_url.replace("www.","").startswith(profile_url.replace("www.","")):
             if not self.app_manager.browser_handler.navigate_to(profile_url):
                 self.app_manager.mark_user_as_followed(target_user_to_follow, success=False); return False, f"Échec navigation {target_user_to_follow}."
             time.sleep(random.uniform(2, 4)) # Laisse le temps de charger un minimum
        
        # Check si la page est une page d'erreur
        page_title_lower = self.driver.title.lower()
        if "page not found" in page_title_lower or "contenu non disponible" in page_title_lower or "content unavailable" in page_title_lower :
            self.logger.warning(f"Profil {target_user_to_follow} non trouvé ou inaccessible (Titre: {self.driver.title}).")
            self.app_manager.mark_user_as_followed(target_user_to_follow, success=False); return False, f"Profil {target_user_to_follow} inaccessible."

        profile_info = self._get_profile_info_for_filtering(target_user_to_follow)
        if profile_info is None: # Échec critique scraping
             msg = f"Scraping infos profil {target_user_to_follow} échoué critiquement. Skip."
             self.logger.error(msg); self.app_manager.mark_user_as_followed(target_user_to_follow, success=False); return False, msg
        
        # --- Appliquer Filtres (maintenant inclut tout, même relation) ---
        can_follow, filter_reason = self._apply_user_filters(target_user_to_follow, profile_info)
        if not can_follow:
            self.logger.info(f"FollowAction: '{target_user_to_follow}' filtré. Raison: {filter_reason}")
            self.app_manager.mark_user_as_followed(target_user_to_follow, success=False) # Marquer comme traité (non suivi)
            return True, f"Filtré: {filter_reason}" # Succès du "traitement" de l'utilisateur

        # Si on est ici, l'utilisateur a passé tous les filtres, et n'est pas DÉJÀ suivi par le bot
        # La vérif `profile_info.get('i_am_following')` dans `_apply_user_filters` s'en est chargée.
        # On s'attend donc à trouver le bouton "Follow".

        try:
            self.logger.info(f"Tentative de clic sur 'Follow' pour {target_user_to_follow}...")
            wait = WebDriverWait(self.driver, 10)
            follow_button = wait.until(EC.element_to_be_clickable((By.XPATH, ProfilePageLocators.FOLLOW_BUTTON_XPATH)))
            
            # Scroll vers le bouton
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", follow_button)
            time.sleep(0.5)

            try: follow_button.click()
            except ElementClickInterceptedException: self.driver.execute_script("arguments[0].click();", follow_button); self.logger.debug("Clic JS sur Follow.")
            time.sleep(random.uniform(1.5, 3.0)) # Pause après clic pour laisser l'UI se mettre à jour

            block_reason = self._check_for_block_popup() # Check popup après clic
            if block_reason:
                 self.app_manager.mark_user_as_followed(target_user_to_follow, success=False); return False, block_reason

            # Confirmer que le bouton est devenu "Following" ou "Requested"
            if self._check_if_already_following_or_requested(timeout=5):
                 msg = f"'{target_user_to_follow}' suivi avec succès."
                 self.logger.info(f"FollowAction: {msg}")
                 self.app_manager.mark_user_as_followed(target_user_to_follow, success=True)
                 # --- Déclencher DM si configuré (ici car c'est un succès réel) ---
                 if self.app_manager.get_setting("dm_after_follow_enabled", False):
                      # ... (logique pour get dm_texts, choisir un, start_main_task("auto_send_dm") comme avant)
                      dm_texts_list = self.app_manager.current_settings.get("dm_after_follow_texts", [])
                      if dm_texts_list:
                          chosen_dm = random.choice(dm_texts_list)
                          dm_options = {'target_user': target_user_to_follow, 'message_text': chosen_dm}
                          self.logger.info(f"Déclenchement DM vers {target_user_to_follow} après follow.")
                          self.app_manager.start_main_task("auto_send_dm", dm_options)
                 return True, msg
            else: # Échec de confirmation
                 msg = f"Statut Follow non confirmé pour {target_user_to_follow} après clic."
                 self.logger.warning(f"FollowAction: {msg} (Potentiel blocage silencieux/rapide unfollow de leur part?).")
                 self.app_manager.mark_user_as_followed(target_user_to_follow, success=False)
                 # On ne retourne pas "BLOCKED_SUSPECTED" pour laisser TaskScheduler décider en cas d'erreurs répétées
                 return False, msg

        except TimeoutException:
             msg = f"Bouton Follow non trouvé/cliquable pour {target_user_to_follow} (Timeout post-filtres)."
             self.logger.warning(msg); self.app_manager.mark_user_as_followed(target_user_to_follow, success=False); return False, msg
        except NoSuchElementException:
             msg = f"Bouton Follow (NoSuchElement) pour {target_user_to_follow} post-filtres."
             self.logger.warning(msg); self.app_manager.mark_user_as_followed(target_user_to_follow, success=False); return False, msg
        except Exception as e:
            self.logger.error(f"Erreur inattendue pendant action Follow sur {target_user_to_follow}: {e}", exc_info=True)
            block_reason = self._check_for_block_popup()
            final_msg = block_reason if block_reason else f"Erreur Follow: {e}"
            self.app_manager.mark_user_as_followed(target_user_to_follow, success=False); return False, final_msg


    def _check_for_block_popup(self): # Doit être défini DANS la classe ou importé si c'est un helper global
        """Vérifie la présence d'un popup de blocage connu."""
        try:
            block_texts = [
                ErrorAndBlockLocators.ACTION_BLOCKED_TEXT_XPATH,
                ErrorAndBlockLocators.TRY_AGAIN_LATER_TEXT_XPATH,
                ErrorAndBlockLocators.RATE_LIMIT_TEXT_XPATH
            ]
            for i, block_xpath in enumerate(block_texts):
                if not block_xpath or not block_xpath[1]: continue # Skip si sélecteur vide
                elements = self.driver.find_elements(block_xpath[0], block_xpath[1]) # Utiliser By et value
                if elements:
                    msg = f"BLOCKED: Popup détecté (Pattern {i+1})."
                    self.logger.warning(msg)
                    return msg
        except TimeoutException: # find_elements ne lève pas ça, mais un wait le ferait
            pass
        except Exception as e:
            self.logger.error(f"Erreur dans _check_for_block_popup: {e}")
        return None