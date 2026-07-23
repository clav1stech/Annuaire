"""Tests de la comparaison de versions locale / distante (aucun appel réseau)."""

from __future__ import annotations

import pytest

from src.version_check import VersionStatus, parse_version


def _status(local: str, remote: str | None, error: str | None = None) -> VersionStatus:
    return VersionStatus(local_version=local, remote_version=remote, error=error)


class TestParseVersion:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("1.1.0", (1, 1, 0)), (" 1.0.7 ", (1, 0, 7)), ("2.0", (2, 0))],
    )
    def test_valid_versions(self, text, expected):
        assert parse_version(text) == expected

    def test_unparsable_version_sorts_lowest(self):
        assert parse_version("pas-une-version") == (0,)


class TestVersionStatus:
    def test_remote_ahead_offers_an_update(self):
        status = _status("1.0.7", "1.1.0")
        assert status.update_available is True
        assert status.ahead_of_remote is False

    def test_identical_versions_are_up_to_date(self):
        status = _status("1.1.0", "1.1.0")
        assert status.update_available is False
        assert status.ahead_of_remote is False
        assert status.check_ok is True

    def test_local_ahead_is_a_dev_build(self):
        """Une branche non fusionnée ne doit pas se presenter comme la version publiee."""
        status = _status("1.1.0", "1.0.7")
        assert status.ahead_of_remote is True
        assert status.update_available is False

    @pytest.mark.parametrize(
        ("local", "remote"),
        [("1.1.0", "1.0.7"), ("1.0.8", "1.0.7"), ("2.0.0", "1.9.9"), ("1.1.0", "1.1")],
    )
    def test_dev_detection_across_components(self, local, remote):
        assert _status(local, remote).ahead_of_remote is True

    def test_the_two_states_are_mutually_exclusive(self):
        for local, remote in [("1.0.7", "1.1.0"), ("1.1.0", "1.0.7"), ("1.1.0", "1.1.0")]:
            status = _status(local, remote)
            assert not (status.update_available and status.ahead_of_remote)

    def test_failed_check_claims_neither_state(self):
        status = _status("1.1.0", None, error="GitHub injoignable.")
        assert status.check_ok is False
        assert status.update_available is False
        assert status.ahead_of_remote is False
