"""Application d'une mise à jour du code depuis GitHub, partagée entre l'UI Streamlit et le CLI.

Le module ne fait qu'appliquer la mise à jour : la comparaison de versions vit dans
`version_check`. Aucune fonction n'écrit sur la sortie standard ni ne termine le processus,
afin de rester appelable depuis Streamlit ; le journal est renvoyé dans `UpdateOutcome`.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .version_check import BRANCH, PROJECT_ROOT, REPO_NAME, REPO_OWNER

ARCHIVE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{BRANCH}.zip"

# Ne jamais toucher à ces chemins lors d'une mise à jour (données locales, environnement, exports).
PRESERVE_NAMES = {
    ".venv_annuaire_sirene",
    "export",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}


@dataclass
class UpdateOutcome:
    """Résultat d'une tentative de mise à jour.

    `messages` retrace le déroulé pour affichage (terminal ou UI) ; `error` n'est renseigné
    que si la mise à jour n'a pas été appliquée, auquel cas le projet est resté intact.
    """

    applied: bool = False
    messages: list[str] = field(default_factory=list)
    error: str | None = None
    hint: str | None = None
    requirements_changed: bool = False


def is_git_repo() -> bool:
    return (PROJECT_ROOT / ".git").is_dir() and shutil.which("git") is not None


def is_parquet_path(path: Path) -> bool:
    return path.suffix.lower() == ".parquet" or "parquet" in path.name.lower()


def should_preserve(relative_path: Path) -> bool:
    if relative_path.parts and relative_path.parts[0] in PRESERVE_NAMES:
        return True
    return is_parquet_path(relative_path)


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _apply_update_via_git(outcome: UpdateOutcome) -> bool:
    outcome.messages.append("Projet cloné via git : mise à jour par 'git fetch' + 'git pull --ff-only'.")
    _run_git("fetch", "origin", BRANCH)

    status = _run_git("status", "--porcelain")
    if status.stdout.strip():
        # Un pull écraserait le travail local : mieux vaut ne rien faire et laisser la main.
        outcome.error = (
            "Modifications locales non commitées détectées ; mise à jour annulée pour ne pas "
            f"les écraser :\n{status.stdout.strip()}"
        )
        outcome.hint = "Commiter ou mettre de côté (git stash) ces changements, puis réessayer."
        return False

    _run_git("pull", "--ff-only", "origin", BRANCH)
    return True


def _apply_update_via_zip(outcome: UpdateOutcome) -> bool:
    outcome.messages.append(
        "Projet téléchargé en zip (pas de dossier .git) : récupération de l'archive GitHub."
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / "update.zip"

        outcome.messages.append(f"Téléchargement de {ARCHIVE_URL} ...")
        urllib.request.urlretrieve(ARCHIVE_URL, archive_path)

        outcome.messages.append("Extraction de l'archive...")
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(tmp_path)

        extracted_root = next(p for p in tmp_path.iterdir() if p.is_dir() and p != tmp_path)

        outcome.messages.append("Copie des fichiers mis à jour dans le dossier du projet...")
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

    outcome.messages.append("Copie terminée.")
    outcome.hint = (
        "Ce mode ne supprime pas les fichiers devenus obsolètes déjà présents localement ; "
        "en cas de doute, retélécharger le zip complet du projet."
    )
    return True


def apply_update() -> UpdateOutcome:
    """Applique la mise à jour du code, sans interaction ni sortie standard.

    Ne vérifie pas s'il existe une nouvelle version : l'appelant l'a déjà fait via
    `version_check`. En cas d'échec, `applied` reste False et le projet est inchangé.
    """
    outcome = UpdateOutcome()
    requirements_file = PROJECT_ROOT / "requirements.txt"
    requirements_before = requirements_file.read_text(encoding="utf-8")

    try:
        if is_git_repo():
            applied = _apply_update_via_git(outcome)
        else:
            applied = _apply_update_via_zip(outcome)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        outcome.error = f"Échec de la commande git : {details or exc}"
        return outcome
    except (urllib.error.URLError, OSError, zipfile.BadZipFile) as exc:
        outcome.error = f"Échec de la récupération de l'archive GitHub : {exc}"
        return outcome

    if not applied:
        return outcome

    outcome.applied = True
    outcome.requirements_changed = requirements_file.read_text(encoding="utf-8") != requirements_before
    return outcome
