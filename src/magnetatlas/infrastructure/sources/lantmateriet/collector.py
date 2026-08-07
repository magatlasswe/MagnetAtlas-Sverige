"""Collector for reproducible Lantmäteriet vector download datasets."""

from __future__ import annotations

import sqlite3
import struct
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from magnetatlas.domain.collectors import (
    CollectorCapability,
    CollectorDescriptor,
    CollectorOutputModel,
)
from magnetatlas.domain.datasets import SourceDefinition
from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.domain.features import AtlasFeature
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.infrastructure.sources.lantmateriet.client import LantmaterietClient
from magnetatlas.infrastructure.sources.lantmateriet.mapper import map_ortnamn_record

LANTMATERIET_SOURCE_DEFINITION = SourceDefinition(
    "lantmateriet-ortnamn", "Lantmäteriet Ortnamn Nedladdning"
)


@dataclass(frozen=True, slots=True)
class LantmaterietDatasetDefinition:
    """Declarative configuration for one Lantmäteriet download collection."""

    dataset_id: str
    name: str
    collection_id: str
    schema_version: str
    source: SourceDefinition


ORTNAMN_DATASET = LantmaterietDatasetDefinition(
    dataset_id="ortnamn",
    name="Ortnamn Nedladdning, vektor",
    collection_id="ortnamn",
    schema_version="2025.02",
    source=LANTMATERIET_SOURCE_DEFINITION,
)


def _quote(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _point_from_geopackage(blob: bytes) -> tuple[float, float]:
    if len(blob) < 29 or blob[:2] != b"GP":
        raise ValueError("ogiltig GeoPackage-geometri")
    flags = blob[3]
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    envelope = envelope_sizes.get((flags >> 1) & 0b111)
    if envelope is None:
        raise ValueError("okänd GeoPackage-envelope")
    offset = 8 + envelope
    endian = "<" if blob[offset] == 1 else ">"
    geometry_type = struct.unpack_from(f"{endian}I", blob, offset + 1)[0] % 1000
    if geometry_type != 1:
        raise ValueError("Ortnamnslagret innehåller en geometri som inte är punkt")
    return struct.unpack_from(f"{endian}dd", blob, offset + 5)


def _extract_geopackage(archive: Path, destination: Path) -> Path:
    try:
        with zipfile.ZipFile(archive) as package:
            members = [
                item
                for item in package.infolist()
                if not item.is_dir() and item.filename.casefold().endswith(".gpkg")
            ]
            if len(members) != 1:
                raise DataSourceError(
                    "Lantmäteriets arkiv ska innehålla exakt en GeoPackage-fil"
                )
            member = members[0]
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise DataSourceError("Lantmäteriets arkiv innehåller en osäker sökväg")
            temporary = destination.with_suffix(f"{destination.suffix}.part")
            with package.open(member) as source, temporary.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            temporary.replace(destination)
            return destination
    except (OSError, zipfile.BadZipFile) as exc:
        destination.with_suffix(f"{destination.suffix}.part").unlink(missing_ok=True)
        raise DataSourceError(
            f"Lantmäteriets ZIP-arkiv kunde inte läsas: {exc}"
        ) from exc


def _source_layer(connection: sqlite3.Connection) -> tuple[str, str]:
    rows = connection.execute(
        "SELECT table_name, column_name FROM gpkg_geometry_columns"
    ).fetchall()
    for table, geometry_column in rows:
        columns = {
            row[1].casefold()
            for row in connection.execute(f"PRAGMA table_info({_quote(table)})")
        }
        if {"lopnummer", "sprakkod"}.issubset(columns) or {
            "löpnummer",
            "språkkod",
        }.issubset(columns):
            return str(table), str(geometry_column)
    raise DataSourceError("GeoPackage-filen saknar dokumenterat ortnamnslager")


class LantmaterietCollector:
    """Download and stream one configured Lantmäteriet dataset."""

    def __init__(
        self,
        client: LantmaterietClient,
        dataset: LantmaterietDatasetDefinition = ORTNAMN_DATASET,
        *,
        batch_size: int = 500,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size måste vara större än noll")
        self._client = client
        self._dataset = dataset
        self._batch_size = batch_size

    @property
    def descriptor(self) -> CollectorDescriptor:
        return CollectorDescriptor(
            collector_id=f"lantmateriet-{self._dataset.dataset_id}",
            display_name=f"Lantmäteriet {self._dataset.name}",
            version="1.0",
            capabilities=frozenset(
                {
                    CollectorCapability.BASE_IMPORT,
                    CollectorCapability.COUNTRY_SCOPE,
                    CollectorCapability.BBOX_SCOPE,
                }
            ),
            output_model=CollectorOutputModel.ATLAS_FEATURE,
            source=self._dataset.source,
        )

    @property
    def base_schema_version(self) -> str:
        return self._dataset.schema_version

    def fetch_base_batches(
        self,
        destination: Path,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
    ) -> Iterator[tuple[AtlasFeature, ...]]:
        """Download the national snapshot and yield normalized bounded batches."""
        if county or municipality:
            raise ValueError("Ortnamn Nedladdning stöder country och bbox")
        archive_path = destination.with_suffix(".zip")
        download = self._client.download_archive(
            self._dataset.collection_id, archive_path
        )
        try:
            _extract_geopackage(download.path, destination)
            version = download.published_at or download.item_id
            yield from self.collect_base_batches(
                destination,
                source_url=download.source_url,
                dataset_version=version,
                bbox=bbox,
            )
        finally:
            archive_path.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)

    def collect_base_batches(
        self,
        path: Path,
        *,
        source_url: str,
        dataset_version: str,
        bbox: BoundingBox | None = None,
    ) -> Iterator[tuple[AtlasFeature, ...]]:
        """Read one local GeoPackage without materializing the dataset."""
        batch: list[AtlasFeature] = []
        mapped_count = 0
        try:
            connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                table, geometry_column = _source_layer(connection)
                rows = connection.execute(
                    f"SELECT * FROM {_quote(table)} ORDER BY rowid"
                )
                for row in rows:
                    raw: dict[str, Any] = dict(row)
                    blob = raw.pop(geometry_column, None)
                    if not isinstance(blob, bytes):
                        continue
                    raw["_x"], raw["_y"] = _point_from_geopackage(blob)
                    try:
                        feature = map_ortnamn_record(
                            raw,
                            source_url=source_url,
                            dataset_version=dataset_version,
                        )
                    except ValueError:
                        continue
                    mapped_count += 1
                    if bbox is not None and (
                        feature.geometry is None or not bbox.contains(feature.geometry)
                    ):
                        continue
                    batch.append(feature)
                    if len(batch) >= self._batch_size:
                        yield tuple(batch)
                        batch.clear()
            finally:
                connection.close()
        except sqlite3.Error as exc:
            raise DataSourceError(
                f"Lantmäteriets GeoPackage kunde inte läsas: {exc}"
            ) from exc
        if mapped_count == 0:
            raise DataSourceError("GeoPackage-filen innehöll inga giltiga ortnamn")
        if batch:
            yield tuple(batch)

    def collect_changes(self, start: date, end: date) -> list[AtlasFeature]:
        """Reject incremental sync because STAC publishes complete snapshots."""
        del start, end
        raise ValueError("Ortnamn Nedladdning saknar inkrementellt ändringsflöde")
