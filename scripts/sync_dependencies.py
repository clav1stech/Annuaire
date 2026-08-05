"""Synchronise l'environnement virtuel avec `requirements.txt`.

Appelé par les scripts de lancement (`run_app`) et d'installation (`create_venv`) : après
une mise à jour du code, les paquets sont réinstallés automatiquement, sans que
l'utilisateur ait à enchaîner plusieurs scripts.

Usage:
    python scripts/sync_dependencies.py               # réinstalle seulement si nécessaire
    python scripts/sync_dependencies.py --check-only  # diagnostic seul, n'installe rien
    python scripts/sync_dependencies.py --force       # réinstalle systématiquement

Code de retour : 0 si l'environnement est utilisable, 1 si une réinstallation est
nécessaire (`--check-only`) ou a échoué — l'appelant reste libre de lancer l'application
malgré tout plutôt que de bloquer l'utilisateur.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dependencies import get_sync_state, install_requirements  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-only",
        action="store_true",
        help="Signale une désynchronisation sans rien installer.",
    )
    mode.add_argument(
        "--force",
        action="store_true",
        help="Réinstalle les dépendances même si l'environnement paraît à jour.",
    )
    args = parser.parse_args()

    if not args.force:
        state = get_sync_state()
        if args.check_only:
            if state.in_sync:
                print(f"[INFO] {state.reason}")
                return 0
            print(f"[WARN] {state.reason}")
            print("[HINT] Lancer 'python scripts/sync_dependencies.py' pour réinstaller les dépendances.")
            return 1
        print(f"[INFO] {state.reason}")
        if state.in_sync:
            return 0

    # Message affiché avant l'appel à pip, dont la sortie est capturée : sans lui, la fenêtre
    # resterait muette pendant toute l'installation et paraîtrait figée.
    print("[INFO] Installation des dépendances depuis requirements.txt...")
    print("[INFO] Cela peut prendre quelques minutes ; ne pas fermer cette fenêtre.")

    outcome = install_requirements()
    for message in outcome.messages:
        print(f"[INFO] {message}")

    if outcome.error:
        print(f"[ERROR] Installation des dépendances impossible :\n{outcome.error}")
        if outcome.hint:
            print(f"[HINT] {outcome.hint}")
        return 1

    if outcome.installed:
        print("[SUCCESS] Environnement synchronisé avec requirements.txt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
