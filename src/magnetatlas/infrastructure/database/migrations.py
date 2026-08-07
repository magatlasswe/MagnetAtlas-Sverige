"""Small additive SQLite schema migrations for the local feature cache."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Engine

from magnetatlas.infrastructure.database.projections import feature_projection
from magnetatlas.infrastructure.features.json_repository import feature_from_document

SQLITE_SCHEMA_VERSION = 2
PROJECTION_COLUMNS = {
    "source": "TEXT",
    "source_id": "TEXT",
    "feature_type": "TEXT",
    "search_text": "TEXT",
    "min_longitude": "REAL",
    "max_longitude": "REAL",
    "min_latitude": "REAL",
    "max_latitude": "REAL",
}


def _document(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    if isinstance(value, dict):
        return value
    raise ValueError("AtlasFeature-dokumentet har ett ogiltigt format")


def migrate_sqlite(engine: Engine, *, batch_size: int = 500) -> None:
    """Add and backfill query indexes once without replacing user data."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        version = int(connection.exec_driver_sql("PRAGMA user_version").scalar() or 0)
        if version >= SQLITE_SCHEMA_VERSION:
            return
        existing = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(atlas_features)"
            ).fetchall()
        }
        for name, column_type in PROJECTION_COLUMNS.items():
            if name not in existing:
                connection.exec_driver_sql(
                    f'ALTER TABLE atlas_features ADD COLUMN "{name}" {column_type}'
                )

        last_id = 0
        while True:
            rows = connection.exec_driver_sql(
                "SELECT id, document FROM atlas_features "
                "WHERE id > ? ORDER BY id LIMIT ?",
                (last_id, batch_size),
            ).fetchall()
            if not rows:
                break
            updates = []
            for row_id, raw_document in rows:
                projection = feature_projection(
                    feature_from_document(_document(raw_document))
                )
                updates.append((*projection.values(), row_id))
            connection.exec_driver_sql(
                "UPDATE atlas_features SET source=?, source_id=?, feature_type=?, "
                "search_text=?, min_longitude=?, max_longitude=?, min_latitude=?, "
                "max_latitude=? WHERE id=?",
                updates,
            )
            last_id = int(rows[-1][0])

        statements = (
            "CREATE INDEX IF NOT EXISTS ix_atlas_features_dataset_id "
            "ON atlas_features(dataset_id)",
            "CREATE INDEX IF NOT EXISTS ix_atlas_features_feature_id "
            "ON atlas_features(feature_id)",
            "CREATE INDEX IF NOT EXISTS ix_atlas_features_dataset_source "
            "ON atlas_features(dataset_id, source)",
            "CREATE INDEX IF NOT EXISTS ix_atlas_features_dataset_source_id "
            "ON atlas_features(dataset_id, source_id)",
            "CREATE INDEX IF NOT EXISTS ix_atlas_features_dataset_type "
            "ON atlas_features(dataset_id, feature_type)",
            "CREATE INDEX IF NOT EXISTS ix_atlas_features_search_text "
            "ON atlas_features(search_text)",
            "CREATE VIRTUAL TABLE IF NOT EXISTS atlas_features_rtree USING rtree("
            "id, min_longitude, max_longitude, min_latitude, max_latitude)",
            "CREATE VIRTUAL TABLE IF NOT EXISTS atlas_features_fts USING fts5("
            "search_text, content='atlas_features', content_rowid='id')",
        )
        for statement in statements:
            connection.exec_driver_sql(statement)

        connection.exec_driver_sql(
            "INSERT OR REPLACE INTO atlas_features_rtree "
            "SELECT id, min_longitude, max_longitude, min_latitude, max_latitude "
            "FROM atlas_features WHERE min_longitude IS NOT NULL"
        )
        connection.exec_driver_sql(
            "INSERT INTO atlas_features_fts(atlas_features_fts) VALUES('rebuild')"
        )
        triggers = (
            "CREATE TRIGGER IF NOT EXISTS atlas_features_rtree_insert AFTER INSERT "
            "ON atlas_features WHEN new.min_longitude IS NOT NULL BEGIN "
            "INSERT OR REPLACE INTO atlas_features_rtree VALUES "
            "(new.id,new.min_longitude,new.max_longitude,"
            "new.min_latitude,new.max_latitude); END",
            "CREATE TRIGGER IF NOT EXISTS atlas_features_rtree_update AFTER UPDATE "
            "ON atlas_features BEGIN DELETE FROM atlas_features_rtree WHERE id=old.id; "
            "INSERT OR REPLACE INTO atlas_features_rtree "
            "SELECT new.id,new.min_longitude,new.max_longitude,"
            "new.min_latitude,new.max_latitude "
            "WHERE new.min_longitude IS NOT NULL; END",
            "CREATE TRIGGER IF NOT EXISTS atlas_features_rtree_delete AFTER DELETE "
            "ON atlas_features BEGIN DELETE FROM atlas_features_rtree "
            "WHERE id=old.id; END",
            "CREATE TRIGGER IF NOT EXISTS atlas_features_fts_insert AFTER INSERT ON "
            "atlas_features BEGIN INSERT INTO atlas_features_fts(rowid,search_text) "
            "VALUES(new.id,new.search_text); END",
            "CREATE TRIGGER IF NOT EXISTS atlas_features_fts_update AFTER UPDATE ON "
            "atlas_features BEGIN INSERT INTO atlas_features_fts"
            "(atlas_features_fts,rowid,search_text) "
            "VALUES('delete',old.id,old.search_text); "
            "INSERT INTO atlas_features_fts(rowid,search_text) "
            "VALUES(new.id,new.search_text); END",
            "CREATE TRIGGER IF NOT EXISTS atlas_features_fts_delete AFTER DELETE ON "
            "atlas_features BEGIN INSERT INTO atlas_features_fts"
            "(atlas_features_fts,rowid,search_text) "
            "VALUES('delete',old.id,old.search_text); END",
        )
        for trigger in triggers:
            connection.exec_driver_sql(trigger)
        connection.exec_driver_sql("ANALYZE")
        connection.exec_driver_sql(f"PRAGMA user_version={SQLITE_SCHEMA_VERSION}")
