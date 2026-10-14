#!/usr/bin/env bash
# Création de l'environnement virtuel et installation des dépendances (macOS / Linux).
# Équivalent de create_venv.bat pour les postes non-Windows.
# Appelé automatiquement par run_app.command au premier lancement : en usage direct, ce script
# ne sert plus qu'à réinstaller ou réparer un environnement existant.
# Extension .command : double-clic dans le Finder l'ouvre directement dans Terminal.app.
set -euo pipefail

cd "$(dirname "$0")"
VENV_DIR=".venv_annuaire_sirene"

echo "[INFO] Working directory: $(pwd)"

# --- Détection de l'interpréteur Python ---------------------------------------
# Plage de versions 3.x supportée : au-delà, pyarrow/duckdb n'ont pas de wheels précompilées
# et l'installation des dépendances échoue. Garder en phase avec create_venv.bat, le README
# et la matrice de la CI.
PY_MIN_MINOR=11
PY_MAX_MINOR=14

PYTHON_BIN=""
PY_VERSION=""
REJECTED=""
candidates=()
for ((minor = PY_MAX_MINOR; minor >= PY_MIN_MINOR; minor--)); do
    candidates+=("python3.$minor")
done
# `python3` / `python` peuvent pointer vers une version hors plage : ils ne sont retenus
# qu'après vérification, et le premier écarté est mémorisé pour expliquer l'échec.
for candidate in "${candidates[@]}" python3 python; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    version="$("$candidate" -c 'import platform; print(platform.python_version())' 2>/dev/null)" || continue
    major="${version%%.*}"
    minor="$(echo "$version" | cut -d. -f2)"
    if [ "$major" = "3" ] && [ "$minor" -ge "$PY_MIN_MINOR" ] 2>/dev/null \
        && [ "$minor" -le "$PY_MAX_MINOR" ]; then
        PYTHON_BIN="$candidate"
        PY_VERSION="$version"
        break
    fi
    if [ -z "$REJECTED" ]; then
        REJECTED="$version ($candidate)"
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    if [ -n "$REJECTED" ]; then
        echo "[ERROR] Python $REJECTED détecté, mais ce projet requiert Python 3.$PY_MIN_MINOR à 3.$PY_MAX_MINOR."
        echo "[ERROR] Certaines dépendances (duckdb, pyarrow, pandas) ne sont pas encore disponibles"
        echo "[ERROR] pour cette version de Python : l'installation échouerait."
        echo "[HINT] Installer Python 3.$PY_MAX_MINOR (python.org/downloads ou 'brew install python@3.$PY_MAX_MINOR')."
        echo "[HINT] Inutile de désinstaller la version actuelle : les deux cohabitent, et ce script"
        echo "[HINT] choisira automatiquement la version supportée. Relancer ensuite ./run_app.command"
    else
        echo "[ERROR] Aucun interpréteur Python trouvé."
        echo "[HINT] Installer Python 3.$PY_MIN_MINOR à 3.$PY_MAX_MINOR (python.org ou 'brew install python@3.$PY_MAX_MINOR')."
    fi
    exit 1
fi

echo "[INFO] Python détecté: $PYTHON_BIN ($PY_VERSION)"

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

# Installation déléguée au script partagé : même commande pip que la resynchronisation
# automatique de run_app, et enregistrement de l'empreinte des dépendances installées.
echo "[INFO] Installation des dépendances depuis requirements.txt..."
"$VENV_DIR/bin/python" scripts/sync_dependencies.py --force

echo "[SUCCESS] Environnement prêt. Lancer l'application avec ./run_app.command"
