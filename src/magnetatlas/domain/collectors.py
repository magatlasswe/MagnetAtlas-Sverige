"""Provider-independent contracts for collecting source data."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from magnetatlas.domain.datasets import SourceDefinition
from magnetatlas.domain.features import AtlasFeature
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.domain.models import ArchiveRecord


class CollectorCapability(StrEnum):
    """A source-independent operation supported by a collector."""

    BASE_IMPORT = "base_import"
    INCREMENTAL_CHANGES = "incremental_changes"
    REMOTE_SEARCH = "remote_search"
    COUNTRY_SCOPE = "country_scope"
    COUNTY_SCOPE = "county_scope"
    MUNICIPALITY_SCOPE = "municipality_scope"
    BBOX_SCOPE = "bbox_scope"
    # Retained while ArchiveRecord integrations migrate to REMOTE_SEARCH.
    TEXT_SEARCH = "text_search"
    RESULT_LIMIT = "result_limit"
    CURSOR_PAGINATION = "cursor_pagination"


class CollectorOutputModel(StrEnum):
    """Normalized model produced by a Collector generation."""

    ATLAS_FEATURE = "atlas_feature"
    ARCHIVE_RECORD = "archive_record"


@dataclass(frozen=True, slots=True)
class CollectorDescriptor:
    """Stable identity and advertised behavior for a collector plugin."""

    collector_id: str
    display_name: str
    version: str
    capabilities: frozenset[CollectorCapability] = field(default_factory=frozenset)
    output_model: CollectorOutputModel = CollectorOutputModel.ARCHIVE_RECORD
    source: SourceDefinition | None = None

    def __post_init__(self) -> None:
        if not self.collector_id.strip():
            raise ValueError("collector_id får inte vara tomt")
        if not self.display_name.strip():
            raise ValueError("display_name får inte vara tomt")
        if not self.version.strip():
            raise ValueError("version får inte vara tom")
        if (
            self.output_model is CollectorOutputModel.ATLAS_FEATURE
            and self.source is None
        ):
            raise ValueError("AtlasFeature-collectors kräver en SourceDefinition")

    def supports(self, capability: CollectorCapability) -> bool:
        """Return whether the collector advertises a capability."""
        return capability in self.capabilities


@dataclass(frozen=True, slots=True)
class CollectionRequest:
    """A provider-independent request sent to a collector."""

    query: str | None = None
    limit: int = 20
    cursor: str | None = None

    def __post_init__(self) -> None:
        if self.query is not None and not self.query.strip():
            raise ValueError("Sökfrågan får inte vara tom")
        if not 1 <= self.limit <= 100:
            raise ValueError("Antal träffar måste vara mellan 1 och 100")
        if self.cursor is not None and not self.cursor.strip():
            raise ValueError("cursor får inte vara tom")

    @property
    def required_capabilities(self) -> frozenset[CollectorCapability]:
        """Derive capabilities required to satisfy this request."""
        required = {CollectorCapability.RESULT_LIMIT}
        if self.query is not None:
            required.add(CollectorCapability.REMOTE_SEARCH)
        if self.cursor is not None:
            required.add(CollectorCapability.CURSOR_PAGINATION)
        return frozenset(required)


@dataclass(frozen=True, slots=True)
class CollectionBatch:
    """One normalized result batch returned by a collector."""

    records: list[ArchiveRecord]
    total_hits: int
    next_cursor: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.total_hits < 0:
            raise ValueError("total_hits får inte vara negativt")


class Collector(Protocol):
    """Contract implemented by every MagnetAtlas data-source plugin."""

    @property
    def descriptor(self) -> CollectorDescriptor: ...

    def collect(self, request: CollectionRequest) -> CollectionBatch: ...


class AtlasFeatureCollector(Protocol):
    """Contract for versioned base imports and incremental feature changes."""

    @property
    def descriptor(self) -> CollectorDescriptor: ...

    @property
    def base_schema_version(self) -> str: ...

    def fetch_base_batches(
        self,
        destination: Path,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
    ) -> Iterator[tuple[AtlasFeature, ...]]: ...

    def collect_changes(self, start: date, end: date) -> list[AtlasFeature]: ...


type CollectorPlugin = Collector | AtlasFeatureCollector
