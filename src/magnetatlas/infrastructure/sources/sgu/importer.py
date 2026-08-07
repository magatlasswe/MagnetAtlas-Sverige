"""SGU import facade over the shared SyncService."""

from __future__ import annotations

from collections.abc import Callable

from magnetatlas.application.sync import SyncResult, SyncService
from magnetatlas.domain.geography import BoundingBox


class SGUImporter:
    """Expose explicit SGU base imports without owning persistence policy."""

    def __init__(self, service: SyncService) -> None:
        self._service = service

    def run(
        self,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> SyncResult:
        """Request an official SGU base import through SyncService."""
        return self._service.base_import(
            county=county,
            municipality=municipality,
            bbox=bbox,
            progress=progress,
        )
