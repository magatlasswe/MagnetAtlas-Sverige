"""Map SGU GeoJSON records to source-neutral AtlasFeature objects."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from magnetatlas.domain.features import (
    AtlasFeature,
    Confidence,
    FeatureId,
    LicenseInfo,
    Provenance,
)
from magnetatlas.domain.geography import GeoPoint, LineString, Polygon

SGU_LICENSE = LicenseInfo(
    name="Creative Commons CC0 1.0",
    url="https://www.sgu.se/produkter-och-tjanster/geologiska-data/om-geologiska-data/licensvillkor/",
    attribution="Sveriges geologiska undersökning (SGU)",
    requires_attribution=False,
    commercial_use_allowed=True,
)


def _point(value: object) -> GeoPoint:
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError("SGU-geometrin saknar koordinater")
    longitude, latitude = value[:2]
    if isinstance(longitude, bool) or isinstance(latitude, bool):
        raise ValueError("SGU-koordinater måste vara tal")
    if not isinstance(longitude, int | float) or not isinstance(latitude, int | float):
        raise ValueError("SGU-koordinater måste vara tal")
    return GeoPoint(float(longitude), float(latitude))


def _geometries(value: object) -> list[GeoPoint | LineString | Polygon]:
    if not isinstance(value, dict):
        raise ValueError("SGU-posten saknar geometri")
    geometry_type = value.get("type")
    coordinates = value.get("coordinates")
    if geometry_type == "Point":
        return [_point(coordinates)]
    if geometry_type == "LineString" and isinstance(coordinates, list):
        return [LineString(tuple(_point(item) for item in coordinates))]
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return [
            Polygon(tuple(tuple(_point(item) for item in ring) for ring in coordinates))
        ]
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return [
            Polygon(tuple(tuple(_point(item) for item in ring) for ring in polygon))
            for polygon in coordinates
        ]
    raise ValueError(f"SGU-geometrin stöds inte: {geometry_type}")


def map_sgu_feature(
    raw: dict[str, Any],
    *,
    dataset_id: str,
    dataset_name: str,
    collection_id: str,
    source_url: str,
    fetched_at: datetime | None = None,
) -> tuple[AtlasFeature, ...]:
    """Map one official SGU GeoJSON feature, splitting multipolygons safely."""
    source_id = raw.get("id")
    properties = raw.get("properties")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("SGU-posten saknar ett stabilt id")
    if not isinstance(properties, dict):
        raise ValueError("SGU-posten saknar properties")
    geometries = _geometries(raw.get("geometry"))
    soil_name = properties.get("jg2_tx")
    title = (
        soil_name.strip()
        if isinstance(soil_name, str) and soil_name.strip()
        else dataset_name
    )
    retrieved = fetched_at or datetime.now(UTC)
    confidence = Confidence(
        rationale=(
            "Översiktlig SGU-kartering i skala 1:25 000-1:100 000; "
            "inte avsedd för detaljerad markbedömning."
        )
    )
    source_properties = {
        key: value
        for key, value in properties.items()
        if key
        in {
            "jg2",
            "jg2_tx",
            "kartering",
            "karttyp",
            "symbol",
            "objectid",
            "geom_area",
            "geom_length",
        }
        and value is not None
    }
    return tuple(
        AtlasFeature(
            feature_id=FeatureId(
                f"sgu:{dataset_id}:{source_id}"
                if len(geometries) == 1
                else f"sgu:{dataset_id}:{source_id}:geometry:{index + 1}"
            ),
            title=title,
            feature_type="jordart",
            description=f"{dataset_name}: {title}.",
            geometry=geometry,
            confidence=confidence,
            geometry_confidence=confidence,
            properties={
                "source_properties": {"sgu": source_properties},
                "sgu_dataset": dataset_id,
                "sgu_collection": collection_id,
            },
            provenance=Provenance(
                source="Sveriges geologiska undersökning (SGU)",
                source_id=source_id,
                source_url=f"{source_url}/{source_id}",
                fetched_at=retrieved,
                license_info=SGU_LICENSE,
                raw_data=raw,
            ),
        )
        for index, geometry in enumerate(geometries)
    )
