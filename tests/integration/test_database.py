"""SQLite repository integration tests."""

from pathlib import Path

from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyArchiveRecordRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory


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
