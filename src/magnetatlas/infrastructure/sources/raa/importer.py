"""Small RAÄ command facades over the application SyncService."""

from __future__ import annotations

from magnetatlas.application.sync import CacheStatus, SyncResult, SyncService
from magnetatlas.domain.geography import BoundingBox


class RAAImporter:
    """Expose explicit RAÄ imports without owning synchronization policy."""

    def __init__(self, service: SyncService) -> None:
        self._service = service

    def run(
        self,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
    ) -> SyncResult:
        """Request an official base import through SyncService."""
        return self._service.base_import(
            county=county,
            municipality=municipality,
            bbox=bbox,
        )


class RAACache:
    """Command facade; SQLite and sync metadata remain the only cache."""

    def __init__(self, service: SyncService) -> None:
        self._service = service

    def status(self) -> CacheStatus:
        """Return local status without network access."""
        return self._service.status()

    def refresh(self) -> SyncResult:
        """Refresh according to SyncService policy."""
        return self._service.refresh(force=True)

    def clear(self) -> int:
        """Clear the local RAÄ dataset through SyncService."""
        return self._service.clear()
