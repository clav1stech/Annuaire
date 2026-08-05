"""Synchronisation de l'environnement virtuel avec `requirements.txt`.

Le public visé n'utilise pas de terminal : une mise à jour du code qui change les
dépendances ne doit pas laisser un environnement virtuel figé sur les anciens paquets.
Le module compare une empreinte de `requirements.txt` à celle enregistrée dans
l'environnement lors de la dernière installation réussie, et réinstalle si besoin.

Module transverse, appelable depuis les scripts de lancement comme depuis l'UI : aucune
fonction n'écrit sur la sortie standard ni ne termine le processus, le déroulé est
renvoyé dans un `InstallOutcome`.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    BINARY_ONLY_PACKAGES,
    PIP_INSTALL_TIMEOUT_SECONDS,
    PROJECT_ROOT,
    REQUIREMENTS_FILENAME,
    REQUIREMENTS_STAMP_FILENAME,
    VENV_DIR_NAME,
)

REQUIREMENTS_FILE = PROJECT_ROOT / REQUIREMENTS_FILENAME
VENV_DIR = PROJECT_ROOT / VENV_DIR_NAME
STAMP_FILE = VENV_DIR / REQUIREMENTS_STAMP_FILENAME

MANUAL_FALLBACK_HINT = (
    "Fermer cette fenêtre et relancer create_venv (.bat/.command) pour réinstaller "
    "l'environnement. Si l'erreur mentionne pyarrow ou duckdb, aucune wheel précompilée "
    "n'existe pour cette version de Python : utiliser Python 3.11 à 3.14."
)

# Une erreur pip tient en quelques lignes utiles à la fin de sa sortie ; tout remonter
# noierait le message dans des centaines de lignes de résolution de dépendances.
_ERROR_TAIL_LINES = 15


@dataclass(frozen=True)
class SyncState:
    """Cohérence entre `requirements.txt` et les paquets installés."""

    in_sync: bool
    reason: str


@dataclass
class InstallOutcome:
    """Résultat d'une tentative de synchronisation des dépendances.

    `installed` distingue une installation réellement effectuée d'un environnement déjà
    à jour (`already_in_sync`) ; `error` n'est renseigné qu'en cas d'échec, auquel cas
    l'empreinte n'est pas enregistrée et la réinstallation sera retentée au prochain
    lancement.
    """

    installed: bool = False
    already_in_sync: bool = False
    messages: list[str] = field(default_factory=list)
    error: str | None = None
    hint: str | None = None

    @property
    def usable(self) -> bool:
        return self.error is None


def requirements_fingerprint(requirements_text: str) -> str:
    """Empreinte du contenu utile de `requirements.txt`.

    Commentaires, lignes vides, espaces et ordre des lignes sont neutralisés : seul un
    changement réel de dépendance déclenche une réinstallation, pas une reformulation.
    """
    lines = sorted(
        cleaned
        for raw_line in requirements_text.splitlines()
        if (cleaned := raw_line.split("#", 1)[0].strip())
    )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def read_stamp(stamp_file: Path = STAMP_FILE) -> str | None:
    """Empreinte de la dernière installation réussie, `None` si inconnue."""
    try:
        return stamp_file.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def write_stamp(fingerprint: str, stamp_file: Path = STAMP_FILE) -> None:
    """Enregistre l'empreinte de façon atomique (jamais de marqueur à moitié écrit)."""
    stamp_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = stamp_file.with_suffix(".tmp")
    temp_file.write_text(f"{fingerprint}\n", encoding="utf-8")
    os.replace(temp_file, stamp_file)


def get_sync_state(
    requirements_file: Path = REQUIREMENTS_FILE,
    stamp_file: Path = STAMP_FILE,
) -> SyncState:
    """Compare `requirements.txt` à l'empreinte enregistrée dans l'environnement.

    Une empreinte absente est traitée comme une désynchronisation : c'est le cas d'un
    environnement créé avant ce mécanisme, dont rien ne garantit qu'il corresponde aux
    dépendances actuelles.
    """
    try:
        expected = requirements_fingerprint(requirements_file.read_text(encoding="utf-8"))
    except OSError as exc:
        return SyncState(in_sync=True, reason=f"requirements.txt illisible ({exc}) : contrôle ignoré.")

    recorded = read_stamp(stamp_file)
    if recorded is None:
        return SyncState(
            in_sync=False,
            reason="Aucune trace d'installation des dépendances dans l'environnement virtuel.",
        )
    if recorded != expected:
        return SyncState(
            in_sync=False,
            reason="requirements.txt a changé depuis la dernière installation des dépendances.",
        )
    return SyncState(in_sync=True, reason="Dépendances déjà synchronisées avec requirements.txt.")


def install_requirements(
    python_executable: str | None = None,
    requirements_file: Path = REQUIREMENTS_FILE,
    stamp_file: Path = STAMP_FILE,
) -> InstallOutcome:
    """Installe `requirements.txt` avec pip, puis enregistre l'empreinte si tout s'est bien passé.

    L'interpréteur par défaut est celui qui exécute ce code : appelé depuis les scripts de
    lancement, c'est bien le Python de l'environnement virtuel qui est mis à jour.
    """
    outcome = InstallOutcome()
    executable = python_executable or sys.executable
    command = [
        executable,
        "-m",
        "pip",
        "install",
        *(f"--only-binary={package}" for package in BINARY_ONLY_PACKAGES),
        "-r",
        str(requirements_file),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=PIP_INSTALL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        outcome.error = (
            f"pip n'a pas terminé en {PIP_INSTALL_TIMEOUT_SECONDS} secondes ; installation abandonnée."
        )
        outcome.hint = MANUAL_FALLBACK_HINT
        return outcome
    except OSError as exc:
        outcome.error = f"Impossible de lancer pip : {exc}"
        outcome.hint = MANUAL_FALLBACK_HINT
        return outcome

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip().splitlines()
        outcome.error = "\n".join(details[-_ERROR_TAIL_LINES:]) or f"pip a échoué (code {completed.returncode})."
        outcome.hint = MANUAL_FALLBACK_HINT
        return outcome

    try:
        write_stamp(
            requirements_fingerprint(requirements_file.read_text(encoding="utf-8")),
            stamp_file,
        )
    except OSError as exc:
        # Les paquets sont installés : ne pas transformer un marqueur non écrit en échec,
        # la seule conséquence est une réinstallation inutile au prochain lancement.
        outcome.messages.append(f"Empreinte des dépendances non enregistrée ({exc}).")

    outcome.installed = True
    outcome.messages.append("Dépendances installées.")
    return outcome


def ensure_dependencies(
    force: bool = False,
    python_executable: str | None = None,
    requirements_file: Path = REQUIREMENTS_FILE,
    stamp_file: Path = STAMP_FILE,
) -> InstallOutcome:
    """Réinstalle les dépendances si l'environnement a divergé de `requirements.txt`."""
    if not force:
        state = get_sync_state(requirements_file, stamp_file)
        if state.in_sync:
            return InstallOutcome(already_in_sync=True, messages=[state.reason])
        outcome = install_requirements(python_executable, requirements_file, stamp_file)
        outcome.messages.insert(0, state.reason)
        return outcome

    return install_requirements(python_executable, requirements_file, stamp_file)
