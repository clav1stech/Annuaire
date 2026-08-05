#!/usr/bin/env bash
# Lancement de l'application Streamlit principale (macOS / Linux).
# Équivalent de run_app.bat pour les postes non-Windows.
# Extension .command : double-clic dans le Finder l'ouvre directement dans Terminal.app.
set -euo pipefail

cd "$(dirname "$0")"
VENV_DIR=".venv_annuaire_sirene"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[ERROR] Environnement virtuel introuvable."
    echo "[HINT] Lancer d'abord ./create_venv.command"
    exit 1
fi

# Vérification rapide et non bloquante d'une nouvelle version (timeout court, ignorée si hors ligne).
"$VENV_DIR/bin/python" scripts/update_project.py --check-only || true

# Remise à niveau des paquets si requirements.txt a changé depuis la dernière installation :
# sans cela, une mise à jour du code tournerait sur un environnement virtuel obsolète.
# Un échec n'empêche pas le lancement : le script affiche déjà la marche à suivre.
"$VENV_DIR/bin/python" scripts/sync_dependencies.py || {
    echo "[WARN] Les dépendances n'ont pas pu être synchronisées automatiquement."
    echo "[HINT] L'application est lancée malgré tout ; en cas d'erreur, la fermer et relancer ./create_venv.command"
}

echo "[INFO] Lancement de l'application Streamlit..."
exec "$VENV_DIR/bin/streamlit" run app.py
