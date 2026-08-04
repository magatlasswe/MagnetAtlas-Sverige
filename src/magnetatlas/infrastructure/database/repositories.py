"""SQLAlchemy implementation of domain repositories."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.infrastructure.database.models import ArchiveRecordRow


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
