"""Schema handling for SIRENE parquet tables with defensive alias matching."""

from __future__ import annotations

import re
from typing import Iterable


def normalize_column_token(name: str) -> str:
    """Normalize a column name to a comparison token."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _variants(base: str) -> list[str]:
    """Generate simple naming variants to improve matching robustness."""
    lowered = base.lower()
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", base).lower()
    return list(
        {
            base,
            lowered,
            snake,
            snake.replace("_", ""),
            lowered.replace("_", ""),
        }
    )


ETABLISSEMENT_COLUMN_ALIASES: dict[str, list[str]] = {
    "siret": _variants("siret"),
    "siren": _variants("siren"),
    "nic": _variants("nic"),
    "etatAdministratifEtablissement": _variants("etatAdministratifEtablissement"),
    "dateCreationEtablissement": _variants("dateCreationEtablissement"),
    "dateDebut": _variants("dateDebut"),
    "dateFin": _variants("dateFin"),
    "activitePrincipaleEtablissement": _variants("activitePrincipaleEtablissement"),
    "nomenclatureActivitePrincipaleEtablissement": _variants(
        "nomenclatureActivitePrincipaleEtablissement"
    ),
    "enseigne1Etablissement": _variants("enseigne1Etablissement"),
    "denominationUsuelleEtablissement": _variants("denominationUsuelleEtablissement"),
    "complementAdresseEtablissement": _variants("complementAdresseEtablissement"),
    "numeroVoieEtablissement": _variants("numeroVoieEtablissement"),
    "indiceRepetitionEtablissement": _variants("indiceRepetitionEtablissement"),
    "typeVoieEtablissement": _variants("typeVoieEtablissement"),
    "libelleVoieEtablissement": _variants("libelleVoieEtablissement"),
    "codePostalEtablissement": _variants("codePostalEtablissement"),
    "libelleCommuneEtablissement": _variants("libelleCommuneEtablissement"),
    "libelleCommuneEtrangerEtablissement": _variants(
        "libelleCommuneEtrangerEtablissement"
    ),
    "distributionSpecialeEtablissement": _variants("distributionSpecialeEtablissement"),
    "codeCommuneEtablissement": _variants("codeCommuneEtablissement"),
    "codeCedexEtablissement": _variants("codeCedexEtablissement"),
    "libelleCedexEtablissement": _variants("libelleCedexEtablissement"),
    "paysEtrangerEtablissement": _variants("paysEtrangerEtablissement"),
    "etablissementSiege": _variants("etablissementSiege"),
}

UNITE_LEGALE_COLUMN_ALIASES: dict[str, list[str]] = {
    "siren": _variants("siren"),
    "etatAdministratifUniteLegale": _variants("etatAdministratifUniteLegale"),
    "statutDiffusionUniteLegale": _variants("statutDiffusionUniteLegale"),
    "categorieJuridiqueUniteLegale": _variants("categorieJuridiqueUniteLegale"),
    "activitePrincipaleUniteLegale": _variants("activitePrincipaleUniteLegale"),
    "nomenclatureActivitePrincipaleUniteLegale": _variants(
        "nomenclatureActivitePrincipaleUniteLegale"
    ),
    "denominationUniteLegale": _variants("denominationUniteLegale"),
    "denominationUsuelle1UniteLegale": _variants("denominationUsuelle1UniteLegale"),
    "denominationUsuelle2UniteLegale": _variants("denominationUsuelle2UniteLegale"),
    "denominationUsuelle3UniteLegale": _variants("denominationUsuelle3UniteLegale"),
    "sigleUniteLegale": _variants("sigleUniteLegale"),
    "nomUniteLegale": _variants("nomUniteLegale"),
    "nomUsageUniteLegale": _variants("nomUsageUniteLegale"),
    "prenom1UniteLegale": _variants("prenom1UniteLegale"),
    "prenom2UniteLegale": _variants("prenom2UniteLegale"),
    "prenom3UniteLegale": _variants("prenom3UniteLegale"),
}

SUCCESSION_COLUMN_ALIASES: dict[str, list[str]] = {
    "siretEtablissementPredecesseur": _variants("siretEtablissementPredecesseur")
    + _variants("siretPredecesseur"),
    "siretEtablissementSuccesseur": _variants("siretEtablissementSuccesseur")
    + _variants("siretSuccesseur"),
    "dateLienSuccession": _variants("dateLienSuccession"),
    "transfereSiege": _variants("transfereSiege"),
    "continuiteEconomique": _variants("continuiteEconomique"),
}

HISTORIQUE_COLUMN_ALIASES: dict[str, list[str]] = {
    "siret": _variants("siret"),
    "siren": _variants("siren"),
    "nic": _variants("nic"),
    "dateDebut": _variants("dateDebut"),
    "dateFin": _variants("dateFin"),
    "etatAdministratifEtablissement": _variants("etatAdministratifEtablissement"),
    "complementAdresseEtablissement": _variants("complementAdresseEtablissement"),
    "numeroVoieEtablissement": _variants("numeroVoieEtablissement"),
    "indiceRepetitionEtablissement": _variants("indiceRepetitionEtablissement"),
    "typeVoieEtablissement": _variants("typeVoieEtablissement"),
    "libelleVoieEtablissement": _variants("libelleVoieEtablissement"),
    "codePostalEtablissement": _variants("codePostalEtablissement"),
    "libelleCommuneEtablissement": _variants("libelleCommuneEtablissement"),
}


def resolve_column_map(
    available_columns: Iterable[str],
    aliases_map: dict[str, list[str]],
) -> dict[str, str]:
    """Resolve canonical names to available parquet columns."""
    available = list(available_columns)
    by_token = {normalize_column_token(col): col for col in available}
    resolved: dict[str, str] = {}
    for canonical, aliases in aliases_map.items():
        candidates = [canonical, *aliases]
        for alias in candidates:
            match = by_token.get(normalize_column_token(alias))
            if match:
                resolved[canonical] = match
                break
    return resolved


def sql_identifier(name: str) -> str:
    """Quote SQL identifiers safely for DuckDB."""
    return '"' + name.replace('"', '""') + '"'


def build_select_expressions(
    column_map: dict[str, str],
    table_alias: str = "p",
) -> list[str]:
    """Build CAST-to-VARCHAR select expressions with canonical aliases."""
    expressions: list[str] = []
    for canonical, actual in column_map.items():
        expressions.append(
            f"CAST({table_alias}.{sql_identifier(actual)} AS VARCHAR) AS {sql_identifier(canonical)}"
        )
    return expressions
