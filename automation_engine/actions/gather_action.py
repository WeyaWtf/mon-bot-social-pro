# mon_bot_social/automation_engine/actions/gather_action.py
import time
import random
from urllib.parse import urlparse # Pour extraire username des liens
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# Importer des sélecteurs si nécessaire (ici, on va utiliser des sélecteurs génériques en exemple)
# Nous allons supposer que les sélecteurs pour les posts sur une page de hashtag/location
# et pour les noms d'utilisateurs dans ces posts sont dans ElementSelectors.
from automation_engine.element_selectors import HashtagPageLocators, LocationPageLocators # Assumer que ces classes existent

class GatherAction:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.driver = None 
        self.logger = self.app_manager.logger # Utiliser le logger

    def _scroll_page(self, times=1):
        """Fait défiler la page pour charger plus de contenu."""
        if not self.driver: return
        self.logger.debug(f"Défilement de la page ({times} fois)...")
        for i in range(times):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Une pause un peu plus longue et plus variable peut être nécessaire
            # pour que le nouveau contenu (surtout les images/vidéos) se charge réellement
            time.sleep(random.uniform(2.5, 4.5)) 
            self.logger.debug(f"Scroll {i+1}/{times} effectué.")

    def _extract_usernames_from_visible_posts(self, source_type="hashtag"):
        """
        Extrait les noms d'utilisateurs des publications actuellement visibles sur la page.
        Ceci est TRES DÉPENDANT de la structure HTML du site cible (ex: Instagram).
        Retourne un set de usernames.
        """
        if not self.driver: return set()
        
        current_page_usernames = set()
        
        # SÉLECTEURS À ADAPTER IMPÉRATIVEMENT !
        # Ces sélecteurs sont des exemples et ne fonctionneront probablement pas tels quels.
        post_container_xpath = "" # Le conteneur de chaque post individuel (miniature ou complet)
        # Le lien vers le profil de l'auteur DANS chaque post_container
        owner_link_xpath_relative = ".//a[contains(@href,'/') and not(contains(@href,'explore')) and not(contains(@href,'tags')) and not(contains(@href,'locations'))]" # Tente de trouver un lien de profil

        if source_type == "hashtag":
            post_container_xpath = HashtagPageLocators.POST_CONTAINER_ON_HASHTAG_PAGE_XPATH # Doit être défini dans ElementSelectors
            # owner_link_xpath_relative = HashtagPageLocators.OWNER_LINK_IN_POST_XPATH # Peut être le même que générique
        elif source_type == "location":
            post_container_xpath = LocationPageLocators.LOCATION_POST_THUMBNAIL_LINK_XPATH # Ou un sélecteur pour le conteneur du post
            # owner_link_xpath_relative = LocationPageLocators.OWNER_LINK_IN_POST_XPATH
        else:
            self.logger.warning(f"Type de source de collecte inconnu pour l'extraction: {source_type}")
            return set()

        try:
            # Attendre un peu que les posts soient présents après un scroll
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_all_elements_located((By.XPATH, post_container_xpath))
            )
            
            post_elements = self.driver.find_elements(By.XPATH, post_container_xpath)
            self.logger.debug(f"Extraction: Trouvé {len(post_elements)} conteneurs de posts potentiels.")

            for post_el in post_elements:
                username = None
                try:
                    # Chercher le lien de l'auteur à l'intérieur du conteneur du post
                    # Si post_container_xpath est déjà le lien <a> vers le post (comme pour les miniatures),
                    # il faudrait naviguer vers ce post, puis scraper l'auteur sur la page du post.
                    # L'approche actuelle suppose que l'auteur est trouvable depuis le `post_el`.

                    # Essai 1: Si post_el est un conteneur, chercher un lien profil dedans
                    author_links = post_el.find_elements(By.XPATH, owner_link_xpath_relative)
                    if author_links:
                        href = author_links[0].get_attribute('href')
                        if href:
                            path = urlparse(href).path.strip('/')
                            # Extraire le premier segment de chemin non vide
                            parts = [p for p in path.split('/') if p]
                            if parts and not any(kw in parts[0] for kw in ["explore", "tags", "locations", "p", "reel"]):
                                username = parts[0]
                    
                    # Essai 2 (SIMULATION - À REMPLACER PAR DU VRAI SCRAPING):
                    if not username and random.random() < 0.7 : # Simuler la trouvaille d'un username
                         username = f"sim_user_{random.randint(1000,9999)}"

                    if username:
                        # Nettoyer le nom d'utilisateur (supprimer les paramètres, etc.)
                        username_cleaned = username.split('?')[0].lower()
                        if username_cleaned and len(username_cleaned) <= 30: # Longueur max approx d'un username IG
                            # self.logger.debug(f"Extraction: Username trouvé: {username_cleaned}")
                            current_page_usernames.add(username_cleaned)
                        # else:
                        #     self.logger.debug(f"Extraction: Username '{username_cleaned}' invalide ou trop long, ignoré.")
                            
                except StaleElementReferenceException:
                    self.logger.debug("Extraction: Élément post devenu 'stale', skip.")
                    continue
                except NoSuchElementException: # Si owner_link_xpath_relative n'est pas trouvé dans post_el
                    # self.logger.debug(f"Extraction: Pas de lien d'auteur trouvé pour un post.")
                    pass 
                except Exception as e_extract_single:
                    self.logger.warning(f"Extraction: Erreur mineure extraction username: {e_extract_single}")
            
        except TimeoutException:
            self.logger.debug("Extraction: Aucun post trouvé ou timeout attente.")
        except Exception as e_extract_all:
            self.logger.error(f"Extraction: Erreur majeure lors de l'extraction des usernames: {e_extract_all}")
            
        if current_page_usernames:
            self.logger.info(f"Extraction: {len(current_page_usernames)} usernames extraits de cette page.")
        return current_page_usernames


    def execute(self, options):
        self.driver = self.app_manager.browser_handler.driver
        if not self.driver: return False, "Navigateur non disponible pour la collecte."

        source_type = options.get('source_type', 'hashtag') # Ex: 'hashtag', 'location', 'followers_of_user', etc.
        targets = options.get('targets', []) # Liste de hashtags, IDs de location, ou usernames cibles
        if not isinstance(targets, list): targets = [targets] # S'assurer que c'est une liste
        
        if not targets:
            return False, f"Aucune cible ({source_type}) fournie pour la collecte."
            
        run_limit = options.get('gather_run_limit', 0) 
        max_per_target = options.get('max_items_per_target', 50) # max_users_per_hashtag, max_users_per_location...
        scroll_count_per_target = options.get('scroll_count_per_target', 3)

        # Set local pour les utilisateurs collectés dans CE run de la tâche
        current_run_collected_items = set() 

        self.logger.info(f"Démarrage Collecte (source: {source_type}). Cibles: {targets}. Limite Run: {run_limit if run_limit > 0 else 'aucune'}.")

        for target_value in targets:
            if run_limit > 0 and len(current_run_collected_items) >= run_limit:
                self.logger.info(f"Limite de collecte ({run_limit}) pour ce run atteinte. Arrêt prématuré.")
                break 

            target_cleaned = str(target_value).strip().lstrip('#@')
            if not target_cleaned: continue

            self.logger.info(f"Traitement cible ({source_type}): {target_cleaned}")
            
            # Construire l'URL en fonction du source_type
            # IMPORTANT: Instagram a des URLs spécifiques pour explorer par hashtag, location, etc.
            # Ces URLs peuvent changer.
            if source_type == "hashtag":
                target_url = f"https://www.instagram.com/explore/tags/{target_cleaned}/"
            elif source_type == "location":
                # La collecte par localisation est plus complexe et nécessite souvent l'ID numérique
                if target_cleaned.isdigit():
                    target_url = f"https://www.instagram.com/explore/locations/{target_cleaned}/"
                else: # On pourrait tenter une recherche, mais c'est hors scope pour cette version simplifiée
                    self.logger.warning(f"Le ciblage de localisation par nom '{target_cleaned}' est imprécis. Utiliser ID numérique.")
                    # On construit une URL hypothétique, mais peu susceptible de marcher sans ID
                    target_url = f"https://www.instagram.com/explore/locations/search/?query={target_cleaned.replace(' ','%20')}" # Exemple, pas une vraie URL d'explo
                    # Pour l'instant, on skippe si ce n'est pas un ID numérique
                    continue
            # Ajouter d'autres sources ici: 'followers_of_user', 'following_of_user', etc.
            else:
                self.logger.error(f"Type de source de collecte '{source_type}' non supporté.")
                continue

            if not self.app_manager.browser_handler.navigate_to(target_url):
                self.logger.error(f"Échec de la navigation vers {target_url} pour la collecte.")
                continue
            time.sleep(random.uniform(3.5, 6.0)) # Attente plus longue pour le chargement initial de la page

            items_from_this_target = 0
            
            for scroll_attempt in range(scroll_count_per_target):
                if run_limit > 0 and len(current_run_collected_items) >= run_limit: break
                if items_from_this_target >= max_per_target: break

                self._scroll_page(times=1) # Un scroll à la fois est souvent mieux
                
                extracted_this_scroll = self._extract_usernames_from_visible_posts(source_type)
                
                if not extracted_this_scroll and scroll_attempt > 0: 
                    self.logger.info(f"Aucun nouvel item extrait pour '{target_cleaned}' après scroll {scroll_attempt + 1}. Arrêt pour cette cible.")
                    break 
                
                newly_added_this_scroll = 0
                for item in extracted_this_scroll:
                    if run_limit > 0 and len(current_run_collected_items) >= run_limit: break
                    if items_from_this_target >= max_per_target: break

                    if item not in current_run_collected_items: 
                        # Appliquer filtres d'exclusion/whitelist TÔT ?
                        # Si on les applique ici, on réduit la taille de current_run_collected_items,
                        # mais on fait plus de requêtes (si is_excluded/whitelisted va scraper).
                        # Pour l'instant, on collecte brut. Le filtrage se fait AVANT les actions réelles (Follow, etc.).
                        current_run_collected_items.add(item)
                        items_from_this_target += 1
                        newly_added_this_scroll +=1
                
                self.logger.info(f"Cible '{target_cleaned}', Scroll {scroll_attempt + 1}: {newly_added_this_scroll} ajoutés. Cible: {items_from_this_target}/{max_per_target}. Run: {len(current_run_collected_items)}/{run_limit if run_limit > 0 else '∞'}")
                
                if run_limit > 0 and len(current_run_collected_items) >= run_limit: break
                if items_from_this_target >= max_per_target: break
            
            self.logger.info(f"Fin de traitement pour la cible '{target_cleaned}'. {items_from_this_target} items collectés.")
            # Petite pause entre les cibles
            if len(targets) > 1: time.sleep(random.uniform(5,10))


        final_list_this_run = list(current_run_collected_items)
        self.logger.info(f"Collecte (ce run) terminée. {len(final_list_this_run)} items uniques trouvés.")
        
        return True, final_list_this_run

# --- Placeholder pour les classes de sélecteurs ---
# Ces classes devraient être DANS element_selectors.py, mais pour que ce fichier soit
# auto-contenu pour un test simple, on les esquisse ici.
class HashtagPageLocators:
    POST_CONTAINER_ON_HASHTAG_PAGE_XPATH = "//article//a[@href]" # EXEMPLE TRES BASIQUE pour les liens des posts
    # OWNER_LINK_IN_POST_XPATH = ".//..." # Sélecteur relatif pour trouver l'auteur dans un post

class LocationPageLocators:
    LOCATION_POST_THUMBNAIL_LINK_XPATH = "//article//a[@href]" # EXEMPLE TRES BASIQUE
    # RECENT_POSTS_TAB_XPATH = "//..."