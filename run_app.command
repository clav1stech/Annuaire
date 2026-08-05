#!/usr/bin/env bash
# Lancement de l'application Streamlit principale (macOS / Linux).
# Seul script que l'utilisateur ait à lancer : il installe l'environnement au premier
# démarrage, le remet à niveau si besoin, puis ouvre l'application.
# Équivalent de run_app.bat pour les postes non-Windows.
# Extension .command : double-clic dans le Finder l'ouvre directement dans Terminal.app.
set -euo pipefail

cd "$(dirname "$0")"
VENV_DIR=".venv_annuaire_sirene"

# Premier lancement : l'environnement est créé ici même, pour que run_app.command reste le
# seul script à lancer. L'installation est déléguée à create_venv.command, qui garde la
# détection de l'interpréteur Python et la plage de versions supportée.
# Appel via `bash` et non `./` : fonctionne même si le bit exécutable a été perdu au
# décompressage de l'archive GitHub, cas fréquent sur macOS.
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[INFO] Première utilisation : installation de l'environnement en cours."
    echo "[INFO] Cela peut prendre quelques minutes ; ne pas fermer cette fenêtre."
    bash create_venv.command || {
        echo "[ERROR] Installation impossible : l'application ne peut pas démarrer."
        exit 1
    }
fi

# Second contrôle volontaire : create_venv.command sort en code 0 sans créer d'environnement
# quand l'utilisateur refuse de continuer avec un Python hors de la plage testée.
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[ERROR] Environnement virtuel absent après l'étape d'installation."
    echo "[HINT] Relancer ./create_venv.command pour voir le détail de l'échec."
    exit 1
fi

# Vérification rapide et non bloquante d'une nouvelle version (timeout court, ignorée si hors ligne).
"$VENV_DIR/bin/python" scripts/update_project.py --check-only || true

# Remise à niveau des paquets si requirements.txt a changé depuis la dernière installation :
# sans cela, une mise à jour du code tournerait sur un environnement virtuel obsolète.
# Un échec n'empêche pas le lancement : le script affiche déjà la marche à suivre.
# Streamlit manquant dans un environnement par ailleurs complet (installation interrompue,
# dossier bricolé) : l'empreinte enregistrée ne reflétant plus la réalité, on réinstalle.
# Variable simple et non quotée plutôt qu'un tableau : macOS ne fournit que bash 3.2, où
# l'expansion d'un tableau vide échoue sous `set -u`.
SYNC_FLAGS=""
if [ ! -x "$VENV_DIR/bin/streamlit" ]; then
    echo "[WARN] Streamlit introuvable dans l'environnement : réinstallation des dépendances."
    SYNC_FLAGS="--force"
fi

"$VENV_DIR/bin/python" scripts/sync_dependencies.py $SYNC_FLAGS || {
    echo "[WARN] Les dépendances n'ont pas pu être synchronisées automatiquement."
    echo "[HINT] L'application est lancée malgré tout ; en cas d'erreur, la fermer et relancer ./create_venv.command"
}

echo "[INFO] Lancement de l'application Streamlit..."
exec "$VENV_DIR/bin/streamlit" run app.py
