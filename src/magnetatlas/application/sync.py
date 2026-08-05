"""Source-neutral orchestration of base imports and incremental synchronization."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import perf_counter

from magnetatlas.domain.collectors import AtlasFeatureCollector
from magnetatlas.domain.features import AtlasFeature
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.domain.repositories import (
    AtlasFeatureRepository,
    DatasetMetadata,
    StoredFeature,
)


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Outcome of a completed atomic synchronization operation."""

    mode: str
    imported: int
    deleted: int
    marker: str | None
    duration_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class CacheStatus:
    """Local cache state obtained without contacting the source."""

    available: bool
    feature_count: int
    schema_version: str | None = None
    base_imported_at: datetime | None = None
    sync_marker: str | None = None
    cache_valid_until: datetime | None = None


def _source_version(feature: AtlasFeature) -> str | None:
    value = feature.properties.get("source_version")
    return str(value) if value is not None else None


class SyncService:
    """Own base/import policy, sync markers, versions and cache lifecycle."""

    def __init__(
        self,
        dataset_id: str,
        collector: AtlasFeatureCollector,
        repository: AtlasFeatureRepository,
        work_dir: Path,
        *,
        cache_ttl: timedelta = timedelta(hours=24),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._dataset_id = dataset_id
        self._collector = collector
        self._repository = repository
        self._work_dir = work_dir
        self._cache_ttl = cache_ttl
        self._clock = clock or (lambda: datetime.now(UTC))

    def status(self) -> CacheStatus:
        """Read local cache status without any source call."""
        metadata = self._repository.get_metadata(self._dataset_id)
        count = self._repository.count_features(dataset_id=self._dataset_id)
        if metadata is None:
            return CacheStatus(available=False, feature_count=count)
        return CacheStatus(
            available=True,
            feature_count=count,
            schema_version=metadata.schema_version,
            base_imported_at=metadata.base_imported_at,
            sync_marker=metadata.sync_marker,
            cache_valid_until=metadata.cache_valid_until,
        )

    def clear(self) -> int:
        """Remove the selected local dataset and its synchronization metadata."""
        return self._repository.clear_dataset(self._dataset_id)

    def refresh(
        self,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
        force: bool = False,
    ) -> SyncResult:
        """Use a base import when absent, otherwise synchronize changes."""
        metadata = self._repository.get_metadata(self._dataset_id)
        now = self._clock()
        if metadata is None or county or municipality or bbox:
            return self.base_import(
                county=county,
                municipality=municipality,
                bbox=bbox,
            )
        if (
            not force
            and metadata.cache_valid_until is not None
            and metadata.cache_valid_until > now
        ):
            return SyncResult("cached", 0, 0, metadata.sync_marker)
        return self.incremental_sync()

    def base_import(
        self,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> SyncResult:
        """Build and atomically activate an official base dataset."""
        started = perf_counter()
        now = self._clock()
        self._work_dir.mkdir(parents=True, exist_ok=True)
        destination = self._work_dir / f"{self._dataset_id}.gpkg"
        batches = self._collector.fetch_base_batches(
            destination,
            county=county,
            municipality=municipality,
            bbox=bbox,
        )
        marker = (now.date() - timedelta(days=1)).isoformat()
        metadata = DatasetMetadata(
            dataset_id=self._dataset_id,
            schema_version=self._collector.base_schema_version,
            base_imported_at=now,
            sync_marker=marker,
            cache_valid_until=now + self._cache_ttl,
        )
        import_session = self._repository.begin_dataset_replace(metadata)
        imported = 0
        try:
            for batch in batches:
                stored = tuple(
                    StoredFeature(feature, _source_version(feature))
                    for feature in batch
                )
                import_session.write_batch(stored)
                imported += len(stored)
                if progress is not None:
                    progress(imported)
            if imported == 0:
                raise ValueError("Importen innehöll inga giltiga objekt")
            import_session.commit()
        except BaseException:
            import_session.rollback()
            raise
        finally:
            close = getattr(batches, "close", None)
            if callable(close):
                close()
        return SyncResult("base", imported, 0, marker, perf_counter() - started)

    def incremental_sync(self) -> SyncResult:
        """Apply all changes after the last completed marker atomically."""
        metadata = self._repository.get_metadata(self._dataset_id)
        if metadata is None or metadata.sync_marker is None:
            return self.base_import()
        now = self._clock()
        start = date.fromisoformat(metadata.sync_marker) + timedelta(days=1)
        end = now.date() - timedelta(days=1)
        if start > end:
            refreshed = DatasetMetadata(
                dataset_id=metadata.dataset_id,
                schema_version=metadata.schema_version,
                base_imported_at=metadata.base_imported_at,
                sync_marker=metadata.sync_marker,
                cache_valid_until=now + self._cache_ttl,
            )
            self._repository.apply_changes(refreshed, [], [])
            return SyncResult("incremental", 0, 0, metadata.sync_marker)
        changes = self._collector.collect_changes(start, end)
        existing = self._repository.list_features(dataset_id=self._dataset_id)
        deleted_source_ids = {
            feature.provenance.source_id
            for feature in changes
            if feature.properties.get("deleted") is True
        }
        delete_ids = [
            feature.feature_id
            for feature in existing
            if feature.provenance.source_id in deleted_source_ids
        ]
        upserts = [
            StoredFeature(feature, _source_version(feature))
            for feature in changes
            if feature.properties.get("deleted") is not True
        ]
        next_metadata = DatasetMetadata(
            dataset_id=metadata.dataset_id,
            schema_version=metadata.schema_version,
            base_imported_at=metadata.base_imported_at,
            sync_marker=end.isoformat(),
            cache_valid_until=now + self._cache_ttl,
        )
        self._repository.apply_changes(next_metadata, upserts, delete_ids)
        return SyncResult("incremental", len(upserts), len(delete_ids), end.isoformat())


class SyncScheduler:
    """Trigger SyncService without source, mapping or persistence logic."""

    def __init__(self, service: SyncService) -> None:
        self._service = service

    def run(self) -> SyncResult:
        """Run one scheduled refresh."""
        return self._service.refresh()
