# mon_bot_social/automation_engine/actions/direct_message_action.py
import time
import random
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, 
    ElementNotInteractableException, ElementClickInterceptedException
)

from automation_engine.element_selectors import ProfilePageLocators, DMInboxLocators, ErrorAndBlockLocators

class DirectMessageAction:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.driver = None
        self.logger = self.app_manager.logger

    def _check_for_block_popup(self): # Helper
        try:
            block_xpaths = [ErrorAndBlockLocators.ACTION_BLOCKED_TEXT_XPATH, ErrorAndBlockLocators.TRY_AGAIN_LATER_TEXT_XPATH]
            for i, xpath_tuple in enumerate(block_xpaths):
                if not xpath_tuple or not xpath_tuple[1]: continue
                if self.driver.find_elements(xpath_tuple[0], xpath_tuple[1]):
                    msg = f"BLOCKED: Popup détecté (Pattern {i+1}) pour DM."; self.logger.warning(msg); return msg
        except: pass
        return None

    def send_dm_to_user(self, username, message_text_template):
        """Tente d'envoyer un DM à un utilisateur spécifique."""
        self.driver = self.app_manager.browser_handler.driver
        if not self.driver: return False, "Navigateur non disponible pour DM."
        if not message_text_template: return False, "Texte de message DM vide."
        
        # Remplacer {username} placeholder
        message_to_send = message_text_template.replace("{username}", username).replace("{USERNAME}", username)
        self.logger.info(f"Tentative d'envoi de DM à {username}: '{message_to_send[:50]}...'")

        original_url = self.driver.current_url # Sauvegarder l'URL actuelle pour y revenir
        
        try:
            # Étape 1: S'assurer d'être sur le profil de l'utilisateur
            profile_url = f"https://www.instagram.com/{username}/"
            if not self.driver.current_url.replace("www.","").startswith(profile_url.replace("www.","")):
                self.logger.debug(f"DM: Navigation vers profil {username}")
                if not self.app_manager.browser_handler.navigate_to(profile_url):
                    return False, f"Échec navigation profil {username} pour DM."
                time.sleep(random.uniform(2.5, 4.0)) # Attente chargement profil
            
            # Étape 2: Cliquer sur le bouton "Message" sur le profil
            self.logger.debug(f"DM: Recherche bouton 'Message' pour {username}")
            message_button = WebDriverWait(self.driver, 10).until(
                 EC.element_to_be_clickable((By.XPATH, ProfilePageLocators.MESSAGE_BUTTON_XPATH))
            )
            self.driver.execute_script("arguments[0].scrollIntoViewIfNeeded(true);", message_button) # Assurer visibilité
            time.sleep(0.5)
            message_button.click()
            self.logger.debug(f"DM: Clic sur bouton 'Message'. Attente chargement interface DM...")
            # Attente que l'interface DM (souvent une modale ou une nouvelle section) se charge.
            # C'est crucial et peut nécessiter une attente spécifique à un élément de l'interface DM.
            # Par exemple, attendre que le champ de saisie devienne visible.
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, DMInboxLocators.INPUT_FIELD_XPATH))
            )
            self.logger.debug("DM: Interface de chat détectée.")
            time.sleep(random.uniform(1.0, 2.0)) # Stabilisation UI DM

            # Étape 3: Trouver le champ de saisie et écrire le message
            self.logger.debug("DM: Recherche champ de saisie du message...")
            message_input = WebDriverWait(self.driver, 10).until( # Augmenter attente si interface DM lente
                EC.element_to_be_clickable((By.XPATH, DMInboxLocators.INPUT_FIELD_XPATH))
            )
            message_input.click() # Activer le champ
            time.sleep(0.3)
            message_input.clear() # Optionnel, mais bien si champ pré-rempli
            message_input.send_keys(message_to_send)
            self.logger.debug(f"DM: Message saisi.")
            time.sleep(random.uniform(0.8, 1.8)) # Simuler frappe

            # Étape 4: Trouver et cliquer sur le bouton "Envoyer"
            self.logger.debug("DM: Recherche bouton 'Envoyer'...")
            # S'assurer que le bouton Envoyer est cliquable (parfois désactivé si message vide)
            send_button = WebDriverWait(self.driver, 7).until(
                EC.element_to_be_clickable((By.XPATH, DMInboxLocators.SEND_BUTTON_XPATH))
            )
            send_button.click()
            self.logger.info(f"DM envoyé (tentative) à {username}.")
            time.sleep(random.uniform(2.5, 4.5)) # Pause après envoi pour laisser le temps à IG

            # Vérifier un blocage popup APRES l'action d'envoi
            block_msg = self._check_for_block_popup()
            if block_msg: return False, block_msg

            # Étape 5: Fermer la fenêtre de chat (propreté, et pour éviter interférences)
            self.logger.debug("DM: Tentative de fermeture du chat DM...")
            if not self._click_element_if_exists(By.XPATH, DMInboxLocators.CLOSE_CHAT_BUTTON_XPATH, "Close DM Chat", timeout=3):
                 self.logger.warning("N'a pas pu fermer explicitement le chat DM. Tentative de retour à l'URL précédente.")
                 self.app_manager.browser_handler.navigate_to(original_url if original_url and original_url != self.driver.current_url else "https://www.instagram.com/")
                 time.sleep(1)
            else:
                 self.logger.info("Chat DM fermé.")


            # Vérification du succès ? Difficile sans lire les messages envoyés.
            # On suppose le succès si pas d'erreur et pas de popup de blocage.
            return True, f"DM (présumé) envoyé à {username}."

        except TimeoutException as e_timeout:
            self.logger.error(f"DM Échec (Timeout): Élément non trouvé pour {username}. {e_timeout}")
            return False, f"DM Échec Timeout: {e_timeout}"
        except NoSuchElementException as e_no_el:
            self.logger.error(f"DM Échec (NoSuchElement): Élément non trouvé pour {username}. {e_no_el}")
            return False, f"DM Échec NoSuchElement: {e_no_el}"
        except ElementNotInteractableException as e_interact:
            self.logger.error(f"DM Échec (NotInteractable): Élément non interactif pour {username}. {e_interact}")
            return False, f"DM Échec NotInteractable: {e_interact}"
        except Exception as e:
            self.logger.error(f"DM Erreur inattendue pour {username}: {e}", exc_info=True)
            block_msg = self._check_for_block_popup() # Vérifier blocage même sur erreur générale
            return False, block_msg or f"DM Erreur Inattendue: {e}"
        finally:
             # S'assurer de revenir à une page neutre si on n'est pas déjà revenu
             # Ou au moins, ne pas rester bloqué dans l'interface DM si possible
             # Mais si on ferme la modale DM, on est souvent déjà sur le profil ou l'URL d'origine.
             # La navigation vers original_url ci-dessus devrait aider si le bouton fermer échoue.
             pass


    def execute(self, options):
        """Exécute l'envoi d'un DM. Appelé par TaskScheduler pour la tâche 'auto_send_dm'."""
        target_user = options.get('target_user')
        message_text_template = options.get('message_text')
        
        if not target_user or not message_text_template:
            self.logger.error("DM Action: Utilisateur cible ou template de message manquant.")
            return False, "Données DM manquantes."
            
        # Vérifier l'exclusion avant d'envoyer (important pour les DMs)
        if self.app_manager.is_excluded(target_user):
            self.logger.info(f"DM Skipped: Utilisateur {target_user} est dans la liste d'exclusion.")
            return True, f"DM non envoyé à {target_user} (exclu)." # Succès du "traitement" car intentionnel
            
        # Envoyer le DM
        success, message = self.send_dm_to_user(target_user, message_text_template)
        
        # Optionnel : Enregistrer une statistique pour les DMs envoyés (si 'dms_sent' existe comme action_type)
        if success:
             self.app_manager.record_action('dms_sent') # Assurer que 'dms_sent' est un type valide dans database.py
        
        # La structure de retour pour le TaskScheduler attend (bool, dict) si c'est une action qui alimente des handlers post-action.
        # Pour un DM simple, un message suffit mais soyons consistents.
        return success, {"message": message, "target_user": target_user, "dm_sent_status": success}

    def _click_element_if_exists(self, by_method, selector_value, description="element", timeout=1.0): # Copié de ViewStoryAction
        try:
            element = WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by_method, selector_value)))
            try: element.click()
            except ElementClickInterceptedException: self.driver.execute_script("arguments[0].click();", element)
            return True
        except TimeoutException: return False
        except Exception as e: self.logger.warning(f"Erreur clic sur '{description}': {e}"); return False