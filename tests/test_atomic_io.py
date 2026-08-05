"""Remplacement atomique : tolérance aux verrous transitoires, échec explicite sinon."""

from __future__ import annotations

import os

import pytest

from src.atomic_io import AtomicWriteError, replace_atomically, write_text_atomically
from src.config import ATOMIC_REPLACE_MAX_ATTEMPTS


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    """Neutraliser l'attente entre deux essais : les tests ne dorment jamais."""
    monkeypatch.setattr("src.atomic_io.time.sleep", lambda _seconds: None)


def _flaky_replace(failures: int, calls: dict[str, int]):
    """`os.replace` qui refuse l'accès `failures` fois avant de laisser passer."""
    real_replace = os.replace

    def fake_replace(src, dst):
        calls["count"] += 1
        if calls["count"] <= failures:
            raise PermissionError(5, "Accès refusé")
        real_replace(src, dst)

    return fake_replace


class TestReplaceAtomically:
    def test_replaces_on_first_attempt(self, tmp_path):
        target = tmp_path / "état.json"
        target.write_text("ancien", encoding="utf-8")
        temp = tmp_path / "état.json.tmp"
        temp.write_text("nouveau", encoding="utf-8")

        replace_atomically(temp, target)

        assert target.read_text(encoding="utf-8") == "nouveau"
        assert not temp.exists()

    def test_transient_lock_is_retried_then_succeeds(self, tmp_path, monkeypatch):
        target = tmp_path / "état.json"
        target.write_text("ancien", encoding="utf-8")
        temp = tmp_path / "état.json.tmp"
        temp.write_text("nouveau", encoding="utf-8")
        calls = {"count": 0}
        monkeypatch.setattr("src.atomic_io.os.replace", _flaky_replace(2, calls))

        replace_atomically(temp, target)

        assert calls["count"] == 3
        assert target.read_text(encoding="utf-8") == "nouveau"

    def test_permanent_lock_fails_without_touching_target(self, tmp_path, monkeypatch):
        target = tmp_path / "état.json"
        target.write_text("ancien", encoding="utf-8")
        temp = tmp_path / "état.json.tmp"
        temp.write_text("nouveau", encoding="utf-8")
        calls = {"count": 0}
        monkeypatch.setattr(
            "src.atomic_io.os.replace", _flaky_replace(ATOMIC_REPLACE_MAX_ATTEMPTS, calls)
        )

        with pytest.raises(AtomicWriteError, match="verrouillé"):
            replace_atomically(temp, target)

        assert calls["count"] == ATOMIC_REPLACE_MAX_ATTEMPTS
        assert target.read_text(encoding="utf-8") == "ancien"
        assert not temp.exists()


class TestWriteTextAtomically:
    def test_writes_utf8_and_leaves_no_temporary_file(self, tmp_path):
        target = tmp_path / "note.txt"

        write_text_atomically(target, "établissement créé à Nîmes")

        assert target.read_text(encoding="utf-8") == "établissement créé à Nîmes"
        assert list(tmp_path.glob("*.tmp")) == []
