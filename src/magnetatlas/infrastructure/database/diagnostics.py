"""Read-only production database diagnostics for CLI verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from magnetatlas.domain.datasets import DatasetInstance
from magnetatlas.infrastructure.database.models import (
    AtlasFeatureRow,
    DatasetMetadataRow,
)
from magnetatlas.infrastructure.database.repositories import _metadata_to_domain


@dataclass(frozen=True, slots=True)
class DatasetDiagnostic:
    """Persisted dataset state without materializing its features."""

    instance: DatasetInstance
    active: bool
    feature_count: int
    imported_at: datetime | None
    snapshot: str | None
    license_name: str | None


class SqlAlchemyDatabaseDiagnostics:
    """Inspect persisted dataset and schema state through bounded queries."""

    REQUIRED_TABLES = frozenset({"dataset_metadata", "atlas_features"})

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def datasets(self) -> tuple[DatasetDiagnostic, ...]:
        """List dataset metadata with authoritative persisted feature counts."""
        with self._session_factory() as session:
            counts = (
                select(
                    AtlasFeatureRow.dataset_id,
                    func.count(AtlasFeatureRow.id).label("feature_count"),
                )
                .group_by(AtlasFeatureRow.dataset_id)
                .subquery()
            )
            rows = session.execute(
                select(DatasetMetadataRow, counts.c.feature_count)
                .outerjoin(counts, counts.c.dataset_id == DatasetMetadataRow.dataset_id)
                .order_by(DatasetMetadataRow.dataset_id)
            ).all()
            result = []
            for metadata, feature_count in rows:
                feature = session.scalar(
                    select(AtlasFeatureRow)
                    .where(AtlasFeatureRow.dataset_id == metadata.dataset_id)
                    .order_by(AtlasFeatureRow.id)
                    .limit(1)
                )
                document = feature.document if feature is not None else {}
                provenance = _mapping(document).get("provenance")
                license_info = (
                    _mapping(provenance).get("license_info")
                    if provenance is not None
                    else None
                )
                result.append(
                    DatasetDiagnostic(
                        instance=_metadata_to_domain(metadata).instance,
                        active=metadata.is_active,
                        feature_count=int(feature_count or 0),
                        imported_at=_metadata_to_domain(metadata).base_imported_at,
                        snapshot=(
                            feature.source_version
                            if feature is not None and feature.source_version
                            else metadata.sync_marker
                        ),
                        license_name=_optional_text(
                            _mapping(license_info).get("name")
                            if license_info is not None
                            else None
                        ),
                    )
                )
            return tuple(result)

    def schema_status(self) -> tuple[bool, str]:
        """Verify required tables, columns, indexes, and SQLite integrity."""
        bind = self._session_factory.kw.get("bind")
        if bind is None:
            return False, "databasmotor saknas"
        inspector = inspect(bind)
        tables = set(inspector.get_table_names())
        missing = sorted(self.REQUIRED_TABLES - tables)
        if missing:
            return False, f"saknade tabeller: {', '.join(missing)}"
        metadata_columns = {
            column["name"] for column in inspector.get_columns("dataset_metadata")
        }
        required_columns = {"dataset_id", "source_id", "scope_kind", "is_active"}
        if absent := sorted(required_columns - metadata_columns):
            return False, f"saknade metadatafält: {', '.join(absent)}"
        with self._session_factory() as session:
            integrity = session.execute(text("PRAGMA quick_check")).scalar_one()
        return integrity == "ok", f"quick_check={integrity}"

    def staging_count(self) -> int:
        """Count incomplete database staging rows left by interrupted imports."""
        with self._session_factory() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(AtlasFeatureRow)
                    .where(AtlasFeatureRow.dataset_id.contains("::staging::"))
                )
                or 0
            )


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
