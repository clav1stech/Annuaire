#!/usr/bin/env bash
# Lancement de l'application Streamlit principale (macOS / Linux).
# Équivalent de run_app.bat pour les postes non-Windows.
set -euo pipefail

cd "$(dirname "$0")"
VENV_DIR=".venv_annuaire_sirene"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[ERROR] Environnement virtuel introuvable."
    echo "[HINT] Lancer d'abord ./create_venv.sh"
    exit 1
fi

echo "[INFO] Lancement de l'application Streamlit..."
exec "$VENV_DIR/bin/streamlit" run app.py
