"""JSON serializers for the local map interface."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any
from urllib.parse import urlencode

from magnetatlas.application.feature_queries import DatasetSummary, ViewportResult
from magnetatlas.application.features import (
    FeatureCatalog,
    feature_period,
    navigation_target,
)
from magnetatlas.domain.evidence import Evidence, EvidenceReport, EvidenceSource
from magnetatlas.domain.evidence_rules import EvidenceCategory, RuleMetadata
from magnetatlas.domain.features import AtlasFeature, Confidence, TimeSpan
from magnetatlas.domain.geography import BoundingBox, GeoPoint, LineString, Polygon
from magnetatlas.domain.map_layers import ComposedLayer


def serialize_rule_metadata(metadata: RuleMetadata) -> dict[str, Any]:
    """Serialize only the public contract of an evidence rule."""
    return {
        "id": metadata.id,
        "version": str(metadata.version),
        "category": metadata.category.value,
        "title": metadata.title,
        "description": metadata.description,
        "provider_support": sorted(metadata.provider_support),
        "dataset_support": sorted(metadata.dataset_support),
        "evidence_type": metadata.evidence_type.value,
        "enabled": metadata.enabled,
        "created_at": metadata.created_at.isoformat(),
    }


def serialize_evidence_category(category: EvidenceCategory) -> dict[str, str]:
    """Serialize one stable category identifier and display name."""
    return {"id": category.value, "name": category.name.replace("_", " ").title()}


def serialize_layer(layer: ComposedLayer) -> dict[str, Any]:
    """Serialize one source-neutral composed map layer."""
    definition = layer.definition
    return {
        "id": definition.id,
        "name": definition.name,
        "description": layer.description,
        "provider": definition.provider,
        "dataset": definition.dataset,
        "layer_type": definition.layer_type.value,
        "geometry_type": definition.geometry_type,
        "render_mode": definition.render_mode.value,
        "visible": layer.visible,
        "opacity": layer.opacity,
        "z_index": definition.z_index,
        "icon": definition.icon,
        "legend": [
            {"label": item.label, "color": item.color} for item in definition.legend
        ],
        "attribution": definition.attribution,
        "license": definition.license,
        "source": definition.source,
        "min_zoom": definition.min_zoom,
        "max_zoom": definition.max_zoom,
        "default_enabled": definition.default_enabled,
        "category": layer.category,
        "enabled": layer.enabled,
        "supported": layer.supported,
        # Compatibility aliases keep the existing generic panel contract stable.
        "default_visibility": definition.default_enabled,
        "active": layer.visible,
    }


def _evidence_source(source: EvidenceSource) -> dict[str, Any]:
    license_info = source.license
    return {
        "provider": source.provider,
        "dataset": source.dataset,
        "snapshot": source.snapshot,
        "source_url": source.source_url,
        "provenance": {
            "source": source.provenance.source,
            "source_id": source.provenance.source_id,
            "source_url": source.provenance.source_url,
            "fetched_at": source.provenance.fetched_at.isoformat(),
        },
        "license": (
            {
                "name": license_info.name,
                "url": license_info.url,
                "attribution": license_info.attribution,
            }
            if license_info is not None
            else None
        ),
    }


def serialize_evidence(evidence: Evidence) -> dict[str, Any]:
    """Serialize traceable evidence without exposing provider raw data."""
    return {
        "id": evidence.id,
        "type": evidence.type.value,
        **_evidence_source(evidence.source),
        "feature_id": str(evidence.feature_id),
        "geometry": _geometry_value(evidence.geometry),
        "created_at": evidence.created_at.isoformat(),
        "confidence": _confidence(evidence.confidence),
        "strength": evidence.strength.value,
        "explanation": evidence.explanation,
        "rule_id": evidence.rule_id,
    }


def serialize_evidence_report(report: EvidenceReport) -> dict[str, Any]:
    """Serialize a deterministic EvidenceReport for API and future consumers."""
    return {
        "area": report.area,
        "bbox": {
            "west": report.bbox.west,
            "south": report.bbox.south,
            "east": report.bbox.east,
            "north": report.bbox.north,
        },
        "created_at": report.created_at.isoformat(),
        "datasets": list(report.datasets),
        "evidence_count": report.evidence_count,
        "summary": report.summary,
        "confidence": report.confidence.value,
        "provenance": [_evidence_source(item) for item in report.provenance],
        "evidence": [serialize_evidence(item) for item in report.evidence.items],
    }


def _geometry_value(geometry: object) -> dict[str, Any] | None:
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


def _geometry(feature: AtlasFeature) -> dict[str, Any] | None:
    return _geometry_value(feature.geometry)


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


def _navigation(feature: AtlasFeature) -> dict[str, Any] | None:
    target = navigation_target(feature)
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


def _source_properties(feature: AtlasFeature) -> dict[str, Any]:
    value = feature.properties.get("source_properties")
    if not isinstance(value, dict):
        return {}
    return {
        namespace: properties
        for namespace, properties in value.items()
        if isinstance(namespace, str) and isinstance(properties, dict)
    }


def serialize_feature(
    feature: AtlasFeature, catalog: FeatureCatalog | None = None
) -> dict[str, Any]:
    """Serialize one feature without exposing provider raw data."""
    license_info = feature.provenance.license_info
    navigation = _navigation(feature)
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
            "provenance": {
                "source": feature.provenance.source,
                "source_id": feature.provenance.source_id,
                "source_url": feature.provenance.source_url,
                "fetched_at": feature.provenance.fetched_at.isoformat(),
            },
            "source_properties": _source_properties(feature),
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


def serialize_map_feature(feature: AtlasFeature) -> dict[str, Any]:
    """Serialize only properties required for map rendering and compact popups."""
    return {
        "type": "Feature",
        "id": str(feature.feature_id),
        "geometry": _geometry(feature),
        "properties": {
            "feature_id": str(feature.feature_id),
            "title": feature.title,
            "feature_type": feature.feature_type,
            "place": feature.place,
            "source": {
                "name": feature.provenance.source,
                "id": feature.provenance.source_id,
            },
            "navigation": _navigation(feature),
        },
    }


def serialize_dataset_summary(summary: DatasetSummary) -> dict[str, Any]:
    """Serialize dataset status independently from map features."""
    return {
        "count": summary.count,
        "latest_import": (
            summary.latest_import.isoformat() if summary.latest_import else None
        ),
        "source": summary.source,
        "status": summary.status,
        "is_demo": summary.is_demo,
    }


def serialize_viewport(result: ViewportResult) -> dict[str, Any]:
    """Serialize one bounded viewport response as compact GeoJSON."""
    return {
        "type": "FeatureCollection",
        "summary": {
            "count": len(result.features),
            "truncated": result.truncated,
        },
        "features": [serialize_map_feature(feature) for feature in result.features],
    }


def serialize_search_results(features: Iterable[AtlasFeature]) -> dict[str, Any]:
    """Serialize one already bounded search result."""
    selected = tuple(features)
    return {
        "type": "FeatureCollection",
        "summary": {"count": len(selected), "truncated": False},
        "features": [serialize_feature(feature) for feature in selected],
    }


def serialize_feature_collection(
    catalog: FeatureCatalog,
    features: Iterable[AtlasFeature] | None = None,
) -> dict[str, Any]:
    """Serialize all local features as a GeoJSON FeatureCollection."""
    selected = tuple(catalog.list_all() if features is None else features)
    is_demo = bool(selected) and all(
        feature.properties.get("demo") is True for feature in selected
    )
    sources = sorted({feature.provenance.source for feature in selected})
    latest_import = max(
        (feature.provenance.fetched_at for feature in selected), default=None
    )
    return {
        "type": "FeatureCollection",
        "is_demo": is_demo,
        "summary": {
            "count": len(selected),
            "latest_import": latest_import.isoformat() if latest_import else None,
            "source": ", ".join(sources) if sources else None,
            "status": "Demo" if is_demo else "Officiell" if selected else "Tom",
        },
        "features": [serialize_feature(feature, catalog) for feature in selected],
    }
