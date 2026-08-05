"""Normalize RAÄ Kulturmiljöregistret records into AtlasFeature."""

from __future__ import annotations

from datetime import UTC, datetime
from math import cos, degrees, radians, sin, sqrt, tan
from typing import Any

from magnetatlas.domain.features import (
    AtlasFeature,
    Confidence,
    FeatureId,
    LicenseInfo,
    Provenance,
    TimeSpan,
)
from magnetatlas.domain.geography import Geometry, GeoPoint, LineString, Polygon

SOURCE_NAME = "Riksantikvarieämbetets Kulturmiljöregister"
LICENSE = LicenseInfo(
    name="CC0 1.0",
    url="https://creativecommons.org/publicdomain/zero/1.0/",
    attribution="Riksantikvarieämbetets Kulturmiljöregister (KMR)",
    usage_notes="Ange gärna källa och hämtningsdatum vid vidare spridning.",
    requires_attribution=False,
    commercial_use_allowed=True,
)


def sweref99tm_to_wgs84(easting: float, northing: float) -> GeoPoint:
    """Convert EPSG:3006 coordinates to WGS84 without a GIS dependency."""
    axis = 6_378_137.0
    flattening = 1.0 / 298.257222101
    central_meridian = radians(15.0)
    scale = 0.9996
    false_easting = 500_000.0
    eccentricity_squared = flattening * (2.0 - flattening)
    eccentricity_prime_squared = eccentricity_squared / (1.0 - eccentricity_squared)
    meridional_arc = northing / scale
    mu = meridional_arc / (
        axis
        * (
            1.0
            - eccentricity_squared / 4.0
            - 3.0 * eccentricity_squared**2 / 64.0
            - 5.0 * eccentricity_squared**3 / 256.0
        )
    )
    e1 = (1.0 - sqrt(1.0 - eccentricity_squared)) / (
        1.0 + sqrt(1.0 - eccentricity_squared)
    )
    footprint = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * sin(2.0 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * sin(4.0 * mu)
        + 151.0 * e1**3 / 96.0 * sin(6.0 * mu)
        + 1097.0 * e1**4 / 512.0 * sin(8.0 * mu)
    )
    sin_footprint = sin(footprint)
    cos_footprint = cos(footprint)
    tangent = tan(footprint)
    curvature = axis / sqrt(1.0 - eccentricity_squared * sin_footprint * sin_footprint)
    radius = (
        axis
        * (1.0 - eccentricity_squared)
        / (1.0 - eccentricity_squared * sin_footprint * sin_footprint) ** 1.5
    )
    tangent_squared = tangent * tangent
    c = eccentricity_prime_squared * cos_footprint * cos_footprint
    d = (easting - false_easting) / (curvature * scale)
    latitude = footprint - (curvature * tangent / radius) * (
        d**2 / 2.0
        - (
            5.0
            + 3.0 * tangent_squared
            + 10.0 * c
            - 4.0 * c**2
            - 9.0 * eccentricity_prime_squared
        )
        * d**4
        / 24.0
        + (
            61.0
            + 90.0 * tangent_squared
            + 298.0 * c
            + 45.0 * tangent_squared**2
            - 252.0 * eccentricity_prime_squared
            - 3.0 * c**2
        )
        * d**6
        / 720.0
    )
    longitude = (
        central_meridian
        + (
            d
            - (1.0 + 2.0 * tangent_squared + c) * d**3 / 6.0
            + (
                5.0
                - 2.0 * c
                + 28.0 * tangent_squared
                - 3.0 * c**2
                + 8.0 * eccentricity_prime_squared
                + 24.0 * tangent_squared**2
            )
            * d**5
            / 120.0
        )
        / cos_footprint
    )
    return GeoPoint(
        longitude=degrees(longitude),
        latitude=degrees(latitude),
    )


def _name(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        nested = value.get("namn")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _string(raw: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _point(coordinates: object) -> GeoPoint:
    if not isinstance(coordinates, list | tuple) or len(coordinates) < 2:
        raise ValueError("RAÄ-punkt saknar giltiga koordinater")
    x, y = coordinates[:2]
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int | float)
        or not isinstance(y, int | float)
    ):
        raise ValueError("RAÄ-koordinater måste vara tal")
    return sweref99tm_to_wgs84(float(x), float(y))


def _simple_geometry(data: dict[str, Any]) -> Geometry:
    geometry_type = data.get("type")
    coordinates = data.get("coordinates")
    if geometry_type == "Point":
        return _point(coordinates)
    if geometry_type == "LineString" and isinstance(coordinates, list):
        return LineString(tuple(_point(item) for item in coordinates))
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return Polygon(
            tuple(tuple(_point(item) for item in ring) for ring in coordinates)
        )
    raise ValueError(f"RAÄ-geometrin stöds inte: {geometry_type}")


def _geometry_documents(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    if value.get("type") == "FeatureCollection":
        features = value.get("features")
        if not isinstance(features, list):
            return []
        documents = []
        for feature in features:
            if isinstance(feature, dict) and isinstance(feature.get("geometry"), dict):
                documents.extend(_geometry_documents(feature["geometry"]))
        return documents
    geometry_type = value.get("type")
    coordinates = value.get("coordinates")
    if geometry_type == "MultiPoint" and isinstance(coordinates, list):
        return [{"type": "Point", "coordinates": item} for item in coordinates]
    if geometry_type == "MultiLineString" and isinstance(coordinates, list):
        return [{"type": "LineString", "coordinates": item} for item in coordinates]
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return [{"type": "Polygon", "coordinates": item} for item in coordinates]
    return [value]


def map_raa_record(
    raw: dict[str, Any],
    *,
    fetched_at: datetime | None = None,
) -> list[AtlasFeature]:
    """Map one documented RAÄ record, splitting unsupported multi-geometries."""
    source_id = _string(raw, "id", "lamning_uuid")
    number = _string(raw, "lamningsnummer")
    feature_type = _name(raw.get("lamningstyp")) or _string(raw, "lamningstyp")
    if source_id is None or number is None or feature_type is None:
        raise ValueError("RAÄ-posten saknar id, lämningsnummer eller lämningstyp")
    title = _string(raw, "namn", "lamningsnamn") or number
    description = _string(raw, "beskrivning")
    counties = raw.get("lan")
    municipalities = raw.get("kommun")
    place_names: list[str] = []
    for values in (counties, municipalities):
        if isinstance(values, list):
            place_names.extend(name for item in values if (name := _name(item)))
        elif (name := _name(values)) is not None:
            place_names.append(name)
    place = ", ".join(dict.fromkeys(place_names)) or None
    assessment = _name(raw.get("antikvariskBedomning")) or _string(
        raw, "antikvariskbedomning"
    )
    status = _name(raw.get("aktualitetstatus")) or _string(raw, "aktualitetstatus")
    quality = _name(raw.get("inmatningskvalitet")) or _string(raw, "inmatningskvalitet")
    source_url = _string(raw, "url")
    publication = _string(raw, "publiceringsdatum", "senast_publicerad")
    dating = _string(raw, "datering")
    geometry_value = raw.get("geometri") or raw.get("geometry")
    documents = _geometry_documents(geometry_value)
    geometries = [_simple_geometry(item) for item in documents] if documents else [None]
    retrieved = fetched_at or datetime.now(UTC)
    version = raw.get("version")
    update_types = raw.get("uppdateringstyp")
    normalized_updates = (
        [item for item in update_types if isinstance(item, str)]
        if isinstance(update_types, list)
        else []
    )
    properties = {
        "raa_id": source_id,
        "lamningsnummer": number,
        "category": feature_type,
        "antikvarisk_bedomning": assessment,
        "senast_uppdaterad": publication,
        "source_version": str(version) if version is not None else publication,
        "aktualitetstatus": status,
        "definition_av_kvalitet": _string(raw, "definition_av_kvalitet"),
        "lagesosakerhet_i_meter": raw.get("lagesosakerhet_i_meter"),
        "update_types": normalized_updates,
        "deleted": "UTGAR" in normalized_updates,
    }
    return [
        AtlasFeature(
            feature_id=FeatureId(
                f"raa:{source_id}"
                if len(geometries) == 1
                else f"raa:{source_id}:geometry:{index + 1}"
            ),
            title=title,
            feature_type=feature_type,
            description=description,
            place=place,
            geometry=geometry,
            time_span=TimeSpan(original_text=dating) if dating else None,
            confidence=Confidence(rationale=status),
            geometry_confidence=Confidence(rationale=quality),
            properties={
                key: value for key, value in properties.items() if value is not None
            },
            provenance=Provenance(
                source=SOURCE_NAME,
                source_id=source_id,
                source_url=source_url,
                fetched_at=retrieved,
                license_info=LICENSE,
                raw_data=raw,
            ),
        )
        for index, geometry in enumerate(geometries)
    ]
