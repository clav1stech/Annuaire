"""Tests des garde-fous purs de la mise à jour : ce qui doit rester intact sur le disque."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.updater import UpdateOutcome, is_parquet_path, should_preserve


class TestShouldPreserve:
    @pytest.mark.parametrize(
        "relative_path",
        [
            ".venv_annuaire_sirene/Scripts/python.exe",
            "export/rapport.xlsx",
            ".git/config",
            "StockEtablissement_utf8.parquet",
            "data/StockUniteLegale_utf8.parquet",
        ],
    )
    def test_local_data_is_preserved(self, relative_path):
        assert should_preserve(Path(relative_path)) is True

    def test_only_the_file_name_is_inspected(self):
        """Un dossier parent nommé « parquet » ne protège pas son contenu non-Parquet.

        Sans effet en pratique : les fichiers SIRENE qu'il contient sont préservés un à un
        par leur propre nom, et un fichier de code n'a rien à faire là.
        """
        assert should_preserve(Path("sources_parquet/notes.txt")) is False

    @pytest.mark.parametrize(
        "relative_path",
        ["app.py", "src/pipeline.py", "requirements.txt", "docs/CODEMAP.md"],
    )
    def test_project_code_is_updated(self, relative_path):
        assert should_preserve(Path(relative_path)) is False


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a.parquet", True),
        ("a.PARQUET", True),  # extension insensible à la casse
        ("mes_parquet_sirene.zip", True),  # nom évocateur : préservé par précaution
        ("app.py", False),
    ],
)
def test_is_parquet_path(name, expected):
    assert is_parquet_path(Path(name)) is expected


def test_outcome_defaults_to_not_applied():
    """Un résultat vierge ne doit jamais laisser croire qu'une mise à jour a eu lieu."""
    outcome = UpdateOutcome()
    assert outcome.applied is False
    assert outcome.messages == []
    assert outcome.requirements_changed is False
