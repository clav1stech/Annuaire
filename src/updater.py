"""Application d'une mise à jour du code depuis GitHub, partagée entre l'UI Streamlit et le CLI.

Le module ne fait qu'appliquer la mise à jour : la comparaison de versions vit dans
`version_check`. Aucune fonction n'écrit sur la sortie standard ni ne termine le processus,
afin de rester appelable depuis Streamlit ; le journal est renvoyé dans `UpdateOutcome`.
"""

from __future__ import annotations

import filecmp
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .config import UPDATE_ARCHIVE_MAX_UNCOMPRESSED_BYTES, UPDATE_ARCHIVE_MAX_UPLOAD_MO
from .version_check import BRANCH, PROJECT_ROOT, REPO_NAME, REPO_OWNER
from .version_check import parse_version, read_local_version

ARCHIVE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{BRANCH}.zip"

# Ne jamais toucher à ces chemins lors d'une mise à jour (données locales, environnement, exports).
PRESERVE_NAMES = {
    ".sirene_manifest.json",
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


class InvalidUpdateArchive(ValueError):
    """Archive refusée avant toute modification du projet."""


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


def _validated_archive_members(
    archive: zipfile.ZipFile,
    *,
    require_newer: bool,
) -> tuple[str, list[tuple[zipfile.ZipInfo, Path]]]:
    """Valider une archive GitHub et retourner ses fichiers avec leurs chemins relatifs."""
    members: list[tuple[zipfile.ZipInfo, Path]] = []
    roots: set[str] = set()
    seen_paths: set[str] = set()
    total_size = 0

    for info in archive.infolist():
        if not info.filename or "\\" in info.filename:
            raise InvalidUpdateArchive("un chemin de l'archive est invalide")
        archive_path = PurePosixPath(info.filename)
        if archive_path.is_absolute() or ".." in archive_path.parts or not archive_path.parts:
            raise InvalidUpdateArchive("un chemin de l'archive sort du dossier du projet")
        roots.add(archive_path.parts[0])
        if info.is_dir():
            continue
        if len(archive_path.parts) < 2:
            raise InvalidUpdateArchive("les fichiers doivent être regroupés dans un dossier racine")
        unix_mode = info.external_attr >> 16
        if stat.S_ISLNK(unix_mode):
            raise InvalidUpdateArchive("les liens symboliques ne sont pas acceptés")
        total_size += info.file_size
        if total_size > UPDATE_ARCHIVE_MAX_UNCOMPRESSED_BYTES:
            raise InvalidUpdateArchive("l'archive décompressée dépasse la taille autorisée")
        relative_path = Path(*archive_path.parts[1:])
        normalized_path = relative_path.as_posix().casefold()
        if normalized_path in seen_paths:
            raise InvalidUpdateArchive("l'archive contient plusieurs fois le même chemin")
        seen_paths.add(normalized_path)
        members.append((info, relative_path))

    if len(roots) != 1 or not members:
        raise InvalidUpdateArchive("le ZIP doit contenir un unique dossier de projet GitHub")

    by_path = {relative_path.as_posix(): info for info, relative_path in members}
    required = {"VERSION", "app.py", "src/__init__.py"}
    missing = sorted(required - by_path.keys())
    if missing:
        raise InvalidUpdateArchive(
            "ce ZIP ne semble pas être celui du projet Annuaire (fichiers manquants : "
            + ", ".join(missing)
            + ")"
        )

    try:
        archive_version = archive.read(by_path["VERSION"]).decode("utf-8").strip()
    except (OSError, UnicodeDecodeError, RuntimeError, zipfile.BadZipFile) as exc:
        raise InvalidUpdateArchive(f"le fichier VERSION du ZIP est illisible : {exc}") from exc
    if re.fullmatch(r"\d+\.\d+\.\d+", archive_version) is None:
        raise InvalidUpdateArchive("le fichier VERSION du ZIP n'est pas valide")
    local_version = read_local_version()
    if require_newer and parse_version(archive_version) <= parse_version(local_version):
        raise InvalidUpdateArchive(
            f"la version du ZIP ({archive_version}) n'est pas plus récente que la version "
            f"installée ({local_version})"
        )
    return archive_version, members


def _apply_zip_archive(
    archive_path: Path,
    outcome: UpdateOutcome,
    *,
    require_newer: bool,
) -> bool:
    """Valider, préparer puis copier uniquement les fichiers de code différents."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        staged_root = Path(tmp_dir) / "project"
        staged_root.mkdir()

        outcome.messages.append("Validation de l'archive...")
        with zipfile.ZipFile(archive_path) as archive:
            archive_version, members = _validated_archive_members(
                archive,
                require_newer=require_newer,
            )
            for info, relative_path in members:
                if should_preserve(relative_path):
                    continue
                staged_path = staged_root / relative_path
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, staged_path.open("wb") as destination:
                    shutil.copyfileobj(source, destination)

        outcome.messages.append(f"Archive Annuaire {archive_version} validée.")
        outcome.messages.append("Copie des fichiers modifiés dans le dossier du projet...")
        copied = 0
        for source_path in staged_root.rglob("*"):
            if source_path.is_dir():
                continue
            relative_path = source_path.relative_to(staged_root)
            destination_path = PROJECT_ROOT / relative_path
            if destination_path.is_file() and filecmp.cmp(source_path, destination_path, shallow=False):
                # Contenu identique : on ne touche pas au fichier local (permissions, mtime...).
                continue

            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
            copied += 1
            if destination_path.suffix in (".command", ".sh"):
                # Les archives zip GitHub ne conservent pas le bit exécutable.
                mode = destination_path.stat().st_mode
                destination_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    outcome.messages.append(f"Copie terminée : {copied} fichier(s) remplacé(s).")
    outcome.hint = (
        "Ce mode ne supprime pas les fichiers devenus obsolètes déjà présents localement ; "
        "en cas de doute, retélécharger le zip complet du projet."
    )
    return True


def _apply_update_via_zip(outcome: UpdateOutcome) -> bool:
    outcome.messages.append(
        "Projet téléchargé en zip (pas de dossier .git) : récupération de l'archive GitHub."
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "update.zip"
        outcome.messages.append(f"Téléchargement de {ARCHIVE_URL} ...")
        urllib.request.urlretrieve(ARCHIVE_URL, archive_path)
        return _apply_zip_archive(archive_path, outcome, require_newer=False)


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
    except (
        urllib.error.URLError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        InvalidUpdateArchive,
    ) as exc:
        outcome.error = f"Échec de la récupération de l'archive GitHub : {exc}"
        return outcome

    if not applied:
        return outcome

    outcome.applied = True
    outcome.requirements_changed = requirements_file.read_text(encoding="utf-8") != requirements_before
    return outcome


def apply_update_from_zip(archive_data: bytes) -> UpdateOutcome:
    """Appliquer un ZIP GitHub fourni par l'utilisateur, sans aucun accès réseau."""
    outcome = UpdateOutcome()
    requirements_file = PROJECT_ROOT / "requirements.txt"
    requirements_before = requirements_file.read_text(encoding="utf-8")
    maximum_bytes = UPDATE_ARCHIVE_MAX_UPLOAD_MO * 1024 * 1024
    if not archive_data:
        outcome.error = "Le fichier ZIP est vide."
        return outcome
    if len(archive_data) > maximum_bytes:
        outcome.error = f"Le fichier ZIP dépasse la limite de {UPDATE_ARCHIVE_MAX_UPLOAD_MO} Mo."
        return outcome

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_path = Path(tmp_dir) / "update.zip"
            archive_path.write_bytes(archive_data)
            outcome.messages.append("Mise à jour hors ligne depuis le ZIP déposé par l'utilisateur.")
            applied = _apply_zip_archive(archive_path, outcome, require_newer=True)
    except (OSError, RuntimeError, zipfile.BadZipFile, InvalidUpdateArchive) as exc:
        outcome.error = f"Archive de mise à jour refusée : {exc}"
        return outcome

    if not applied:
        return outcome
    outcome.applied = True
    outcome.requirements_changed = requirements_file.read_text(encoding="utf-8") != requirements_before
    return outcome
