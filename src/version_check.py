"""Vérification de version distante (GitHub), partagée entre l'UI Streamlit et scripts/update_project.py."""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_OWNER = "clav1stech"
REPO_NAME = "Annuaire"
BRANCH = "main"
RAW_VERSION_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/VERSION"
NETWORK_TIMEOUT_SECONDS = 5

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_version(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in text.strip().split("."))
    except ValueError:
        return (0,)


def read_local_version() -> str:
    version_file = PROJECT_ROOT / "VERSION"
    return version_file.read_text(encoding="utf-8").strip() if version_file.exists() else "0.0.0"


def fetch_remote_version() -> tuple[str | None, str | None]:
    """Retourne (version_distante, message_erreur). L'un des deux est toujours None."""
    try:
        with urllib.request.urlopen(RAW_VERSION_URL, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8").strip(), None
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "CERTIFICATE_VERIFY_FAILED" in reason:
            return None, (
                "Certificats SSL non configurés pour ce Python (installeur python.org : lancer "
                "'Install Certificates.command', voir le README)."
            )
        return None, f"GitHub injoignable ({reason})."
    except (TimeoutError, OSError) as exc:
        return None, f"GitHub injoignable ({exc})."


@dataclass(frozen=True)
class VersionStatus:
    local_version: str
    remote_version: str | None
    error: str | None

    @property
    def check_ok(self) -> bool:
        return self.remote_version is not None

    @property
    def update_available(self) -> bool:
        return self.remote_version is not None and parse_version(self.remote_version) > parse_version(
            self.local_version
        )

    @property
    def ahead_of_remote(self) -> bool:
        """Version locale en avance sur `main` : branche de développement, pas une version diffusée.

        Distinguer ce cas de « à jour » évite de laisser croire que le code exécuté est
        celui publié, alors qu'il n'a pas encore été fusionné.
        """
        return self.remote_version is not None and parse_version(self.local_version) > parse_version(
            self.remote_version
        )


def get_version_status() -> VersionStatus:
    local_version = read_local_version()
    remote_version, error = fetch_remote_version()
    return VersionStatus(local_version=local_version, remote_version=remote_version, error=error)
