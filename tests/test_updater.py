"""Tests des garde-fous purs de la mise à jour : ce qui doit rester intact sur le disque."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

import pytest

from src import updater
from src.updater import UpdateOutcome, apply_update_from_zip, is_parquet_path, should_preserve


def _github_zip(version: str = "1.0.1", extra_files: dict[str, bytes] | None = None) -> bytes:
    files = {
        "VERSION": version.encode("utf-8"),
        "app.py": b"APP_MARKER = 'new app'\n",
        "src/__init__.py": b"PACKAGE_MARKER = 'new package'\n",
        "requirements.txt": b"streamlit\n",
    }
    files.update(extra_files or {})
    payload = BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for relative_path, content in files.items():
            archive.writestr(f"Annuaire-main/{relative_path}", content)
    return payload.getvalue()


@pytest.fixture
def update_project_root(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "export").mkdir()
    (tmp_path / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("APP_MARKER = 'old app'\n", encoding="utf-8")
    (tmp_path / "src" / "__init__.py").write_text(
        "PACKAGE_MARKER = 'old package'\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("streamlit\n", encoding="utf-8")
    monkeypatch.setattr(updater, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("src.version_check.PROJECT_ROOT", tmp_path)
    return tmp_path


class TestShouldPreserve:
    @pytest.mark.parametrize(
        "relative_path",
        [
            ".sirene_manifest.json",
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


class TestManualZipUpdate:
    def test_newer_github_zip_updates_only_changed_code(self, update_project_root):
        root = update_project_root
        parquet = root / "StockEtablissement_utf8.parquet"
        parquet.write_bytes(b"local sirene")
        report = root / "export" / "rapport.xlsx"
        report.write_bytes(b"local report")
        local_note = root / "notes-locales.txt"
        local_note.write_text("à conserver", encoding="utf-8")

        outcome = apply_update_from_zip(
            _github_zip(
                extra_files={
                    "StockEtablissement_utf8.parquet": b"archive sirene",
                    "export/rapport.xlsx": b"archive report",
                }
            )
        )

        assert outcome.applied is True
        assert outcome.requirements_changed is False
        assert (root / "VERSION").read_text(encoding="utf-8") == "1.0.1"
        assert (root / "app.py").read_text(encoding="utf-8") == "APP_MARKER = 'new app'\n"
        assert parquet.read_bytes() == b"local sirene"
        assert report.read_bytes() == b"local report"
        assert local_note.read_text(encoding="utf-8") == "à conserver"

    def test_requirements_change_is_reported(self, update_project_root):
        outcome = apply_update_from_zip(
            _github_zip(extra_files={"requirements.txt": b"streamlit\nnew-package\n"})
        )

        assert outcome.applied is True
        assert outcome.requirements_changed is True

    @pytest.mark.parametrize("version", ["1.0.0", "0.9.9"])
    def test_same_or_older_archive_is_rejected_before_copy(self, update_project_root, version):
        outcome = apply_update_from_zip(_github_zip(version=version))

        assert outcome.applied is False
        assert "n'est pas plus récente" in str(outcome.error)
        assert (update_project_root / "app.py").read_text(encoding="utf-8") == (
            "APP_MARKER = 'old app'\n"
        )

    def test_unrelated_zip_is_rejected(self, update_project_root):
        payload = BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("autre-projet/README.md", "pas Annuaire")

        outcome = apply_update_from_zip(payload.getvalue())

        assert outcome.applied is False
        assert "ne semble pas être celui du projet Annuaire" in str(outcome.error)
        assert (update_project_root / "app.py").read_text(encoding="utf-8") == (
            "APP_MARKER = 'old app'\n"
        )

    def test_path_traversal_is_rejected_before_copy(self, update_project_root):
        archive_data = _github_zip(extra_files={"../hors-projet.txt": b"danger"})

        outcome = apply_update_from_zip(archive_data)

        assert outcome.applied is False
        assert "sort du dossier" in str(outcome.error)
        assert not (update_project_root.parent / "hors-projet.txt").exists()
