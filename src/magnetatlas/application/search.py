"""Archive search use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from magnetatlas.domain.collectors import (
    CollectionBatch,
    CollectionRequest,
    Collector,
)
from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.domain.repositories import ArchiveRecordRepository

# Compatibility name retained for integrations built against Sprint 1.
SourceSearchResult = CollectionBatch


class ArchiveSource(Protocol):
    """Search contract implemented by external source adapters."""

    def search(self, query: str, *, limit: int = 20) -> SourceSearchResult: ...


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Persisted records and the source's total number of matches."""

    records: list[ArchiveRecord]
    total_hits: int


class SearchService:
    """Search a source and persist normalized results."""

    def __init__(
        self,
        source: Collector | ArchiveSource,
        repository: ArchiveRecordRepository,
    ) -> None:
        self._source = source
        self._repository = repository

    def search(self, query: str, *, limit: int = 20) -> SearchResult:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Sökfrågan får inte vara tom")
        if not 1 <= limit <= 100:
            raise ValueError("Antal träffar måste vara mellan 1 och 100")

        request = CollectionRequest(query=normalized_query, limit=limit)
        collect = getattr(self._source, "collect", None)
        if callable(collect):
            source_result = collect(request)
        else:
            source_result = self._source.search(normalized_query, limit=limit)  # type: ignore[union-attr]
        saved = self._repository.save_many(source_result.records)
        return SearchResult(records=saved, total_hits=source_result.total_hits)
