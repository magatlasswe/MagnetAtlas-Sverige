"""Provider-independent domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ArchiveRecord:
    """A normalized record originating from an archival data source."""

    source: str
    source_id: str
    title: str
    object_type: str
    detail_type: str | None = None
    description: str | None = None
    date_text: str | None = None
    place: str | None = None
    source_url: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source får inte vara tom")
        if not self.source_id.strip():
            raise ValueError("source_id får inte vara tom")
        if not self.title.strip():
            raise ValueError("title får inte vara tom")
