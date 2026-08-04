"""Persistence contracts owned by the domain layer."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from magnetatlas.domain.models import ArchiveRecord


class ArchiveRecordRepository(Protocol):
    """Storage contract for normalized archive records."""

    def save_many(self, records: Sequence[ArchiveRecord]) -> list[ArchiveRecord]: ...

    def list_all(self) -> list[ArchiveRecord]: ...
