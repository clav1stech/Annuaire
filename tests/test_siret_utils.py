"""Tests des fonctions pures de validation/normalisation SIRET/SIREN.

Ces fonctions portent la logique métier sensible (clé Luhn, routage
SIRET/SIREN, statut établissement). Elles servent de socle de non-régression :
tout refactor doit laisser ces assertions vertes (cf. docs/CONVENTIONS.md).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import (
    LA_POSTE_SIREN,
    SIRET_STATUS_ACTIVE,
    SIRET_STATUS_CLOSED,
    SIRET_STATUS_FOUND_UNKNOWN,
)
from src.siret_utils import (
    build_address,
    build_siret_validation_frame,
    classify_etablissement_status,
    compute_tva_intracom,
    first_non_empty,
    is_luhn_valid,
    is_sirene_key_valid,
    normalize_digits,
    normalize_identifier_for_lookup,
)

# Identifiants Luhn-valides utilisés comme fixtures (aucune donnée réelle requise).
VALID_SIRET = "73282932000074"
VALID_SIREN = "732829320"

# SIRET La Poste réels (StockEtablissement) : le premier ne vaut que par la règle du
# multiple de 5, le second (établissement ancien) que par la clé de Luhn.
LA_POSTE_SIRET_DIGIT_SUM = "35600000000051"
LA_POSTE_SIRET_LUHN_ONLY = "35600000000048"


class TestNormalizeDigits:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, ""),
            ("", ""),
            ("732 829 320", "732829320"),
            ("732-829-320", "732829320"),
            ("SIRET: 73282932000074 ", "73282932000074"),
            (732829320, "732829320"),
        ],
    )
    def test_keeps_only_digits(self, value, expected):
        assert normalize_digits(value) == expected


class TestNormalizeIdentifierForLookup:
    def test_empty_when_no_digit(self):
        assert normalize_identifier_for_lookup("abc") == ""

    def test_truncates_beyond_max_digits(self):
        assert normalize_identifier_for_lookup(VALID_SIRET + "999") == VALID_SIRET

    def test_short_identifier_kept_as_is(self):
        assert normalize_identifier_for_lookup(VALID_SIREN) == VALID_SIREN


class TestLuhn:
    @pytest.mark.parametrize("value", [VALID_SIRET, VALID_SIREN, "55204944776279", "552049447"])
    def test_valid(self, value):
        assert is_luhn_valid(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "73282932000075",  # dernier chiffre altéré
            "732829321",  # SIREN invalide
            "00000000000000",  # placeholder tout à zéro rejeté
            "0",
            "12abc",  # non numérique
            "",
        ],
    )
    def test_invalid(self, value):
        assert is_luhn_valid(value) is False


class TestLaPosteKey:
    """Exception SIRENE documentée : règle de clé propre aux SIRET de La Poste."""

    def test_siren_needs_no_exception(self):
        # Le SIREN de La Poste satisfait Luhn : seule la clé de ses SIRET est spécifique.
        assert is_luhn_valid(LA_POSTE_SIREN) is True
        assert is_sirene_key_valid(LA_POSTE_SIREN) is True

    def test_siret_valid_by_digit_sum_multiple_of_five(self):
        assert is_luhn_valid(LA_POSTE_SIRET_DIGIT_SUM) is False
        assert sum(int(char) for char in LA_POSTE_SIRET_DIGIT_SUM) % 5 == 0
        assert is_sirene_key_valid(LA_POSTE_SIRET_DIGIT_SUM) is True

    def test_old_siret_valid_by_luhn_only(self):
        # Les établissements La Poste antérieurs à la règle du multiple de 5 restent
        # Luhn-valides : les deux contrôles sont alternatifs, pas exclusifs.
        assert sum(int(char) for char in LA_POSTE_SIRET_LUHN_ONLY) % 5 != 0
        assert is_sirene_key_valid(LA_POSTE_SIRET_LUHN_ONLY) is True

    @pytest.mark.parametrize(
        "value",
        [
            "35600000000052",  # ni Luhn, ni somme multiple de 5
            "35600000",  # préfixe tronqué, longueur hors SIREN/SIRET
            "356000000123",  # longueur intermédiaire non exploitable
            "73282932000004",  # somme multiple de 5 mais SIREN autre que La Poste
        ],
    )
    def test_rule_stays_confined_to_la_poste(self, value):
        assert is_sirene_key_valid(value) is False

    def test_route_accepts_la_poste_siren_and_siret(self):
        frame = build_siret_validation_frame(pd.Series([LA_POSTE_SIREN, LA_POSTE_SIRET_DIGIT_SUM]))
        siren_row, siret_row = frame.iloc[0], frame.iloc[1]
        assert siren_row["siret_input_type"] == "SIREN"
        assert siren_row["siret_validation_route"] == "SIREN_DIRECT"
        assert bool(siren_row["siret_format_ok"]) is True
        assert siret_row["siret_input_type"] == "SIRET"
        assert siret_row["siret_validation_route"] == "SIRET_OK"
        assert siret_row["siret_lookup_key"] == LA_POSTE_SIRET_DIGIT_SUM


class TestResolveLookupRoute:
    """Le routage est testé via build_siret_validation_frame (API publique)."""

    def _row(self, raw: str) -> pd.Series:
        frame = build_siret_validation_frame(pd.Series([raw]))
        return frame.iloc[0]

    def test_siret_route(self):
        row = self._row(VALID_SIRET)
        assert row["siret_input_type"] == "SIRET"
        assert row["siret_validation_route"] == "SIRET_OK"
        assert row["siret_lookup_key"] == VALID_SIRET
        assert bool(row["siret_format_ok"]) is True

    def test_siren_direct_route(self):
        row = self._row(VALID_SIREN)
        assert row["siret_input_type"] == "SIREN"
        assert row["siret_validation_route"] == "SIREN_DIRECT"
        assert row["siret_lookup_key"] == VALID_SIREN

    def test_siren_fallback_from_invalid_siret(self):
        # 14 chiffres dont le SIRET échoue au Luhn mais dont les 9 premiers forment un SIREN valide.
        raw = VALID_SIREN + "00099"  # 14 chiffres, SIRET invalide
        row = self._row(raw)
        assert row["siret_input_type"] == "SIREN"
        assert row["siret_validation_route"] == "SIREN_FALLBACK_FROM_SIRET"
        assert row["siret_lookup_key"] == VALID_SIREN

    def test_invalid_identifier(self):
        row = self._row("123")
        assert row["siret_input_type"] == ""
        assert row["siret_validation_route"] == "INVALID"
        assert bool(row["siret_format_ok"]) is False


class TestClassifyStatus:
    @pytest.mark.parametrize(
        ("etat", "expected"),
        [
            ("A", SIRET_STATUS_ACTIVE),
            ("a", SIRET_STATUS_ACTIVE),
            (" A ", SIRET_STATUS_ACTIVE),
            ("F", SIRET_STATUS_CLOSED),
            ("", SIRET_STATUS_FOUND_UNKNOWN),
            (None, SIRET_STATUS_FOUND_UNKNOWN),
            ("X", SIRET_STATUS_FOUND_UNKNOWN),
        ],
    )
    def test_mapping(self, etat, expected):
        assert classify_etablissement_status(etat) == expected


class TestFirstNonEmpty:
    def test_returns_first_meaningful(self):
        assert first_non_empty([None, "", "  ", "nan", "Danone", "x"]) == "Danone"

    def test_all_empty(self):
        assert first_non_empty([None, "", "NaN"]) == ""


class TestComputeTvaIntracom:
    def test_known_siren(self):
        # Formule officielle : cle = (12 + 3 * (SIREN mod 97)) mod 97.
        assert compute_tva_intracom(VALID_SIREN) == "FR44732829320"

    def test_strips_non_digits_before_computing(self):
        assert compute_tva_intracom("732 829 320") == "FR44732829320"

    @pytest.mark.parametrize("value", ["", None, "123", "12345678901"])
    def test_invalid_length_returns_empty(self, value):
        assert compute_tva_intracom(value) == ""


class TestBuildAddress:
    def test_joins_available_components(self):
        row = pd.Series({"numeroVoie": "17", "typeVoie": "BD", "libelleVoie": "HAUSSMANN"})
        result = build_address(row, ["numeroVoie", "typeVoie", "libelleVoie"])
        assert result == "17 BD HAUSSMANN"

    def test_skips_missing_and_nan(self):
        row = pd.Series({"numeroVoie": "17", "libelleVoie": "nan"})
        result = build_address(row, ["numeroVoie", "typeVoie", "libelleVoie"])
        assert result == "17"
