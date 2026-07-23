"""Vérifie et applique les mises à jour du code depuis GitHub (branche main).

Usage:
    python scripts/update_project.py                # vérifie et applique si une nouvelle version existe (confirmation demandée)
    python scripts/update_project.py --check-only    # vérifie seulement, n'affiche qu'une ligne de statut, ne modifie rien
    python scripts/update_project.py --yes           # applique sans demander de confirmation

Fonctionne dans les deux cas de figure :
- projet cloné avec git (dossier `.git` présent) : utilise `git fetch` / `git pull --ff-only`,
- projet téléchargé en zip (pas de `.git`) : télécharge l'archive de la branche main sur GitHub
  et copie les fichiers par-dessus le dossier du projet.

Dans les deux cas, les fichiers de données locales ne sont jamais touchés : environnement virtuel
(`.venv_annuaire_sirene`), fichiers/dossiers Parquet SIRENE, dossier `export/`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.updater import apply_update  # noqa: E402
from src.version_check import (  # noqa: E402
    fetch_remote_version,
    parse_version,
    read_local_version,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Vérifie seulement s'il existe une nouvelle version, n'applique rien.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Applique la mise à jour sans demander de confirmation.",
    )
    args = parser.parse_args()

    local_version = read_local_version()
    remote_version, error = fetch_remote_version()

    if remote_version is None:
        print(f"[WARN] Impossible de vérifier la disponibilité d'une mise à jour : {error}")
        return 0

    if parse_version(remote_version) <= parse_version(local_version):
        print(f"[INFO] Version locale à jour ({local_version}).")
        return 0

    print(f"[INFO] Nouvelle version disponible : {local_version} -> {remote_version}")

    if args.check_only:
        print("[HINT] Lancer 'python scripts/update_project.py' pour mettre à jour.")
        return 0

    if not args.yes:
        reply = input("Appliquer la mise à jour maintenant ? [o/N] ").strip().lower()
        if reply not in ("o", "oui", "y", "yes"):
            print("[INFO] Mise à jour annulée par l'utilisateur.")
            return 0

    outcome = apply_update()
    for message in outcome.messages:
        print(f"[INFO] {message}")

    if not outcome.applied:
        print(f"[ERROR] {outcome.error}")
        if outcome.hint:
            print(f"[HINT] {outcome.hint}")
        return 1

    print(f"[SUCCESS] Mise à jour appliquée ({local_version} -> {remote_version}).")
    if outcome.hint:
        print(f"[HINT] {outcome.hint}")
    if outcome.requirements_changed:
        print("[WARN] requirements.txt a changé : relancer create_venv (.bat/.command) avant de relancer l'application.")
    else:
        print("[INFO] Dépendances inchangées : ./run_app.command (ou run_app.bat) peut être relancé directement.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
