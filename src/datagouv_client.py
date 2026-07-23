"""Client de l'API data.gouv.fr : métadonnées des ressources Parquet SIRENE.

Ce module ne manipule que des métadonnées HTTP (lien stable, checksum, taille, date de
publication). Il n'ouvre ni ne lit jamais les fichiers Parquet eux-mêmes.
"""

from __future__ import annotations

import json
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable
import re

from .config import (
    BYTES_PER_MO,
    DATAGOUV_DATASET_ID,
    DATAGOUV_DATASET_URL_TEMPLATE,
    DATAGOUV_MAX_ATTEMPTS,
    DATAGOUV_PARQUET_FORMAT,
    DATAGOUV_RESOURCE_TITLE_FRAGMENTS,
    DATAGOUV_TIMEOUT_SECONDS,
    DATAGOUV_USER_AGENT,
    SIRENE_DATA_CATEGORIES,
)


class DataGouvError(RuntimeError):
    """Échec d'accès aux métadonnées data.gouv.fr.

    Toujours levée explicitement : une métadonnée manquante ou incohérente ne doit
    jamais se replier silencieusement sur une valeur par défaut, sous peine de faire
    croire à des données locales à jour alors qu'aucune comparaison n'a pu avoir lieu.
    """


@dataclass(frozen=True)
class RemoteResource:
    """Métadonnées d'une ressource Parquet SIRENE publiée sur data.gouv.fr."""

    category: str
    title: str
    url: str
    checksum: str | None
    checksum_type: str | None
    filesize: int | None
    last_modified: str | None
    format: str

    @property
    def filesize_mo(self) -> float | None:
        """Taille distante en Mo, pour l'affichage utilisateur."""
        if self.filesize is None:
            return None
        return self.filesize / BYTES_PER_MO


def _normalize_title_token(title: str) -> str:
    """Réduire un titre de ressource à un jeton comparable (sans accent ni ponctuation)."""
    normalized = unicodedata.normalize("NFKD", title.lower())
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", ascii_only)


def classify_resource_title(title: str) -> str | None:
    """Retourner la catégorie SIRENE correspondant à un titre de ressource, si connue."""
    token = _normalize_title_token(title)
    for category, fragment in DATAGOUV_RESOURCE_TITLE_FRAGMENTS:
        if fragment in token:
            return category
    return None


def _request_dataset_payload(url: str) -> dict[str, Any]:
    """Appeler l'API et retourner la charge JSON, avec un retry léger sur erreur réseau."""
    last_error: str | None = None
    for attempt in range(1, DATAGOUV_MAX_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers={"User-Agent": DATAGOUV_USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=DATAGOUV_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Un code HTTP d'erreur traduit un jeu de données déplacé ou supprimé :
            # réessayer n'y changerait rien.
            raise DataGouvError(
                f"data.gouv.fr a répondu {exc.code} pour le jeu de données SIRENE."
            ) from exc
        except urllib.error.URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            if "CERTIFICATE_VERIFY_FAILED" in reason:
                raise DataGouvError(
                    "Certificats SSL non configurés pour ce Python (installeur python.org : "
                    "lancer 'Install Certificates.command', voir le README)."
                ) from exc
            last_error = f"data.gouv.fr injoignable ({reason})."
        except (TimeoutError, OSError) as exc:
            last_error = f"data.gouv.fr injoignable ({exc})."
        except (ValueError, UnicodeDecodeError) as exc:
            raise DataGouvError(f"Réponse illisible de data.gouv.fr : {exc}") from exc
        else:
            if not isinstance(payload, dict):
                raise DataGouvError("Réponse inattendue de data.gouv.fr (format non reconnu).")
            return payload

        if attempt < DATAGOUV_MAX_ATTEMPTS:
            continue

    raise DataGouvError(last_error or "data.gouv.fr injoignable.")


def _coerce_filesize(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_resource(category: str, raw: dict[str, Any]) -> RemoteResource | None:
    """Construire une ressource exploitable, ou None si le lien stable fait défaut."""
    # `latest` est le lien permanent de data.gouv.fr : il suit les republications
    # mensuelles, contrairement à `url` qui pointe vers un fichier statique horodaté.
    stable_url = str(raw.get("latest") or "").strip()
    if not stable_url:
        return None

    checksum_payload = raw.get("checksum") or {}
    if not isinstance(checksum_payload, dict):
        checksum_payload = {}

    return RemoteResource(
        category=category,
        title=str(raw.get("title") or ""),
        url=stable_url,
        checksum=(str(checksum_payload["value"]) if checksum_payload.get("value") else None),
        checksum_type=(str(checksum_payload["type"]) if checksum_payload.get("type") else None),
        filesize=_coerce_filesize(raw.get("filesize")),
        last_modified=(str(raw["last_modified"]) if raw.get("last_modified") else None),
        format=str(raw.get("format") or ""),
    )


def _is_more_recent(candidate: RemoteResource, current: RemoteResource) -> bool:
    """Départager deux ressources d'une même catégorie sur leur date de publication."""
    if candidate.last_modified is None:
        return False
    if current.last_modified is None:
        return True
    return candidate.last_modified > current.last_modified


def select_parquet_resources(
    raw_resources: Iterable[dict[str, Any]],
    categories: Iterable[str] = SIRENE_DATA_CATEGORIES,
) -> dict[str, RemoteResource]:
    """Extraire une ressource Parquet par catégorie demandée.

    Séparé de l'appel réseau pour rester testable sans HTTP.
    """
    wanted = set(categories)
    selected: dict[str, RemoteResource] = {}

    for raw in raw_resources:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("format") or "").strip().lower() != DATAGOUV_PARQUET_FORMAT:
            continue
        category = classify_resource_title(str(raw.get("title") or ""))
        if category is None or category not in wanted:
            continue
        resource = _build_resource(category, raw)
        if resource is None:
            continue
        current = selected.get(category)
        if current is None or _is_more_recent(resource, current):
            selected[category] = resource

    missing = [category for category in categories if category not in selected]
    if missing:
        raise DataGouvError(
            "Ressource(s) Parquet introuvable(s) dans le jeu de données data.gouv.fr : "
            + ", ".join(missing)
        )
    return selected


def fetch_remote_resources(
    categories: Iterable[str] = SIRENE_DATA_CATEGORIES,
) -> dict[str, RemoteResource]:
    """Retourner les métadonnées Parquet publiées, indexées par catégorie SIRENE.

    Lève ``DataGouvError`` en cas d'échec réseau ou de catégorie manquante.
    """
    url = DATAGOUV_DATASET_URL_TEMPLATE.format(dataset_id=DATAGOUV_DATASET_ID)
    payload = _request_dataset_payload(url)
    raw_resources = payload.get("resources")
    if not isinstance(raw_resources, list):
        raise DataGouvError("Le jeu de données data.gouv.fr ne contient aucune ressource.")
    return select_parquet_resources(raw_resources, categories)
