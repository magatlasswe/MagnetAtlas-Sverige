"""Persistence contracts owned by the domain layer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from magnetatlas.domain.datasets import DatasetInstance
from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.models import ArchiveRecord


class ArchiveRecordRepository(Protocol):
    """Storage contract for normalized archive records."""

    def save_many(self, records: Sequence[ArchiveRecord]) -> list[ArchiveRecord]: ...

    def list_all(self) -> list[ArchiveRecord]: ...


@dataclass(frozen=True, slots=True)
class StoredFeature:
    """A domain feature with an opaque source version used for idempotency."""

    feature: AtlasFeature
    version: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    """Source-neutral state associated with one locally persisted dataset."""

    instance: DatasetInstance
    schema_version: str
    base_imported_at: datetime | None = None
    sync_marker: str | None = None
    cache_valid_until: datetime | None = None

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("schema_version får inte vara tomt")
        for value in (
            self.base_imported_at,
            self.cache_valid_until,
        ):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() is None
            ):
                raise ValueError("Metadata-tidpunkter måste innehålla tidszon")

    @property
    def dataset_id(self) -> str:
        """Return the persisted identity of this dataset instance."""
        return self.instance.dataset_id


class DatasetImportSession(Protocol):
    """Incrementally build and atomically activate one dataset replacement."""

    def write_batch(self, features: Sequence[StoredFeature]) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class AtlasFeatureRepository(Protocol):
    """Domain-neutral atomic persistence contract for atlas datasets."""

    def replace_dataset(
        self,
        metadata: DatasetMetadata,
        features: Sequence[StoredFeature],
    ) -> None: ...

    def begin_dataset_replace(
        self, metadata: DatasetMetadata
    ) -> DatasetImportSession: ...

    def apply_changes(
        self,
        metadata: DatasetMetadata,
        upserts: Sequence[StoredFeature],
        delete_source_ids: Sequence[str],
    ) -> None: ...

    def lookup(self, source_id: str, *, dataset_id: str) -> tuple[FeatureId, ...]: ...

    def delete(self, source_ids: str | Sequence[str], *, dataset_id: str) -> int: ...

    def list_features(self, *, dataset_id: str | None = None) -> list[AtlasFeature]: ...

    def search_features(
        self,
        query: str,
        *,
        dataset_id: str | None = None,
        limit: int = 100,
    ) -> list[AtlasFeature]: ...

    def get_metadata(self, dataset_id: str) -> DatasetMetadata | None: ...

    def list_dataset_instances(self) -> tuple[DatasetInstance, ...]: ...

    def get_active_instance(self, source_id: str) -> DatasetInstance | None: ...

    def count_features(self, *, dataset_id: str | None = None) -> int: ...

    def clear_dataset(self, dataset_id: str) -> int: ...

    def clear_source(self, source_id: str) -> int: ...
