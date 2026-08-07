"""Normalize Ortnamn Nedladdning records into AtlasFeature."""

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
from magnetatlas.infrastructure.sources.raa.mapper import sweref99tm_to_wgs84

LANTMATERIET_LICENSE = LicenseInfo(
    name="Creative Commons Attribution 4.0",
    url="https://creativecommons.org/licenses/by/4.0/",
    attribution="Lantmäteriet",
    requires_attribution=True,
    commercial_use_allowed=True,
)


def _text(raw: dict[str, Any], *keys: str) -> str | None:
    normalized = {key.casefold(): value for key, value in raw.items()}
    for key in keys:
        value = normalized.get(key.casefold())
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int):
            return str(value)
    return None


def map_ortnamn_record(
    raw: dict[str, Any],
    *,
    source_url: str,
    dataset_version: str,
    fetched_at: datetime | None = None,
) -> AtlasFeature:
    """Map one official name point using its documented composite identity."""
    sequence = _text(raw, "lopnummer", "löpnummer", "id")
    language = _text(raw, "sprakkod", "språkkod", "sprak", "språk")
    name = _text(raw, "ortnamn", "namn", "text")
    x = raw.get("_x")
    y = raw.get("_y")
    if sequence is None or language is None or name is None:
        raise ValueError("Ortnamnsposten saknar löpnummer, språkkod eller namn")
    if not isinstance(x, int | float) or not isinstance(y, int | float):
        raise ValueError("Ortnamnsposten saknar punktgeometri")
    stable_id = f"{sequence}:{language.casefold()}"
    municipality = _text(raw, "kommunnamn", "kommun")
    county = _text(raw, "lansnamn", "länsnamn", "lan", "län")
    place = ", ".join(value for value in (municipality, county) if value) or None
    detail_type = _text(raw, "detaljtyp", "detaljtypkod", "namntyp")
    retrieved = fetched_at or datetime.now(UTC)
    source_properties = {
        key: value
        for key, value in raw.items()
        if not key.startswith("_") and value is not None
    }
    confidence = Confidence(
        rationale=(
            "Namnet är granskat och fastställt av Lantmäteriet; koordinaten är "
            "en kartografisk textinsättningspunkt och inte objektets exakta utbredning."
        )
    )
    return AtlasFeature(
        feature_id=FeatureId(f"lantmateriet:ortnamn:{stable_id}"),
        title=name,
        feature_type=detail_type or "ortnamn",
        description=f"Officiellt ortnamn ({language}).",
        place=place,
        geometry=sweref99tm_to_wgs84(float(x), float(y)),
        confidence=confidence,
        geometry_confidence=confidence,
        properties={
            "source_version": dataset_version,
            "source_properties": {"lantmateriet-ortnamn": source_properties},
            "lantmateriet_dataset": "ortnamn",
        },
        provenance=Provenance(
            source="Lantmäteriet - Ortnamn Nedladdning, vektor",
            source_id=stable_id,
            source_url=source_url,
            fetched_at=retrieved,
            license_info=LANTMATERIET_LICENSE,
            raw_data=raw,
        ),
    )
