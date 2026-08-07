"""Source-neutral metadata and matching contracts for evidence rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from magnetatlas.domain.evidence import EvidenceType
from magnetatlas.domain.features import AtlasFeature


class EvidenceCategory(StrEnum):
    """Stable categories used to discover rules without executing them."""

    TRANSPORT = "transport"
    WATER = "water"
    INDUSTRY = "industry"
    ARCHAEOLOGY = "archaeology"
    GEOLOGY = "geology"
    PLACE_NAMES = "place_names"
    HISTORICAL_MAPS = "historical_maps"
    USER_DATA = "user_data"
    GENERIC = "generic"


@dataclass(frozen=True, order=True, slots=True)
class RuleVersion:
    """Comparable semantic version for a deterministic rule contract."""

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        if any(isinstance(value, bool) or value < 0 for value in self.parts):
            raise ValueError("RuleVersion kräver tre icke-negativa heltal")

    @property
    def parts(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch

    @classmethod
    def parse(cls, value: str) -> RuleVersion:
        """Parse a strict major.minor.patch version."""
        parts = value.split(".")
        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            raise ValueError("regelversion måste anges som major.minor.patch")
        return cls(*(int(part) for part in parts))

    def __str__(self) -> str:
        return ".".join(str(part) for part in self.parts)


@dataclass(frozen=True, slots=True)
class RuleMetadata:
    """Public, serializable description of one rule version."""

    id: str
    version: RuleVersion
    category: EvidenceCategory
    title: str
    description: str
    provider_support: frozenset[str]
    dataset_support: frozenset[str]
    evidence_type: EvidenceType
    enabled: bool
    created_at: datetime

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.id, self.title, self.description)):
            raise ValueError("RuleMetadata kräver id, title och description")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("RuleMetadata created_at måste innehålla tidszon")
        if any(not value.strip() for value in self.provider_support):
            raise ValueError("provider_support får inte innehålla tomma värden")
        if any(not value.strip() for value in self.dataset_support):
            raise ValueError("dataset_support får inte innehålla tomma värden")


@dataclass(frozen=True, slots=True)
class EvidenceContext:
    """Read-only source context made available to matchers."""

    provider: str
    dataset: str
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.dataset.strip():
            raise ValueError("EvidenceContext kräver provider och dataset")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


class EvidenceMatcher(Protocol):
    """Pure predicate that may only inspect a feature and its context."""

    def matches(self, feature: AtlasFeature, context: EvidenceContext) -> bool: ...


@dataclass(frozen=True, slots=True)
class FeatureTypeMatcher:
    """Match normalized feature types using case-insensitive exact values."""

    feature_types: frozenset[str]

    def matches(self, feature: AtlasFeature, context: EvidenceContext) -> bool:
        del context
        supported = {value.casefold() for value in self.feature_types}
        return feature.feature_type.casefold() in supported


@dataclass(frozen=True, slots=True)
class AttributeMatcher:
    """Match an explicitly normalized attribute value."""

    attribute: str
    values: frozenset[str]

    def matches(self, feature: AtlasFeature, context: EvidenceContext) -> bool:
        value = feature.properties.get(
            self.attribute, context.attributes.get(self.attribute)
        )
        return value is not None and str(value).casefold() in {
            item.casefold() for item in self.values
        }


class AnyEvidenceMatcher:
    """Match every feature already constrained by rule source metadata."""

    def matches(self, feature: AtlasFeature, context: EvidenceContext) -> bool:
        del feature, context
        return True


@dataclass(frozen=True, slots=True)
class EvidenceRuleSet:
    """Named, unweighted grouping of rule metadata."""

    id: str
    title: str
    description: str
    rules: tuple[RuleMetadata, ...]

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.id, self.title, self.description)):
            raise ValueError("EvidenceRuleSet kräver id, title och description")
        keys = [(rule.id, rule.version) for rule in self.rules]
        if len(keys) != len(set(keys)):
            raise ValueError("EvidenceRuleSet innehåller duplicerade regelversioner")
        object.__setattr__(
            self,
            "rules",
            tuple(sorted(self.rules, key=lambda rule: (rule.id, rule.version))),
        )
