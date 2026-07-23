"""Tests du manifeste local et de la comparaison avec les métadonnées data.gouv.fr.

Aucun appel réseau réel : la couche HTTP est simulée au niveau de ``urlopen``.
"""

from __future__ import annotations

import json
from io import BytesIO

import pytest

from src.config import (
    DATA_STATUS_ABSENT,
    DATA_STATUS_OUTDATED,
    DATA_STATUS_UP_TO_DATE,
    SIRENE_MANIFEST_FILENAME,
)
from src.data_manifest import (
    ManifestEntry,
    build_freshness_status,
    download_category,
    format_publication_date,
    format_size_mo,
    get_data_freshness_status,
    load_manifest,
    record_download,
    save_manifest,
)
from src.datagouv_client import (
    DataGouvError,
    RemoteResource,
    classify_resource_title,
    fetch_remote_resources,
    select_parquet_resources,
)
from src.download_utils import DownloadError, download_with_progress

CATEGORIES = (
    "stocketablissement",
    "stockunitelegale",
    "stocketablissementlienssuccession",
    "stocketablissementhistorique",
)


def _raw_resource(title: str, fmt: str = "parquet", **overrides):
    payload = {
        "title": title,
        "format": fmt,
        "filesize": 1_048_576,
        "last_modified": "2026-07-01T09:30:45.065000+00:00",
        "url": "https://static.data.gouv.fr/resources/direct-file.parquet",
        "latest": "https://www.data.gouv.fr/api/1/datasets/r/" + title.lower().replace(" ", "-"),
        "checksum": {"type": "sha1", "value": "abc123"},
    }
    payload.update(overrides)
    return payload


def _dataset_payload():
    return {
        "title": "Base Sirene",
        "resources": [
            _raw_resource("Sirene : Fichier StockEtablissement - 01 juillet 2026 (format parquet)"),
            _raw_resource("Sirene : Fichier StockUniteLegale - 01 juillet 2026 (format parquet)"),
            _raw_resource(
                "Sirene : Fichier StockEtablissementLiensSuccession - 01 juillet 2026 "
                "(format parquet)"
            ),
            _raw_resource(
                "Sirene : Fichier StockEtablissementHistorique - 01 juillet 2026 (format parquet)"
            ),
            _raw_resource("Sirene : Fichier StockUniteLegaleHistorique - 01 juillet 2026 (format parquet)"),
            _raw_resource("Sirene : Fichier StockDoublons - 01 juillet 2026 (format parquet)"),
            _raw_resource("Sirene : Fichier StockEtablissement - 01 juillet 2026", fmt="zip"),
        ],
    }


def _remote(category: str, checksum: str = "abc123", last_modified: str = "2026-07-01T09:30:45+00:00"):
    return RemoteResource(
        category=category,
        title=category,
        url=f"https://www.data.gouv.fr/api/1/datasets/r/{category}",
        checksum=checksum,
        checksum_type="sha1",
        filesize=1_048_576,
        last_modified=last_modified,
        format="parquet",
    )


@pytest.fixture
def fake_urlopen(monkeypatch):
    """Remplace urlopen dans le client data.gouv.fr par une réponse JSON figée."""

    def install(payload, *, error=None):
        calls = {"count": 0}

        def _urlopen(request, timeout=None):
            calls["count"] += 1
            if error is not None:
                raise error
            return BytesIO(json.dumps(payload).encode("utf-8"))

        monkeypatch.setattr("src.datagouv_client.urllib.request.urlopen", _urlopen)
        return calls

    return install


class TestResourceClassification:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("Sirene : Fichier StockEtablissement - 01 juillet 2026 (format parquet)", "stocketablissement"),
            (
                "Sirene : Fichier StockEtablissementHistorique - 01 juillet 2026 (format parquet)",
                "stocketablissementhistorique",
            ),
            (
                "Sirene : Fichier StockEtablissementLiensSuccession - 01 juillet 2026 (format parquet)",
                "stocketablissementlienssuccession",
            ),
            ("Sirene : Fichier StockUniteLegale - 01 juillet 2026 (format parquet)", "stockunitelegale"),
            (
                "Sirene : Fichier StockUniteLegaleHistorique - 01 juillet 2026 (format parquet)",
                "stockunitelegalehistorique",
            ),
            ("Description-fichier-stocketablissement-311.pdf", "stocketablissement"),
            ("Un titre sans rapport", None),
        ],
    )
    def test_specific_titles_win_over_prefixes(self, title, expected):
        """Les libellés courts sont des préfixes des longs : l'ordre de test doit les départager."""
        assert classify_resource_title(title) == expected


class TestSelectParquetResources:
    def test_only_parquet_resources_of_wanted_categories_are_kept(self):
        selected = select_parquet_resources(_dataset_payload()["resources"], CATEGORIES)
        assert set(selected) == set(CATEGORIES)
        assert all(resource.format == "parquet" for resource in selected.values())

    def test_stable_link_is_used_never_the_direct_url(self):
        selected = select_parquet_resources(_dataset_payload()["resources"], CATEGORIES)
        for resource in selected.values():
            assert resource.url.startswith("https://www.data.gouv.fr/api/1/datasets/r/")

    def test_metadata_is_exposed(self):
        selected = select_parquet_resources(_dataset_payload()["resources"], CATEGORIES)
        resource = selected["stocketablissement"]
        assert resource.checksum == "abc123"
        assert resource.filesize == 1_048_576
        assert resource.last_modified == "2026-07-01T09:30:45.065000+00:00"
        assert resource.filesize_mo == pytest.approx(1.0)

    def test_most_recent_publication_wins_for_a_category(self):
        resources = [
            _raw_resource(
                "Sirene : Fichier StockEtablissement - 01 juin 2026 (format parquet)",
                last_modified="2026-06-01T00:00:00+00:00",
                latest="https://www.data.gouv.fr/api/1/datasets/r/old",
            ),
            _raw_resource(
                "Sirene : Fichier StockEtablissement - 01 juillet 2026 (format parquet)",
                last_modified="2026-07-01T00:00:00+00:00",
                latest="https://www.data.gouv.fr/api/1/datasets/r/new",
            ),
        ]
        selected = select_parquet_resources(resources, ("stocketablissement",))
        assert selected["stocketablissement"].url.endswith("/new")

    def test_missing_category_fails_explicitly(self):
        resources = [_raw_resource("Sirene : Fichier StockUniteLegale (format parquet)")]
        with pytest.raises(DataGouvError, match="stocketablissement"):
            select_parquet_resources(resources, CATEGORIES)

    def test_resource_without_stable_link_is_rejected(self):
        """Sans lien permanent, aucun repli sur l'URL statique horodatée."""
        resources = [
            _raw_resource("Sirene : Fichier StockEtablissement (format parquet)", latest=None)
        ]
        with pytest.raises(DataGouvError):
            select_parquet_resources(resources, ("stocketablissement",))


class TestFetchRemoteResources:
    def test_returns_one_resource_per_category(self, fake_urlopen):
        fake_urlopen(_dataset_payload())
        resources = fetch_remote_resources(CATEGORIES)
        assert set(resources) == set(CATEGORIES)

    def test_network_failure_is_retried_then_raised(self, fake_urlopen):
        calls = fake_urlopen(None, error=TimeoutError("délai dépassé"))
        with pytest.raises(DataGouvError, match="injoignable"):
            fetch_remote_resources(CATEGORIES)
        assert calls["count"] == 2

    def test_payload_without_resources_fails_explicitly(self, fake_urlopen):
        fake_urlopen({"title": "Base Sirene"})
        with pytest.raises(DataGouvError):
            fetch_remote_resources(CATEGORIES)


class TestManifestPersistence:
    def test_missing_manifest_reads_as_empty(self, tmp_path):
        assert load_manifest(tmp_path) == {}

    def test_corrupt_manifest_reads_as_empty(self, tmp_path):
        (tmp_path / SIRENE_MANIFEST_FILENAME).write_text("{ pas du json", encoding="utf-8")
        assert load_manifest(tmp_path) == {}

    def test_round_trip(self, tmp_path):
        entry = ManifestEntry(
            category="stocketablissement",
            checksum="abc123",
            filesize=42,
            last_modified="2026-07-01T00:00:00+00:00",
            local_path=str(tmp_path / "StockEtablissement_utf8.parquet"),
            downloaded_at="2026-07-02T10:00:00+00:00",
        )
        save_manifest({"stocketablissement": entry}, tmp_path)
        assert load_manifest(tmp_path)["stocketablissement"] == entry

    def test_save_leaves_no_temporary_file(self, tmp_path):
        save_manifest({}, tmp_path)
        assert list(tmp_path.glob("*.tmp")) == []

    def test_record_download_preserves_other_categories(self, tmp_path):
        local_file = tmp_path / "StockEtablissement_utf8.parquet"
        local_file.write_bytes(b"")
        save_manifest(
            {
                "stockunitelegale": ManifestEntry(
                    category="stockunitelegale",
                    checksum="deadbeef",
                    filesize=1,
                    last_modified="2026-01-01T00:00:00+00:00",
                    local_path="ul.parquet",
                    downloaded_at="2026-01-01T00:00:00+00:00",
                )
            },
            tmp_path,
        )
        record_download(_remote("stocketablissement"), local_file, tmp_path)
        entries = load_manifest(tmp_path)
        assert set(entries) == {"stocketablissement", "stockunitelegale"}
        assert entries["stocketablissement"].checksum == "abc123"
        assert entries["stocketablissement"].downloaded_at


class TestFreshnessComparison:
    def _entry(self, tmp_path, category, checksum="abc123", last_modified="2026-07-01T09:30:45+00:00"):
        local_file = tmp_path / f"{category}.parquet"
        local_file.write_bytes(b"")
        return ManifestEntry(
            category=category,
            checksum=checksum,
            filesize=1_048_576,
            last_modified=last_modified,
            local_path=str(local_file),
            downloaded_at="2026-07-02T10:00:00+00:00",
        )

    def test_absent_when_nothing_local(self):
        status = build_freshness_status(
            {"stocketablissement": _remote("stocketablissement")},
            {},
            categories=("stocketablissement",),
        )
        verdict = status.categories[0]
        assert verdict.status == DATA_STATUS_ABSENT
        assert verdict.needs_download is True
        assert verdict.remote_size_mo == pytest.approx(1.0)

    def test_up_to_date_when_checksums_match(self, tmp_path):
        status = build_freshness_status(
            {"stocketablissement": _remote("stocketablissement")},
            {"stocketablissement": self._entry(tmp_path, "stocketablissement")},
            categories=("stocketablissement",),
        )
        assert status.categories[0].status == DATA_STATUS_UP_TO_DATE
        assert status.up_to_date is True
        assert status.total_download_mo == 0

    def test_outdated_when_checksums_differ(self, tmp_path):
        status = build_freshness_status(
            {"stocketablissement": _remote("stocketablissement", checksum="newchecksum")},
            {"stocketablissement": self._entry(tmp_path, "stocketablissement")},
            categories=("stocketablissement",),
        )
        assert status.categories[0].status == DATA_STATUS_OUTDATED
        assert status.total_download_mo == pytest.approx(1.0)

    def test_falls_back_on_publication_date_without_checksum(self, tmp_path):
        entry = self._entry(tmp_path, "stocketablissement", checksum=None)
        same = build_freshness_status(
            {"stocketablissement": _remote("stocketablissement", checksum=None)},
            {"stocketablissement": entry},
            categories=("stocketablissement",),
        )
        newer = build_freshness_status(
            {
                "stocketablissement": _remote(
                    "stocketablissement", checksum=None, last_modified="2026-08-01T00:00:00+00:00"
                )
            },
            {"stocketablissement": entry},
            categories=("stocketablissement",),
        )
        assert same.categories[0].status == DATA_STATUS_UP_TO_DATE
        assert newer.categories[0].status == DATA_STATUS_OUTDATED

    def test_manifest_entry_pointing_to_a_deleted_file_is_absent(self, tmp_path):
        entry = ManifestEntry(
            category="stocketablissement",
            checksum="abc123",
            filesize=1,
            last_modified="2026-07-01T09:30:45+00:00",
            local_path=str(tmp_path / "disparu.parquet"),
            downloaded_at="2026-07-02T10:00:00+00:00",
        )
        status = build_freshness_status(
            {"stocketablissement": _remote("stocketablissement")},
            {"stocketablissement": entry},
            categories=("stocketablissement",),
        )
        assert status.categories[0].status == DATA_STATUS_ABSENT

    def test_manually_installed_file_is_outdated_not_absent(self):
        """Un fichier déposé à la main existe : sa version est inconnue, pas le fichier."""
        status = build_freshness_status(
            {"stocketablissement": _remote("stocketablissement")},
            {},
            existing_local_paths={"stocketablissement": "StockEtablissement_utf8.parquet"},
            categories=("stocketablissement",),
        )
        verdict = status.categories[0]
        assert verdict.status == DATA_STATUS_OUTDATED
        assert verdict.local_path == "StockEtablissement_utf8.parquet"

    def test_latest_publication_is_the_most_recent(self):
        status = build_freshness_status(
            {
                "stocketablissement": _remote(
                    "stocketablissement", last_modified="2026-07-01T00:00:00+00:00"
                ),
                "stockunitelegale": _remote(
                    "stockunitelegale", last_modified="2026-06-01T00:00:00+00:00"
                ),
            },
            {},
            categories=("stocketablissement", "stockunitelegale"),
        )
        assert status.latest_publication == "2026-07-01T00:00:00+00:00"


class TestGetDataFreshnessStatus:
    def test_network_error_is_reported_not_raised(self, fake_urlopen, tmp_path):
        fake_urlopen(None, error=TimeoutError("délai dépassé"))
        status = get_data_freshness_status(root=tmp_path)
        assert status.check_ok is False
        assert status.up_to_date is False
        assert "injoignable" in str(status.error)

    def test_all_categories_absent_on_a_fresh_install(self, fake_urlopen, tmp_path):
        fake_urlopen(_dataset_payload())
        status = get_data_freshness_status(root=tmp_path)
        assert status.check_ok is True
        assert {item.status for item in status.categories} == {DATA_STATUS_ABSENT}
        assert len(status.stale) == len(CATEGORIES)


class _FakeResponse(BytesIO):
    """Réponse HTTP minimale : un corps binaire et un Content-Length."""

    def __init__(self, payload: bytes, declared_length: int | None = None):
        super().__init__(payload)
        length = len(payload) if declared_length is None else declared_length
        self.headers = {"Content-Length": str(length)}


class TestDownloadWithProgress:
    @pytest.fixture
    def fake_download(self, monkeypatch):
        def install(payload: bytes, declared_length: int | None = None):
            monkeypatch.setattr(
                "src.download_utils.urllib.request.urlopen",
                lambda request, timeout=None: _FakeResponse(payload, declared_length),
            )

        return install

    def test_file_is_written_and_progress_reported(self, fake_download, tmp_path):
        fake_download(b"x" * 2048)
        seen: list[tuple[int, float, float | None]] = []
        target = tmp_path / "StockEtablissement_utf8.parquet"

        result = download_with_progress(
            "https://example.invalid/f.parquet",
            target,
            expected_size=2048,
            progress_callback=lambda *args: seen.append(args),
            chunk_size=512,
        )

        assert result == target
        assert target.stat().st_size == 2048
        assert seen[-1][0] == 100

    def test_truncated_transfer_leaves_no_file(self, fake_download, tmp_path):
        """Un transfert incomplet ne doit jamais remplacer le Parquet en place."""
        fake_download(b"x" * 100, declared_length=999_999)
        target = tmp_path / "StockEtablissement_utf8.parquet"
        target.write_bytes(b"version precedente")

        with pytest.raises(DownloadError, match="incomplet"):
            download_with_progress("https://example.invalid/f.parquet", target, chunk_size=512)

        assert target.read_bytes() == b"version precedente"
        assert list(tmp_path.glob("*.part")) == []

    def test_manifest_is_not_written_when_download_fails(self, fake_download, tmp_path):
        fake_download(b"", declared_length=10)
        with pytest.raises(DownloadError):
            download_category(_remote("stocketablissement"), root=tmp_path)
        assert load_manifest(tmp_path) == {}

    def test_manifest_records_the_downloaded_version(self, fake_download, tmp_path):
        fake_download(b"x" * 1024)
        target = download_category(_remote("stocketablissement"), root=tmp_path)

        entry = load_manifest(tmp_path)["stocketablissement"]
        assert target.exists()
        assert entry.local_path == str(target)
        assert entry.checksum == "abc123"


class TestDisplayFormatting:
    @pytest.mark.parametrize(
        ("size_mo", "expected"),
        [(None, "taille inconnue"), (700.4, "700 Mo"), (2048.0, "2.0 Go")],
    )
    def test_format_size_mo(self, size_mo, expected):
        assert format_size_mo(size_mo) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (None, "date inconnue"),
            ("2026-07-01T09:30:45+00:00", "01/07/2026"),
            ("pas une date", "pas une date"),
        ],
    )
    def test_format_publication_date(self, raw, expected):
        assert format_publication_date(raw) == expected
