"""Manifeste local de version des fichiers SIRENE et comparaison avec data.gouv.fr.

Le manifeste mémorise ce qui a été téléchargé (checksum, taille, date de publication) afin
de répondre à « mes fichiers sont-ils à jour ? » sans jamais ouvrir les Parquet eux-mêmes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .config import (
    BYTES_PER_MO,
    DATA_STATUS_ABSENT,
    DATA_STATUS_OUTDATED,
    DATA_STATUS_UP_TO_DATE,
    PROJECT_ROOT,
    SIRENE_CATEGORY_DEFAULT_FILENAMES,
    SIRENE_CATEGORY_LABELS,
    SIRENE_DATA_CATEGORIES,
    SIRENE_MANIFEST_FILENAME,
    SIRENE_MANIFEST_VERSION,
)
from .datagouv_client import DataGouvError, RemoteResource, fetch_remote_resources
from .download_utils import ProgressCallback, download_with_progress


@dataclass(frozen=True)
class ManifestEntry:
    """Ce qui a été effectivement téléchargé pour une catégorie."""

    category: str
    checksum: str | None
    filesize: int | None
    last_modified: str | None
    local_path: str
    downloaded_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checksum": self.checksum,
            "filesize": self.filesize,
            "last_modified": self.last_modified,
            "local_path": self.local_path,
            "downloaded_at": self.downloaded_at,
        }

    @classmethod
    def from_dict(cls, category: str, payload: Mapping[str, Any]) -> "ManifestEntry":
        return cls(
            category=category,
            checksum=payload.get("checksum"),
            filesize=payload.get("filesize"),
            last_modified=payload.get("last_modified"),
            local_path=str(payload.get("local_path") or ""),
            downloaded_at=str(payload.get("downloaded_at") or ""),
        )


@dataclass(frozen=True)
class CategoryFreshness:
    """Verdict de fraîcheur pour une catégorie de fichier SIRENE."""

    category: str
    status: str
    label: str
    detail: str
    local_path: str | None
    remote_size_mo: float | None
    remote_last_modified: str | None
    downloaded_at: str | None

    @property
    def needs_download(self) -> bool:
        return self.status != DATA_STATUS_UP_TO_DATE


@dataclass(frozen=True)
class DataFreshnessStatus:
    """Résultat global de la comparaison manifeste local / ressources distantes."""

    categories: tuple[CategoryFreshness, ...] = ()
    error: str | None = None

    @property
    def check_ok(self) -> bool:
        return self.error is None

    @property
    def stale(self) -> tuple[CategoryFreshness, ...]:
        return tuple(item for item in self.categories if item.needs_download)

    @property
    def up_to_date(self) -> bool:
        return self.check_ok and not self.stale

    @property
    def total_download_mo(self) -> float:
        return sum(item.remote_size_mo or 0.0 for item in self.stale)

    @property
    def latest_publication(self) -> str | None:
        """Date de publication la plus récente parmi les catégories suivies."""
        dates = [item.remote_last_modified for item in self.categories if item.remote_last_modified]
        return max(dates) if dates else None


def manifest_path(root: str | Path | None = None) -> Path:
    return Path(root or PROJECT_ROOT) / SIRENE_MANIFEST_FILENAME


def default_target_path(category: str, root: str | Path | None = None) -> Path:
    """Emplacement local attendu pour une catégorie, aligné sur la détection automatique."""
    filename = SIRENE_CATEGORY_DEFAULT_FILENAMES[category]
    return Path(root or PROJECT_ROOT) / filename


def load_manifest(root: str | Path | None = None) -> dict[str, ManifestEntry]:
    """Lire le manifeste local.

    Un manifeste absent ou illisible équivaut à « rien de connu » : les catégories seront
    recalculées comme à télécharger, ce qui est le comportement sûr.
    """
    path = manifest_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    entries = payload.get("categories")
    if not isinstance(entries, dict):
        return {}
    return {
        str(category): ManifestEntry.from_dict(str(category), item)
        for category, item in entries.items()
        if isinstance(item, Mapping)
    }


def save_manifest(entries: Mapping[str, ManifestEntry], root: str | Path | None = None) -> Path:
    """Écrire le manifeste de façon atomique (temporaire puis remplacement)."""
    path = manifest_path(root)
    payload = {
        "manifest_version": SIRENE_MANIFEST_VERSION,
        "categories": {category: entry.to_dict() for category, entry in entries.items()},
    }
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temp_path, path)
    return path


def record_download(
    resource: RemoteResource,
    local_path: str | Path,
    root: str | Path | None = None,
) -> ManifestEntry:
    """Enregistrer une catégorie fraîchement téléchargée dans le manifeste."""
    entry = ManifestEntry(
        category=resource.category,
        checksum=resource.checksum,
        filesize=resource.filesize,
        last_modified=resource.last_modified,
        local_path=str(local_path),
        downloaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    entries = load_manifest(root)
    entries[resource.category] = entry
    save_manifest(entries, root)
    return entry


def _compare_category(
    category: str,
    resource: RemoteResource,
    entry: ManifestEntry | None,
    existing_local_path: str | None,
) -> CategoryFreshness:
    label = SIRENE_CATEGORY_LABELS.get(category, category)
    size_mo = resource.filesize_mo
    tracked_path = entry.local_path if entry is not None else None
    tracked_exists = bool(tracked_path) and Path(str(tracked_path)).exists()

    if entry is None or not tracked_exists:
        # Un fichier déposé à la main est bien présent mais de version inconnue : le
        # signaler comme obsolète plutôt qu'absent évite d'annoncer à tort un fichier
        # manquant à un utilisateur qui l'a déjà installé.
        if existing_local_path:
            return CategoryFreshness(
                category=category,
                status=DATA_STATUS_OUTDATED,
                label=label,
                detail="fichier local présent, version inconnue",
                local_path=existing_local_path,
                remote_size_mo=size_mo,
                remote_last_modified=resource.last_modified,
                downloaded_at=None,
            )
        return CategoryFreshness(
            category=category,
            status=DATA_STATUS_ABSENT,
            label=label,
            detail="aucun fichier local",
            local_path=None,
            remote_size_mo=size_mo,
            remote_last_modified=resource.last_modified,
            downloaded_at=None,
        )

    if resource.checksum and entry.checksum:
        same_version = resource.checksum == entry.checksum
    else:
        # Sans checksum des deux côtés, la date de publication est le seul repère fiable :
        # la taille seule ne distingue pas deux millésimes de volume voisin.
        same_version = (
            resource.last_modified is not None and resource.last_modified == entry.last_modified
        )

    return CategoryFreshness(
        category=category,
        status=DATA_STATUS_UP_TO_DATE if same_version else DATA_STATUS_OUTDATED,
        label=label,
        detail="" if same_version else "nouvelle version publiée",
        local_path=str(tracked_path),
        remote_size_mo=size_mo,
        remote_last_modified=resource.last_modified,
        downloaded_at=entry.downloaded_at or None,
    )


def build_freshness_status(
    resources: Mapping[str, RemoteResource],
    entries: Mapping[str, ManifestEntry],
    existing_local_paths: Mapping[str, str] | None = None,
    categories: Iterable[str] = SIRENE_DATA_CATEGORIES,
) -> DataFreshnessStatus:
    """Comparer manifeste et ressources distantes, sans aucun accès réseau."""
    detected = existing_local_paths or {}
    verdicts = [
        _compare_category(category, resources[category], entries.get(category), detected.get(category))
        for category in categories
        if category in resources
    ]
    return DataFreshnessStatus(categories=tuple(verdicts))


def get_data_freshness_status(
    existing_local_paths: Mapping[str, str] | None = None,
    root: str | Path | None = None,
) -> DataFreshnessStatus:
    """Statut de fraîcheur des données SIRENE locales face à data.gouv.fr.

    ``existing_local_paths`` provient de la détection de fichiers déjà présents : il permet
    de distinguer un fichier absent d'un fichier installé manuellement, hors manifeste.
    """
    try:
        resources = fetch_remote_resources()
    except DataGouvError as exc:
        return DataFreshnessStatus(error=str(exc))
    return build_freshness_status(resources, load_manifest(root), existing_local_paths)


def download_category(
    resource: RemoteResource,
    root: str | Path | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Télécharger une catégorie puis inscrire le résultat au manifeste.

    Le manifeste n'est mis à jour qu'après un transfert complet : un échec laisse la
    version précédemment enregistrée intacte, jamais un état partiel.
    """
    target = default_target_path(resource.category, root)
    download_with_progress(
        resource.url,
        target,
        expected_size=resource.filesize,
        progress_callback=progress_callback,
    )
    record_download(resource, target, root)
    return target


def format_size_mo(size_mo: float | None) -> str:
    """Formatage court d'une taille pour l'interface."""
    if size_mo is None:
        return "taille inconnue"
    if size_mo >= 1024:
        return f"{size_mo / 1024:.1f} Go"
    return f"{size_mo:.0f} Mo"


def format_publication_date(raw: str | None) -> str:
    """Rendre lisible une date ISO de publication data.gouv.fr."""
    if not raw:
        return "date inconnue"
    try:
        return datetime.fromisoformat(raw).strftime("%d/%m/%Y")
    except ValueError:
        return raw


def bytes_to_mo(size_bytes: int | None) -> float | None:
    if size_bytes is None:
        return None
    return size_bytes / BYTES_PER_MO
