# mon_bot_social/automation_engine/actions/comment_action.py
import time
import random
import re # Pour _parse_interaction_count_string_helper
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    ElementNotInteractableException, StaleElementReferenceException,
    ElementClickInterceptedException
)

from automation_engine.element_selectors import PostLocators, ErrorAndBlockLocators

# Copier le helper depuis LikeAction ou le mettre dans un utils partagé
def _parse_interaction_count_string_helper(count_str):
    if not count_str: return None
    text = str(count_str).lower().replace(',', '').replace(' ', '')
    text = text.replace('likes','').replace('j’aime','').replace('comments','').replace('commentaires','')
    text = re.sub(r'\s*and\s*\d+\s*others', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*et\s*\d+\s*autres', '', text, flags=re.IGNORECASE)
    text = re.sub(r'view\s*all\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'afficher\s*les\s*', '', text, flags=re.IGNORECASE)
    text = text.strip()
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
        except ValueError: return None
    else: return None
    return int(val)

class CommentAction:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.driver = None
        self.logger = self.app_manager.logger
        self.commented_this_session_count = 0

    def _get_post_id_from_element_or_url(self, post_element=None): # Dupliqué/adapté de LikeAction
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
        return None
        
    def _get_post_owner_username(self, post_element): # Dupliqué/adapté de LikeAction
        try:
            owner_link = post_element.find_element(By.XPATH, PostLocators.POST_OWNER_LINK_XPATH)
            href = owner_link.get_attribute("href"); username = urlparse(href).path.strip('/')
            if username and '/' not in username: return username
            parts = [p for p in username.split('/') if p and p not in ['p','reel','tv','stories']]
            return parts[0] if parts else None
        except: return None

    def _extract_post_caption(self, post_element): # Dupliqué/adapté de LikeAction
        caption_text = ""; 
        try:
            try: # ... (clic "... more") ...
                more_button = WebDriverWait(post_element, 0.5).until(EC.element_to_be_clickable((By.XPATH, PostLocators.MORE_CAPTION_BUTTON_XPATH)))
                more_button.click(); time.sleep(0.3)
            except: pass 
            caption_elements = post_element.find_elements(By.XPATH, PostLocators.POST_CAPTION_TEXT_XPATH) # ...
            if caption_elements: caption_text = " ".join([elem.text for elem in caption_elements if elem.text]).strip()
            try: # ... (ajout hashtags) ...
                hashtag_elements = post_element.find_elements(By.XPATH, PostLocators.HASHTAG_LINKS_IN_CAPTION_XPATH)
                if hashtag_elements: caption_text += " " + " ".join([ht.text for ht in hashtag_elements if ht.text])
            except: pass
        except StaleElementReferenceException: self.logger.warning("Élément légende 'stale'."); return ""
        except Exception as e: self.logger.warning(f"Erreur extraction légende pour Comment: {e}")
        return caption_text.lower()

    def _get_post_counts(self, post_element): # Dupliqué/adapté de LikeAction
        like_count, comment_count = None, None; # ... (logique pour parser les counts)
        try:
            like_els = post_element.find_elements(By.XPATH, PostLocators.LIKE_COUNT_TEXT_XPATH) # ...
            if like_els: #... (parser le texte) ... like_count = _parse_interaction_count_string_helper(...)
        except: pass
        try:
            comm_els = post_element.find_elements(By.XPATH, PostLocators.VIEW_ALL_COMMENTS_BUTTON_XPATH) # ...
            if comm_els: #... (parser le texte) ... comment_count = _parse_interaction_count_string_helper(...)
        except: pass
        return like_count, comment_count

    def _check_for_block_popup(self): # Dupliqué/adapté
        try: #... (check ErrorAndBlockLocators)
            block_xpaths = [ErrorAndBlockLocators.ACTION_BLOCKED_TEXT_XPATH, ErrorAndBlockLocators.TRY_AGAIN_LATER_TEXT_XPATH]
            for i, xpath_tuple in enumerate(block_xpaths):
                if not xpath_tuple or not xpath_tuple[1]: continue
                if self.driver.find_elements(xpath_tuple[0], xpath_tuple[1]):
                    msg = f"BLOCKED: Popup détecté (Pattern {i+1})."; self.logger.warning(msg); return msg
        except: pass
        return None


    def _post_comment(self, post_element, comment_text):
        if not comment_text: return "no_comment_text", "Texte commentaire vide.", None # Ajouter owner
        
        owner_username = self._get_post_owner_username(post_element) # Récupérer avant modif DOM
        like_count_before, comment_count_before = self._get_post_counts(post_element) # Counts avant

        try:
            comment_area_wait = WebDriverWait(post_element, 7) # Attendre un peu plus pour le champ
            comment_area = comment_area_wait.until(
                EC.element_to_be_clickable((By.XPATH, PostLocators.COMMENT_TEXT_AREA_XPATH))
            )
            self.driver.execute_script("arguments[0].scrollIntoViewIfNeeded({block: 'center'});", comment_area)
            time.sleep(0.5)
            comment_area.click(); time.sleep(0.3)
            comment_area.clear() # Peut être nécessaire
            comment_area.send_keys(comment_text)
            self.logger.debug(f"Commentaire saisi: '{comment_text[:30]}...'")
            time.sleep(random.uniform(1.0, 2.0))

            # Trouver et cliquer sur "Post" (bouton souvent HORS du post_element, donc self.driver)
            post_button = WebDriverWait(self.driver, 7).until( # Augmenter l'attente si besoin
                EC.element_to_be_clickable((By.XPATH, PostLocators.POST_COMMENT_BUTTON_XPATH))
            )
            try: post_button.click()
            except ElementClickInterceptedException: self.driver.execute_script("arguments[0].click();", post_button); self.logger.debug("Clic JS sur Post Comment.")
            
            self.logger.info(f"Commentaire envoyé (ou tentative) sur post de {owner_username}.")
            time.sleep(random.uniform(3, 6)) # Attente PLUS LONGUE pour traitement du commentaire

            block_msg = self._check_for_block_popup()
            if block_msg: return "blocked", block_msg, owner_username, like_count_before, comment_count_before

            # Vérif basique: le champ est-il vide ? (Peu fiable)
            # Idéalement: scraper les commentaires et voir si le nôtre y est. Très complexe.
            try:
                current_val = comment_area.get_attribute("value") # Récupérer le nouvel élément
                if not current_val: # Si vide, bon signe
                    return "success", "Commentaire posté (champ vidé).", owner_username, like_count_before, comment_count_before
                else:
                    self.logger.warning(f"Champ commentaire non vide ('{current_val[:30]}...') après post. Succès supposé mais incertain.")
                    return "success_unconfirmed", "Succès supposé (champ non vide).", owner_username, like_count_before, comment_count_before
            except StaleElementReferenceException: # Champ recréé (bon signe)
                return "success", "Commentaire posté (champ recréé).", owner_username, like_count_before, comment_count_before

        except (NoSuchElementException, TimeoutException): return "not_found", "Champ/Bouton Comment non trouvé.", owner_username, like_count_before, comment_count_before
        except ElementNotInteractableException: return "not_interactable", "Champ/Bouton Comment non interactif.", owner_username, like_count_before, comment_count_before
        except Exception as e: return "error", f"Erreur post commentaire: {str(e)}", owner_username, like_count_before, comment_count_before


    def comment_on_feed(self, num_posts_to_comment, comment_texts_ignored=None): # comment_texts vient d'AppManager
        # ... (Navigation feed, scroll, boucle sur posts...)
        action_results = []; commented_count_this_run = 0; processed_post_ids = set()
        # ...
        for post_element in posts_on_screen:
            # ... (Check limites, get post_id, check processed/commented DB...)
            if self.app_manager.has_commented_post(post_id): continue

            post_owner = self._get_post_owner_username(post_element)
            if self.app_manager.is_excluded(post_owner): # ... (skip si exclu)
            
            post_caption = self._extract_post_caption(post_element)
            comment_to_post = self.app_manager.get_contextual_comment(post_caption) # Utilise logique AppManager
            if not comment_to_post: self.logger.warning("Aucun commentaire (générique/contextuel) à poster."); continue

            status, message, owner_scraped, l_count, c_count = self._post_comment(post_element, comment_to_post)
            self.logger.info(f"Comment Feed - Post {post_id} (Owner:{post_owner}): {status} - '{comment_to_post[:20]}...'")
            
            if status.startswith("success"):
                self.app_manager.add_commented_post(post_id, comment_to_post, l_count, c_count) # Passer counts
                commented_count_this_run +=1; self.commented_this_session_count +=1
                action_results.append({'post_id': post_id, 'owner': post_owner, 'status': 'commented', 'comment_text': comment_to_post, 'l_count': l_count, 'c_count': c_count})
                # ... (délai)
            elif status == "blocked": return False, action_results # Arrêter si blocage
        return True, action_results


    def comment_user_last_posts(self, username, num_posts_to_comment, comment_texts_ignored=None):
        # ... (Navigation profil, get thumbnails...)
        action_results = []; commented_count_for_user = 0 # ...
        # ... (Boucle sur thumbnails)
            # ... (Get URL, check si traité/commenté DB)
            # ... (Naviguer vers post)
            try:
                # ... (get post_container, current_post_id)
                if self.app_manager.has_commented_post(current_post_id): continue

                post_caption = self._extract_post_caption(post_container)
                comment_to_post = self.app_manager.get_contextual_comment(post_caption)
                if not comment_to_post: continue

                status, message, owner_scraped, l_count, c_count = self._post_comment(post_container, comment_to_post)
                # ... (Log, if success: add_commented_post avec counts, incréments, action_results, délai)
                if status.startswith("success"):
                    action_results.append({'post_id': current_post_id, 'owner': username, 'status': 'commented', 'comment_text': comment_to_post, 'l_count':l_count, 'c_count':c_count})
                # ...
                if status == "blocked": return False, action_results # Arrêter si blocage
            except: #...
        return True, action_results


    def execute(self, options):
        self.driver = self.app_manager.browser_handler.driver; #...
        if not self.driver: return False, {"message": "Nav non dispo.", "results": [], "original_options": options}
        
        self.commented_this_session_count = 0
        comment_source = options.get("comment_source", "feed")
        num_comments_overall_limit = options.get("num_comments_per_run", 3)
        # comment_texts sont gérés par AppManager.get_contextual_comment() maintenant

        overall_success = True; combined_results = []; final_summary_message = ""

        if comment_source == "feed":
            success, results = self.comment_on_feed(num_posts_to_comment=num_comments_overall_limit)
            if success and isinstance(results, list): combined_results.extend(results)
            else: overall_success = False
            final_summary_message = f"{len(combined_results)} commentaires sur le feed."
        elif comment_source == "users_last_posts":
            target_users = options.get("target_users_list", []) #...
            # ... (boucle sur users, appel comment_user_last_posts)
            # ...
            final_summary_message = f"{len(combined_results)} commentaires sur {users_processed_count} profils."
        else:
            return False, {"message": f"Source inconnue: {comment_source}", "results": [], "original_options": options}

        return overall_success, {'results': combined_results, 'original_options': options, 'message': final_summary_message}