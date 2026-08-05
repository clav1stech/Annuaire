"""Remplacement atomique tolérant aux verrous transitoires du système de fichiers.

Couche transverse : ce module ne connaît ni les données SIRENE ni l'interface. Il ne fait
que fiabiliser l'étape « temporaire → fichier final » commune à toutes les écritures.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from .config import ATOMIC_REPLACE_MAX_ATTEMPTS, ATOMIC_REPLACE_RETRY_DELAY_SECONDS


class AtomicWriteError(OSError):
    """Le fichier final n'a pas pu être remplacé : le contenu précédent reste en place."""


def replace_atomically(temp_path: str | Path, target_path: str | Path) -> Path:
    """Remplacer ``target_path`` par ``temp_path``, en réessayant si l'accès est refusé.

    Un dossier synchronisé (OneDrive, Dropbox) ou un antivirus peut tenir la destination
    ouverte pendant une fraction de seconde après son écriture ; ``os.replace`` échoue alors
    en ``PermissionError`` alors qu'un simple nouvel essai passerait. Le temporaire est
    supprimé si tous les essais échouent, pour ne pas laisser de résidu à côté du fichier.
    """
    temp = Path(temp_path)
    target = Path(target_path)
    last_error: OSError | None = None

    for attempt in range(1, ATOMIC_REPLACE_MAX_ATTEMPTS + 1):
        try:
            os.replace(temp, target)
            return target
        except OSError as exc:
            last_error = exc
            if attempt < ATOMIC_REPLACE_MAX_ATTEMPTS:
                time.sleep(ATOMIC_REPLACE_RETRY_DELAY_SECONDS * attempt)

    try:
        temp.unlink(missing_ok=True)
    except OSError:
        pass

    raise AtomicWriteError(
        f"Impossible de remplacer « {target} » après {ATOMIC_REPLACE_MAX_ATTEMPTS} tentatives "
        f"({last_error}). Le fichier est probablement verrouillé par une synchronisation cloud "
        "(OneDrive, Dropbox), un antivirus ou un logiciel qui le garde ouvert."
    ) from last_error


def write_text_atomically(
    target_path: str | Path,
    text: str,
    temp_suffix: str = ".tmp",
) -> Path:
    """Écrire du texte UTF-8 via un temporaire voisin, puis remplacer le fichier final."""
    target = Path(target_path)
    temp = target.with_name(target.name + temp_suffix)
    temp.write_text(text, encoding="utf-8")
    return replace_atomically(temp, target)
