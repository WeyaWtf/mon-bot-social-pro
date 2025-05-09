# data_layer/database.py
import sqlite3
import os
import datetime
import json 
import time 
from utils.logger import get_logger 

DATABASE_PATH = os.path.join("data_files", "bot_data.db")
logger = get_logger("Database") # Logger spécifique pour ce module

# --- Chemins des anciens fichiers JSON pour la migration ---
OLD_FOLLOWED_JSON_FILE = os.path.join("data_files", "followed_by_bot.json") 
OLD_LIKED_JSON_FILE = os.path.join("data_files", "liked_posts.json")
OLD_COMMENTED_JSON_FILE = os.path.join("data_files", "commented_posts.json")
OLD_VIEWED_STORIES_JSON_FILE = os.path.join("data_files", "viewed_stories_users.json")

def get_db_connection():
    """Établit et retourne une connexion à la base de données SQLite."""
    try:
        db_dir = os.path.dirname(DATABASE_PATH)
        if db_dir and not os.path.exists(db_dir):
             os.makedirs(db_dir)
             logger.info(f"Répertoire de base de données créé: {db_dir}")
             
        conn = sqlite3.connect(DATABASE_PATH, timeout=10) # Ajout timeout
        conn.row_factory = sqlite3.Row 
        # Activer WAL mode pour une meilleure concurrence (si plusieurs accès, bien que mono-thread ici)
        conn.execute("PRAGMA journal_mode=WAL;")
        logger.debug("Connexion SQLite établie (mode WAL activé).")
        return conn
    except sqlite3.Error as e:
        logger.critical(f"Erreur critique de connexion à la base de données SQLite: {e}", exc_info=True)
        return None
    except Exception as e_gen:
        logger.critical(f"Erreur générale lors de la connexion DB: {e_gen}", exc_info=True)
        return None

def initialize_database():
    """Crée/vérifie toutes les tables nécessaires et lance les migrations JSON si besoin."""
    logger.info("Vérification et initialisation de la base de données...")
    conn = get_db_connection()
    if conn is None: 
        logger.error("Impossible d'initialiser la base de données: connexion échouée.")
        return

    try:
        cursor = conn.cursor()
        
        # Table action_stats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_stats (
                date TEXT PRIMARY KEY,
                follows INTEGER DEFAULT 0,
                unfollows INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                story_views INTEGER DEFAULT 0,
                dms_sent INTEGER DEFAULT 0  -- Ajouté
            )
        """)
        
        # Table followed_users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followed_users (
                username TEXT PRIMARY KEY,
                followed_at_ts REAL NOT NULL,
                status TEXT,
                is_following_back INTEGER DEFAULT 0 
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_followed_at ON followed_users (followed_at_ts)")

        # Table liked_posts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liked_posts (
                post_id TEXT PRIMARY KEY,
                liked_at_ts REAL NOT NULL,
                like_count INTEGER,     
                comment_count INTEGER   
            )
        """)
        
        # Table commented_posts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commented_posts (
                post_id TEXT PRIMARY KEY,
                comment_text TEXT,         
                commented_at_ts REAL NOT NULL,
                like_count INTEGER,        
                comment_count INTEGER      
            )
        """)

        # Table viewed_story_users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS viewed_story_users (
                username TEXT PRIMARY KEY,
                last_viewed_at_ts REAL NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_viewed_at ON viewed_story_users (last_viewed_at_ts)")

        conn.commit()
        logger.info("Structure de la base de données vérifiée/initialisée avec succès.")
        
        # Exécuter les migrations après s'être assuré que les tables existent
        _migrate_followed_from_json(conn)
        _migrate_liked_from_json(conn)
        _migrate_commented_from_json(conn)
        _migrate_viewed_stories_from_json(conn)

    except sqlite3.Error as e:
        logger.error(f"Erreur lors de l'initialisation/vérification de la DB: {e}", exc_info=True)
    finally:
        if conn: conn.close()


# --- Fonctions de Migration JSON vers DB ---
def _rename_or_delete_old_json(file_path, suffix=".migrated_to_db"):
    if not os.path.exists(file_path): return
    try:
        new_name = file_path + suffix
        # Supprimer un ancien .migrated_to_db s'il existe (pour une nouvelle tentative)
        if os.path.exists(new_name): os.remove(new_name) 
        os.rename(file_path, new_name)
        logger.info(f"Ancien fichier JSON '{os.path.basename(file_path)}' renommé en '{os.path.basename(new_name)}'.")
    except OSError as e: logger.error(f"Impossible de renommer/supprimer {file_path}: {e}")

def _migrate_followed_from_json(conn):
    if not os.path.exists(OLD_FOLLOWED_JSON_FILE): return
    try:
        cursor = conn.cursor(); cursor.execute("SELECT COUNT(*) FROM followed_users");
        if cursor.fetchone()[0] > 0: logger.info("'followed_users' contient déjà des données. Skip migration JSON."); _rename_or_delete_old_json(OLD_FOLLOWED_JSON_FILE); return
        
        logger.warning(f"Migration 'followed_users' depuis {OLD_FOLLOWED_JSON_FILE}...")
        with open(OLD_FOLLOWED_JSON_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        migrated = 0
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and 'username' in entry and 'followed_at_ts' in entry:
                    uname = str(entry['username']).lower(); ts = float(entry['followed_at_ts']); status = entry.get('status', 'mig_json'); is_back = int(entry.get('is_following_back',0))
                    try: cursor.execute("INSERT INTO followed_users VALUES (?, ?, ?, ?)", (uname, ts, status, is_back)); migrated +=1
                    except sqlite3.IntegrityError: logger.debug(f"Migration Follow: {uname} existe déjà, skip.")
                    except sqlite3.Error as e: logger.error(f"DB err mig Follow {uname}: {e}")
        conn.commit(); logger.info(f"Migration Follows terminée. {migrated} ajoutés."); _rename_or_delete_old_json(OLD_FOLLOWED_JSON_FILE)
    except Exception as e: logger.error(f"Erreur migration {OLD_FOLLOWED_JSON_FILE}: {e}", exc_info=True)

def _migrate_liked_from_json(conn):
    if not os.path.exists(OLD_LIKED_JSON_FILE): return
    try:
        cursor = conn.cursor(); cursor.execute("SELECT COUNT(*) FROM liked_posts");
        if cursor.fetchone()[0] > 0: logger.info("'liked_posts' contient données. Skip migration JSON."); _rename_or_delete_old_json(OLD_LIKED_JSON_FILE); return
        logger.warning(f"Migration 'liked_posts' depuis {OLD_LIKED_JSON_FILE}...")
        with open(OLD_LIKED_JSON_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        migrated = 0
        if isinstance(data, list): # Supposant une liste d'IDs
            ts_now = time.time()
            for post_id_str in data:
                 if isinstance(post_id_str, str) and post_id_str:
                    try: cursor.execute("INSERT INTO liked_posts (post_id, liked_at_ts) VALUES (?, ?)", (post_id_str, ts_now)); migrated +=1
                    except sqlite3.IntegrityError: pass
                    except sqlite3.Error as e: logger.error(f"DB err mig Like {post_id_str}: {e}")
        conn.commit(); logger.info(f"Migration Likes terminée. {migrated} ajoutés."); _rename_or_delete_old_json(OLD_LIKED_JSON_FILE)
    except Exception as e: logger.error(f"Erreur migration {OLD_LIKED_JSON_FILE}: {e}", exc_info=True)

def _migrate_commented_from_json(conn): # Similaire à Liked
    if not os.path.exists(OLD_COMMENTED_JSON_FILE): return
    try: #... (check si table vide, lire JSON, insérer avec NULL pour counts, renommer)
        cursor = conn.cursor(); cursor.execute("SELECT COUNT(*) FROM commented_posts");
        if cursor.fetchone()[0] > 0: logger.info("'commented_posts' contient données. Skip migration JSON."); _rename_or_delete_old_json(OLD_COMMENTED_JSON_FILE); return
        logger.warning(f"Migration 'commented_posts' depuis {OLD_COMMENTED_JSON_FILE}...")
        with open(OLD_COMMENTED_JSON_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        migrated = 0; ts_now = time.time()
        if isinstance(data, list):
             for post_id_str in data:
                 if isinstance(post_id_str, str) and post_id_str:
                     try: cursor.execute("INSERT INTO commented_posts (post_id, commented_at_ts) VALUES (?, ?)", (post_id_str, ts_now)); migrated +=1
                     except sqlite3.IntegrityError: pass
                     except sqlite3.Error as e: logger.error(f"DB err mig Comment {post_id_str}: {e}")
        conn.commit(); logger.info(f"Migration Comments terminée. {migrated} ajoutés."); _rename_or_delete_old_json(OLD_COMMENTED_JSON_FILE)
    except Exception as e: logger.error(f"Erreur migration {OLD_COMMENTED_JSON_FILE}: {e}", exc_info=True)

def _migrate_viewed_stories_from_json(conn):
    if not os.path.exists(OLD_VIEWED_STORIES_JSON_FILE): return
    try: #... (check si table vide, lire JSON dict {'user':ts}, insérer, renommer)
        cursor = conn.cursor(); cursor.execute("SELECT COUNT(*) FROM viewed_story_users");
        if cursor.fetchone()[0] > 0: logger.info("'viewed_story_users' contient données. Skip migration JSON."); _rename_or_delete_old_json(OLD_VIEWED_STORIES_JSON_FILE); return
        logger.warning(f"Migration 'viewed_story_users' depuis {OLD_VIEWED_STORIES_JSON_FILE}...")
        with open(OLD_VIEWED_STORIES_JSON_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        migrated = 0
        if isinstance(data, dict):
            for username, ts_val in data.items():
                 if isinstance(username, str) and username and isinstance(ts_val, (int,float)):
                     try: cursor.execute("INSERT INTO viewed_story_users VALUES (?, ?)", (username.lower(), float(ts_val))); migrated +=1
                     except sqlite3.IntegrityError: pass
                     except sqlite3.Error as e: logger.error(f"DB err mig ViewStory {username}: {e}")
        conn.commit(); logger.info(f"Migration ViewStories terminée. {migrated} ajoutés."); _rename_or_delete_old_json(OLD_VIEWED_STORIES_JSON_FILE)
    except Exception as e: logger.error(f"Erreur migration {OLD_VIEWED_STORIES_JSON_FILE}: {e}", exc_info=True)


# --- Fonctions CRUD pour action_stats ---
def record_action(action_type):
    conn = get_db_connection(); #... (check conn)
    today = datetime.date.today().isoformat()
    valid_types = ['follows', 'unfollows', 'likes', 'comments', 'story_views', 'dms_sent']
    if action_type not in valid_types: logger.warning(f"Type d'action invalide: {action_type}"); conn.close(); return
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO action_stats (date, {0}) VALUES (?, 0)".format(action_type), (today,)) # Assure que la ligne et colonne existent
        cursor.execute(f"UPDATE action_stats SET {action_type} = {action_type} + 1 WHERE date = ?", (today,))
        conn.commit(); logger.debug(f"Action DB: +1 {action_type} pour {today}")
    except sqlite3.Error as e: logger.error(f"Erreur DB record_action '{action_type}': {e}")
    finally:
        if conn: conn.close()

def get_stats_for_period(start_date_dt, end_date_dt): # Prend des objets date
    conn = get_db_connection(); #... (check conn)
    stats = {'follows': 0, 'unfollows': 0, 'likes': 0, 'comments': 0, 'story_views': 0, 'dms_sent':0}
    try:
        start_str = start_date_dt.isoformat(); end_str = end_date_dt.isoformat()
        cursor = conn.cursor()
        cursor.execute(f"""SELECT SUM(follows) tf, SUM(unfollows) tu, SUM(likes) tl, SUM(comments) tc, SUM(story_views) tv, SUM(dms_sent) td
                           FROM action_stats WHERE date BETWEEN ? AND ?""", (start_str, end_str))
        row = cursor.fetchone()
        if row:
            stats['follows']=row['tf'] or 0; stats['unfollows']=row['tu'] or 0; stats['likes']=row['tl'] or 0
            stats['comments']=row['tc'] or 0; stats['story_views']=row['tv'] or 0; stats['dms_sent']=row['td'] or 0
        logger.debug(f"Stats récupérées pour {start_str} à {end_str}: {stats}")
    except sqlite3.Error as e: logger.error(f"Erreur DB get_stats ({start_str}-{end_str}): {e}")
    finally:
        if conn: conn.close()
    return stats

# --- CRUD followed_users (déjà définies dans l'étape précédente) ---
def add_or_update_followed_user(username, status="followed_by_bot", is_following_back=0): #...
def remove_followed_user(username): #...
def get_followed_user_details(username): #...
def get_all_followed_usernames(): #...
def update_following_back_status_db(username, follows_back_status): #...

# --- CRUD liked_posts (déjà définies dans l'étape précédente) ---
def add_liked_post_db(post_id, like_count=None, comment_count=None): #...
def has_liked_post_db(post_id): #...

# --- CRUD commented_posts (déjà définies dans l'étape précédente) ---
def add_commented_post_db(post_id, comment_text="", like_count=None, comment_count=None): #...
def has_commented_post_db(post_id): #...

# --- CRUD viewed_story_users (déjà définies dans l'étape précédente) ---
def add_or_update_viewed_story_user(username): #...
def get_last_story_view_ts(username): #...


# Appel initial pour créer la DB/tables et tenter les migrations si nécessaire
initialize_database()

if __name__ == '__main__':
    logger.info("--- Test Manuel des Fonctions DB ---")
    # Créer quelques faux fichiers JSON pour tester la migration s'ils n'existent pas
    # ... (code de création de faux JSON si besoin pour test) ...
    
    # initialize_database() # Est déjà appelé à l'import
    
    # Test des actions
    logger.info("Test enregistrement actions...")
    record_action('likes'); record_action('likes'); record_action('follows')
    record_action('dms_sent')

    # Test stats
    today = datetime.date.today()
    stats_today = get_stats_for_period(today, today)
    logger.info(f"Stats pour Aujourd'hui: {stats_today}")
    
    # Test followed users
    logger.info("Test DB utilisateurs suivis...")
    add_or_update_followed_user("testuser1_db", is_following_back=1)
    add_or_update_followed_user("testuser2_db")
    details1 = get_followed_user_details("testuser1_db")
    logger.info(f"Détails testuser1_db: {details1}")
    all_f = get_all_followed_usernames()
    logger.info(f"Tous suivis: {all_f}")
    update_following_back_status_db("testuser2_db", True)
    details2 = get_followed_user_details("testuser2_db")
    logger.info(f"Détails testuser2_db (MAJ): {details2}")
    remove_followed_user("testuser_non_existent") # Devrait juste ne rien faire
    # remove_followed_user("testuser2_db") # Pour tester la suppression
    
    # Test liked posts
    logger.info("Test DB posts likés...")
    add_liked_post_db("postid123", 10, 2)
    logger.info(f"Post 'postid123' a-t-il été liké ? {has_liked_post_db('postid123')}")
    logger.info(f"Post 'postid_fake' a-t-il été liké ? {has_liked_post_db('postid_fake')}")

    logger.info("--- Fin Tests DB ---")