"""Bounded read models for the local viewport-based web interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from magnetatlas.application.features import FeatureCatalog, FeatureSearchFilters
from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.geography import BoundingBox, GeoPoint, LineString, Polygon


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    """Small dataset status that never requires a full feature response."""

    count: int
    latest_import: datetime | None
    source: str | None
    status: str
    is_demo: bool = False


@dataclass(frozen=True, slots=True)
class ViewportResult:
    """Bounded features returned for one visible map extent."""

    features: tuple[AtlasFeature, ...]
    truncated: bool


class FeatureQuerySource(Protocol):
    """Source-neutral bounded queries consumed by the web interface."""

    def summary(self) -> DatasetSummary: ...

    def in_bounds(self, bounds: BoundingBox, *, limit: int) -> ViewportResult: ...

    def get(self, feature_id: FeatureId | str) -> AtlasFeature: ...

    def search(
        self,
        query: str,
        *,
        filters: FeatureSearchFilters,
        limit: int,
    ) -> tuple[AtlasFeature, ...]: ...


def intersects_bounds(feature: AtlasFeature, bounds: BoundingBox) -> bool:
    """Return whether a feature geometry intersects a WGS84 viewport."""
    geometry = feature.geometry
    if geometry is None:
        return False
    if isinstance(geometry, GeoPoint):
        return bounds.contains(geometry)
    if isinstance(geometry, LineString):
        points = geometry.points
    elif isinstance(geometry, Polygon):
        points = tuple(point for ring in geometry.rings for point in ring)
    else:
        return not (
            geometry.east < bounds.west
            or geometry.west > bounds.east
            or geometry.north < bounds.south
            or geometry.south > bounds.north
        )
    return not (
        max(point.longitude for point in points) < bounds.west
        or min(point.longitude for point in points) > bounds.east
        or max(point.latitude for point in points) < bounds.south
        or min(point.latitude for point in points) > bounds.north
    )


class CatalogFeatureQuerySource:
    """Bounded query adapter for small demo or explicit JSON datasets."""

    def __init__(self, features: list[AtlasFeature]) -> None:
        self._catalog = FeatureCatalog(features)
        selected = self._catalog.list_all()
        is_demo = bool(selected) and all(
            feature.properties.get("demo") is True for feature in selected
        )
        sources = sorted({feature.provenance.source for feature in selected})
        latest = max(
            (feature.provenance.fetched_at for feature in selected), default=None
        )
        self._summary = DatasetSummary(
            count=len(selected),
            latest_import=latest,
            source=", ".join(sources) if sources else None,
            status="Demo" if is_demo else "RAÄ" if selected else "Tom",
            is_demo=is_demo,
        )

    def summary(self) -> DatasetSummary:
        return self._summary

    def in_bounds(self, bounds: BoundingBox, *, limit: int) -> ViewportResult:
        matches: list[AtlasFeature] = []
        truncated = False
        for feature in self._catalog.list_all():
            if not intersects_bounds(feature, bounds):
                continue
            if len(matches) == limit:
                truncated = True
                break
            matches.append(feature)
        return ViewportResult(tuple(matches), truncated)

    def get(self, feature_id: FeatureId | str) -> AtlasFeature:
        return self._catalog.get(feature_id)

    def search(
        self,
        query: str,
        *,
        filters: FeatureSearchFilters,
        limit: int,
    ) -> tuple[AtlasFeature, ...]:
        return tuple(self._catalog.search(query, filters=filters, limit=limit))
