"""Shared pytest fixtures."""

from datetime import UTC, datetime

import pytest

from magnetatlas.domain.models import ArchiveRecord


@pytest.fixture
def archive_record() -> ArchiveRecord:
    return ArchiveRecord(
        source="riksarkivet",
        source_id="record-1",
        title="Ritning över gammal bro",
        object_type="Record",
        detail_type="MapDrawing",
        description="Historisk ritning",
        date_text="1890",
        place="Uppsala",
        source_url="https://example.test/record-1",
        raw_data={"id": "record-1"},
        fetched_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    )
