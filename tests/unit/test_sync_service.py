"""Tests for atomic synchronization policy and scheduler boundaries."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from magnetatlas.application.sync import SyncScheduler, SyncService
from magnetatlas.domain.features import AtlasFeature, FeatureId, Provenance
from magnetatlas.domain.repositories import DatasetMetadata
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyAtlasFeatureRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory

NOW = datetime(2026, 8, 5, 12, tzinfo=UTC)


def feature(identifier: str, *, deleted: bool = False) -> AtlasFeature:
    return AtlasFeature(
        feature_id=FeatureId(f"raa:{identifier}"),
        title=identifier,
        feature_type="Röse",
        provenance=Provenance(source="official", source_id=identifier),
        properties={"source_version": "2", "deleted": deleted},
    )


class FakeCollector:
    base_schema_version = "3.0"

    def __init__(self) -> None:
        self.base_features = [feature("base")]
        self.changes: list[AtlasFeature] = []
        self.base_calls = 0
        self.change_calls: list[tuple[date, date]] = []
        self.fail_base = False
        self.fail_after_first = False

    def fetch_base_batches(
        self, destination: Path, **kwargs: object
    ) -> Iterator[tuple[AtlasFeature, ...]]:
        self.base_calls += 1
        if self.fail_base:
            raise RuntimeError("avbruten")

        def batches() -> Iterator[tuple[AtlasFeature, ...]]:
            for item in self.base_features:
                yield (item,)
                if self.fail_after_first:
                    raise RuntimeError("avbruten efter batch")

        return batches()

    def collect_changes(self, start: date, end: date) -> list[AtlasFeature]:
        self.change_calls.append((start, end))
        return self.changes


def repository(tmp_path: Path) -> SqlAlchemyAtlasFeatureRepository:
    return SqlAlchemyAtlasFeatureRepository(
        create_session_factory(f"sqlite:///{tmp_path / 'sync.db'}")
    )


def service(
    tmp_path: Path,
    collector: FakeCollector,
) -> tuple[SyncService, SqlAlchemyAtlasFeatureRepository]:
    repo = repository(tmp_path)
    return (
        SyncService("raa", collector, repo, tmp_path, clock=lambda: NOW),
        repo,
    )


def test_first_refresh_performs_atomic_base_import(tmp_path: Path) -> None:
    collector = FakeCollector()
    sync, repo = service(tmp_path, collector)

    result = sync.refresh()

    assert result.mode == "base"
    assert result.imported == 1
    assert repo.count_features(dataset_id="raa") == 1
    assert repo.get_metadata("raa").sync_marker == "2026-08-04"  # type: ignore[union-attr]


def test_valid_cache_avoids_source_calls(tmp_path: Path) -> None:
    collector = FakeCollector()
    sync, _ = service(tmp_path, collector)
    sync.refresh()

    result = sync.refresh()

    assert result.mode == "cached"
    assert collector.base_calls == 1
    assert collector.change_calls == []


def test_incremental_sync_updates_only_changes_and_deletions(tmp_path: Path) -> None:
    collector = FakeCollector()
    collector.base_features = [feature("keep"), feature("remove")]
    sync, repo = service(tmp_path, collector)
    sync.refresh()
    original = repo.get_metadata("raa")
    assert original is not None
    repo.apply_changes(
        DatasetMetadata(
            dataset_id="raa",
            schema_version="3.0",
            base_imported_at=original.base_imported_at,
            sync_marker="2026-08-02",
            cache_valid_until=NOW - timedelta(hours=1),
        ),
        [],
        [],
    )
    collector.changes = [feature("new"), feature("remove", deleted=True)]

    result = sync.refresh()

    assert result.mode == "incremental"
    assert collector.change_calls == [(date(2026, 8, 3), date(2026, 8, 4))]
    assert {item.provenance.source_id for item in repo.list_features()} == {
        "keep",
        "new",
    }


def test_failed_base_import_preserves_last_successful_dataset(tmp_path: Path) -> None:
    collector = FakeCollector()
    sync, repo = service(tmp_path, collector)
    sync.refresh()
    collector.fail_base = True

    with pytest.raises(RuntimeError, match="avbruten"):
        sync.base_import(county="ostergotland")

    assert [item.provenance.source_id for item in repo.list_features()] == ["base"]


def test_failed_stream_discards_staging_and_reports_completed_batches(
    tmp_path: Path,
) -> None:
    collector = FakeCollector()
    sync, repo = service(tmp_path, collector)
    sync.refresh()
    collector.base_features = [feature("new-1"), feature("new-2")]
    collector.fail_after_first = True
    progress: list[int] = []

    with pytest.raises(RuntimeError, match="efter batch"):
        sync.base_import(county="ostergotland", progress=progress.append)

    assert progress == [1]
    assert [item.provenance.source_id for item in repo.list_features()] == ["base"]


def test_scheduler_only_triggers_service_refresh(tmp_path: Path) -> None:
    collector = FakeCollector()
    sync, _ = service(tmp_path, collector)

    result = SyncScheduler(sync).run()

    assert result.mode == "base"
