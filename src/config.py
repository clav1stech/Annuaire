"""Application constants and shared configuration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

APP_NAME = "Annuaire_SIRENE"
APP_TITLE = "Annuaire_SIRENE - Contrôle de SIRET"
APP_DESCRIPTION = (
    "Application locale pour contrôler et enrichir une liste de SIRET à partir "
    "des fichiers SIRENE Parquet."
)

DEFAULT_STOCKETABLISSEMENT_PATH = "StockEtablissement_utf8.parquet"
DEFAULT_STOCKUNITELEGALE_PATH = "StockUniteLegale_utf8.parquet"
DEFAULT_SUCCESSION_PATH = "StockEtablissementLiensSuccession_utf8.parquet"
DEFAULT_HISTORIQUE_PATH = "StockEtablissementHistorique_utf8.parquet"

SUPPORTED_INPUT_EXTENSIONS = {".xlsx", ".csv", ".parquet"}

REQUIRED_SHEETS = ["controle_siret", "all_etablissements", "move_candidates"]
OPTIONAL_SHEETS = ["succession_links", "historique", "params_logs"]

SIRET_STATUS_INVALID = "INVALID_SIRET_FORMAT"
SIRET_STATUS_NOT_FOUND = "NOT_FOUND_IN_SIRENE"
SIRET_STATUS_ACTIVE = "ACTIVE"
SIRET_STATUS_CLOSED = "CLOSED"
SIRET_STATUS_RADIATED = "RADIATED"
SIRET_STATUS_FOUND_UNKNOWN = "FOUND_UNKNOWN_STATUS"

SIRET_STATUS_ORDER = [
    SIRET_STATUS_INVALID,
    SIRET_STATUS_NOT_FOUND,
    SIRET_STATUS_ACTIVE,
    SIRET_STATUS_CLOSED,
    SIRET_STATUS_RADIATED,
    SIRET_STATUS_FOUND_UNKNOWN,
]

DENOMINATION_COALESCE_FIELDS = [
    "denominationUniteLegale",
    "denominationUsuelle1UniteLegale",
    "denominationUsuelle2UniteLegale",
    "denominationUsuelle3UniteLegale",
    "sigleUniteLegale",
]

PERSON_NAME_FIELDS = [
    "prenom1UniteLegale",
    "prenom2UniteLegale",
    "prenom3UniteLegale",
    "nomUsageUniteLegale",
    "nomUniteLegale",
]

ETABLISSEMENT_CANONICAL_FIELDS = [
    "siret",
    "siren",
    "nic",
    "etatAdministratifEtablissement",
    "dateCreationEtablissement",
    "dateDebut",
    "dateFin",
    "activitePrincipaleEtablissement",
    "nomenclatureActivitePrincipaleEtablissement",
    "enseigne1Etablissement",
    "denominationUsuelleEtablissement",
    "complementAdresseEtablissement",
    "numeroVoieEtablissement",
    "indiceRepetitionEtablissement",
    "typeVoieEtablissement",
    "libelleVoieEtablissement",
    "codePostalEtablissement",
    "libelleCommuneEtablissement",
    "libelleCommuneEtrangerEtablissement",
    "distributionSpecialeEtablissement",
    "codeCommuneEtablissement",
    "codeCedexEtablissement",
    "libelleCedexEtablissement",
    "paysEtrangerEtablissement",
]

UNITE_LEGALE_CANONICAL_FIELDS = [
    "siren",
    "etatAdministratifUniteLegale",
    "statutDiffusionUniteLegale",
    "categorieJuridiqueUniteLegale",
    "activitePrincipaleUniteLegale",
    "nomenclatureActivitePrincipaleUniteLegale",
    "denominationUniteLegale",
    "denominationUsuelle1UniteLegale",
    "denominationUsuelle2UniteLegale",
    "denominationUsuelle3UniteLegale",
    "sigleUniteLegale",
    "nomUniteLegale",
    "nomUsageUniteLegale",
    "prenom1UniteLegale",
    "prenom2UniteLegale",
    "prenom3UniteLegale",
]

HISTORIQUE_PRIORITY_FIELDS = [
    "siret",
    "siren",
    "nic",
    "dateDebut",
    "dateFin",
    "etatAdministratifEtablissement",
    "complementAdresseEtablissement",
    "numeroVoieEtablissement",
    "indiceRepetitionEtablissement",
    "typeVoieEtablissement",
    "libelleVoieEtablissement",
    "codePostalEtablissement",
    "libelleCommuneEtablissement",
]

ADDRESS_COMPONENT_FIELDS = [
    "complementAdresseEtablissement",
    "numeroVoieEtablissement",
    "indiceRepetitionEtablissement",
    "typeVoieEtablissement",
    "libelleVoieEtablissement",
    "distributionSpecialeEtablissement",
    "codePostalEtablissement",
    "libelleCommuneEtablissement",
    "libelleCedexEtablissement",
    "libelleCommuneEtrangerEtablissement",
    "paysEtrangerEtablissement",
]


def _safe_output_stem(input_filename: str | None) -> str:
    """Build a filesystem-safe output stem from an optional input filename."""
    if input_filename:
        stem = Path(str(input_filename)).stem.strip()
    else:
        stem = APP_NAME
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", stem)
    stem = re.sub(r"\s+", "_", stem).strip("._")
    return stem or APP_NAME


def build_default_output_path(input_filename: str | None = None) -> Path:
    """Return a default output file path in Downloads."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    downloads_dir = get_downloads_dir()
    stem = _safe_output_stem(input_filename)
    return downloads_dir / f"{stem}_{timestamp}.xlsx"


def get_downloads_dir() -> Path:
    """Return user Downloads folder with a robust fallback."""
    home = Path.home()
    candidates = [home / "Downloads", home / "Téléchargements"]
    for folder in candidates:
        if folder.exists():
            return folder
    return home / "Downloads"
