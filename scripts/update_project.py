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
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.version_check import (  # noqa: E402
    BRANCH,
    PROJECT_ROOT,
    REPO_NAME,
    REPO_OWNER,
    fetch_remote_version,
    parse_version,
    read_local_version,
)

ARCHIVE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{BRANCH}.zip"

# Ne jamais toucher à ces chemins lors d'une mise à jour (données locales, environnement, exports).
PRESERVE_NAMES = {
    ".venv_annuaire_sirene",
    "export",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
}


def is_git_repo() -> bool:
    return (PROJECT_ROOT / ".git").is_dir() and shutil.which("git") is not None


def is_parquet_path(path: Path) -> bool:
    return path.suffix.lower() == ".parquet" or "parquet" in path.name.lower()


def should_preserve(relative_path: Path) -> bool:
    if relative_path.parts and relative_path.parts[0] in PRESERVE_NAMES:
        return True
    return is_parquet_path(relative_path)


def apply_update_via_git() -> None:
    print("[INFO] Projet cloné via git : mise à jour avec 'git fetch' + 'git pull --ff-only'.")
    subprocess.run(["git", "-C", str(PROJECT_ROOT), "fetch", "origin", BRANCH], check=True)

    status = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        print("[WARN] Modifications locales non commitées détectées :")
        print(status.stdout)
        print("[ERROR] Mise à jour annulée pour ne pas écraser ces modifications.")
        print("[HINT] Commiter/mettre de côté (git stash) ces changements, puis relancer ce script.")
        sys.exit(1)

    subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "pull", "--ff-only", "origin", BRANCH],
        check=True,
    )


def apply_update_via_zip() -> None:
    print("[INFO] Projet téléchargé en zip (pas de dossier .git) : récupération de l'archive GitHub.")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / "update.zip"

        print(f"[INFO] Téléchargement de {ARCHIVE_URL} ...")
        urllib.request.urlretrieve(ARCHIVE_URL, archive_path)

        print("[INFO] Extraction de l'archive...")
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(tmp_path)

        extracted_root = next(p for p in tmp_path.iterdir() if p.is_dir() and p != tmp_path)

        print("[INFO] Copie des fichiers mis à jour dans le dossier du projet...")
        for source_path in extracted_root.rglob("*"):
            relative_path = source_path.relative_to(extracted_root)
            if should_preserve(relative_path):
                continue

            destination_path = PROJECT_ROOT / relative_path
            if source_path.is_dir():
                destination_path.mkdir(parents=True, exist_ok=True)
            else:
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination_path)

    print("[INFO] Copie terminée.")
    print("[HINT] Ce mode ne supprime pas d'anciens fichiers déjà présents localement et devenus obsolètes ;")
    print("[HINT] en cas de doute, préférer un nouveau téléchargement zip complet du projet.")


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

    requirements_before = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    if is_git_repo():
        apply_update_via_git()
    else:
        apply_update_via_zip()

    requirements_after = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    print(f"[SUCCESS] Mise à jour appliquée ({local_version} -> {remote_version}).")
    if requirements_before != requirements_after:
        print("[WARN] requirements.txt a changé : relancer create_venv (.bat/.command) avant de relancer l'application.")
    else:
        print("[INFO] Dépendances inchangées : ./run_app.command (ou run_app.bat) peut être relancé directement.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
