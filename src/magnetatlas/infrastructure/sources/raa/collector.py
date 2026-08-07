"""RAÄ Collector for official GeoPackage bases and REST changes."""

from __future__ import annotations

import sqlite3
import struct
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from magnetatlas.domain.collectors import (
    CollectorCapability,
    CollectorDescriptor,
    CollectorOutputModel,
)
from magnetatlas.domain.datasets import SourceDefinition
from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.domain.features import AtlasFeature
from magnetatlas.domain.geography import BoundingBox, GeoPoint, LineString, Polygon
from magnetatlas.infrastructure.sources.raa.client import (
    API_VERSION,
    GEOPACKAGE_SCHEMA_VERSION,
    RAAClient,
)
from magnetatlas.infrastructure.sources.raa.mapper import map_raa_record

DEFAULT_IMPORT_BATCH_SIZE = 500
RAA_SOURCE_DEFINITION = SourceDefinition("raa-kmr", "RAÄ Kulturmiljöregistret")
SOURCE_FIELDS = (
    "lamningsnummer",
    "raa_nummer",
    "lamningstyp",
    "lamningsnamn",
    "namn",
    "beskrivning",
    "publiceringsdatum",
    "uttagsdatum",
    "antikvariskbedomning",
    "aktualitetstatus",
    "lan",
    "kommun",
    "socken",
    "url",
)
QUALITY_FIELDS = (
    "inmatningskvalitet",
    "definition_av_kvalitet",
    "lagesosakerhet_i_meter",
)


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _table_columns(connection: sqlite3.Connection, table: str) -> frozenset[str]:
    quoted = _quote_identifier(table)
    return frozenset(
        row["name"] for row in connection.execute(f"PRAGMA table_info({quoted})")
    )


def _source_query(connection: sqlite3.Connection) -> str:
    """Build one ordered stream over complete GeoPackage feature layers."""
    layers = connection.execute(
        "SELECT table_name, column_name FROM gpkg_geometry_columns"
    ).fetchall()
    quality_table: str | None = None
    quality_columns: frozenset[str] = frozenset()
    candidates: list[tuple[str, str, str, frozenset[str]]] = []
    for layer in layers:
        table = layer["table_name"]
        geometry_column = layer["column_name"]
        if not isinstance(table, str) or not isinstance(geometry_column, str):
            continue
        columns = _table_columns(connection, table)
        if "inmatningskvalitet" in columns and "lamning_uuid" in columns:
            quality_table = table
            quality_columns = columns
            continue
        id_column = next(
            (name for name in ("uuid", "lamning_uuid", "id") if name in columns),
            None,
        )
        if (
            id_column is not None
            and "lamningsnummer" in columns
            and "lamningstyp" in columns
        ):
            candidates.append((table, geometry_column, id_column, columns))
    if not candidates:
        raise DataSourceError(
            "RAÄ GeoPackage innehåller inga objektlager med komplett schema"
        )

    selects: list[str] = []
    for table, geometry_column, id_column, columns in candidates:
        source_columns = [
            (
                f"t.{_quote_identifier(field)} AS {_quote_identifier(field)}"
                if field in columns
                else f"NULL AS {_quote_identifier(field)}"
            )
            for field in SOURCE_FIELDS
        ]
        join = ""
        quality_selects = [
            f"NULL AS {_quote_identifier(field)}" for field in QUALITY_FIELDS
        ]
        if quality_table is not None:
            quality_selects = [
                (
                    f"q.{_quote_identifier(field)} AS {_quote_identifier(field)}"
                    if field in quality_columns
                    else f"NULL AS {_quote_identifier(field)}"
                )
                for field in QUALITY_FIELDS
            ]
            join = (
                f" LEFT JOIN {_quote_identifier(quality_table)} q"
                f" ON q.{_quote_identifier('lamning_uuid')} ="
                f" t.{_quote_identifier(id_column)}"
            )
        selects.append(
            "SELECT "
            f"t.{_quote_identifier(id_column)} AS source_id, "
            f"t.{_quote_identifier(geometry_column)} AS geometry_blob, "
            + ", ".join((*source_columns, *quality_selects))
            + f" FROM {_quote_identifier(table)} t{join}"
        )
    return "SELECT * FROM (" + " UNION ALL ".join(selects) + ") ORDER BY source_id"


def _read_uint(data: bytes, offset: int, endian: str) -> tuple[int, int]:
    return struct.unpack_from(f"{endian}I", data, offset)[0], offset + 4


def _read_double(data: bytes, offset: int, endian: str) -> tuple[float, int]:
    return struct.unpack_from(f"{endian}d", data, offset)[0], offset + 8


def _wkb_geometry(data: bytes, offset: int = 0) -> tuple[dict[str, Any], int]:
    byte_order = data[offset]
    endian = "<" if byte_order == 1 else ">"
    geometry_type, offset = _read_uint(data, offset + 1, endian)
    geometry_type %= 1000
    if geometry_type == 1:
        x, offset = _read_double(data, offset, endian)
        y, offset = _read_double(data, offset, endian)
        return {"type": "Point", "coordinates": [x, y]}, offset
    if geometry_type == 2:
        count, offset = _read_uint(data, offset, endian)
        coordinates = []
        for _ in range(count):
            x, offset = _read_double(data, offset, endian)
            y, offset = _read_double(data, offset, endian)
            coordinates.append([x, y])
        return {"type": "LineString", "coordinates": coordinates}, offset
    if geometry_type == 3:
        ring_count, offset = _read_uint(data, offset, endian)
        rings = []
        for _ in range(ring_count):
            point_count, offset = _read_uint(data, offset, endian)
            ring = []
            for _ in range(point_count):
                x, offset = _read_double(data, offset, endian)
                y, offset = _read_double(data, offset, endian)
                ring.append([x, y])
            rings.append(ring)
        return {"type": "Polygon", "coordinates": rings}, offset
    multi_names = {4: "MultiPoint", 5: "MultiLineString", 6: "MultiPolygon"}
    if geometry_type in multi_names:
        count, offset = _read_uint(data, offset, endian)
        coordinates = []
        for _ in range(count):
            nested, offset = _wkb_geometry(data, offset)
            coordinates.append(nested["coordinates"])
        return {"type": multi_names[geometry_type], "coordinates": coordinates}, offset
    raise ValueError(f"GeoPackage-geometritypen stöds inte: {geometry_type}")


def parse_geopackage_geometry(blob: bytes) -> dict[str, Any]:
    """Parse a standard GeoPackage geometry blob into a GeoJSON-like object."""
    if len(blob) < 8 or blob[:2] != b"GP":
        raise ValueError("Ogiltig GeoPackage-geometri")
    flags = blob[3]
    envelope_indicator = (flags >> 1) & 0b111
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    try:
        wkb_offset = 8 + envelope_sizes[envelope_indicator]
    except KeyError as exc:
        raise ValueError("Okänd GeoPackage-envelope") from exc
    geometry, _ = _wkb_geometry(blob, wkb_offset)
    return geometry


def _intersects(feature: AtlasFeature, bounds: BoundingBox) -> bool:
    geometry = feature.geometry
    if geometry is None:
        return False
    if isinstance(geometry, GeoPoint):
        return bounds.contains(geometry)
    if isinstance(geometry, LineString):
        points = geometry.points
    elif isinstance(geometry, Polygon):
        points = tuple(point for ring in geometry.rings for point in ring)
    else:
        return not (
            geometry.east < bounds.west
            or geometry.west > bounds.east
            or geometry.north < bounds.south
            or geometry.south > bounds.north
        )
    west = min(point.longitude for point in points)
    east = max(point.longitude for point in points)
    south = min(point.latitude for point in points)
    north = max(point.latitude for point in points)
    return not (
        east < bounds.west
        or west > bounds.east
        or north < bounds.south
        or south > bounds.north
    )


class RAACollector:
    """Collect normalized KMR features without persistence concerns."""

    descriptor = CollectorDescriptor(
        collector_id="raa",
        display_name="RAÄ Kulturmiljöregistret",
        version=API_VERSION,
        capabilities=frozenset(
            {
                CollectorCapability.BASE_IMPORT,
                CollectorCapability.INCREMENTAL_CHANGES,
                CollectorCapability.COUNTRY_SCOPE,
                CollectorCapability.COUNTY_SCOPE,
                CollectorCapability.MUNICIPALITY_SCOPE,
                CollectorCapability.BBOX_SCOPE,
            }
        ),
        output_model=CollectorOutputModel.ATLAS_FEATURE,
        source=RAA_SOURCE_DEFINITION,
    )

    def __init__(self, client: RAAClient) -> None:
        self._client = client

    @property
    def base_schema_version(self) -> str:
        """Return the documented GeoPackage product schema version."""
        return GEOPACKAGE_SCHEMA_VERSION

    def fetch_base_batches(
        self,
        destination: Path,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
        batch_size: int = DEFAULT_IMPORT_BATCH_SIZE,
    ) -> Iterator[tuple[AtlasFeature, ...]]:
        """Download and lazily normalize one official base package in batches."""
        download = self._client.download_geopackage(
            destination,
            county=county,
            municipality=municipality,
        )
        try:
            yield from self.collect_base_batches(
                download.path, bbox=bbox, batch_size=batch_size
            )
        finally:
            download.path.unlink(missing_ok=True)

    def fetch_base(
        self,
        destination: Path,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
    ) -> list[AtlasFeature]:
        """Compatibility helper that materializes a complete base import."""
        return [
            feature
            for batch in self.fetch_base_batches(
                destination,
                county=county,
                municipality=municipality,
                bbox=bbox,
            )
            for feature in batch
        ]

    def collect_base(
        self,
        path: Path,
        *,
        bbox: BoundingBox | None = None,
    ) -> list[AtlasFeature]:
        """Compatibility helper that materializes a local GeoPackage."""
        return [
            feature
            for batch in self.collect_base_batches(path, bbox=bbox)
            for feature in batch
        ]

    def collect_base_batches(
        self,
        path: Path,
        *,
        bbox: BoundingBox | None = None,
        batch_size: int = DEFAULT_IMPORT_BATCH_SIZE,
    ) -> Iterator[tuple[AtlasFeature, ...]]:
        """Read a GeoPackage lazily while retaining at most one output batch."""
        if not path.is_file():
            raise DataSourceError(f"RAÄ GeoPackage saknas: {path}")
        if batch_size < 1:
            raise ValueError("Importens batchstorlek måste vara minst 1")
        batch: list[AtlasFeature] = []
        mapped_feature_count = 0
        try:
            connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                rows = connection.execute(_source_query(connection))
                current_id: str | None = None
                current_raw: dict[str, Any] = {}
                current_blobs: set[bytes] = set()

                def map_current() -> list[AtlasFeature]:
                    if current_id is None:
                        return []
                    raw = dict(current_raw)
                    raw["id"] = current_id
                    if current_blobs:
                        raw["geometri"] = {
                            "type": "FeatureCollection",
                            "features": [
                                {
                                    "type": "Feature",
                                    "geometry": parse_geopackage_geometry(blob),
                                }
                                for blob in current_blobs
                            ],
                        }
                    try:
                        return map_raa_record(raw)
                    except ValueError:
                        return []

                for row in rows:
                    record = dict(row)
                    source_id = record.pop("source_id", None)
                    blob = record.pop("geometry_blob", None)
                    if not isinstance(source_id, str) or not source_id.strip():
                        continue
                    if current_id is not None and source_id != current_id:
                        mapped = map_current()
                        mapped_feature_count += len(mapped)
                        batch.extend(
                            feature
                            for feature in mapped
                            if bbox is None or _intersects(feature, bbox)
                        )
                        if len(batch) >= batch_size:
                            yield tuple(batch)
                            batch.clear()
                        current_raw.clear()
                        current_blobs.clear()
                    current_id = source_id
                    for key, value in record.items():
                        if value is not None and current_raw.get(key) is None:
                            current_raw[key] = value
                    if isinstance(blob, bytes):
                        current_blobs.add(blob)

                mapped = map_current()
                mapped_feature_count += len(mapped)
                batch.extend(
                    feature
                    for feature in mapped
                    if bbox is None or _intersects(feature, bbox)
                )
            finally:
                connection.close()
        except (sqlite3.Error, ValueError) as exc:
            raise DataSourceError(f"RAÄ GeoPackage kunde inte läsas: {exc}") from exc
        if mapped_feature_count == 0:
            raise DataSourceError(
                "RAÄ GeoPackage innehåller inga objekt som kunde normaliseras"
            )
        if batch:
            yield tuple(batch)

    def collect_changes(self, start: date, end: date) -> list[AtlasFeature]:
        """Fetch and normalize all official changes for an inclusive interval."""
        features: list[AtlasFeature] = []
        for raw in self._client.fetch_changes(start, end):
            try:
                features.extend(map_raa_record(raw))
            except ValueError:
                continue
        return features
