"""Network-isolated tests for the Lantmäteriet download provider."""

import json
import sqlite3
import struct
import zipfile
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from magnetatlas.application.sync import SyncResult
from magnetatlas.domain.collectors import CollectorCapability, CollectorOutputModel
from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.infrastructure.sources.lantmateriet.client import LantmaterietClient
from magnetatlas.infrastructure.sources.lantmateriet.collector import (
    LANTMATERIET_SOURCE_DEFINITION,
    ORTNAMN_DATASET,
    LantmaterietCollector,
)
from magnetatlas.infrastructure.sources.lantmateriet.importer import (
    LantmaterietImporter,
)
from magnetatlas.infrastructure.sources.lantmateriet.mapper import (
    LANTMATERIET_LICENSE,
    map_ortnamn_record,
)
from magnetatlas.interfaces.web.layers import BUILT_IN_LAYERS


class FakeResponse:
    def __init__(self, payload: object = None, chunks: tuple[bytes, ...] = ()) -> None:
        self.payload = payload
        self.chunks = chunks

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self.payload

    def iter_content(self, chunk_size: int) -> tuple[bytes, ...]:
        del chunk_size
        return self.chunks


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = iter(responses)
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return next(self.responses)

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return next(self.responses)


def _stac_payload() -> dict[str, object]:
    return {
        "features": [
            {
                "id": "ortnamn-2026-08-01",
                "properties": {"datetime": "2026-08-01T00:00:00Z"},
                "assets": {
                    "data": {
                        "href": "https://download.lantmateriet.se/ortnamn.zip",
                        "type": "application/zip",
                    }
                },
            }
        ]
    }


def test_client_discovers_and_downloads_latest_stac_asset(tmp_path: Path) -> None:
    session = FakeSession(
        [FakeResponse(_stac_payload()), FakeResponse(chunks=(b"zip", b"data"))]
    )
    client = LantmaterietClient(session=session)  # type: ignore[arg-type]

    result = client.download_archive("ortnamn", tmp_path / "ortnamn.zip")

    assert result.path.read_bytes() == b"zipdata"
    assert result.item_id == "ortnamn-2026-08-01"
    assert session.calls[0][1].endswith("/collections/ortnamn/items")
    assert session.calls[0][2]["params"] == {"limit": 100, "sortby": "-datetime"}


def test_client_uses_oauth2_without_exposing_secret(tmp_path: Path) -> None:
    session = FakeSession(
        [
            FakeResponse({"access_token": "token-value", "expires_in": 3600}),
            FakeResponse(_stac_payload()),
            FakeResponse(chunks=(b"archive",)),
        ]
    )
    client = LantmaterietClient(
        client_id="client",
        client_secret="secret",
        token_url="https://auth.example/token",
        session=session,  # type: ignore[arg-type]
    )

    client.download_archive("ortnamn", tmp_path / "data.zip")

    assert session.calls[0][0] == "POST"
    assert session.calls[1][2]["headers"]["Authorization"] == "Bearer token-value"  # type: ignore[index]
    assert "secret" not in repr(client)


def test_client_rejects_insecure_asset_url() -> None:
    payload = _stac_payload()
    payload["features"][0]["assets"]["data"]["href"] = "http://example/data.zip"  # type: ignore[index]
    client = LantmaterietClient(  # type: ignore[arg-type]
        session=FakeSession([FakeResponse(payload)])
    )

    with pytest.raises(DataSourceError, match="osäker"):
        client.download_archive("ortnamn", Path("unused.zip"))


def _geometry(x: float, y: float) -> bytes:
    return b"GP\x00\x01" + struct.pack("<i", 3006) + struct.pack("<BIdd", 1, 1, x, y)


def _geopackage(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE gpkg_geometry_columns (
            table_name TEXT, column_name TEXT, geometry_type_name TEXT,
            srs_id INTEGER, z INTEGER, m INTEGER
        );
        CREATE TABLE ortnamn (
            fid INTEGER PRIMARY KEY, geom BLOB, lopnummer INTEGER,
            sprakkod TEXT, ortnamn TEXT, kommunnamn TEXT, lansnamn TEXT,
            detaljtyp TEXT
        );
        INSERT INTO gpkg_geometry_columns VALUES
            ('ortnamn', 'geom', 'POINT', 3006, 0, 0);
        """)
    connection.executemany(
        "INSERT INTO ortnamn VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                1,
                _geometry(674571.9, 6580743.0),
                10,
                "swe",
                "Vaxholm",
                "Vaxholm",
                "Stockholm",
                "Bebyggelse",
            ),
            (
                2,
                _geometry(500000.0, 6500000.0),
                11,
                "swe",
                "Testnamn",
                "Test",
                "Test",
                "Natur",
            ),
        ],
    )
    connection.commit()
    connection.close()


class FakeDownloadClient:
    def __init__(self, source: Path) -> None:
        self.source = source

    def download_archive(self, collection: str, destination: Path) -> Any:
        from magnetatlas.infrastructure.sources.lantmateriet.client import (
            DownloadedArchive,
        )

        assert collection == "ortnamn"
        destination.write_bytes(self.source.read_bytes())
        return DownloadedArchive(
            destination,
            "https://download.lantmateriet.se/ortnamn.zip",
            "snapshot-1",
            "2026-08-01T00:00:00Z",
        )


def test_collector_streams_downloaded_geopackage_in_batches(tmp_path: Path) -> None:
    gpkg = tmp_path / "source.gpkg"
    archive = tmp_path / "source.zip"
    _geopackage(gpkg)
    with zipfile.ZipFile(archive, "w") as package:
        package.write(gpkg, "ortnamn/ortnamn.gpkg")
    collector = LantmaterietCollector(
        FakeDownloadClient(archive), batch_size=1  # type: ignore[arg-type]
    )

    batches = list(collector.fetch_base_batches(tmp_path / "work.gpkg"))

    assert [len(batch) for batch in batches] == [1, 1]
    assert batches[0][0].provenance.source_id == "10:swe"
    assert not (tmp_path / "work.gpkg").exists()
    assert collector.descriptor.output_model is CollectorOutputModel.ATLAS_FEATURE
    assert collector.descriptor.supports(CollectorCapability.COUNTRY_SCOPE)
    assert collector.descriptor.supports(CollectorCapability.BBOX_SCOPE)


def test_collector_filters_bbox_after_coordinate_normalization(tmp_path: Path) -> None:
    gpkg = tmp_path / "source.gpkg"
    _geopackage(gpkg)
    collector = LantmaterietCollector(object())  # type: ignore[arg-type]

    batches = list(
        collector.collect_base_batches(
            gpkg,
            source_url="https://example/data.zip",
            dataset_version="snapshot",
            bbox=BoundingBox(18.0, 59.3, 18.6, 59.6),
        )
    )

    assert sum(map(len, batches)) == 1
    assert batches[0][0].title == "Vaxholm"


def test_mapper_preserves_identity_provenance_and_source_properties() -> None:
    feature = map_ortnamn_record(
        {
            "lopnummer": 42,
            "sprakkod": "swe",
            "ortnamn": "Stora testet",
            "detaljtyp": "Natur",
            "_x": 674571.9,
            "_y": 6580743.0,
        },
        source_url="https://example/ortnamn.zip",
        dataset_version="2026-08-01",
        fetched_at=datetime(2026, 8, 7, tzinfo=UTC),
    )

    assert feature.feature_id.value == "lantmateriet:ortnamn:42:swe"
    assert feature.provenance.source_id == "42:swe"
    assert feature.provenance.license_info == LANTMATERIET_LICENSE
    assert feature.properties["source_version"] == "2026-08-01"
    assert feature.properties["source_properties"]["lantmateriet-ortnamn"]


def test_importer_delegates_to_shared_sync_service() -> None:
    class Service:
        def base_import(self, **kwargs: object) -> SyncResult:
            assert kwargs["bbox"] == BoundingBox(18.0, 59.0, 19.0, 60.0)
            return SyncResult("base", 2, 0, "2026-08-01")

    result = LantmaterietImporter(Service()).run(  # type: ignore[arg-type]
        bbox=BoundingBox(18.0, 59.0, 19.0, 60.0)
    )

    assert result.imported == 2


def test_dataset_catalog_activates_only_ortnamn_download() -> None:
    document = json.loads(
        resources.files("magnetatlas.data")
        .joinpath("dataset_catalog.json")
        .read_text(encoding="utf-8")
    )
    source = next(item for item in document["sources"] if item["id"] == "lantmateriet")
    datasets = {item["id"]: item for item in source["datasets"]}

    assert source["status"] == "active"
    assert datasets["ortnamn"]["transport"] == "stac-vector-download"
    assert datasets["ortnamn"]["import_enabled"] is True
    assert datasets["historiska-kartor"]["import_enabled"] is False


def test_protected_layer_catalog_is_unchanged() -> None:
    historical = next(item for item in BUILT_IN_LAYERS if item.id == "historical-maps")

    assert len(BUILT_IN_LAYERS) == 13
    assert historical.supported_sources == frozenset()
    assert historical.enabled is False
    assert ORTNAMN_DATASET.source == LANTMATERIET_SOURCE_DEFINITION
