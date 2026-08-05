"""SQLite integration tests for source-neutral AtlasFeature persistence."""

from datetime import UTC, datetime
from pathlib import Path

from magnetatlas.domain.features import AtlasFeature, FeatureId, Provenance
from magnetatlas.domain.repositories import DatasetMetadata, StoredFeature
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyAtlasFeatureRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory


def make_feature(identifier: str, title: str = "Historisk plats") -> AtlasFeature:
    return AtlasFeature(
        feature_id=FeatureId(identifier),
        title=title,
        feature_type="lämning",
        provenance=Provenance(source="official", source_id=identifier),
    )


def make_repository(tmp_path: Path) -> SqlAlchemyAtlasFeatureRepository:
    return SqlAlchemyAtlasFeatureRepository(
        create_session_factory(f"sqlite:///{tmp_path / 'features.db'}")
    )


def metadata(marker: str = "2026-08-04") -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id="dataset",
        schema_version="1",
        base_imported_at=datetime(2026, 8, 5, tzinfo=UTC),
        sync_marker=marker,
    )


def test_replace_dataset_round_trips_features_and_metadata(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    feature = make_feature("official:1")

    repository.replace_dataset(metadata(), [StoredFeature(feature, "1")])

    assert repository.list_features(dataset_id="dataset") == [feature]
    assert repository.get_metadata("dataset") == metadata()
    assert repository.count_features(dataset_id="dataset") == 1


def test_apply_changes_upserts_deletes_and_advances_marker(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.replace_dataset(
        metadata(),
        [StoredFeature(make_feature("official:1"), "1")],
    )
    updated = make_feature("official:2", "Uppdaterad plats")

    repository.apply_changes(
        metadata("2026-08-05"),
        [StoredFeature(updated, "2")],
        [FeatureId("official:1")],
    )

    assert repository.list_features(dataset_id="dataset") == [updated]
    assert repository.get_metadata("dataset") == metadata("2026-08-05")


def test_clear_dataset_does_not_touch_other_datasets(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.replace_dataset(metadata(), [StoredFeature(make_feature("one"))])
    other = DatasetMetadata(dataset_id="other", schema_version="1")
    repository.replace_dataset(other, [StoredFeature(make_feature("two"))])

    removed = repository.clear_dataset("dataset")

    assert removed == 1
    assert repository.get_metadata("dataset") is None
    assert [str(item.feature_id) for item in repository.list_features()] == ["two"]
