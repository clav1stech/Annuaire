#!/usr/bin/env bash
# Vérifie et applique les mises à jour du code du projet depuis GitHub (macOS / Linux).
# Équivalent de update_project.bat pour les postes non-Windows.
# Extension .command : double-clic dans le Finder l'ouvre directement dans Terminal.app.
set -euo pipefail

cd "$(dirname "$0")"
VENV_DIR=".venv_annuaire_sirene"

if [ -x "$VENV_DIR/bin/python" ]; then
    PYTHON_BIN="$VENV_DIR/bin/python"
else
    PYTHON_BIN=""
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    done
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Aucun interpréteur Python trouvé."
    echo "[HINT] Installer Python 3.11 à 3.14 (python.org ou 'brew install python@3.12')."
    exit 1
fi

"$PYTHON_BIN" scripts/update_project.py "$@"
