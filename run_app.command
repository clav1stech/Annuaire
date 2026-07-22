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

echo "[INFO] Lancement de l'application Streamlit..."
exec "$VENV_DIR/bin/streamlit" run app.py
