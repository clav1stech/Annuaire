"""Tests des fonctions pures de validation/normalisation SIRET/SIREN.

Ces fonctions portent la logique métier sensible (clé Luhn, routage
SIRET/SIREN, statut établissement). Elles servent de socle de non-régression :
tout refactor doit laisser ces assertions vertes (cf. docs/CONVENTIONS.md).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.config import (
    SIRET_STATUS_ACTIVE,
    SIRET_STATUS_CLOSED,
    SIRET_STATUS_FOUND_UNKNOWN,
)
from src.siret_utils import (
    build_address,
    build_siret_validation_frame,
    classify_etablissement_status,
    first_non_empty,
    is_luhn_valid,
    normalize_digits,
    normalize_identifier_for_lookup,
)

# Identifiants Luhn-valides utilisés comme fixtures (aucune donnée réelle requise).
VALID_SIRET = "73282932000074"
VALID_SIREN = "732829320"


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


class TestBuildAddress:
    def test_joins_available_components(self):
        row = pd.Series({"numeroVoie": "17", "typeVoie": "BD", "libelleVoie": "HAUSSMANN"})
        result = build_address(row, ["numeroVoie", "typeVoie", "libelleVoie"])
        assert result == "17 BD HAUSSMANN"

    def test_skips_missing_and_nan(self):
        row = pd.Series({"numeroVoie": "17", "libelleVoie": "nan"})
        result = build_address(row, ["numeroVoie", "typeVoie", "libelleVoie"])
        assert result == "17"
