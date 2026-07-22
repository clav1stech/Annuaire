"""Tests des helpers purs de configuration (nommage des sorties, version)."""

from __future__ import annotations

import pytest

from src import config
from src.config import __version__, _safe_output_stem


class TestSafeOutputStem:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("fournisseurs.xlsx", "fournisseurs"),
            ("liste tiers 2026.csv", "liste_tiers_2026"),
            ('bad<>:"|?*name.xlsx', "bad_name"),  # caractères interdits Windows -> _
            ("rapport final.parquet", "rapport_final"),
            (None, config.APP_NAME),
            ("", config.APP_NAME),
            ("   ", config.APP_NAME),  # que des espaces -> repli sur APP_NAME
        ],
    )
    def test_stem(self, value, expected):
        assert _safe_output_stem(value) == expected


def test_version_matches_version_file():
    """__version__ doit refléter le fichier VERSION (source de vérité unique)."""
    version_path = config.Path(__file__).resolve().parent.parent / "VERSION"
    assert __version__ == version_path.read_text(encoding="utf-8").strip()
