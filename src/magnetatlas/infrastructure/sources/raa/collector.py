"""RAÄ Collector for official GeoPackage bases and REST changes."""

from __future__ import annotations

import sqlite3
import struct
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from magnetatlas.domain.collectors import CollectorDescriptor
from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.domain.features import AtlasFeature
from magnetatlas.domain.geography import BoundingBox, GeoPoint, LineString, Polygon
from magnetatlas.infrastructure.sources.raa.client import (
    API_VERSION,
    GEOPACKAGE_SCHEMA_VERSION,
    RAAClient,
)
from magnetatlas.infrastructure.sources.raa.mapper import map_raa_record


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
    )

    def __init__(self, client: RAAClient) -> None:
        self._client = client

    @property
    def base_schema_version(self) -> str:
        """Return the documented GeoPackage product schema version."""
        return GEOPACKAGE_SCHEMA_VERSION

    def fetch_base(
        self,
        destination: Path,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
    ) -> list[AtlasFeature]:
        """Download, normalize and discard one official base package."""
        download = self._client.download_geopackage(
            destination,
            county=county,
            municipality=municipality,
        )
        try:
            return self.collect_base(download.path, bbox=bbox)
        finally:
            download.path.unlink(missing_ok=True)

    def collect_base(
        self,
        path: Path,
        *,
        bbox: BoundingBox | None = None,
    ) -> list[AtlasFeature]:
        """Read and normalize every feature from an official GeoPackage."""
        if not path.is_file():
            raise DataSourceError(f"RAÄ GeoPackage saknas: {path}")
        grouped: dict[str, dict[str, Any]] = {}
        geometries: dict[str, list[dict[str, Any]]] = defaultdict(list)
        geometry_blobs: dict[str, set[bytes]] = defaultdict(set)
        quality: dict[str, dict[str, Any]] = {}
        try:
            connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                layers = connection.execute(
                    "SELECT table_name, column_name FROM gpkg_geometry_columns"
                ).fetchall()
                for layer in layers:
                    table = layer["table_name"]
                    geometry_column = layer["column_name"]
                    if not isinstance(table, str) or not isinstance(
                        geometry_column, str
                    ):
                        continue
                    quoted_table = table.replace('"', '""')
                    rows = connection.execute(f'SELECT * FROM "{quoted_table}"')
                    for row in rows:
                        record = dict(row)
                        blob = record.pop(geometry_column, None)
                        source_id = (
                            record.get("uuid")
                            or record.get("lamning_uuid")
                            or record.get("id")
                        )
                        if not isinstance(source_id, str) or not source_id.strip():
                            continue
                        if "inmatningskvalitet" in record:
                            quality[source_id] = {
                                key: record.get(key)
                                for key in (
                                    "inmatningskvalitet",
                                    "definition_av_kvalitet",
                                    "lagesosakerhet_i_meter",
                                )
                                if record.get(key) is not None
                            }
                            continue
                        current = grouped.setdefault(source_id, {})
                        for key, value in record.items():
                            if value is not None and current.get(key) is None:
                                current[key] = value
                        if (
                            isinstance(blob, bytes)
                            and blob not in geometry_blobs[source_id]
                        ):
                            geometry_blobs[source_id].add(blob)
                            geometries[source_id].append(
                                parse_geopackage_geometry(blob)
                            )
            finally:
                connection.close()
        except (sqlite3.Error, ValueError) as exc:
            raise DataSourceError(f"RAÄ GeoPackage kunde inte läsas: {exc}") from exc

        features: list[AtlasFeature] = []
        mapped_feature_count = 0
        for source_id, raw in grouped.items():
            raw["id"] = source_id
            raw.update(quality.get(source_id, {}))
            documents = geometries.get(source_id, [])
            if documents:
                raw["geometri"] = {
                    "type": "FeatureCollection",
                    "features": [
                        {"type": "Feature", "geometry": document}
                        for document in documents
                    ],
                }
            try:
                mapped = map_raa_record(raw)
            except ValueError:
                continue
            mapped_feature_count += len(mapped)
            features.extend(
                feature
                for feature in mapped
                if bbox is None or _intersects(feature, bbox)
            )
        if not grouped or mapped_feature_count == 0:
            raise DataSourceError(
                "RAÄ GeoPackage innehåller inga objekt som kunde normaliseras"
            )
        return features

    def collect_changes(self, start: date, end: date) -> list[AtlasFeature]:
        """Fetch and normalize all official changes for an inclusive interval."""
        features: list[AtlasFeature] = []
        for raw in self._client.fetch_changes(start, end):
            try:
                features.extend(map_raa_record(raw))
            except ValueError:
                continue
        return features
