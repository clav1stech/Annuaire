"""Tests de la synchronisation environnement virtuel / requirements.txt.

Aucun test n'installe quoi que ce soit : l'appel à pip est simulé, seuls la détection de
désynchronisation et le marqueur d'installation sont vérifiés.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from src.dependencies import (
    ensure_dependencies,
    get_sync_state,
    install_requirements,
    read_stamp,
    requirements_fingerprint,
    write_stamp,
)

REQUIREMENTS_SAMPLE = "streamlit>=1.40,<2\nduckdb>=1.1,<2\n"


@pytest.fixture
def env(tmp_path: Path) -> tuple[Path, Path]:
    """Un requirements.txt et un emplacement de marqueur isolés du projet réel."""
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.write_text(REQUIREMENTS_SAMPLE, encoding="utf-8")
    return requirements_file, tmp_path / "venv" / ".requirements_fingerprint"


class FakePip:
    """Remplace subprocess.run : enregistre les appels et renvoie le code voulu."""

    def __init__(self, returncode: int = 0, stderr: str = ""):
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, self.returncode, stdout="", stderr=self.stderr)


class TestRequirementsFingerprint:
    @pytest.mark.parametrize(
        "variant",
        [
            "streamlit>=1.40,<2\n\nduckdb>=1.1,<2\n",  # ligne vide
            "duckdb>=1.1,<2\nstreamlit>=1.40,<2\n",  # ordre différent
            "# commentaire\nstreamlit>=1.40,<2\nduckdb>=1.1,<2  # pin\n",  # commentaires
            "streamlit>=1.40,<2   \n   duckdb>=1.1,<2\n",  # espaces
        ],
    )
    def test_cosmetic_changes_do_not_trigger_a_reinstall(self, variant):
        assert requirements_fingerprint(variant) == requirements_fingerprint(REQUIREMENTS_SAMPLE)

    def test_a_real_dependency_change_is_detected(self):
        changed = REQUIREMENTS_SAMPLE + "starlette>=0.46,<1.4\n"
        assert requirements_fingerprint(changed) != requirements_fingerprint(REQUIREMENTS_SAMPLE)


class TestSyncState:
    def test_missing_stamp_is_treated_as_out_of_sync(self, env):
        requirements_file, stamp_file = env
        assert get_sync_state(requirements_file, stamp_file).in_sync is False

    def test_matching_stamp_is_in_sync(self, env):
        requirements_file, stamp_file = env
        write_stamp(requirements_fingerprint(REQUIREMENTS_SAMPLE), stamp_file)
        assert get_sync_state(requirements_file, stamp_file).in_sync is True

    def test_changed_requirements_are_out_of_sync(self, env):
        requirements_file, stamp_file = env
        write_stamp(requirements_fingerprint(REQUIREMENTS_SAMPLE), stamp_file)
        requirements_file.write_text(REQUIREMENTS_SAMPLE + "pandas>=2.1,<3\n", encoding="utf-8")
        assert get_sync_state(requirements_file, stamp_file).in_sync is False

    def test_unreadable_requirements_do_not_block_the_launch(self, tmp_path):
        """Sans requirements.txt lisible, rien ne peut être conclu : ne pas forcer d'installation."""
        state = get_sync_state(tmp_path / "absent.txt", tmp_path / "stamp")
        assert state.in_sync is True


class TestInstallRequirements:
    def test_success_records_the_fingerprint(self, env, monkeypatch):
        requirements_file, stamp_file = env
        fake_pip = FakePip()
        monkeypatch.setattr(subprocess, "run", fake_pip)

        outcome = install_requirements("python", requirements_file, stamp_file)

        assert outcome.installed is True
        assert outcome.error is None
        assert read_stamp(stamp_file) == requirements_fingerprint(REQUIREMENTS_SAMPLE)

    def test_pyarrow_and_duckdb_are_installed_from_wheels_only(self, env, monkeypatch):
        """Une compilation depuis les sources échoue sur un poste sans chaîne de build."""
        requirements_file, stamp_file = env
        fake_pip = FakePip()
        monkeypatch.setattr(subprocess, "run", fake_pip)

        install_requirements("python", requirements_file, stamp_file)

        command = fake_pip.calls[0]
        assert "--only-binary=pyarrow" in command
        assert "--only-binary=duckdb" in command

    def test_failure_keeps_the_environment_marked_out_of_sync(self, env, monkeypatch):
        """L'échec doit être retenté au lancement suivant, pas masqué par un marqueur écrit trop tôt."""
        requirements_file, stamp_file = env
        monkeypatch.setattr(subprocess, "run", FakePip(returncode=1, stderr="No matching distribution"))

        outcome = install_requirements("python", requirements_file, stamp_file)

        assert outcome.installed is False
        assert outcome.usable is False
        assert "No matching distribution" in outcome.error
        assert outcome.hint is not None
        assert read_stamp(stamp_file) is None
        assert get_sync_state(requirements_file, stamp_file).in_sync is False

    def test_timeout_is_reported_instead_of_hanging(self, env, monkeypatch):
        requirements_file, stamp_file = env

        def timing_out(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 1)

        monkeypatch.setattr(subprocess, "run", timing_out)
        outcome = install_requirements("python", requirements_file, stamp_file)

        assert outcome.usable is False
        assert outcome.hint is not None


class TestEnsureDependencies:
    def test_nothing_is_installed_when_already_in_sync(self, env, monkeypatch):
        requirements_file, stamp_file = env
        write_stamp(requirements_fingerprint(REQUIREMENTS_SAMPLE), stamp_file)
        fake_pip = FakePip()
        monkeypatch.setattr(subprocess, "run", fake_pip)

        outcome = ensure_dependencies(
            requirements_file=requirements_file,
            stamp_file=stamp_file,
        )

        assert outcome.already_in_sync is True
        assert fake_pip.calls == []

    def test_desynchronisation_triggers_an_install(self, env, monkeypatch):
        requirements_file, stamp_file = env
        fake_pip = FakePip()
        monkeypatch.setattr(subprocess, "run", fake_pip)

        outcome = ensure_dependencies(
            python_executable="python",
            requirements_file=requirements_file,
            stamp_file=stamp_file,
        )

        assert outcome.installed is True
        assert len(fake_pip.calls) == 1

    def test_force_reinstalls_even_when_in_sync(self, env, monkeypatch):
        requirements_file, stamp_file = env
        write_stamp(requirements_fingerprint(REQUIREMENTS_SAMPLE), stamp_file)
        fake_pip = FakePip()
        monkeypatch.setattr(subprocess, "run", fake_pip)

        outcome = ensure_dependencies(
            force=True,
            python_executable="python",
            requirements_file=requirements_file,
            stamp_file=stamp_file,
        )

        assert outcome.installed is True
        assert len(fake_pip.calls) == 1


def test_starlette_gzip_signature_stays_compatible_with_streamlit():
    """Garde-fou contre la combinaison Streamlit/starlette qui casse le serveur au démarrage.

    Le middleware gzip de Streamlit construit `GZipResponder(app, minimum_size,
    compresslevel=...)`. starlette 1.4.0 a ajouté à cette signature un argument obligatoire
    (`thread_minimum_size`), ce qui fait échouer toutes les requêtes en erreur 500 sur un
    environnement fraîchement installé. Le test échoue ici, en CI, plutôt que chez
    l'utilisateur : `requirements.txt` doit alors être réajusté.
    """
    gzip_module = pytest.importorskip("starlette.middleware.gzip")
    signature = inspect.signature(gzip_module.GZipResponder.__init__)

    try:
        signature.bind(None, None, 500, compresslevel=9)
    except TypeError as exc:
        pytest.fail(
            "La version installée de starlette n'accepte plus l'appel fait par Streamlit "
            f"({exc}) : ajuster la contrainte starlette de requirements.txt / pyproject.toml."
        )
