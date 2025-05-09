#!/bin/bash

# setup_kali.sh - Installateur pour Mon Bot Social Pro sur Kali Linux

# --- Configuration (À ADAPTER) ---
APP_NAME="Mon Bot Social Pro"
APP_DIR_NAME="mon_bot_social_pro_kali"
VENV_NAME="venv_mbs_kali"
PYTHON_CMD="python3"
PIP_CMD="pip3"
GIT_REPO_URL="https://github.com/WeyaWtf/mon-bot-social-pro.git"  # <<< REMPLACER par l’URL réelle du dépôt Git
INSTALL_BASE_DIR="$HOME/Bots"
INSTALL_PATH="$INSTALL_BASE_DIR/$APP_DIR_NAME"
MAIN_PYTHON_SCRIPT="main.py"

# Couleurs
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

echo_green() { echo -e "${GREEN}$1${NC}"; }
echo_yellow() { echo -e "${YELLOW}$1${NC}"; }
echo_red() { echo -e "${RED}$1${NC}"; }

if [ "$(id -u)" -eq 0 ]; then
  echo_yellow "AVERTISSEMENT: Ce script n'a normalement pas besoin d'être exécuté en tant que root, sauf pour apt."
  read -p "Continuer en tant que root ? (o/N) " choice
  if [[ "$choice" != "o" && "$choice" != "O" ]]; then
    echo_red "Installation annulée. Veuillez exécuter sans sudo."
    exit 1
  fi
fi

check_and_install_pkg() {
    PKG_NAME=$1
    PKG_CMD=$2
    if ! command -v "$PKG_CMD" &> /dev/null; then
        echo_yellow "La commande '$PKG_CMD' (pour '$PKG_NAME') n'est pas trouvée."
        if confirm_action "Voulez-vous installer via 'sudo apt install $PKG_NAME' ?"; then
            sudo apt update
            sudo apt install -y "$PKG_NAME"
            if ! command -v "$PKG_CMD" &> /dev/null; then
                echo_red "ERREUR: Installation de '$PKG_NAME' échouée."
                exit 1
            fi
            echo_green "'$PKG_NAME' installé."
        else
            echo_red "Installation annulée. Le script s'arrête."
            exit 1
        fi
    fi
}

confirm_action() {
    while true; do read -p "$1 (o/N) " yn; case $yn in [Oo]*) return 0;; [Nn]*) return 1;; *) echo "o/N";; esac; done
}

echo "#########################################"
echo "# Installation de $APP_NAME sur Kali  #"
echo "#########################################"
echo

read -p "Entrez le chemin d'installation (laisser vide pour '$INSTALL_PATH'): " USER_INSTALL_PATH
if [ -n "$USER_INSTALL_PATH" ]; then INSTALL_PATH="${USER_INSTALL_PATH/#\~/$HOME}"; fi
echo_green "Installation dans: $INSTALL_PATH"
echo

echo_yellow "1. Vérification des dépendances système..."
check_and_install_pkg "python3" "$PYTHON_CMD"
check_and_install_pkg "python3-pip" "$PIP_CMD"
check_and_install_pkg "python3-venv" "true"
if [[ -n "$GIT_REPO_URL" && "$GIT_REPO_URL" != *"VOTRE_USER"* ]]; then check_and_install_pkg "git" "git"; fi
echo_green "Dépendances OK."
echo

echo_yellow "2. Préparation répertoire '$INSTALL_PATH'..."
if [ -d "$INSTALL_PATH" ]; then
    if confirm_action "Le dossier existe déjà. Supprimer et réinstaller ?"; then
        rm -rf "$INSTALL_PATH"
    else
        echo_red "Installation annulée."
        exit 1
    fi
fi
mkdir -p "$INSTALL_PATH" && cd "$INSTALL_PATH" || { echo_red "Erreur création '$INSTALL_PATH'"; exit 1; }
echo_green "Répertoire prêt."
echo

echo_yellow "3. Téléchargement code source..."
if [[ -n "$GIT_REPO_URL" && "$GIT_REPO_URL" != *"VOTRE_USER"* ]]; then
    git clone --depth 1 "$GIT_REPO_URL" .
    if [ $? -ne 0 ]; then echo_red "Échec clonage Git."; exit 1; fi
else
    echo_red "ERREUR: L'URL Git n'est pas configurée. Remplacez GIT_REPO_URL par l'URL de votre dépôt."
    exit 1
fi
if [ ! -f "$MAIN_PYTHON_SCRIPT" ]; then echo_red "$MAIN_PYTHON_SCRIPT non trouvé."; exit 1; fi
echo_green "Code source téléchargé."
echo

echo_yellow "4. Création de l'environnement virtuel..."
"$PYTHON_CMD" -m venv "$VENV_NAME"
if [ $? -ne 0 ]; then echo_red "Échec création venv."; exit 1; fi
echo_green "Environnement virtuel créé."
echo

echo_yellow "5. Installation des dépendances Python..."
source "$VENV_NAME/bin/activate"
"$PIP_CMD" install --upgrade pip
if [ ! -f "requirements.txt" ]; then echo_red "requirements.txt manquant."; deactivate; exit 1; fi
"$PIP_CMD" install -r requirements.txt
if [ $? -ne 0 ]; then echo_red "Échec installation deps Python."; deactivate; exit 1; fi
if ! "$PIP_CMD" show webdriver-manager > /dev/null 2>&1; then
    echo_yellow "Installation webdriver-manager..."
    "$PIP_CMD" install webdriver-manager
    if [ $? -ne 0 ]; then echo_red "Échec webdriver-manager."; deactivate; exit 1; fi
fi
echo_green "Dépendances Python installées."
deactivate
echo

LAUNCH_SCRIPT_NAME="run_${APP_DIR_NAME//\//_}.sh"
LAUNCH_SCRIPT_PATH_FINAL="$INSTALL_BASE_DIR/$LAUNCH_SCRIPT_NAME"

echo_yellow "6. Création script de lancement..."
cat << 'EOF' > "$LAUNCH_SCRIPT_PATH_FINAL"
#!/bin/bash
APP_FULL_INSTALL_PATH="'"$INSTALL_PATH"'"
VENV_NAME_IN_LAUNCHER="'"$VENV_NAME"'"
PYTHON_CMD_IN_LAUNCHER="'"$PYTHON_CMD"'"
MAIN_SCRIPT_IN_LAUNCHER="'"$MAIN_PYTHON_SCRIPT"'"

echo "Lancement de '"$APP_NAME"'..."
cd "$APP_FULL_INSTALL_PATH" || { echo "ERREUR: Dossier $APP_FULL_INSTALL_PATH introuvable."; exit 1; }

if [ -f "$VENV_NAME_IN_LAUNCHER/bin/activate" ]; then
    source "$VENV_NAME_IN_LAUNCHER/bin/activate"
else
    echo "ERREUR: Environnement virtuel $VENV_NAME_IN_LAUNCHER non trouvé."
    exit 1
fi

export PYTHONPATH="$APP_FULL_INSTALL_PATH:$PYTHONPATH"
"$PYTHON_CMD_IN_LAUNCHER" "$MAIN_SCRIPT_IN_LAUNCHER" "$@"

if type deactivate > /dev/null 2>&1; then
    deactivate
fi
echo "'"$APP_NAME"' arrêté."
EOF

chmod +x "$LAUNCH_SCRIPT_PATH_FINAL"
echo_green "Script de lancement créé : $LAUNCH_SCRIPT_PATH_FINAL"
echo

echo_green "##############################################"
echo_green "# Installation de $APP_NAME terminée !      #"
echo_green "##############################################"
echo "Pour lancer : $LAUNCH_SCRIPT_PATH_FINAL"

exit 0

