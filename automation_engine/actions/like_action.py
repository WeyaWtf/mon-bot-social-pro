# mon_bot_social/automation_engine/actions/like_action.py
import time
import random
import re
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    StaleElementReferenceException, ElementClickInterceptedException
)

from automation_engine.element_selectors import PostLocators, ErrorAndBlockLocators # Ajouter ErrorAndBlockLocators

def _parse_interaction_count_string_helper(count_str): # Helper global ou local
    if not count_str: return None
    text = str(count_str).lower().replace(',', '').replace(' ', '')
    text = text.replace('likes','').replace('j’aime','').replace('comments','').replace('commentaires','')
    text = re.sub(r'\s*and\s*\d+\s*others', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*et\s*\d+\s*autres', '', text, flags=re.IGNORECASE)
    text = re.sub(r'view\s*all\s*', '', text, flags=re.IGNORECASE) # Ex: "View all 10 comments"
    text = re.sub(r'afficher\s*les\s*', '', text, flags=re.IGNORECASE)
    text = text.strip()
    
    num_part_match = re.search(r'([\d\.]+)', text)
    num_str = ""
    if num_part_match: num_str = num_part_match.group(1)
    else:
        if not any(char.isdigit() for char in text) and ('k' in text or 'm' in text or 'b' in text): num_str = text
    
    val = 0
    if 'k' in num_str: val = float(num_str.replace('k', '')) * 1000
    elif 'm' in num_str: val = float(num_str.replace('m', '')) * 1000000
    elif 'b' in num_str: val = float(num_str.replace('b', '')) * 1000000000
    elif num_str:
        try: val = float(num_str)
        except ValueError: return None
    else: return None
    return int(val)


class LikeAction:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.driver = None
        self.logger = self.app_manager.logger
        self.liked_this_session_count = 0 # Total de likes pour CETTE exécution de la tâche Auto-Like

    def _get_post_id_from_element_or_url(self, post_element=None):
        current_url = self.driver.current_url; path = urlparse(current_url).path.strip('/')
        if path.startswith('p/'):
            try: return path.split('/')[1]
            except IndexError: pass
        elif path.startswith('reel/'):
            try: return f"reel_{path.split('/')[1]}"
            except IndexError: pass
        if post_element:
            links_xpath = ['.//a[contains(@href, "/p/")]', './/a[contains(@href, "/reel/")]']
            for xpath in links_xpath:
                try:
                    link_el = post_element.find_element(By.XPATH, xpath)
                    href = link_el.get_attribute('href'); p_path = urlparse(href).path.strip('/')
                    if p_path.startswith('p/'): return p_path.split('/')[1]
                    if p_path.startswith('reel/'): return f"reel_{p_path.split('/')[1]}"
                except: continue
        self.logger.debug("Impossible de déterminer l'ID du post/reel.")
        return None

    def _get_post_owner_username(self, post_element):
        try:
            owner_link = post_element.find_element(By.XPATH, PostLocators.POST_OWNER_LINK_XPATH)
            href = owner_link.get_attribute("href"); username = urlparse(href).path.strip('/')
            if username and '/' not in username: return username # Simple username
            # Gérer les cas où href peut contenir plus, ex: /reel/username/ ou /p/username/
            parts = [p for p in username.split('/') if p and p not in ['p','reel','tv','stories']]
            return parts[0] if parts else None # Prendre la première partie significative
        except (NoSuchElementException, AttributeError, IndexError): return None

    def _is_post_already_liked_ui(self, post_element_or_driver_scope):
        try:
            # WebDriverWait pour une très courte durée, car find_elements ne lèvera pas d'erreur
            WebDriverWait(post_element_or_driver_scope, 0.2).until(
                 EC.presence_of_element_located((By.XPATH, PostLocators.UNLIKE_BUTTON_SVG_XPATH))
            )
            return True # Coeur rouge trouvé
        except TimeoutException: return False


    def _extract_post_caption(self, post_element):
        caption_text = ""; logger = self.logger
        try:
            try:
                more_button = WebDriverWait(post_element, 0.5).until(EC.element_to_be_clickable((By.XPATH, PostLocators.MORE_CAPTION_BUTTON_XPATH)))
                more_button.click(); time.sleep(0.3)
            except: pass 
            caption_elements = post_element.find_elements(By.XPATH, PostLocators.POST_CAPTION_TEXT_XPATH)
            if caption_elements: caption_text = " ".join([elem.text for elem in caption_elements if elem.text]).strip()
            try:
                hashtag_elements = post_element.find_elements(By.XPATH, PostLocators.HASHTAG_LINKS_IN_CAPTION_XPATH)
                if hashtag_elements: caption_text += " " + " ".join([ht.text for ht in hashtag_elements if ht.text])
            except: pass
        except StaleElementReferenceException: logger.warning("Élément légende 'stale'."); return ""
        except Exception as e: logger.warning(f"Erreur extraction légende: {e}")
        return caption_text.lower()

    def _get_post_counts(self, post_element):
        like_count, comment_count = None, None; logger = self.logger
        try:
            like_count_elements = post_element.find_elements(By.XPATH, PostLocators.LIKE_COUNT_TEXT_XPATH)
            if like_count_elements:
                raw_text = ""; 
                for el in like_count_elements:
                    if el.text.strip(): raw_text = el.text.strip(); break
                if raw_text: like_count = _parse_interaction_count_string_helper(raw_text)
        except: pass
        try:
            comment_count_elements = post_element.find_elements(By.XPATH, PostLocators.VIEW_ALL_COMMENTS_BUTTON_XPATH)
            if comment_count_elements:
                raw_text = ""; 
                for el in comment_count_elements:
                     if el.text.strip(): raw_text = el.text.strip(); break
                if raw_text: comment_count = _parse_interaction_count_string_helper(raw_text)
        except: pass
        return like_count, comment_count

    def _check_for_block_popup(self): # Helper (peut être partagé ou ici)
        try:
            block_xpaths = [ErrorAndBlockLocators.ACTION_BLOCKED_TEXT_XPATH, ErrorAndBlockLocators.TRY_AGAIN_LATER_TEXT_XPATH]
            for i, xpath_tuple in enumerate(block_xpaths):
                if not xpath_tuple or not xpath_tuple[1]: continue
                if self.driver.find_elements(xpath_tuple[0], xpath_tuple[1]):
                    msg = f"BLOCKED: Popup détecté (Pattern {i+1})."; self.logger.warning(msg); return msg
        except: pass
        return None


    def _apply_like_filters(self, post_element, post_id, post_owner=None):
        settings = self.app_manager.current_settings; logger = self.logger
        if self.app_manager.is_excluded(post_owner): return False, f"Auteur '{post_owner}' exclu"
        if settings.get("like_filter_skip_sponsored", True) and self._is_post_sponsored(post_element):
             return False, "Post sponsorisé"
        
        include_kws_str = settings.get("like_filter_caption_include", "")
        exclude_kws_str = settings.get("like_filter_caption_exclude", "")
        if include_kws_str or exclude_kws_str:
             caption = self._extract_post_caption(post_element)
             if include_kws_str:
                 include_kws = [kw.strip().lower() for kw in include_kws_str.split(',') if kw.strip()]
                 if include_kws and not any(re.search(r'\b'+re.escape(kw)+r'\b', caption) for kw in include_kws): return False, "Manque mot-clé requis (légende)"
             if exclude_kws_str:
                 exclude_kws = [kw.strip().lower() for kw in exclude_kws_str.split(',') if kw.strip()]
                 if exclude_kws and any(re.search(r'\b'+re.escape(kw)+r'\b', caption) for kw in exclude_kws): return False, "Contient mot-clé exclu (légende)"
        # Ajouter ici filtres d'âge de post / nb de likes existants si implémentés
        return True, "Passe filtres Like"

    def _is_post_sponsored(self, post_element): # Version simple
        try:
             return bool(post_element.find_elements(By.XPATH, PostLocators.SPONSORED_TEXT_INDICATOR_XPATH))
        except: return False

    def _click_like_button(self, post_element):
        status, message = "error", "Erreur clic Like inconnue"
        owner_username = self._get_post_owner_username(post_element) # Récupérer avant que l'UI change
        
        if self._is_post_already_liked_ui(post_element): return "already_liked", "Déjà liké (UI)", owner_username
        try:
            # S'assurer que le conteneur du bouton (ou le bouton lui-même) est visible
            button_container_xpath = PostLocators.LIKE_BUTTON_CONTAINER_XPATH or PostLocators.LIKE_BUTTON_SVG_XPATH
            container_to_click = WebDriverWait(post_element, 5).until(EC.presence_of_element_located((By.XPATH, button_container_xpath)))
            self.driver.execute_script("arguments[0].scrollIntoViewIfNeeded({block: 'center'});", container_to_click)
            time.sleep(0.3) # Attendre scroll
            
            # Cliquer sur le conteneur (plus fiable) ou le SVG
            like_button_to_click = WebDriverWait(container_to_click, 3).until(EC.element_to_be_clickable((By.XPATH, PostLocators.LIKE_BUTTON_SVG_XPATH if PostLocators.LIKE_BUTTON_SVG_XPATH.startswith(".//") else ".//*[local-name()='svg' and (@aria-label='Like' or @aria-label='J’aime')]"))) # S'assurer que c'est bien le SVG coeur vide

            try: like_button_to_click.click()
            except ElementClickInterceptedException: self.driver.execute_script("arguments[0].click();", like_button_to_click)
            time.sleep(random.uniform(0.8, 1.8)) # Attente màj UI

            block_msg = self._check_for_block_popup()
            if block_msg: return "blocked", block_msg, owner_username

            if self._is_post_already_liked_ui(post_element): return "success", "Liké (confirmé UI)", owner_username
            else: return "failed_to_confirm", "Non confirmé liké après clic", owner_username
        except (NoSuchElementException, TimeoutException): return "not_found", "Bouton Like (coeur vide) non trouvé", owner_username
        except Exception as e: return "error", f"Erreur clic: {str(e)}", owner_username

    # --- Méthodes d'action principale ---
    def like_posts_on_feed(self, num_posts_to_like):
        self.logger.info(f"Auto-Like sur Feed: {num_posts_to_like} posts ciblés.")
        # ... (navigation, scroll) ...
        action_results = []; liked_count_this_run = 0; processed_post_ids = set()
        attempts = 0; max_attempts = num_posts_to_like * 5 # Plus de tentatives

        while liked_count_this_run < num_posts_to_like and attempts < max_attempts:
            attempts += 1; posts_on_screen = self.driver.find_elements(By.XPATH, PostLocators.ARTICLE_POST_XPATH)
            if not posts_on_screen and attempts < max_attempts / 2: # Si vide, scroller et réessayer
                 self.driver.execute_script("window.scrollBy(0, window.innerHeight*1.5);"); time.sleep(random.uniform(3,4)); continue
            elif not posts_on_screen : break

            found_actionable_post = False
            for post_element in posts_on_screen:
                if liked_count_this_run >= num_posts_to_like: break
                try:
                    post_id = self._get_post_id_from_element_or_url(post_element)
                    if not post_id or post_id in processed_post_ids: continue
                    processed_post_ids.add(post_id)
                    if self.app_manager.has_liked_post(post_id): continue

                    post_owner = self._get_post_owner_username(post_element)
                    passes_filters, filter_reason = self._apply_like_filters(post_element, post_id, post_owner)
                    if not passes_filters: self.logger.info(f"Like Feed: Post {post_id} (Owner: {post_owner}) filtré: {filter_reason}"); continue
                    
                    like_c_before, comm_c_before = self._get_post_counts(post_element)
                    status, message, owner_username_after_click = self._click_like_button(post_element)
                    self.logger.info(f"Like Feed - Post {post_id} (Owner:{post_owner}): {status} - {message}")
                    
                    if status == "success":
                        self.app_manager.add_liked_post(post_id, like_c_before, comm_c_before)
                        liked_count_this_run += 1; self.liked_this_session_count += 1; found_actionable_post = True
                        action_results.append({'post_id': post_id, 'owner': post_owner, 'status': 'liked', 'l_count': like_c_before, 'c_count': comm_c_before})
                        time.sleep(self.app_manager.get_setting("like_delay_min", 5)) # Utiliser le délai global ici
                    elif status == "already_liked": self.app_manager.add_liked_post(post_id, like_c_before, comm_c_before)
                    elif status == "blocked": return False, action_results # Arrêter immédiatement si blocage
                except StaleElementReferenceException: continue
                except Exception as loop_err: self.logger.warning(f"Erreur boucle like feed: {loop_err}"); continue
            if liked_count_this_run < num_posts_to_like and not found_actionable_post and attempts < max_attempts:
                 self.driver.execute_script("window.scrollBy(0, window.innerHeight*1.5);"); time.sleep(random.uniform(3,5))
        return True, action_results

    def like_user_last_posts(self, username, num_posts_to_like):
        # ... (logique existante MAIS utiliser _get_post_counts, _apply_like_filters, et retourner action_results)
        action_results = []; liked_count_for_user = 0 # ...
        # ... (Naviguer, scraper thumbnails)
        for thumb_link_element in thumbnails_to_check:
            # ... (Naviguer vers post_page_url)
            try: # ... (get post_container, current_post_id)
                if self.app_manager.has_liked_post(current_post_id): continue
                passes_filters, _ = self._apply_like_filters(post_container, current_post_id, username)
                if not passes_filters: continue
                
                like_c_b, comm_c_b = self._get_post_counts(post_container)
                status, msg, owner_check = self._click_like_button(post_container)
                # ... (logique succès/échec, ajout action_results, incrément, délai)
                if status == "blocked": return False, action_results
                if liked_count_for_user >= num_posts_to_like: break
            except: # ...
        return True, action_results


    def like_specific_user_latest_post(self, username):
        # ... (Logique similaire à like_user_last_posts mais avec num_posts_to_like=1 et pas de boucle externe d'utilisateurs)
        # S'assurer qu'elle retourne aussi (success, action_results_list) où action_results_list a au plus un élément.
        # Utiliser self._get_post_counts et _apply_like_filters ici aussi.
        # Va retourner une liste avec au plus un dict de résultat si succès.
        return self.like_user_last_posts(username, num_posts_to_like=1)


    def execute(self, options):
        self.driver = self.app_manager.browser_handler.driver
        if not self.driver: return False, {"message": "Navigateur non disponible.", "results": [], "original_options": options}
        
        self.liked_this_session_count = 0 # Reset pour ce run de la tâche "auto_like"
        like_source = options.get("like_source", "feed")
        num_likes_overall_limit = options.get("num_likes_per_run", 5) # Limite pour toute cette exécution

        overall_success = True; combined_results = []; final_summary_message = ""

        if like_source == "feed":
            success, results = self.like_posts_on_feed(num_posts_to_like=num_likes_overall_limit)
            if success and isinstance(results, list): combined_results.extend(results)
            else: overall_success = False # Erreur majeure si pas liste de résultats
            final_summary_message = f"{len(combined_results)} likes sur le feed."
        elif like_source == "users_last_posts":
            target_users = options.get("target_users_list", [])
            num_posts_per_user = options.get("num_posts_to_like_per_user", 1)
            max_users_to_process = options.get("max_users_to_process_this_run", 5)
            users_processed_count = 0
            for username in target_users:
                if self.liked_this_session_count >= num_likes_overall_limit: final_summary_message += " Limite likes/tâche atteinte."; break
                if users_processed_count >= max_users_to_process: final_summary_message += f" Limite {max_users_to_process} users/tâche atteinte."; break
                
                success, results = self.like_user_last_posts(username, num_posts_to_like=num_posts_per_user)
                if success and isinstance(results, list): combined_results.extend(results)
                # overall_success &= success # Ne pas mettre False si juste aucun post trouvé pour un user
                users_processed_count += 1
                if "posts likés pour" in (results[0].get('message') if results and isinstance(results,list) and results[0].get('message') else "") : # Approximatif
                    time.sleep(self.app_manager.get_setting("delay_between_users_like", 15))
            final_summary_message = f"{len(combined_results)} likes sur {users_processed_count} profils."
        elif like_source == "location":
            location_target = options.get('location_target')
            max_post_age = options.get('location_max_post_age_minutes', 60)
            # num_likes_overall_limit est le max de posts à liker par VÉRIFICATION pour la localisation
            success, results = self.like_posts_from_location_feed(location_target, num_posts_to_like=num_likes_overall_limit, max_post_age_minutes=max_post_age)
            if success and isinstance(results, list): combined_results.extend(results) # results est la liste des dicts d'action
            else: overall_success = False
            final_summary_message = f"{len(combined_results)} likes pour loc {location_target}."
        elif like_source == "specific_user_latest": # Appelé par AppManager après story view
            target_user = options.get('target_user')
            if not target_user: return False, {"message": "User cible manquant pour like_latest_post.", "results": [], "original_options": options}
            success, results = self.like_specific_user_latest_post(target_user)
            if success and isinstance(results, list): combined_results.extend(results)
            else: overall_success = False
            final_summary_message = f"{len(combined_results)} dernier post liké pour {target_user}."
        elif like_source == "specific_post": # Appelé par AppManager après comment
            target_post_id = options.get('target_post_id')
            # Implémenter une méthode self.like_single_post_by_id(post_id) qui navigue et like
            # Pour l'instant, ceci n'est pas complètement implémenté.
            self.logger.warning("Liker un post spécifique par ID n'est pas encore complètement implémenté dans LikeAction.execute")
            final_summary_message = "Like post spécifique non implémenté."
            overall_success = False
        else: 
            return False, {"message": f"Source de like inconnue: {like_source}", "results": [], "original_options": options}

        return overall_success, {'results': combined_results, 'original_options': options, 'message': final_summary_message}