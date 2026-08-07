"""Deterministic, traceable evidence derived from AtlasFeature objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from magnetatlas.domain.datasets import DatasetInstance
from magnetatlas.domain.features import (
    AtlasFeature,
    Confidence,
    FeatureId,
    LicenseInfo,
    Provenance,
)
from magnetatlas.domain.geography import BoundingBox, Geometry


class EvidenceType(StrEnum):
    """Supported evidence classifications without classification policy."""

    HISTORICAL_BRIDGE = "historical_bridge"
    HISTORICAL_ROAD = "historical_road"
    FERRY_LOCATION = "ferry_location"
    HARBOUR = "harbour"
    QUAY = "quay"
    LOCK = "lock"
    MILL = "mill"
    SAWMILL = "sawmill"
    INDUSTRIAL_SITE = "industrial_site"
    ARCHAEOLOGICAL_SITE = "archaeological_site"
    SOIL_TYPE = "soil_type"
    BEDROCK = "bedrock"
    PLACE_NAME = "place_name"
    HISTORICAL_MAP = "historical_map"
    CUSTOM = "custom"


class EvidenceStrength(StrEnum):
    """Direct representation of source confidence, never a combined score."""

    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @classmethod
    def from_confidence(cls, confidence: Confidence) -> EvidenceStrength:
        """Translate one source-reported confidence without inference."""
        if confidence.value is None:
            return cls.UNKNOWN
        if confidence.value < 0.34:
            return cls.LOW
        if confidence.value < 0.67:
            return cls.MEDIUM
        return cls.HIGH


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    """Exact dataset and source metadata from which evidence was derived."""

    provider: str
    dataset: str
    snapshot: str
    provenance: Provenance
    license: LicenseInfo | None
    source_url: str | None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.dataset.strip():
            raise ValueError("EvidenceSource kräver provider och dataset")
        if not self.snapshot.strip():
            raise ValueError("EvidenceSource kräver snapshot")

    @classmethod
    def from_feature(
        cls, instance: DatasetInstance, feature: AtlasFeature
    ) -> EvidenceSource:
        """Build traceability metadata without inspecting provider raw data."""
        source_version = feature.properties.get("source_version")
        snapshot = (
            str(source_version) if source_version is not None else instance.dataset_id
        )
        return cls(
            provider=instance.source.display_name,
            dataset=instance.dataset_id,
            snapshot=snapshot,
            provenance=feature.provenance,
            license=feature.provenance.license_info,
            source_url=feature.provenance.source_url,
        )


@dataclass(frozen=True, slots=True)
class Evidence:
    """One deterministic statement traceable to exactly one AtlasFeature."""

    id: str
    type: EvidenceType
    source: EvidenceSource
    feature_id: FeatureId
    geometry: Geometry | None
    created_at: datetime
    confidence: Confidence
    strength: EvidenceStrength
    explanation: str
    rule_id: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.rule_id.strip():
            raise ValueError("Evidence kräver id och rule_id")
        if not self.explanation.strip():
            raise ValueError("Evidence kräver en verifierbar explanation")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("Evidence created_at måste innehålla tidszon")

    @property
    def provider(self) -> str:
        return self.source.provider

    @property
    def dataset(self) -> str:
        return self.source.dataset

    @property
    def provenance(self) -> Provenance:
        return self.source.provenance

    @property
    def license(self) -> LicenseInfo | None:
        return self.source.license

    @property
    def snapshot(self) -> str:
        return self.source.snapshot

    @property
    def source_url(self) -> str | None:
        return self.source.source_url


@dataclass(frozen=True, slots=True)
class EvidenceCollection:
    """Immutable evidence set with unique deterministic identities."""

    items: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        identities = [item.id for item in self.items]
        if len(set(identities)) != len(identities):
            raise ValueError("EvidenceCollection innehåller duplicerade id")
        object.__setattr__(
            self, "items", tuple(sorted(self.items, key=lambda item: item.id))
        )

    def __len__(self) -> int:
        return len(self.items)


@dataclass(frozen=True, slots=True)
class EvidenceReport:
    """Deterministic report containing evidence and no generated conclusions."""

    area: str
    bbox: BoundingBox
    created_at: datetime
    datasets: tuple[str, ...]
    summary: str
    confidence: EvidenceStrength
    provenance: tuple[EvidenceSource, ...]
    evidence: EvidenceCollection

    def __post_init__(self) -> None:
        if not self.area.strip() or not self.summary.strip():
            raise ValueError("EvidenceReport kräver area och summary")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("EvidenceReport created_at måste innehålla tidszon")

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)
