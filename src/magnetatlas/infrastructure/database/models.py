"""SQLAlchemy persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from magnetatlas.infrastructure.database.base import Base


class ArchiveRecordRow(Base):
    """Persisted representation of a normalized archive record."""

    __tablename__ = "archive_records"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_record_source_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detail_type: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    date_text: Mapped[str | None] = mapped_column(String(255))
    place: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
