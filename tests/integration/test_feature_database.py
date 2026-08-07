"""SQLite integration tests for source-neutral AtlasFeature persistence."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import event, text

from magnetatlas.application.features import FeatureSearchFilters
from magnetatlas.domain.features import AtlasFeature, FeatureId, Provenance
from magnetatlas.domain.geography import BoundingBox, GeoPoint
from magnetatlas.domain.repositories import DatasetMetadata, StoredFeature
from magnetatlas.infrastructure.database.feature_queries import (
    SqlAlchemyFeatureQuerySource,
)
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


def test_staged_batches_are_hidden_until_atomic_commit(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.replace_dataset(metadata(), [StoredFeature(make_feature("active"), "1")])
    import_session = repository.begin_dataset_replace(metadata("2026-08-06"))

    import_session.write_batch([StoredFeature(make_feature("new-1"), "2")])
    import_session.write_batch([StoredFeature(make_feature("new-2"), "2")])

    assert [
        str(item.feature_id) for item in repository.list_features(dataset_id="dataset")
    ] == ["active"]
    import_session.commit()
    assert [
        str(item.feature_id) for item in repository.list_features(dataset_id="dataset")
    ] == ["new-1", "new-2"]
    assert repository.get_metadata("dataset") == metadata("2026-08-06")


def test_staging_rollback_preserves_active_dataset(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.replace_dataset(metadata(), [StoredFeature(make_feature("active"))])
    import_session = repository.begin_dataset_replace(metadata("2026-08-06"))
    import_session.write_batch([StoredFeature(make_feature("new"))])

    import_session.rollback()

    assert [str(item.feature_id) for item in repository.list_features()] == ["active"]


def test_sqlite_query_source_bounds_details_metadata_and_search(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(f"sqlite:///{tmp_path / 'queries.db'}")
    repository = SqlAlchemyAtlasFeatureRepository(session_factory)
    inside = replace(
        make_feature("inside", "Historisk bro"), geometry=GeoPoint(18.1, 59.3)
    )
    second = replace(
        make_feature("second", "Gammalt röse"), geometry=GeoPoint(18.2, 59.4)
    )
    outside = replace(
        make_feature("outside", "Avlägsen plats"), geometry=GeoPoint(12.0, 57.0)
    )
    repository.replace_dataset(
        metadata(),
        [StoredFeature(inside), StoredFeature(second), StoredFeature(outside)],
    )
    source = SqlAlchemyFeatureQuerySource(session_factory, "dataset")

    viewport = source.in_bounds(BoundingBox(18.0, 59.0, 19.0, 60.0), limit=1)

    assert [str(item.feature_id) for item in viewport.features] == ["inside"]
    assert viewport.truncated is True
    assert source.get("second") == second
    assert source.summary().count == 3
    assert source.summary().source == "official"
    assert source.search(
        "historsk",
        filters=FeatureSearchFilters(),
        limit=10,
    ) == (inside,)
    assert source.search(
        "historisk",
        filters=FeatureSearchFilters(),
        limit=10,
    ) == (inside,)
    plan = source.viewport_query_plan(BoundingBox(18.0, 59.0, 19.0, 60.0))
    assert any("VIRTUAL TABLE INDEX" in step for step in plan)
    assert any("INTEGER PRIMARY KEY" in step or "dataset_id" in step for step in plan)
    assert not any(step.startswith("SCAN atlas_features ") for step in plan)
    assert not any("TEMP B-TREE" in step for step in plan)

    with session_factory() as session:
        assert session.scalar(text("SELECT count(*) FROM atlas_features_rtree")) == 3
        assert session.scalar(text("SELECT count(*) FROM atlas_features_fts")) == 3
        search_plan = session.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT af.id FROM atlas_features af "
                "JOIN atlas_features_fts f ON f.rowid=af.id "
                "WHERE f.search_text MATCH 'historisk*'"
            )
        ).all()
    assert any("VIRTUAL TABLE INDEX" in str(row[3]) for row in search_plan)
    assert not any("TEMP B-TREE" in str(row[3]) for row in search_plan)


def test_incremental_features_use_one_batched_sqlite_upsert(tmp_path: Path) -> None:
    session_factory = create_session_factory(f"sqlite:///{tmp_path / 'batch.db'}")
    repository = SqlAlchemyAtlasFeatureRepository(session_factory)
    statements: list[str] = []

    def record_statement(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("INSERT INTO ATLAS_FEATURES "):
            statements.append(statement)

    engine = session_factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", record_statement)
    repository.apply_changes(
        metadata("2026-08-06"),
        [StoredFeature(make_feature(f"batch:{index}")) for index in range(10)],
        [],
    )
    event.remove(engine, "before_cursor_execute", record_statement)

    assert len(statements) == 1
    assert repository.count_features(dataset_id="dataset") == 10
