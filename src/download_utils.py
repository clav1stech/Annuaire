"""Téléchargement de fichiers volumineux en flux, avec écriture atomique.

Transport pur : ce module ne connaît ni le manifeste local ni l'interface. Il ne lit
jamais le contenu téléchargé, il ne fait que l'écrire bloc par bloc.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .config import (
    BYTES_PER_MO,
    DATAGOUV_USER_AGENT,
    DOWNLOAD_CHUNK_SIZE_BYTES,
    DOWNLOAD_TEMP_SUFFIX,
    DOWNLOAD_TIMEOUT_SECONDS,
)

# (pourcentage, Mo téléchargés, Mo attendus) ; le total vaut None tant qu'il est inconnu.
ProgressCallback = Callable[[int, float, float | None], None]


class DownloadError(RuntimeError):
    """Échec de téléchargement : aucun fichier utilisable n'a été produit."""


def _content_length(response: object) -> int | None:
    """Taille annoncée par le serveur, ou None si l'en-tête est absent ou illisible."""
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("Content-Length")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _percent(downloaded: int, total: int | None) -> int:
    if not total or total <= 0:
        return 0
    return min(100, int(downloaded * 100 / total))


def download_with_progress(
    url: str,
    target_path: str | Path,
    expected_size: int | None = None,
    progress_callback: ProgressCallback | None = None,
    *,
    chunk_size: int = DOWNLOAD_CHUNK_SIZE_BYTES,
    timeout: int = DOWNLOAD_TIMEOUT_SECONDS,
) -> Path:
    """Télécharger ``url`` vers ``target_path`` et retourner le chemin final.

    L'écriture passe par un fichier temporaire renommé seulement une fois le transfert
    complet : un téléchargement interrompu ne laisse jamais un Parquet tronqué à la place
    d'un fichier valide. Le temporaire est supprimé en cas d'échec.
    """
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(target.name + DOWNLOAD_TEMP_SUFFIX)

    request = urllib.request.Request(url, headers={"User-Agent": DATAGOUV_USER_AGENT})
    downloaded = 0

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = _content_length(response) or expected_size
            total_mo = total / BYTES_PER_MO if total else None
            if progress_callback is not None:
                progress_callback(0, 0.0, total_mo)

            with open(temp_path, "wb") as handle:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback is not None:
                        progress_callback(
                            _percent(downloaded, total),
                            downloaded / BYTES_PER_MO,
                            total_mo,
                        )
                handle.flush()
                os.fsync(handle.fileno())

        if total and downloaded != total:
            raise DownloadError(
                f"Téléchargement incomplet ({downloaded} octets reçus sur {total} attendus)."
            )
        if downloaded == 0:
            raise DownloadError("Téléchargement vide : aucune donnée reçue.")

        os.replace(temp_path, target)
    except urllib.error.HTTPError as exc:
        _discard(temp_path)
        raise DownloadError(f"Téléchargement refusé (HTTP {exc.code}) : {url}") from exc
    except urllib.error.URLError as exc:
        _discard(temp_path)
        raise DownloadError(f"Serveur injoignable ({getattr(exc, 'reason', exc)}).") from exc
    except DownloadError:
        _discard(temp_path)
        raise
    except OSError as exc:
        _discard(temp_path)
        raise DownloadError(f"Écriture impossible sur le disque : {exc}") from exc

    if progress_callback is not None:
        total_mo = downloaded / BYTES_PER_MO
        progress_callback(100, total_mo, total_mo)
    return target


def _discard(temp_path: Path) -> None:
    """Supprimer le fichier temporaire d'un transfert avorté, sans masquer l'erreur d'origine."""
    try:
        temp_path.unlink(missing_ok=True)
    except OSError:
        pass
