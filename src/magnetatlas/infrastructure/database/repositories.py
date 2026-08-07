"""SQLAlchemy implementation of domain repositories."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from magnetatlas.domain.datasets import (
    DatasetInstance,
    DatasetScope,
    DatasetScopeKind,
    SourceDefinition,
)
from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.domain.repositories import DatasetMetadata, StoredFeature
from magnetatlas.infrastructure.database.models import (
    ArchiveRecordRow,
    AtlasFeatureRow,
    DatasetMetadataRow,
)
from magnetatlas.infrastructure.database.projections import feature_projection
from magnetatlas.infrastructure.features.json_repository import (
    feature_from_document,
    feature_to_document,
)


def _to_domain(row: ArchiveRecordRow) -> ArchiveRecord:
    return ArchiveRecord(
        id=row.id,
        source=row.source,
        source_id=row.source_id,
        title=row.title,
        object_type=row.object_type,
        detail_type=row.detail_type,
        description=row.description,
        date_text=row.date_text,
        place=row.place,
        source_url=row.source_url,
        raw_data=row.raw_data,
        fetched_at=row.fetched_at,
    )


class SqlAlchemyArchiveRecordRepository:
    """Store records idempotently using source identity."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save_many(self, records: Sequence[ArchiveRecord]) -> list[ArchiveRecord]:
        saved: list[ArchiveRecord] = []
        with self._session_factory() as session, session.begin():
            for record in records:
                row = session.scalar(
                    select(ArchiveRecordRow).where(
                        ArchiveRecordRow.source == record.source,
                        ArchiveRecordRow.source_id == record.source_id,
                    )
                )
                if row is None:
                    row = ArchiveRecordRow(
                        source=record.source,
                        source_id=record.source_id,
                        title=record.title,
                        object_type=record.object_type,
                        detail_type=record.detail_type,
                        description=record.description,
                        date_text=record.date_text,
                        place=record.place,
                        source_url=record.source_url,
                        raw_data=record.raw_data,
                        fetched_at=record.fetched_at,
                    )
                    session.add(row)
                else:
                    row.title = record.title
                    row.object_type = record.object_type
                    row.detail_type = record.detail_type
                    row.description = record.description
                    row.date_text = record.date_text
                    row.place = record.place
                    row.source_url = record.source_url
                    row.raw_data = record.raw_data
                    row.fetched_at = record.fetched_at
                session.flush()
                saved.append(_to_domain(row))
        return saved

    def list_all(self) -> list[ArchiveRecord]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ArchiveRecordRow).order_by(ArchiveRecordRow.id)
            ).all()
            return [_to_domain(row) for row in rows]


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _metadata_to_domain(row: DatasetMetadataRow) -> DatasetMetadata:
    kind = DatasetScopeKind(row.scope_kind)
    scope = (
        DatasetScope.bbox(
            BoundingBox(
                west=row.scope_west,
                south=row.scope_south,
                east=row.scope_east,
                north=row.scope_north,
            ),
            parent=(
                DatasetScope(
                    DatasetScopeKind(row.scope_parent_kind),
                    value=row.scope_parent_value,
                )
                if row.scope_parent_kind is not None
                else None
            ),
        )
        if kind is DatasetScopeKind.BBOX
        and row.scope_west is not None
        and row.scope_south is not None
        and row.scope_east is not None
        and row.scope_north is not None
        else DatasetScope(kind, value=row.scope_value)
    )
    return DatasetMetadata(
        instance=DatasetInstance(
            dataset_id=row.dataset_id,
            source=SourceDefinition(row.source_id, row.source_name),
            scope=scope,
        ),
        schema_version=row.schema_version,
        base_imported_at=_aware(row.base_imported_at),
        sync_marker=row.sync_marker,
        cache_valid_until=_aware(row.cache_valid_until),
    )


class SqlAlchemyAtlasFeatureRepository:
    """Persist source-neutral feature datasets with atomic state changes."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _set_metadata(
        session: Session, metadata: DatasetMetadata, *, activate: bool = False
    ) -> None:
        instance = metadata.instance
        scope = instance.scope
        if activate:
            session.execute(
                update(DatasetMetadataRow)
                .where(DatasetMetadataRow.source_id == instance.source.source_id)
                .values(is_active=False)
            )
        row = session.get(DatasetMetadataRow, metadata.dataset_id)
        if row is None:
            row = DatasetMetadataRow(dataset_id=metadata.dataset_id)
            session.add(row)
            row.is_active = activate
        elif activate:
            row.is_active = True
        row.source_id = instance.source.source_id
        row.source_name = instance.source.display_name
        row.scope_kind = scope.kind.value
        row.scope_value = scope.value
        row.scope_west = scope.bounds.west if scope.bounds else None
        row.scope_south = scope.bounds.south if scope.bounds else None
        row.scope_east = scope.bounds.east if scope.bounds else None
        row.scope_north = scope.bounds.north if scope.bounds else None
        row.scope_parent_kind = (
            scope.parent_kind.value if scope.parent_kind is not None else None
        )
        row.scope_parent_value = scope.parent_value
        row.schema_version = metadata.schema_version
        row.base_imported_at = metadata.base_imported_at
        row.sync_marker = metadata.sync_marker
        row.cache_valid_until = metadata.cache_valid_until

    @staticmethod
    def _upsert(session: Session, dataset_id: str, stored: StoredFeature) -> None:
        feature_id = str(stored.feature.feature_id)
        row = session.scalar(
            select(AtlasFeatureRow).where(
                AtlasFeatureRow.dataset_id == dataset_id,
                AtlasFeatureRow.feature_id == feature_id,
            )
        )
        if row is not None and row.source_version == stored.version:
            return
        document = feature_to_document(stored.feature)
        projection = feature_projection(stored.feature)
        if row is None:
            session.add(
                AtlasFeatureRow(
                    dataset_id=dataset_id,
                    feature_id=feature_id,
                    source_version=stored.version,
                    document=document,
                    **projection,
                )
            )
            return
        row.source_version = stored.version
        row.document = document
        for name, value in projection.items():
            setattr(row, name, value)

    @staticmethod
    def _stored_row(dataset_id: str, stored: StoredFeature) -> dict[str, object]:
        return {
            "dataset_id": dataset_id,
            "feature_id": str(stored.feature.feature_id),
            "source_version": stored.version,
            "document": feature_to_document(stored.feature),
            **feature_projection(stored.feature),
        }

    @classmethod
    def _upsert_batch(
        cls,
        session: Session,
        dataset_id: str,
        features: Sequence[StoredFeature],
    ) -> None:
        if not features:
            return
        if session.bind is None or session.bind.dialect.name != "sqlite":
            for stored in features:
                cls._upsert(session, dataset_id, stored)
            return
        rows = [cls._stored_row(dataset_id, stored) for stored in features]
        statement = sqlite_insert(AtlasFeatureRow).values(rows)
        excluded = statement.excluded
        session.execute(
            statement.on_conflict_do_update(
                index_elements=("dataset_id", "feature_id"),
                set_={
                    "source_version": excluded.source_version,
                    "document": excluded.document,
                    "source": excluded.source,
                    "source_id": excluded.source_id,
                    "feature_type": excluded.feature_type,
                    "search_text": excluded.search_text,
                    "min_longitude": excluded.min_longitude,
                    "max_longitude": excluded.max_longitude,
                    "min_latitude": excluded.min_latitude,
                    "max_latitude": excluded.max_latitude,
                },
            )
        )

    def replace_dataset(
        self,
        metadata: DatasetMetadata,
        features: Sequence[StoredFeature],
    ) -> None:
        import_session = self.begin_dataset_replace(metadata)
        try:
            import_session.write_batch(features)
            import_session.commit()
        except BaseException:
            import_session.rollback()
            raise

    def begin_dataset_replace(
        self, metadata: DatasetMetadata
    ) -> SqlAlchemyDatasetImportSession:
        """Create an isolated staging dataset for an incremental base import."""
        return SqlAlchemyDatasetImportSession(self._session_factory, metadata)

    def apply_changes(
        self,
        metadata: DatasetMetadata,
        upserts: Sequence[StoredFeature],
        delete_source_ids: Sequence[str],
    ) -> None:
        with self._session_factory() as session, session.begin():
            if delete_source_ids:
                session.execute(
                    delete(AtlasFeatureRow).where(
                        AtlasFeatureRow.dataset_id == metadata.dataset_id,
                        AtlasFeatureRow.source_id.in_(delete_source_ids),
                    )
                )
            self._upsert_batch(session, metadata.dataset_id, upserts)
            self._set_metadata(session, metadata)

    def lookup(self, source_id: str, *, dataset_id: str) -> tuple[FeatureId, ...]:
        """Resolve all feature identities for one source identity."""
        with self._session_factory() as session:
            values = session.scalars(
                select(AtlasFeatureRow.feature_id).where(
                    AtlasFeatureRow.dataset_id == dataset_id,
                    AtlasFeatureRow.source_id == source_id,
                )
            ).all()
        return tuple(FeatureId(value) for value in values)

    def delete(self, source_ids: str | Sequence[str], *, dataset_id: str) -> int:
        """Delete a bounded batch by source identity without loading documents."""
        selected = (source_ids,) if isinstance(source_ids, str) else tuple(source_ids)
        if not selected:
            return 0
        with self._session_factory() as session, session.begin():
            result = session.execute(
                delete(AtlasFeatureRow).where(
                    AtlasFeatureRow.dataset_id == dataset_id,
                    AtlasFeatureRow.source_id.in_(selected),
                )
            )
            return result.rowcount or 0

    def list_features(self, *, dataset_id: str | None = None) -> list[AtlasFeature]:
        with self._session_factory() as session:
            statement = select(AtlasFeatureRow).order_by(AtlasFeatureRow.id)
            if dataset_id is not None:
                statement = statement.where(AtlasFeatureRow.dataset_id == dataset_id)
            rows = session.scalars(statement).all()
            return [feature_from_document(row.document) for row in rows]

    def search_features(
        self,
        query: str,
        *,
        dataset_id: str | None = None,
        limit: int = 100,
    ) -> list[AtlasFeature]:
        if limit < 1:
            raise ValueError("Sökgränsen måste vara minst 1")
        needle = query.strip().casefold()
        if not needle:
            return []
        matches: list[AtlasFeature] = []
        for feature in self.list_features(dataset_id=dataset_id):
            haystack = " ".join(
                value
                for value in (
                    feature.title,
                    feature.feature_type,
                    feature.description,
                    feature.place,
                )
                if value
            ).casefold()
            if needle in haystack:
                matches.append(feature)
                if len(matches) == limit:
                    break
        return matches

    def get_metadata(self, dataset_id: str) -> DatasetMetadata | None:
        with self._session_factory() as session:
            row = session.get(DatasetMetadataRow, dataset_id)
            return _metadata_to_domain(row) if row is not None else None

    def list_dataset_instances(self) -> tuple[DatasetInstance, ...]:
        """List imported dataset identities without materializing features."""
        with self._session_factory() as session:
            rows = session.scalars(
                select(DatasetMetadataRow).order_by(DatasetMetadataRow.dataset_id)
            ).all()
        return tuple(_metadata_to_domain(row).instance for row in rows)

    def get_active_instance(self, source_id: str) -> DatasetInstance | None:
        """Return the active imported instance for one source."""
        with self._session_factory() as session:
            row = session.scalar(
                select(DatasetMetadataRow).where(
                    DatasetMetadataRow.source_id == source_id,
                    DatasetMetadataRow.is_active.is_(True),
                )
            )
        return _metadata_to_domain(row).instance if row is not None else None

    def count_features(self, *, dataset_id: str | None = None) -> int:
        with self._session_factory() as session:
            statement = select(func.count()).select_from(AtlasFeatureRow)
            if dataset_id is not None:
                statement = statement.where(AtlasFeatureRow.dataset_id == dataset_id)
            return int(session.scalar(statement) or 0)

    def clear_dataset(self, dataset_id: str) -> int:
        with self._session_factory() as session, session.begin():
            result = session.execute(
                delete(AtlasFeatureRow).where(AtlasFeatureRow.dataset_id == dataset_id)
            )
            session.execute(
                delete(DatasetMetadataRow).where(
                    DatasetMetadataRow.dataset_id == dataset_id
                )
            )
            return result.rowcount or 0

    def clear_source(self, source_id: str) -> int:
        """Remove every local dataset instance belonging to one source."""
        with self._session_factory() as session, session.begin():
            dataset_ids = select(DatasetMetadataRow.dataset_id).where(
                DatasetMetadataRow.source_id == source_id
            )
            result = session.execute(
                delete(AtlasFeatureRow).where(
                    AtlasFeatureRow.dataset_id.in_(dataset_ids)
                )
            )
            session.execute(
                delete(DatasetMetadataRow).where(
                    DatasetMetadataRow.source_id == source_id
                )
            )
            return result.rowcount or 0


class SqlAlchemyDatasetImportSession:
    """Write batches to staging and expose them through one atomic activation."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        metadata: DatasetMetadata,
    ) -> None:
        self._session_factory = session_factory
        self._metadata = metadata
        self._staging_id = f"{metadata.dataset_id}::staging::{uuid4().hex}"
        self._finished = False
        prefix = f"{metadata.dataset_id}::staging::%"
        with self._session_factory() as session, session.begin():
            session.execute(
                delete(AtlasFeatureRow).where(AtlasFeatureRow.dataset_id.like(prefix))
            )

    def _ensure_open(self) -> None:
        if self._finished:
            raise RuntimeError("Importsessionen är redan avslutad")

    def write_batch(self, features: Sequence[StoredFeature]) -> None:
        """Persist one bounded batch without touching the active dataset."""
        self._ensure_open()
        if not features:
            return
        rows = [
            SqlAlchemyAtlasFeatureRepository._stored_row(self._staging_id, stored)
            for stored in features
        ]
        with self._session_factory() as session, session.begin():
            session.execute(insert(AtlasFeatureRow), rows)

    def commit(self) -> None:
        """Atomically replace the active dataset with completed staging rows."""
        self._ensure_open()
        with self._session_factory() as session, session.begin():
            session.execute(
                delete(AtlasFeatureRow).where(
                    AtlasFeatureRow.dataset_id == self._metadata.dataset_id
                )
            )
            session.execute(
                update(AtlasFeatureRow)
                .where(AtlasFeatureRow.dataset_id == self._staging_id)
                .values(dataset_id=self._metadata.dataset_id)
            )
            SqlAlchemyAtlasFeatureRepository._set_metadata(
                session, self._metadata, activate=True
            )
            session.execute(text("ANALYZE atlas_features"))
        self._finished = True

    def rollback(self) -> None:
        """Discard staging rows while preserving the active dataset."""
        if self._finished:
            return
        with self._session_factory() as session, session.begin():
            session.execute(
                delete(AtlasFeatureRow).where(
                    AtlasFeatureRow.dataset_id == self._staging_id
                )
            )
        self._finished = True
