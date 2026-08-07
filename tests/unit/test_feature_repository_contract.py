"""Tests for source-neutral AtlasFeature repository value objects."""

from datetime import UTC, datetime

import pytest

from magnetatlas.domain.datasets import DatasetInstance, DatasetScope, SourceDefinition
from magnetatlas.domain.repositories import DatasetMetadata

INSTANCE = DatasetInstance.create(
    SourceDefinition("official-heritage", "Official heritage"),
    DatasetScope.country("sweden"),
)


def test_dataset_metadata_accepts_generic_version_and_markers() -> None:
    metadata = DatasetMetadata(
        instance=INSTANCE,
        schema_version="3",
        base_imported_at=datetime(2026, 8, 5, tzinfo=UTC),
        sync_marker="opaque-marker",
    )

    assert metadata.dataset_id == "official-heritage:country:sweden"
    assert metadata.sync_marker == "opaque-marker"


def test_dataset_metadata_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="tidszon"):
        DatasetMetadata(
            instance=INSTANCE,
            schema_version="1",
            base_imported_at=datetime(2026, 8, 5),
        )
