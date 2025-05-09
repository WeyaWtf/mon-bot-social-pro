# automation_engine/element_selectors.py
from selenium.webdriver.common.by import By

# IMPORTANT : TOUS CES SÉLECTEURS SONT DES EXEMPLES ET DOIVENT ÊTRE
# VÉRIFIÉS ET ADAPTÉS À LA STRUCTURE ACTUELLE D'INSTAGRAM (OU AUTRE PLATEFORME).
# UTILISEZ LES OUTILS DE DÉVELOPPEMENT (F12) DE VOTRE NAVIGATEUR POUR LES TROUVER.
# Les classes CSS dynamiques (_aa**, _acan, etc.) sont particulièrement volatiles.

class LoginPageLocators:
    USERNAME_FIELD = (By.NAME, "username")
    PASSWORD_FIELD = (By.NAME, "password")
    LOGIN_BUTTON = (By.XPATH, "//button[@type='submit' and div[contains(text(),'Log in') or contains(text(),'Connexion')]]")
    # Alternative si le texte n'est pas fiable :
    # LOGIN_BUTTON = (By.CSS_SELECTOR, "button[type='submit']._acan._acap._acas._aj1-") # Exemple de classe, très instable

    # Bouton pour refuser les cookies (très variable)
    COOKIE_ACCEPT_BUTTON = (By.XPATH, "//button[contains(text(),'Allow all cookies') or contains(text(),'Autoriser tous les cookies') or contains(text(),'Accept All')]")
    COOKIE_DECLINE_BUTTON = (By.XPATH, "//button[contains(text(),'Decline optional cookies') or contains(text(),'Refuser les cookies facultatifs')]")

class HomePageLocators:
    # Pour la barre de recherche
    SEARCH_ICON_XPATH = "//*[local-name()='svg' and @aria-label='Search']" # Ou aria-label='Rechercher'
    SEARCH_INPUT_XPATH = "//input[@aria-label='Search input' or @aria-label='Entrée de recherche']"

    # Pour les cercles de story sur le feed
    ACTIVE_STORY_BUTTON_ON_FEED_XPATH = "//div[@role='button' and .//canvas and (contains(@aria-label, \"'s story\") or contains(@aria-label, \" story de \")) and not(contains(@aria-label,'seen'))]"
    # Alternative : chercher un parent de canvas avec une certaine hauteur/classe, ou l'avatar entouré d'un cercle de couleur
    # USER_STORY_RING_XPATH = "//button[contains(@aria-label, \"'s story\")]" 

    # Pour l'icône de notifications/activité
    NOTIFICATION_ICON_XPATH = "//*[local-name()='svg' and @aria-label='Notifications']/ancestor::a | //a[@href='/accounts/activity/']"


class ProfilePageLocators:
    # Boutons d'action principaux sur le profil
    FOLLOW_BUTTON_XPATH = "//div[@role='main']//button[.//div[contains(text(),'Follow') or contains(text(),'Suivre')] and not(contains(.,'Back'))] | //div[@role='main']//div[@role='button' and (contains(.,'Follow') or contains(.,'Suivre')) and not(contains(.,'Back'))]"
    CURRENTLY_FOLLOWING_BUTTON_XPATH = "//div[@role='main']//button[.//div[contains(text(),'Following') or contains(text(),'Abonné(e)')]] | //div[@role='main']//div[@role='button' and (contains(.,'Following') or contains(.,'Abonné(e)'))]"
    REQUESTED_BUTTON_XPATH = "//div[@role='main']//button[.//div[contains(text(),'Requested') or contains(text(),'Demandé')]] | //div[@role='main']//div[@role='button' and (contains(.,'Requested') or contains(.,'Demandé'))]"
    UNFOLLOW_CONFIRM_BUTTON_XPATH = "//div[@role='dialog']//button[contains(text(),'Unfollow') or contains(text(),'Se désabonner')]" # Dans le popup
    MESSAGE_BUTTON_XPATH = "//div[@role='main']//button[.//div[contains(text(),'Message')]] | //div[@role='main']//div[@role='button' and contains(.,'Message')]"
    CONTACT_BUTTON_XPATH = "//div[@role='main']//button[.//div[text()='Contact']]" # Moins fréquent

    # Indicateur "Follows you"
    FOLLOWS_YOU_INDICATOR_XPATH = "//header//span[text()='Follows you' or text()='Vous suit']" # Vérifier si toujours un span direct

    # Photo de profil et son état
    PROFILE_PIC_IMG_XPATH = "//header//img[contains(@alt, \"profile picture\") or contains(@alt, \"photo de profil\")] | //header//div[@role='button']/img" # Cible l'image elle-même
    # Le substring pour les images par défaut change TRÈS souvent. Il faut l'inspecter.
    # Ex: s150x150, p150x150, default_avatar. C'est la partie la MOINS fiable.
    DEFAULT_PROFILE_PIC_SRC_SUBSTRING_1 = "s150x150" 
    DEFAULT_PROFILE_PIC_SRC_SUBSTRING_2 = "default_profile"
    DEFAULT_PROFILE_PIC_SRC_SUBSTRING_3 = " illustrazione" # Pour "Avatar illustration"

    # Indicateur de story active sur le profil (cercle autour de l'avatar)
    # Utiliser une approche basée sur le conteneur de l'image de profil et vérifier s'il a un style/classe de story active
    # Exemple : L'élément <header> contient un <div> pour l'image. Si cet image est cliquable pour une story, son parent ou lui-même peut avoir un rôle ou une classe spéciale
    ACTIVE_STORY_RING_ON_PROFILE_XPATH = "//header//div[@role='button' and .//canvas]" # Un bouton contenant un canvas est un bon indicateur

    # Infos de profil (Posts, Followers, Following, Bio)
    # Les listes <ul> ou les div avec des rôles "listitem" sont communs pour les stats.
    # L'ordre est généralement Posts, Followers, Following.
    STATS_CONTAINER_XPATH = "//header//ul" # Si les stats sont dans une liste
    # S'ils sont dans des divs/spans séparés :
    POST_COUNT_VALUE_XPATH = "//header//*[contains(text(),'posts') or contains(text(),'publications')]/preceding-sibling::span/span | //header//*[contains(text(),'posts') or contains(text(),'publications')]/span"
    FOLLOWERS_COUNT_VALUE_XPATH = "//header//*[contains(@href,'/followers/')]/span[@title] | //header//*[contains(@href,'/followers/')]/span/span | //header//*[contains(@href,'/followers/')]/span"
    FOLLOWING_COUNT_VALUE_XPATH = "//header//*[contains(@href,'/following/')]/span[@title] | //header//*[contains(@href,'/following/')]/span/span | //header//*[contains(@href,'/following/')]/span"
    
    BIO_TEXT_XPATH = "//header//div[h1]/following-sibling::span | //header//div[h1]/following-sibling::div/span" # Bio sous le nom d'utilisateur (h1)

    # Premier post sur la grille du profil (pour date dernier post)
    FIRST_POST_THUMBNAIL_ON_PROFILE_XPATH = "(//main//article//a[contains(@href,'/p/')])[1] | (//main//div[@role='link' and contains(@href,'/p/')])[1]"


class PostLocators:
    # Element <article> contenant un post sur le feed
    ARTICLE_POST_XPATH = "//article[@role='presentation']" 

    # À l'intérieur d'un <article> ou sur une page de post unique:
    POST_OWNER_LINK_XPATH = ".//header//a[contains(@href,'/') and not(contains(@href,'explore')) and string-length(@href)>2 and string(@href)!='/']" # XPath relatif à l'article
    
    LIKE_BUTTON_SVG_XPATH = ".//*[local-name()='svg' and (@aria-label='Like' or @aria-label='J’aime')]" # Relatif
    UNLIKE_BUTTON_SVG_XPATH = ".//*[local-name()='svg' and (@aria-label='Unlike' or @aria-label='Ne plus aimer')]" # Relatif
    LIKE_BUTTON_CONTAINER_XPATH = ".//span/*[local-name()='svg' and (@aria-label='Like' or @aria-label='J’aime' or @aria-label='Unlike' or @aria-label='Ne plus aimer')]/ancestor::div[@role='button'] | .//button[contains(@class,'_abl-') and .//*[local-name()='svg']]" # Un conteneur cliquable
    
    COMMENT_TEXT_AREA_XPATH = "//textarea[@aria-label='Add a comment…' or @aria_label='Ajouter un commentaire…']" # Souvent global, pas relatif
    POST_COMMENT_BUTTON_XPATH = "//div[@role='button' and (contains(text(),'Post') or contains(text(),'Publier'))]" # Souvent global

    POST_TIMESTAMP_XPATH = ".//time[@datetime]" # Relatif à l'article ou page de post

    # Compteurs de Likes/Commentaires (si visibles sur le post, souvent en cliquant sur le texte)
    LIKE_COUNT_TEXT_XPATH = ".//button[contains(.,'likes') or contains(.,\"J'aime\")]/span | .//section[.//span[contains(text(),'like')]]//a[contains(@href,'liked_by')]/span/span" # Relatif
    VIEW_ALL_COMMENTS_BUTTON_XPATH = ".//a[contains(@href,'all_comments=1') or (contains(.,'comments') or contains(.,'commentaires'))]" # Relatif
    COMMENT_COUNT_FROM_VIEW_ALL_XPATH = ".//a[contains(@href,'all_comments=1') or (contains(.,'comments') or contains(.,'commentaires'))]/span/span" # Relatif

    # Indicateur de post sponsorisé
    SPONSORED_TEXT_INDICATOR_XPATH = ".//header//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'sponsored') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'sponsorisé') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'paid partnership')]" # XPath relatif, insensible à la casse pour "Sponsored"


class StoryViewLocators:
    NEXT_STORY_BUTTON_XPATH = "//*[local-name()='svg' and @aria-label='Next' or @aria-label='Suivant']/ancestor::button | //button[contains(@class,'_a<ctrl60>log_dir and not os.path.exists(log_dir): os.makedirs(log_dir) # ...

class AppManager:
    # ... (__init__ et autres méthodes...) ...
    # Assurer que les clés pour les délais des nouvelles tâches sont bien dans save/load
    # et que _get_random_delay est appelé avec ces clés ou des valeurs par défaut sensées.

    def start_main_task(self, task_name, task_options):
        # ... (Vérifier si navigateur ouvert, préparation options comme avant) ...
        
        # --- AJOUT DE LA LIMITE 'gather_run_limit' aux options si absente et que c'est une tâche gather_users ---
        if task_name == "gather_users" and 'gather_run_limit' not in task_options:
            # Utiliser une valeur par défaut si non fournie par l'UI pour une raison quelconque
            # Normalement, l'UI DEVRAIT la fournir. Ceci est un fallback.
            default_gather_limit = self.get_setting("default_gather_run_limit", 1000) # Un nouveau setting potentiel
            task_options['gather_run_limit'] = task_options.get('gather_run_limit', default_gather_limit)
            self.logger.debug(f"Limite de run pour Gather '{task_name}' mise à {task_options['gather_run_limit']} (utilisant fallback ou valeur UI).")

        if self.task_scheduler:
            success = self.task_scheduler.start_task(task_name, task_options)
            # ... (mise à jour UI comme avant) ...
            return success
        # ...

    # ... (Autres méthodes comme avant) ...