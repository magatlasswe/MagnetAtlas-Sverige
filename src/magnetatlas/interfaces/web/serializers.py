"""JSON serializers for the local map interface."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any
from urllib.parse import urlencode

from magnetatlas.application.features import FeatureCatalog, feature_period
from magnetatlas.domain.features import AtlasFeature, Confidence, TimeSpan
from magnetatlas.domain.geography import BoundingBox, GeoPoint, LineString, Polygon


def _geometry(feature: AtlasFeature) -> dict[str, Any] | None:
    geometry = feature.geometry
    if geometry is None:
        return None
    if isinstance(geometry, GeoPoint):
        return {
            "type": "Point",
            "coordinates": [geometry.longitude, geometry.latitude],
        }
    if isinstance(geometry, BoundingBox):
        return {
            "type": "Polygon",
            "coordinates": [
                [
                    [geometry.west, geometry.south],
                    [geometry.east, geometry.south],
                    [geometry.east, geometry.north],
                    [geometry.west, geometry.north],
                    [geometry.west, geometry.south],
                ]
            ],
        }
    if isinstance(geometry, LineString):
        return {
            "type": "LineString",
            "coordinates": [
                [point.longitude, point.latitude] for point in geometry.points
            ],
        }
    if isinstance(geometry, Polygon):
        return {
            "type": "Polygon",
            "coordinates": [
                [[point.longitude, point.latitude] for point in ring]
                for ring in geometry.rings
            ],
        }
    raise TypeError(f"Geometritypen stöds inte: {type(geometry).__name__}")


def _confidence(confidence: Confidence) -> dict[str, object | None]:
    value = confidence.value
    if value is None:
        label = "Okänd"
    elif value < 0.34:
        label = "Låg"
    elif value < 0.67:
        label = "Medel"
    else:
        label = "Hög"
    return {"value": value, "label": label, "rationale": confidence.rationale}


def _date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _time_span(time_span: TimeSpan | None) -> dict[str, Any] | None:
    if time_span is None:
        return None
    return {
        "start": _date(time_span.start),
        "end": _date(time_span.end),
        "original_text": time_span.original_text,
        "precision": time_span.precision,
        "certainty": _confidence(time_span.certainty),
    }


def _navigation(
    feature: AtlasFeature, catalog: FeatureCatalog
) -> dict[str, Any] | None:
    target = catalog.navigation_target(feature.feature_id)
    if target is None:
        return None
    point = target.point
    query = urlencode({"from": "", "to": f"{point.latitude:.6f},{point.longitude:.6f}"})
    return {
        "longitude": point.longitude,
        "latitude": point.latitude,
        "approximate": target.approximate,
        "url": f"https://www.openstreetmap.org/directions?{query}",
    }


def serialize_feature(feature: AtlasFeature, catalog: FeatureCatalog) -> dict[str, Any]:
    """Serialize one feature without exposing provider raw data."""
    license_info = feature.provenance.license_info
    navigation = _navigation(feature, catalog)
    time_certainty = (
        feature.time_span.certainty.value if feature.time_span is not None else None
    )
    estimated = any(
        (
            navigation is not None and navigation["approximate"],
            feature.geometry_confidence.value is None,
            feature.geometry_confidence.value != 1.0,
            feature.confidence.value is None,
            time_certainty is None,
            time_certainty != 1.0,
        )
    )
    return {
        "type": "Feature",
        "id": str(feature.feature_id),
        "geometry": _geometry(feature),
        "properties": {
            "feature_id": str(feature.feature_id),
            "title": feature.title,
            "feature_type": feature.feature_type,
            "description": feature.description,
            "place": feature.place,
            "time_span": _time_span(feature.time_span),
            "period": feature_period(feature),
            "confidence": _confidence(feature.confidence),
            "geometry_confidence": _confidence(feature.geometry_confidence),
            "source": {
                "name": feature.provenance.source,
                "id": feature.provenance.source_id,
                "url": feature.provenance.source_url,
            },
            "license": (
                {
                    "name": license_info.name,
                    "url": license_info.url,
                    "attribution": license_info.attribution,
                    "usage_notes": license_info.usage_notes,
                    "requires_attribution": license_info.requires_attribution,
                    "commercial_use_allowed": license_info.commercial_use_allowed,
                }
                if license_info is not None
                else None
            ),
            "relationships": [str(item) for item in feature.relationships],
            "navigation": navigation,
            "discovery": {
                "supporting_sources": [feature.provenance.source],
                "estimated": estimated,
                "data_source": feature.provenance.source,
            },
        },
    }


def serialize_feature_collection(
    catalog: FeatureCatalog,
    features: Iterable[AtlasFeature] | None = None,
) -> dict[str, Any]:
    """Serialize all local features as a GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": [
            serialize_feature(feature, catalog)
            for feature in (catalog.list_all() if features is None else features)
        ],
    }
