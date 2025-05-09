# mon_bot_social/automation_engine/browser_handler.py
import os
import zipfile
import time 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
# Import de webdriver_manager (à mettre au conditionnel si pas une dépendance dure)
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

# CHEMIN CHROMEDRIVER (Fallback si webdriver_manager n'est pas utilisé ou échoue)
# Calculer le chemin de base du projet
BASE_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Remonte de 3 niveaux (actions -> automation_engine -> mon_bot_social)
CHROMEDRIVER_DIR = os.path.join(BASE_PROJECT_DIR, "drivers")
CHROMEDRIVER_EXECUTABLE_NAME = "chromedriver.exe" if os.name == 'nt' else "chromedriver"
CHROMEDRIVER_PATH_FALLBACK = os.path.join(CHROMEDRIVER_DIR, CHROMEDRIVER_EXECUTABLE_NAME)


class BrowserHandler:
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.logger = self.app_manager.logger # Obtenir le logger d'AppManager
        self.driver = None
        self.user_agent = None # User-Agent actuel du navigateur
        self.proxy_extension_path_to_clean = None # Pour nettoyer après usage

    def _create_proxy_extension(self, proxy_host, proxy_port, proxy_user, proxy_pass):
        """Crée une extension Chrome temporaire pour gérer l'authentification proxy."""
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy Auth Helper",
            "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"],
            "background": {"scripts": ["background.js"]},
            "minimum_chrome_version":"76.0.0"
        }
        """
        background_js_template = """
        var config = {
                mode: "fixed_servers",
                rules: {
                  singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                  },
                  bypassList: ["localhost", "127.0.0.1"]
                }
              };
        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }
        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {urls: ["<all_urls>"]},
                    ['blocking']
        );
        """
        background_js = background_js_template % (proxy_host, proxy_port, proxy_user, proxy_pass)

        # Créer les fichiers dans un dossier temporaire géré par AppManager ou dans data_files
        # pour éviter les problèmes de droits ou de chemins absolus si le script est déplacé.
        temp_ext_dir_base = os.path.join(BASE_PROJECT_DIR, "data_files", "temp_ext")
        if not os.path.exists(temp_ext_dir_base): os.makedirs(temp_ext_dir_base)
        
        # Utiliser un nom de dossier unique pour l'extension
        unique_ext_folder_name = f"proxy_ext_{int(time.time() * 1000)}"
        extension_build_dir = os.path.join(temp_ext_dir_base, unique_ext_folder_name)
        if not os.path.exists(extension_build_dir): os.makedirs(extension_build_dir)

        path_to_manifest = os.path.join(extension_build_dir, "manifest.json")
        path_to_background = os.path.join(extension_build_dir, "background.js")
        
        # Le fichier ZIP sera créé au même niveau que le dossier de build pour facilité de suppression
        path_to_zip = os.path.join(temp_ext_dir_base, f"{unique_ext_folder_name}.zip")

        with open(path_to_manifest, 'w', encoding='utf-8') as f: f.write(manifest_json)
        with open(path_to_background, 'w', encoding='utf-8') as f: f.write(background_js)

        with zipfile.ZipFile(path_to_zip, 'w', zipfile.ZIP_DEFLATED) as zp:
            zp.write(path_to_manifest, "manifest.json")
            zp.write(path_to_background, "background.js")
        
        # Nettoyer les fichiers source, garder seulement le ZIP
        try:
            os.remove(path_to_manifest)
            os.remove(path_to_background)
            os.rmdir(extension_build_dir)
        except OSError as e: self.logger.warning(f"Erreur nettoyage fichiers source extension proxy: {e}")

        self.logger.info(f"Extension proxy avec authentification créée : {path_to_zip}")
        return path_to_zip


    def _get_chrome_options(self):
        options = ChromeOptions()
        settings = self.app_manager.current_settings # Obtenir les settings à jour
        
        # User-Agent (rotation si liste fournie)
        self.user_agent = self.app_manager.get_random_user_agent() # Peut retourner None
        custom_user_agent_from_settings = settings.get("custom_user_agent_input", "") # Champ texte direct
        
        if custom_user_agent_from_settings: # Priorité au champ direct
            self.user_agent = custom_user_agent_from_settings
            self.logger.info(f"Utilisation User-Agent personnalisé: ...{self.user_agent[-50:]}")
        elif self.user_agent: # Si un UA a été choisi aléatoirement
            self.logger.info(f"Utilisation User-Agent aléatoire: ...{self.user_agent[-50:]}")
        else: # Fallback (ne devrait pas arriver si get_random_user_agent a des defaults)
            self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
            self.logger.info("Utilisation User-Agent par défaut (fallback).")
        options.add_argument(f"user-agent={self.user_agent}")

        # Options de performance/humanisation
        if settings.get("disable_browser_images", False):
            self.logger.debug("Désactivation des images navigateur."); options.add_argument("--blink-settings=imagesEnabled=false")
        
        # Arguments pour la stabilité et l'automatisation
        options.add_argument("--start-maximized")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions") # Sauf la nôtre pour le proxy si utilisée
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-gpu") if os.name == 'nt' else None # Peut aider sur Windows
        options.add_argument("--no-sandbox") # Souvent nécessaire sur Linux, surtout en headless
        options.add_argument("--disable-dev-shm-usage") # Pour surmonter les limites de ressources partagées en mémoire

        # Options anti-détection (expérimental)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--disable-blink-features=AutomationControlled')
        # Emuler certains paramètres de la pile JS que les sites peuvent vérifier
        options.add_argument("--lang=fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7") # Simuler une langue
        # D'autres arguments peuvent être ajoutés pour les permissions, les plugins, etc.

        # Gestion Proxy
        self.proxy_extension_path_to_clean = None # Réinitialiser
        proxy_config_to_use = self.app_manager.get_current_proxy_for_browser()
        if proxy_config_to_use:
            ip, port, user, pwd = proxy_config_to_use.get("ip"), proxy_config_to_use.get("port"), \
                                  proxy_config_to_use.get("user",""), proxy_config_to_use.get("pass","")
            if ip and port:
                if user and pwd:
                    try:
                         self.proxy_extension_path_to_clean = self._create_proxy_extension(ip, port, user, pwd)
                         options.add_extension(self.proxy_extension_path_to_clean)
                         self.logger.info(f"Proxy {ip}:{port} (AVEC auth) configuré via extension.")
                    except Exception as e_ext: self.logger.error(f"ERREUR création extension proxy {ip}:{port}: {e_ext}")
                else:
                    options.add_argument(f'--proxy-server={ip}:{port}')
                    self.logger.info(f"Proxy {ip}:{port} (SANS auth) configuré.")
            else: self.logger.warning("Proxy activé mais IP/Port manquants.")
        else: self.logger.info("Aucun proxy activé/sélectionné pour ce démarrage.")
        
        return options


    def start_browser(self):
        if self.driver: self.logger.info("Navigateur déjà démarré."); return True
        
        self.logger.info("Tentative de démarrage du navigateur Chrome...")
        chrome_options = self._get_chrome_options() # Récupère le path de l'extension aussi
        
        try:
            if WEBDRIVER_MANAGER_AVAILABLE and self.app_manager.get_setting("use_webdriver_manager", True): # Setting optionnel
                 self.logger.info("Utilisation de webdriver-manager pour ChromeDriver...")
                 service = ChromeService(ChromeDriverManager().install())
            else: # Utiliser un chemin local
                 if os.path.exists(CHROMEDRIVER_PATH_FALLBACK) and os.path.isfile(CHROMEDRIVER_PATH_FALLBACK):
                     self.logger.info(f"Utilisation de ChromeDriver local: {CHROMEDRIVER_PATH_FALLBACK}")
                     service = ChromeService(executable_path=CHROMEDRIVER_PATH_FALLBACK)
                 else:
                     self.logger.warning(f"ChromeDriver local non trouvé à {CHROMEDRIVER_PATH_FALLBACK}. Essai via PATH système.")
                     # Selenium va chercher dans le PATH si executable_path n'est pas donné
                     # Ceci peut lever une exception si non trouvé dans le PATH.
                     service = ChromeService() 
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.logger.info("Navigateur Chrome démarré avec succès.")
            
            # Configurer des timeouts implicites et de chargement de page
            page_load_timeout = self.app_manager.get_setting("page_load_timeout_sec", 30)
            script_timeout = self.app_manager.get_setting("script_timeout_sec", 20)
            self.driver.set_page_load_timeout(page_load_timeout)
            self.driver.set_script_timeout(script_timeout)
            # L'attente implicite est généralement déconseillée au profit des WebDriverWait explicites.
            # self.driver.implicitly_wait(self.app_manager.get_setting("implicit_wait_sec", 5))


            if self.app_manager.get_setting("always_clear_cookies_on_startup", True):
                self.logger.info("Nettoyage des cookies au démarrage.")
                self.driver.delete_all_cookies()
            return True

        except Exception as e:
            self.logger.critical(f"ERREUR FATALE lors du démarrage du navigateur: {e}", exc_info=True)
            self.driver = None
            return False
        finally:
            if self.proxy_extension_path_to_clean and os.path.exists(self.proxy_extension_path_to_clean):
                try:
                    os.remove(self.proxy_extension_path_to_clean)
                    self.logger.debug(f"Fichier extension proxy temporaire supprimé: {self.proxy_extension_path_to_clean}")
                    self.proxy_extension_path_to_clean = None
                except OSError as e_del:
                     self.logger.warning(f"Erreur suppression extension proxy {self.proxy_extension_path_to_clean}: {e_del}")

    def close_browser(self):
        if self.driver:
            self.logger.info("Fermeture du navigateur...")
            try:
                self.driver.quit() # Ferme toutes les fenêtres et termine le processus driver
                self.logger.info("Navigateur fermé.")
            except Exception as e:
                self.logger.error(f"Erreur lors de la fermeture du navigateur: {e}")
            finally:
                self.driver = None # Marquer comme fermé
                # Assurer que l'extension proxy (si existante et non nettoyée) est bien nettoyée
                if self.proxy_extension_path_to_clean and os.path.exists(self.proxy_extension_path_to_clean):
                    try: os.remove(self.proxy_extension_path_to_clean); self.logger.debug("Extension proxy nettoyée au close.")
                    except: pass
        else:
            self.logger.debug("Aucun navigateur actif à fermer.")
            
    def navigate_to(self, url):
        if not self.driver:
            self.logger.error("Navigateur non démarré. Impossible de naviguer.")
            return False
        try:
            self.logger.info(f"Navigation vers: {url}")
            self.driver.get(url)
            # Pas d'attente fixe ici, les actions utiliseront WebDriverWait
            return True
        except Exception as e:
            self.logger.error(f"Erreur de navigation vers {url}: {e}")
            return False

    # Ajout d'une méthode pour gérer les alertes (si nécessaire, mais rare sur IG)
    def handle_alert(self, accept=True, timeout=5):
        try:
            alert = WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
            text = alert.text
            self.logger.info(f"Alerte détectée: '{text}'")
            if accept: alert.accept(); self.logger.info("Alerte acceptée.")
            else: alert.dismiss(); self.logger.info("Alerte refusée.")
            return text
        except TimeoutException:
            return None # Pas d'alerte