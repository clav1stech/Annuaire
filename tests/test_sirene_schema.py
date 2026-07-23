"""Tests de résolution de schéma SIRENE, dont la coexistence des nomenclatures NAF.

Les colonnes sont factices : aucun fichier Parquet n'est ouvert.
"""

from __future__ import annotations

import pytest

from src.sirene_schema import (
    ETABLISSEMENT_COLUMN_ALIASES,
    NAF_NOMENCLATURE_2025,
    NAF_NOMENCLATURE_LEGACY,
    NAF_TABLE_ETABLISSEMENT,
    NAF_TABLE_UNITE_LEGALE,
    UNITE_LEGALE_COLUMN_ALIASES,
    resolve_column_map,
    resolve_naf_column,
)

LEGACY_ETAB_COLUMNS = ["siret", "siren", "activitePrincipaleEtablissement"]
NAF25_ETAB_COLUMNS = ["siret", "siren", "activitePrincipaleNAF25Etablissement"]
LEGACY_UL_COLUMNS = ["siren", "activitePrincipaleUniteLegale"]
NAF25_UL_COLUMNS = ["siren", "activitePrincipaleNAF25UniteLegale"]


class TestResolveNafColumn:
    def test_legacy_nomenclature_is_detected(self):
        resolution = resolve_naf_column(LEGACY_ETAB_COLUMNS, NAF_TABLE_ETABLISSEMENT)
        assert resolution.nomenclature == NAF_NOMENCLATURE_LEGACY
        assert resolution.column == "activitePrincipaleEtablissement"
        assert resolution.resolved is True

    def test_naf25_nomenclature_is_detected(self):
        resolution = resolve_naf_column(NAF25_ETAB_COLUMNS, NAF_TABLE_ETABLISSEMENT)
        assert resolution.nomenclature == NAF_NOMENCLATURE_2025
        assert resolution.column == "activitePrincipaleNAF25Etablissement"

    def test_legacy_wins_while_both_coexist(self):
        """Pendant la transition, les deux colonnes cohabitent : l'historique reste prioritaire."""
        resolution = resolve_naf_column(
            ["siret", "activitePrincipaleEtablissement", "activitePrincipaleNAF25Etablissement"],
            NAF_TABLE_ETABLISSEMENT,
        )
        assert resolution.nomenclature == NAF_NOMENCLATURE_LEGACY

    def test_unite_legale_both_nomenclatures(self):
        legacy = resolve_naf_column(LEGACY_UL_COLUMNS, NAF_TABLE_UNITE_LEGALE)
        naf25 = resolve_naf_column(NAF25_UL_COLUMNS, NAF_TABLE_UNITE_LEGALE)
        assert legacy.column == "activitePrincipaleUniteLegale"
        assert naf25.column == "activitePrincipaleNAF25UniteLegale"
        assert naf25.nomenclature == NAF_NOMENCLATURE_2025

    def test_snake_case_variant_is_tolerated(self):
        resolution = resolve_naf_column(
            ["siret", "activite_principale_naf25_etablissement"], NAF_TABLE_ETABLISSEMENT
        )
        assert resolution.nomenclature == NAF_NOMENCLATURE_2025

    def test_absent_column_is_reported_not_guessed(self):
        resolution = resolve_naf_column(["siret", "siren"], NAF_TABLE_ETABLISSEMENT)
        assert resolution.resolved is False
        assert resolution.nomenclature is None
        assert resolution.column is None

    @pytest.mark.parametrize(
        ("columns", "expected_fragment"),
        [
            (LEGACY_ETAB_COLUMNS, NAF_NOMENCLATURE_LEGACY),
            (NAF25_ETAB_COLUMNS, NAF_NOMENCLATURE_2025),
        ],
    )
    def test_label_names_the_nomenclature_for_the_schema_report(self, columns, expected_fragment):
        label = resolve_naf_column(columns, NAF_TABLE_ETABLISSEMENT).label
        assert expected_fragment in label

    def test_label_states_when_nothing_was_found(self):
        assert "aucune" in resolve_naf_column(["siret"], NAF_TABLE_ETABLISSEMENT).label


class TestCanonicalColumnStaysStableAcrossNomenclatures:
    def test_naf25_feeds_the_canonical_establishment_column(self):
        resolved = resolve_column_map(NAF25_ETAB_COLUMNS, ETABLISSEMENT_COLUMN_ALIASES)
        assert resolved["activitePrincipaleEtablissement"] == "activitePrincipaleNAF25Etablissement"

    def test_naf25_feeds_the_canonical_legal_unit_column(self):
        resolved = resolve_column_map(NAF25_UL_COLUMNS, UNITE_LEGALE_COLUMN_ALIASES)
        assert resolved["activitePrincipaleUniteLegale"] == "activitePrincipaleNAF25UniteLegale"

    def test_legacy_column_is_preferred_when_both_exist(self):
        resolved = resolve_column_map(
            ["siret", "activitePrincipaleEtablissement", "activitePrincipaleNAF25Etablissement"],
            ETABLISSEMENT_COLUMN_ALIASES,
        )
        assert resolved["activitePrincipaleEtablissement"] == "activitePrincipaleEtablissement"

    def test_other_columns_are_unaffected(self):
        resolved = resolve_column_map(LEGACY_ETAB_COLUMNS, ETABLISSEMENT_COLUMN_ALIASES)
        assert resolved["siret"] == "siret"
        assert resolved["siren"] == "siren"
