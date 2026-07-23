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


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_version() -> str:
    """Read the project version from the root VERSION file (single source of truth)."""
    version_path = PROJECT_ROOT / "VERSION"
    return version_path.read_text(encoding="utf-8").strip()


__version__ = _read_version()

DEFAULT_STOCKETABLISSEMENT_PATH = "StockEtablissement_utf8.parquet"
DEFAULT_STOCKUNITELEGALE_PATH = "StockUniteLegale_utf8.parquet"
DEFAULT_SUCCESSION_PATH = "StockEtablissementLiensSuccession_utf8.parquet"
DEFAULT_HISTORIQUE_PATH = "StockEtablissementHistorique_utf8.parquet"

SUPPORTED_INPUT_EXTENSIONS = {".xlsx", ".csv", ".parquet"}

# --- Source distante des fichiers SIRENE (data.gouv.fr) ----------------------

# Jeu de données officiel "Base Sirene des entreprises et de leurs établissements
# (SIREN, SIRET)". L'identifiant est stable, contrairement au slug de l'URL publique.
DATAGOUV_DATASET_ID = "5b7ffc618b4c4169d30727e0"
DATAGOUV_DATASET_URL_TEMPLATE = "https://www.data.gouv.fr/api/1/datasets/{dataset_id}/"
DATAGOUV_PARQUET_FORMAT = "parquet"
DATAGOUV_TIMEOUT_SECONDS = 15
DATAGOUV_MAX_ATTEMPTS = 2
DATAGOUV_USER_AGENT = f"{APP_NAME}/{__version__}"

# Catégories de fichiers SIRENE exploitées par l'application. Les clés sont communes
# à la détection locale (io_utils) et à la résolution distante (datagouv_client).
SIRENE_DATA_CATEGORIES = (
    "stocketablissement",
    "stockunitelegale",
    "stocketablissementlienssuccession",
    "stocketablissementhistorique",
)

SIRENE_CATEGORY_LABELS = {
    "stocketablissement": "StockEtablissement",
    "stockunitelegale": "StockUniteLegale",
    "stocketablissementlienssuccession": "StockEtablissementLiensSuccession",
    "stocketablissementhistorique": "StockEtablissementHistorique",
}

SIRENE_CATEGORY_DEFAULT_FILENAMES = {
    "stocketablissement": DEFAULT_STOCKETABLISSEMENT_PATH,
    "stockunitelegale": DEFAULT_STOCKUNITELEGALE_PATH,
    "stocketablissementlienssuccession": DEFAULT_SUCCESSION_PATH,
    "stocketablissementhistorique": DEFAULT_HISTORIQUE_PATH,
}

# Fragments de titre de ressource permettant de classer une ressource data.gouv.fr.
# L'ordre est significatif : "stocketablissement" est un préfixe de
# "stocketablissementhistorique" et "stocketablissementlienssuccession", et
# "stockunitelegale" un préfixe de "stockunitelegalehistorique". Les fragments les plus
# spécifiques doivent donc être testés en premier. Les catégories hors périmètre
# applicatif figurent dans la liste pour être classées puis écartées, jamais confondues
# avec une catégorie voisine.
DATAGOUV_RESOURCE_TITLE_FRAGMENTS = (
    ("stocketablissementlienssuccession", "stocketablissementlienssuccession"),
    ("stocketablissementhistorique", "stocketablissementhistorique"),
    ("stockunitelegalehistorique", "stockunitelegalehistorique"),
    ("stockunitelegale", "stockunitelegale"),
    ("stocketablissement", "stocketablissement"),
    ("stockdoublons", "stockdoublons"),
)

# --- Manifeste local de version des données ---------------------------------

SIRENE_MANIFEST_FILENAME = ".sirene_manifest.json"
SIRENE_MANIFEST_VERSION = 1

DATA_STATUS_ABSENT = "absent"
DATA_STATUS_UP_TO_DATE = "à jour"
DATA_STATUS_OUTDATED = "obsolète"

DATA_FRESHNESS_CACHE_TTL_SECONDS = 3600

# --- Téléchargement ---------------------------------------------------------

# Les fichiers SIRENE pèsent jusqu'à plusieurs gigaoctets : des blocs larges limitent
# le nombre d'aller-retours et de rafraîchissements d'interface pendant le transfert.
DOWNLOAD_CHUNK_SIZE_BYTES = 8 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 60
DOWNLOAD_TEMP_SUFFIX = ".part"
BYTES_PER_MO = 1024 * 1024

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
