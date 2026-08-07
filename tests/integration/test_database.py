"""SQLite repository integration tests."""

import json
import sqlite3
from pathlib import Path

from magnetatlas.domain.features import AtlasFeature, FeatureId, Provenance
from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyArchiveRecordRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory
from magnetatlas.infrastructure.features.json_repository import feature_to_document


def test_repository_upserts_by_source_identity(
    tmp_path: Path,
    archive_record: ArchiveRecord,
) -> None:
    repository = SqlAlchemyArchiveRecordRepository(
        create_session_factory(f"sqlite:///{tmp_path / 'test.db'}")
    )

    first = repository.save_many([archive_record])
    updated = ArchiveRecord(
        source=archive_record.source,
        source_id=archive_record.source_id,
        title="Uppdaterad titel",
        object_type=archive_record.object_type,
    )
    second = repository.save_many([updated])

    records = repository.list_all()
    assert first[0].id == second[0].id
    assert len(records) == 1
    assert records[0].title == "Uppdaterad titel"


def test_legacy_feature_table_is_backfilled_and_indexed(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    feature = AtlasFeature(
        feature_id=FeatureId("legacy:1"),
        title="Historisk bro",
        feature_type="bro",
        provenance=Provenance(source="official", source_id="source-1"),
    )
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE atlas_features (id INTEGER PRIMARY KEY, dataset_id TEXT "
        "NOT NULL, feature_id TEXT NOT NULL, source_version TEXT, document JSON "
        "NOT NULL, UNIQUE(dataset_id, feature_id))"
    )
    connection.execute(
        "INSERT INTO atlas_features(dataset_id,feature_id,document) VALUES(?,?,?)",
        ("dataset", "legacy:1", json.dumps(feature_to_document(feature))),
    )
    connection.commit()
    connection.close()

    create_session_factory(f"sqlite:///{path}")

    connection = sqlite3.connect(path)
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(atlas_features)")
    }
    indexes = {
        row[1] for row in connection.execute("PRAGMA index_list(atlas_features)")
    }
    projection = connection.execute(
        "SELECT source,source_id,feature_type,search_text FROM atlas_features"
    ).fetchone()
    assert {"source", "source_id", "feature_type", "search_text"} <= columns
    assert {
        "ix_atlas_features_feature_id",
        "ix_atlas_features_dataset_source",
        "ix_atlas_features_dataset_source_id",
        "ix_atlas_features_dataset_type",
        "ix_atlas_features_search_text",
    } <= indexes
    assert projection == ("official", "source-1", "bro", "historisk bro bro source-1")
    assert (
        connection.execute("SELECT count(*) FROM atlas_features_fts").fetchone()[0] == 1
    )
    connection.close()


def test_legacy_dataset_metadata_gains_source_scope_and_active_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy-metadata.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE dataset_metadata (dataset_id TEXT PRIMARY KEY, "
        "schema_version TEXT NOT NULL, base_imported_at DATETIME, "
        "sync_marker TEXT, cache_valid_until DATETIME)"
    )
    connection.execute(
        "INSERT INTO dataset_metadata(dataset_id,schema_version) VALUES(?,?)",
        ("raa-kmr", "3.0"),
    )
    connection.commit()
    connection.close()

    create_session_factory(f"sqlite:///{path}")

    connection = sqlite3.connect(path)
    migrated = connection.execute(
        "SELECT source_id,source_name,scope_kind,scope_value,is_active "
        "FROM dataset_metadata WHERE dataset_id='raa-kmr'"
    ).fetchone()
    assert migrated == (
        "raa-kmr",
        "RAÄ Kulturmiljöregistret",
        "country",
        "sweden",
        1,
    )
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    connection.close()
