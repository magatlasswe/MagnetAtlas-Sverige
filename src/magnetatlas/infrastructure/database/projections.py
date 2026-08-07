"""Queryable SQLite projections derived from the source-neutral domain model."""

from __future__ import annotations

from typing import Any

from magnetatlas.application.features import SEARCHABLE_PROPERTY_KEYS
from magnetatlas.domain.features import AtlasFeature
from magnetatlas.domain.geography import BoundingBox, GeoPoint, LineString, Polygon


def _geometry_bounds(
    feature: AtlasFeature,
) -> tuple[float, float, float, float] | None:
    geometry = feature.geometry
    if geometry is None:
        return None
    if isinstance(geometry, GeoPoint):
        return (
            geometry.longitude,
            geometry.longitude,
            geometry.latitude,
            geometry.latitude,
        )
    if isinstance(geometry, BoundingBox):
        return geometry.west, geometry.east, geometry.south, geometry.north
    if isinstance(geometry, LineString):
        points = geometry.points
    elif isinstance(geometry, Polygon):
        points = tuple(point for ring in geometry.rings for point in ring)
    else:  # pragma: no cover - AtlasFeature currently exposes four geometry types.
        return None
    return (
        min(point.longitude for point in points),
        max(point.longitude for point in points),
        min(point.latitude for point in points),
        max(point.latitude for point in points),
    )


def feature_projection(feature: AtlasFeature) -> dict[str, Any]:
    """Project frequently queried values without changing the stored document."""
    property_values = (feature.properties.get(key) for key in SEARCHABLE_PROPERTY_KEYS)
    search_text = " ".join(
        value
        for value in (
            feature.title,
            feature.place,
            feature.feature_type,
            feature.description,
            feature.provenance.source_id,
            *property_values,
        )
        if isinstance(value, str) and value
    ).casefold()
    bounds = _geometry_bounds(feature)
    return {
        "source": feature.provenance.source,
        "source_id": feature.provenance.source_id,
        "feature_type": feature.feature_type,
        "search_text": search_text,
        "min_longitude": bounds[0] if bounds else None,
        "max_longitude": bounds[1] if bounds else None,
        "min_latitude": bounds[2] if bounds else None,
        "max_latitude": bounds[3] if bounds else None,
    }
