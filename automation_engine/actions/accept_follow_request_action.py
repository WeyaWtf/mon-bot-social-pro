# mon_bot_social/automation_engine/actions/accept_follow_request_action.py
import time
import random
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from automation_engine.element_selectors import NotificationsPageLocators, ErrorAndBlockLocators

class AcceptFollowRequestAction:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.driver = None
        self.logger = self.app_manager.logger
        self.accepted_this_session_count = 0 # Compteur pour cette exécution de la tâche

    def _navigate_to_follow_requests_page(self):
        """Tente de naviguer vers la page des demandes d'abonnement. Retourne True si succès."""
        self.logger.info("Tentative de navigation vers la page des demandes d'abonnement...")

        # Instagram change fréquemment cette navigation.
        # 1. Essayer une URL directe (très instable, change souvent)
        # direct_url = "https://www.instagram.com/accounts/activity/?followRequests=1" # Exemple ancien
        # try:
        #     self.driver.get(direct_url)
        #     time.sleep(random.uniform(2,4))
        #     # Vérifier si on est sur la bonne page (par titre ou présence d'éléments spécifiques)
        #     if "Requests" in self.driver.title or self.driver.find_elements(By.XPATH, NotificationsPageLocators.ACCEPT_REQUEST_BUTTON_XPATH):
        #         self.logger.info("Accès direct à la page des demandes (ou déjà dessus).")
        #         return True
        # except Exception as e:
        #     self.logger.debug(f"URL directe des demandes d'abonnement a échoué ou n'est plus valide: {e}")

        # 2. Méthode plus fiable : via le panneau de notifications/activité
        #    Aller sur la page d'accueil pour avoir la barre de navigation
        if not self.driver.current_url.endswith("instagram.com/"):
            self.driver.get("https://www.instagram.com/")
            time.sleep(random.uniform(2.5, 4.5))
        
        try:
            # Cliquer sur l'icône Notifications/Coeur
            # Le sélecteur peut être //a[@href='/explore/activity/'] ou via aria-label
            notification_icon_xpath = NotificationsPageLocators.NOTIFICATION_ICON_XPATH # Assurer que ce sélecteur est dans NotificationsPageLocators
            if not notification_icon_xpath or not notification_icon_xpath[1]: # Sélecteur non défini
                self.logger.error("Sélecteur pour l'icône de notification non défini. Impossible de naviguer.")
                return False

            notif_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((notification_icon_xpath[0], notification_icon_xpath[1]))
            )
            notif_button.click()
            self.logger.info("Panneau/Page de notifications ouvert.")
            time.sleep(random.uniform(2, 3.5)) # Laisser charger

            # Chercher le lien/section "Follow Requests" DANS le panneau/la page d'activité
            # SÉLECTEUR CRUCIAL À ADAPTER !
            follow_requests_link_xpath_tuple = NotificationsPageLocators.FOLLOW_REQUESTS_LINK_XPATH # Doit être DÉFINI
            if not follow_requests_link_xpath_tuple or not follow_requests_link_xpath_tuple[1]:
                 self.logger.error("Sélecteur pour le lien 'Follow Requests' non défini.")
                 # Tenter de voir si des boutons 'Confirm' sont déjà visibles (si on est déjà sur la page des demandes)
                 if self.driver.find_elements(By.XPATH, NotificationsPageLocators.ACCEPT_REQUEST_BUTTON_XPATH):
                     self.logger.info("Déjà sur la page des demandes (boutons 'Confirm' présents).")
                     return True
                 return False

            request_link = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(follow_requests_link_xpath_tuple)
            )
            request_link.click()
            self.logger.info("Accès à la section/page des demandes d'abonnement.")
            time.sleep(random.uniform(2, 4))
            return True

        except TimeoutException:
            self.logger.warning("Timeout: Impossible de trouver l'icône de notification ou le lien 'Follow Requests'.")
            # Vérifier si on est quand même sur la bonne page
            if self.driver.find_elements(By.XPATH, NotificationsPageLocators.ACCEPT_REQUEST_BUTTON_XPATH):
                self.logger.info("Déjà sur la page des demandes (détecté après timeout).")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Erreur de navigation vers les demandes d'abonnement: {e}", exc_info=True)
            return False
            
    def _check_for_block_popup(self): # Dupliqué/adapté
        try:
            block_xpaths = [ErrorAndBlockLocators.ACTION_BLOCKED_TEXT_XPATH, ErrorAndBlockLocators.TRY_AGAIN_LATER_TEXT_XPATH]
            for i, xpath_tuple in enumerate(block_xpaths):
                if not xpath_tuple or not xpath_tuple[1]: continue
                if self.driver.find_elements(xpath_tuple[0], xpath_tuple[1]):
                    msg = f"BLOCKED: Popup détecté (Pattern {i+1})."; self.logger.warning(msg); return msg
        except: pass
        return None


    def execute(self, options):
        self.driver = self.app_manager.browser_handler.driver
        if not self.driver: return False, {"message": "Navigateur non disponible.", "accepted_count": 0}

        if not self.app_manager.get_setting("profile_is_private", False):
            self.logger.info("Profil public, pas de demandes d'abonnement à accepter.")
            # Retourner True car l'action n'a pas besoin de s'exécuter.
            return True, {"message": "Profil public.", "accepted_count": 0}

        num_to_accept_this_run = options.get("num_requests_to_accept_per_run", 5)
        self.accepted_this_session_count = 0 # Pour ce run de la tâche Auto-Accept

        if not self._navigate_to_follow_requests_page():
            return False, {"message": "Impossible d'accéder à la page des demandes d'abonnement.", "accepted_count": 0}
        
        # La page des demandes peut ne pas charger tous les items d'un coup.
        # Il faudra peut-être scroller dans une version plus avancée.
        # Pour l'instant, on traite ce qui est visible.

        processed_request_containers = 0 # Pour éviter de rester bloqué sur les mêmes si la page ne se met pas à jour vite
        max_containers_to_check = num_to_accept_this_run * 3 # Vérifier un peu plus que le nombre à accepter

        for _ in range(max_containers_to_check): # Boucle pour plusieurs tentatives d'acceptation
            if self.accepted_this_session_count >= num_to_accept_this_run: break
            
            request_containers = []
            try:
                # Attendre que les conteneurs soient présents (avec un timeout court)
                # Cela permet de rafraîchir la liste si la page se met à jour après une acceptation
                request_containers = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_all_elements_located((By.XPATH, NotificationsPageLocators.INDIVIDUAL_REQUEST_CONTAINER_XPATH))
                )
                if not request_containers:
                    self.logger.info("Aucune demande d'abonnement visible.")
                    break # Sortir si plus rien n'est visible
            except TimeoutException:
                self.logger.info("Timeout ou plus de demandes d'abonnement visibles.")
                break

            found_and_processed_one = False
            for container in request_containers:
                if self.accepted_this_session_count >= num_to_accept_this_run: break
                
                # Récupérer l'état de la demande pour ne pas la re-traiter si le DOM n'a pas changé
                try:
                     container_id = container.id # Ou un autre attribut stable
                     if container_id in getattr(self, '_processed_container_ids_this_cycle', set()):
                         continue # Déjà vu dans ce cycle de _execute_action
                     if not hasattr(self, '_processed_container_ids_this_cycle'):
                         self._processed_container_ids_this_cycle = set()
                     self._processed_container_ids_this_cycle.add(container_id)
                except StaleElementReferenceException: continue

                try:
                    username = "UtilisateurInconnu" # Default
                    try {
                        username_element = container.find_element(By.XPATH, NotificationsPageLocators.REQUEST_USERNAME_XPATH)
                        raw_username = username_element.text.strip()
                        if not raw_username: # Tenter depuis href si texte vide
                            href = username_element.get_attribute("href")
                            if href: username = urlparse(href).path.strip('/')
                        else: username = raw_username
                        username = username.split('/')[0] # Nettoyer
                    } except NoSuchElementException: self.logger.warning("Nom d'utilisateur non trouvé dans une demande.")

                    # Vérifier si l'utilisateur est dans la liste d'exclusion AVANT d'accepter
                    if self.app_manager.is_excluded(username):
                        self.logger.info(f"Demande de {username} ignorée (exclu).")
                        # Option: Décliner/Supprimer la demande ? Non, trop risqué pour l'instant.
                        continue

                    accept_button = container.find_element(By.XPATH, NotificationsPageLocators.ACCEPT_REQUEST_BUTTON_XPATH)
                    
                    self.logger.info(f"Tentative d'acceptation de la demande de: {username}")
                    # Scroller un peu pour être sûr
                    self.driver.execute_script("arguments[0].scrollIntoViewIfNeeded(true);", accept_button)
                    time.sleep(0.3)
                    accept_button.click()
                    
                    # Petite pause après le clic pour laisser Instagram traiter
                    time.sleep(random.uniform(1.5, 3.0)) 

                    # Vérifier un éventuel popup de blocage
                    block_msg = self._check_for_block_popup()
                    if block_msg:
                        self.logger.error(f"Blocage détecté après tentative d'acceptation pour {username}: {block_msg}")
                        # Arrêter immédiatement cette session d'acceptation si bloqué
                        return False, {"message": block_msg, "accepted_count": self.accepted_this_session_count}

                    self.logger.info(f"Demande de '{username}' acceptée (présomption).")
                    self.accepted_this_session_count += 1
                    found_and_processed_one = True
                    
                    # Marquer le succès pour les stats DB (utiliser username si disponible)
                    self.app_manager.record_action('follows') # Accepter = gain d'un follower
                    # Optionnel: loguer l'utilisateur accepté dans un fichier/DB spécifique si besoin

                    time.sleep(self.app_manager.get_setting("delay_between_accepts", 3)) # Délai spécifique ?
                    
                    # Puisque l'élément disparaît, il faut re-chercher la liste des demandes ou sortir.
                    # Pour simplifier, on sort de la boucle interne des conteneurs après une action.
                    # La boucle externe (max_containers_to_check) refera un find_elements.
                    break 
                
                except StaleElementReferenceException: 
                    self.logger.debug("Élément de demande devenu 'stale', probablement déjà traité.")
                    found_and_processed_one = True # Considérer qu'on a fait qqch
                    break # Re-fetch list
                except NoSuchElementException: 
                    self.logger.debug("Un bouton/username n'est plus trouvable dans un conteneur de demande (peut-être normal).")
                    continue # Essayer le suivant
                except Exception as e_item:
                    self.logger.error(f"Erreur traitement demande de {username}: {e_item}")
                    continue
            
            if not found_and_processed_one: # Si on a parcouru tous les conteneurs visibles sans rien faire
                 self.logger.info("Aucune nouvelle demande traitable trouvée dans les éléments visibles actuels.")
                 break # Sortir de la boucle principale des tentatives d'acceptation

            # Réinitialiser le set des conteneurs traités pour le prochain find_elements
            self._processed_container_ids_this_cycle = set()
            # Petite pause avant de re-vérifier la liste des demandes (si on n'a pas atteint la limite)
            if self.accepted_this_session_count < num_to_accept_this_run:
                time.sleep(random.uniform(1,2))


        final_message = f"{self.accepted_this_session_count} demande(s) acceptée(s) cette session."
        self.logger.info(final_message)
        # La structure de retour doit être un tuple (bool, dict) pour le TaskScheduler
        return True, {"message": final_message, "accepted_count": self.accepted_this_session_count}