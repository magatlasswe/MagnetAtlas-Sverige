"""Shared domain model for geographical and historical features."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from magnetatlas.domain.geography import Geometry


@dataclass(frozen=True, slots=True)
class FeatureId:
    """Stable internal identity for an atlas feature."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("FeatureId får inte vara tomt")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Confidence:
    """An optional normalized confidence score with an explanation."""

    value: float | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError("Confidence måste vara mellan 0 och 1")
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("Confidence-rationale får inte vara tom")


@dataclass(frozen=True, slots=True)
class TimeSpan:
    """A possibly imprecise and uncertain historical time span."""

    start: date | None = None
    end: date | None = None
    original_text: str | None = None
    precision: str | None = None
    certainty: Confidence = field(default_factory=Confidence)

    def __post_init__(self) -> None:
        if self.start is None and self.end is None and self.original_text is None:
            raise ValueError("TimeSpan kräver datum eller original_text")
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("TimeSpan start får inte ligga efter end")
        if self.original_text is not None and not self.original_text.strip():
            raise ValueError("original_text får inte vara tom")
        if self.precision is not None and not self.precision.strip():
            raise ValueError("precision får inte vara tom")


@dataclass(frozen=True, slots=True)
class LicenseInfo:
    """License and attribution conditions attached to source data."""

    name: str
    url: str | None = None
    attribution: str | None = None
    usage_notes: str | None = None
    requires_attribution: bool | None = None
    commercial_use_allowed: bool | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Licensnamn får inte vara tomt")


@dataclass(frozen=True, slots=True)
class Provenance:
    """Traceable source identity and retrieval metadata."""

    source: str
    source_id: str
    source_url: str | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    license_info: LicenseInfo | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source får inte vara tom")
        if not self.source_id.strip():
            raise ValueError("source_id får inte vara tom")
        if self.fetched_at.tzinfo is None or self.fetched_at.utcoffset() is None:
            raise ValueError("fetched_at måste innehålla tidszon")


@dataclass(frozen=True, slots=True)
class AtlasFeature:
    """Provider-independent representation of an atlas object."""

    feature_id: FeatureId
    title: str
    feature_type: str
    provenance: Provenance
    description: str | None = None
    place: str | None = None
    geometry: Geometry | None = None
    time_span: TimeSpan | None = None
    confidence: Confidence = field(default_factory=Confidence)
    geometry_confidence: Confidence = field(default_factory=Confidence)
    properties: dict[str, Any] = field(default_factory=dict)
    relationships: tuple[FeatureId, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title får inte vara tom")
        if not self.feature_type.strip():
            raise ValueError("feature_type får inte vara tom")
