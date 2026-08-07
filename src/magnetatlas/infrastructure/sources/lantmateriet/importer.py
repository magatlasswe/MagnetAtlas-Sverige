"""Lantmäteriet import facade over the shared SyncService."""

from __future__ import annotations

from collections.abc import Callable

from magnetatlas.application.sync import SyncResult, SyncService
from magnetatlas.domain.geography import BoundingBox


class LantmaterietImporter:
    """Expose explicit snapshot imports without persistence concerns."""

    def __init__(self, service: SyncService) -> None:
        self._service = service

    def run(
        self,
        *,
        bbox: BoundingBox | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> SyncResult:
        """Import the selected official Lantmäteriet snapshot."""
        return self._service.base_import(bbox=bbox, progress=progress)
