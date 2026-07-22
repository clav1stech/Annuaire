#!/usr/bin/env bash
# Création de l'environnement virtuel et installation des dépendances (macOS / Linux).
# Équivalent de create_venv.bat pour les postes non-Windows.
set -euo pipefail

cd "$(dirname "$0")"
VENV_DIR=".venv_annuaire_sirene"

echo "[INFO] Working directory: $(pwd)"

# --- Détection de l'interpréteur Python ---------------------------------------
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Aucun interpréteur Python trouvé."
    echo "[HINT] Installer Python 3.11 ou 3.12 (python.org ou 'brew install python@3.12')."
    exit 1
fi

PY_VERSION="$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())')"
echo "[INFO] Python détecté: $PYTHON_BIN ($PY_VERSION)"

PY_MAJOR="${PY_VERSION%%.*}"
PY_MINOR="$(echo "$PY_VERSION" | cut -d. -f2)"
if [ "$PY_MAJOR" != "3" ] || [ "$PY_MINOR" -lt 11 ] || [ "$PY_MINOR" -gt 12 ]; then
    echo "[WARN] Python $PY_VERSION est hors de la plage officiellement testée (3.11-3.12)."
    echo "[WARN] L'installation peut fonctionner grâce aux wheels précompilées de pyarrow/duckdb, sans garantie."
    read -r -p "Continuer avec Python $PY_VERSION ? [o/N] " reply
    case "$reply" in
        o|O|oui|OUI) ;;
        *) echo "[INFO] Installation annulée par l'utilisateur."; exit 0 ;;
    esac
fi

# --- Création de l'environnement virtuel --------------------------------------
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[INFO] Création de l'environnement virtuel dans $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[ERROR] Échec de création de l'environnement virtuel."
    exit 1
fi

# --- Installation des dépendances ---------------------------------------------
echo "[INFO] Mise à jour de pip..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip

echo "[INFO] Installation des dépendances depuis requirements.txt..."
echo "[INFO] pyarrow et duckdb sont restreints aux wheels précompilées (pas de build source)..."
"$VENV_DIR/bin/python" -m pip install \
    --only-binary=pyarrow --only-binary=duckdb \
    -r requirements.txt

echo "[SUCCESS] Environnement prêt. Lancer l'application avec ./run_app.sh"
