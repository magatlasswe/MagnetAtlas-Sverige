"""Defensive local JSON adapter for normalized atlas features."""

from __future__ import annotations

import json
from datetime import date, datetime
from importlib import resources
from pathlib import Path
from typing import Any

from magnetatlas.domain.exceptions import FeatureDataError
from magnetatlas.domain.features import (
    AtlasFeature,
    Confidence,
    FeatureId,
    LicenseInfo,
    Provenance,
    TimeSpan,
)
from magnetatlas.domain.geography import (
    BoundingBox,
    Geometry,
    GeoPoint,
    LineString,
    Polygon,
)


def _object(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} måste vara ett objekt")
    return value


def _string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} måste vara en icke-tom sträng")
    return value


def _optional_string(data: dict[str, Any], field_name: str) -> str | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} måste vara en icke-tom sträng eller null")
    return value


def _number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} måste vara ett tal")
    return float(value)


def _coordinates(value: object, field_name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field_name} måste innehålla [longitud, latitud]")
    return _number(value[0], field_name), _number(value[1], field_name)


def _point(value: object, field_name: str) -> GeoPoint:
    longitude, latitude = _coordinates(value, field_name)
    return GeoPoint(longitude=longitude, latitude=latitude)


def _geometry(value: object) -> Geometry | None:
    if value is None:
        return None
    data = _object(value, "geometry")
    geometry_type = _string(data, "type")
    coordinates = data.get("coordinates")
    if geometry_type == "Point":
        return _point(coordinates, "geometry.coordinates")
    if geometry_type == "BoundingBox":
        if not isinstance(coordinates, list) or len(coordinates) != 4:
            raise ValueError("BoundingBox måste innehålla [west, south, east, north]")
        return BoundingBox(
            west=_number(coordinates[0], "west"),
            south=_number(coordinates[1], "south"),
            east=_number(coordinates[2], "east"),
            north=_number(coordinates[3], "north"),
        )
    if geometry_type == "LineString":
        if not isinstance(coordinates, list):
            raise ValueError("LineString coordinates måste vara en lista")
        return LineString(
            points=tuple(
                _point(point, f"LineString point {index}")
                for index, point in enumerate(coordinates)
            )
        )
    if geometry_type == "Polygon":
        if not isinstance(coordinates, list):
            raise ValueError("Polygon coordinates måste vara en lista")
        return Polygon(
            rings=tuple(
                (
                    tuple(
                        _point(point, f"Polygon ring {ring_index} point {point_index}")
                        for point_index, point in enumerate(ring)
                    )
                    if isinstance(ring, list)
                    else ()
                )
                for ring_index, ring in enumerate(coordinates)
            )
        )
    raise ValueError(f"Okänd geometry type: {geometry_type}")


def _confidence(value: object, field_name: str) -> Confidence:
    if value is None:
        return Confidence()
    data = _object(value, field_name)
    score = data.get("value")
    return Confidence(
        value=None if score is None else _number(score, f"{field_name}.value"),
        rationale=_optional_string(data, "rationale"),
    )


def _time_span(value: object) -> TimeSpan | None:
    if value is None:
        return None
    data = _object(value, "time_span")
    start_text = _optional_string(data, "start")
    end_text = _optional_string(data, "end")
    return TimeSpan(
        start=date.fromisoformat(start_text) if start_text else None,
        end=date.fromisoformat(end_text) if end_text else None,
        original_text=_optional_string(data, "original_text"),
        precision=_optional_string(data, "precision"),
        certainty=_confidence(data.get("certainty"), "time_span.certainty"),
    )


def _optional_bool(data: dict[str, Any], field_name: str) -> bool | None:
    value = data.get(field_name)
    if value is not None and not isinstance(value, bool):
        raise ValueError(f"{field_name} måste vara true, false eller null")
    return value


def _license(value: object) -> LicenseInfo | None:
    if value is None:
        return None
    data = _object(value, "license_info")
    return LicenseInfo(
        name=_string(data, "name"),
        url=_optional_string(data, "url"),
        attribution=_optional_string(data, "attribution"),
        usage_notes=_optional_string(data, "usage_notes"),
        requires_attribution=_optional_bool(data, "requires_attribution"),
        commercial_use_allowed=_optional_bool(data, "commercial_use_allowed"),
    )


def _provenance(value: object) -> Provenance:
    data = _object(value, "provenance")
    fetched_at = _string(data, "fetched_at").replace("Z", "+00:00")
    raw_data = data.get("raw_data", {})
    return Provenance(
        source=_string(data, "source"),
        source_id=_string(data, "source_id"),
        source_url=_optional_string(data, "source_url"),
        fetched_at=datetime.fromisoformat(fetched_at),
        license_info=_license(data.get("license_info")),
        raw_data=_object(raw_data, "provenance.raw_data"),
    )


def feature_from_document(data: dict[str, Any]) -> AtlasFeature:
    """Create a validated AtlasFeature from its local document representation."""
    relationships = data.get("relationships", [])
    if not isinstance(relationships, list):
        raise ValueError("relationships måste vara en lista")
    if any(not isinstance(value, str) or not value.strip() for value in relationships):
        raise ValueError("relationships får endast innehålla icke-tomma FeatureId")
    properties = data.get("properties", {})
    return AtlasFeature(
        feature_id=FeatureId(_string(data, "feature_id")),
        title=_string(data, "title"),
        feature_type=_string(data, "feature_type"),
        provenance=_provenance(data.get("provenance")),
        description=_optional_string(data, "description"),
        place=_optional_string(data, "place"),
        geometry=_geometry(data.get("geometry")),
        time_span=_time_span(data.get("time_span")),
        confidence=_confidence(data.get("confidence"), "confidence"),
        geometry_confidence=_confidence(
            data.get("geometry_confidence"), "geometry_confidence"
        ),
        properties=_object(properties, "properties"),
        relationships=tuple(FeatureId(value) for value in relationships),
    )


def _geometry_document(geometry: Geometry | None) -> dict[str, Any] | None:
    if geometry is None:
        return None
    if isinstance(geometry, GeoPoint):
        return {"type": "Point", "coordinates": [geometry.longitude, geometry.latitude]}
    if isinstance(geometry, BoundingBox):
        return {
            "type": "BoundingBox",
            "coordinates": [
                geometry.west,
                geometry.south,
                geometry.east,
                geometry.north,
            ],
        }
    if isinstance(geometry, LineString):
        return {
            "type": "LineString",
            "coordinates": [
                [point.longitude, point.latitude] for point in geometry.points
            ],
        }
    return {
        "type": "Polygon",
        "coordinates": [
            [[point.longitude, point.latitude] for point in ring]
            for ring in geometry.rings
        ],
    }


def _confidence_document(confidence: Confidence) -> dict[str, Any]:
    return {"value": confidence.value, "rationale": confidence.rationale}


def feature_to_document(feature: AtlasFeature) -> dict[str, Any]:
    """Serialize an AtlasFeature completely for local persistence."""
    license_info = feature.provenance.license_info
    time_span = feature.time_span
    return {
        "feature_id": str(feature.feature_id),
        "title": feature.title,
        "feature_type": feature.feature_type,
        "description": feature.description,
        "place": feature.place,
        "geometry": _geometry_document(feature.geometry),
        "time_span": (
            {
                "start": time_span.start.isoformat() if time_span.start else None,
                "end": time_span.end.isoformat() if time_span.end else None,
                "original_text": time_span.original_text,
                "precision": time_span.precision,
                "certainty": _confidence_document(time_span.certainty),
            }
            if time_span is not None
            else None
        ),
        "confidence": _confidence_document(feature.confidence),
        "geometry_confidence": _confidence_document(feature.geometry_confidence),
        "properties": feature.properties,
        "relationships": [str(item) for item in feature.relationships],
        "provenance": {
            "source": feature.provenance.source,
            "source_id": feature.provenance.source_id,
            "source_url": feature.provenance.source_url,
            "fetched_at": feature.provenance.fetched_at.isoformat(),
            "raw_data": feature.provenance.raw_data,
            "license_info": (
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
        },
    }


def load_features(path: Path) -> list[AtlasFeature]:
    """Load and validate a versioned local AtlasFeature JSON document."""
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        document = _object(payload, "dokumentet")
        if document.get("schema_version") != 1:
            raise ValueError("schema_version måste vara 1")
        items = document.get("features")
        if not isinstance(items, list):
            raise ValueError("features måste vara en lista")
        features = []
        for index, item in enumerate(items):
            try:
                features.append(
                    feature_from_document(_object(item, f"feature {index}"))
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Feature {index}: {exc}") from exc
        return features
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise FeatureDataError(
            f"Kunde inte läsa featuredata från {path}: {exc}"
        ) from exc


def load_demo_features() -> list[AtlasFeature]:
    """Load the bundled, explicitly synthetic demonstration dataset."""
    resource = resources.files("magnetatlas.data").joinpath("demo_features.json")
    with resources.as_file(resource) as path:
        return load_features(path)
