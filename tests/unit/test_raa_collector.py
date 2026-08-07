"""Tests for the persistence-free RAÄ Collector."""

from __future__ import annotations

import sqlite3
import struct
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.domain.geography import BoundingBox, GeoPoint
from magnetatlas.infrastructure.sources.raa.collector import RAACollector


def point_blob(x: float, y: float) -> bytes:
    header = b"GP" + bytes((0, 1)) + struct.pack("<i", 3006)
    return header + struct.pack("<BIdd", 1, 1, x, y)


def make_geopackage(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE gpkg_geometry_columns (
            table_name TEXT, column_name TEXT, geometry_type_name TEXT,
            srs_id INTEGER, z INTEGER, m INTEGER
        );
        CREATE TABLE lamningar_point (
            lamning_uuid TEXT, lamningsnummer TEXT, lamningstyp TEXT,
            beskrivning TEXT, geom BLOB
        );
        INSERT INTO gpkg_geometry_columns VALUES
            ('lamningar_point', 'geom', 'POINT', 3006, 0, 0);
        """)
    connection.execute(
        "INSERT INTO lamningar_point VALUES (?, ?, ?, ?, ?)",
        (
            "uuid-1",
            "L2026:1",
            "Röse",
            "Verifierad beskrivning",
            point_blob(674571.866, 6580743.008),
        ),
    )
    connection.commit()
    connection.close()


class FakeClient:
    def fetch_changes(self, start: date, end: date) -> list[dict[str, Any]]:
        assert start == date(2026, 8, 1)
        assert end == date(2026, 8, 2)
        return [
            {
                "id": "uuid-2",
                "lamningsnummer": "L2026:2",
                "lamningstyp": {"namn": "Fyndplats"},
                "geometri": {
                    "type": "Point",
                    "coordinates": [674571.866, 6580743.008],
                },
            }
        ]


def test_collector_reads_official_geopackage_without_database_writes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "raa.gpkg"
    make_geopackage(path)
    collector = RAACollector(FakeClient())  # type: ignore[arg-type]

    features = collector.collect_base(path)

    assert len(features) == 1
    assert features[0].title == "L2026:1"
    assert features[0].description == "Verifierad beskrivning"
    assert isinstance(features[0].geometry, GeoPoint)


def test_collector_applies_bbox_after_wgs84_conversion(tmp_path: Path) -> None:
    path = tmp_path / "raa.gpkg"
    make_geopackage(path)
    collector = RAACollector(FakeClient())  # type: ignore[arg-type]

    assert collector.collect_base(path, bbox=BoundingBox(18.0, 59.0, 18.2, 59.5))
    assert not collector.collect_base(path, bbox=BoundingBox(10.0, 55.0, 11.0, 56.0))


def test_collector_streams_bounded_batches(tmp_path: Path) -> None:
    path = tmp_path / "stream.gpkg"
    make_geopackage(path)
    connection = sqlite3.connect(path)
    for number in range(2, 6):
        connection.execute(
            "INSERT INTO lamningar_point VALUES (?, ?, ?, ?, ?)",
            (
                f"uuid-{number}",
                f"L2026:{number}",
                "Röse",
                f"Beskrivning {number}",
                point_blob(674571.866 + number, 6580743.008),
            ),
        )
    connection.commit()
    connection.close()
    collector = RAACollector(FakeClient())  # type: ignore[arg-type]

    batches = collector.collect_base_batches(path, batch_size=2)

    assert [len(batch) for batch in batches] == [2, 2, 1]


def test_collector_does_not_start_reading_until_iterator_is_consumed(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.gpkg"
    collector = RAACollector(FakeClient())  # type: ignore[arg-type]

    batches = collector.collect_base_batches(missing)

    with pytest.raises(DataSourceError, match="saknas"):
        next(batches)


def test_collector_maps_rest_changes_to_features() -> None:
    collector = RAACollector(FakeClient())  # type: ignore[arg-type]

    features = collector.collect_changes(date(2026, 8, 1), date(2026, 8, 2))

    assert len(features) == 1
    assert features[0].feature_type == "Fyndplats"


def test_collector_reads_current_uuid_schema_and_quality(tmp_path: Path) -> None:
    path = tmp_path / "current.gpkg"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE gpkg_geometry_columns (
            table_name TEXT, column_name TEXT, geometry_type_name TEXT,
            srs_id INTEGER, z INTEGER, m INTEGER
        );
        CREATE TABLE current_point (
            uuid TEXT, lamningsnummer TEXT, lamningstyp TEXT,
            lamningsnamn TEXT, geometri BLOB
        );
        CREATE TABLE current_quality (
            lamning_uuid TEXT, inmatningskvalitet TEXT,
            definition_av_kvalitet TEXT, lagesosakerhet_i_meter INTEGER,
            geometri BLOB
        );
        INSERT INTO gpkg_geometry_columns VALUES
            ('current_point', 'geometri', 'POINT', 3006, 0, 0),
            ('current_quality', 'geometri', 'POLYGON', 3006, 0, 0);
        """)
    geometry = point_blob(674571.866, 6580743.008)
    connection.execute(
        "INSERT INTO current_point VALUES (?, ?, ?, ?, ?)",
        ("uuid-current", "L2026:2", "Röse", "Namngiven lämning", geometry),
    )
    connection.execute(
        "INSERT INTO current_quality VALUES (?, ?, ?, ?, ?)",
        ("uuid-current", "God", "Digital inmätning", 2, geometry),
    )
    connection.commit()
    connection.close()

    feature = RAACollector(FakeClient()).collect_base(path)[0]  # type: ignore[arg-type]

    assert feature.title == "Namngiven lämning"
    assert feature.geometry_confidence.rationale == "God"
    assert (
        feature.properties["source_properties"]["raa-kmr"]["lagesosakerhet_i_meter"]
        == 2
    )


def test_collector_rejects_unmappable_geopackage(tmp_path: Path) -> None:
    path = tmp_path / "empty.gpkg"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT)"
    )
    connection.commit()
    connection.close()

    with pytest.raises(DataSourceError, match="inga objekt"):
        RAACollector(FakeClient()).collect_base(path)  # type: ignore[arg-type]
