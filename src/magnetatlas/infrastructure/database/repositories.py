"""SQLAlchemy implementation of domain repositories."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.domain.repositories import DatasetMetadata, StoredFeature
from magnetatlas.infrastructure.database.models import (
    ArchiveRecordRow,
    AtlasFeatureRow,
    DatasetMetadataRow,
)
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
    return DatasetMetadata(
        dataset_id=row.dataset_id,
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
    def _set_metadata(session: Session, metadata: DatasetMetadata) -> None:
        row = session.get(DatasetMetadataRow, metadata.dataset_id)
        if row is None:
            row = DatasetMetadataRow(dataset_id=metadata.dataset_id)
            session.add(row)
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
        if row is None:
            session.add(
                AtlasFeatureRow(
                    dataset_id=dataset_id,
                    feature_id=feature_id,
                    source_version=stored.version,
                    document=document,
                )
            )
            return
        row.source_version = stored.version
        row.document = document

    def replace_dataset(
        self,
        metadata: DatasetMetadata,
        features: Sequence[StoredFeature],
    ) -> None:
        with self._session_factory() as session, session.begin():
            session.execute(
                delete(AtlasFeatureRow).where(
                    AtlasFeatureRow.dataset_id == metadata.dataset_id
                )
            )
            for stored in features:
                self._upsert(session, metadata.dataset_id, stored)
            self._set_metadata(session, metadata)

    def apply_changes(
        self,
        metadata: DatasetMetadata,
        upserts: Sequence[StoredFeature],
        deletes: Sequence[FeatureId],
    ) -> None:
        with self._session_factory() as session, session.begin():
            if deletes:
                session.execute(
                    delete(AtlasFeatureRow).where(
                        AtlasFeatureRow.dataset_id == metadata.dataset_id,
                        AtlasFeatureRow.feature_id.in_(str(item) for item in deletes),
                    )
                )
            for stored in upserts:
                self._upsert(session, metadata.dataset_id, stored)
            self._set_metadata(session, metadata)

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
