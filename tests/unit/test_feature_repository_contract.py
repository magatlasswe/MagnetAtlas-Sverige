"""Tests for source-neutral AtlasFeature repository value objects."""

from datetime import UTC, datetime

import pytest

from magnetatlas.domain.repositories import DatasetMetadata


def test_dataset_metadata_accepts_generic_version_and_markers() -> None:
    metadata = DatasetMetadata(
        dataset_id="official-heritage",
        schema_version="3",
        base_imported_at=datetime(2026, 8, 5, tzinfo=UTC),
        sync_marker="opaque-marker",
    )

    assert metadata.dataset_id == "official-heritage"
    assert metadata.sync_marker == "opaque-marker"


def test_dataset_metadata_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="tidszon"):
        DatasetMetadata(
            dataset_id="dataset",
            schema_version="1",
            base_imported_at=datetime(2026, 8, 5),
        )
