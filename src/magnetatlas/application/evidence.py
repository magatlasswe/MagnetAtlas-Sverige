"""Deterministic evidence rule execution and report assembly."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from magnetatlas.application.feature_queries import FeatureQuerySource
from magnetatlas.domain.datasets import DatasetInstance
from magnetatlas.domain.evidence import (
    Evidence,
    EvidenceCollection,
    EvidenceReport,
    EvidenceSource,
    EvidenceStrength,
    EvidenceType,
)
from magnetatlas.domain.features import AtlasFeature
from magnetatlas.domain.geography import BoundingBox


class EvidenceRule(Protocol):
    """Versioned deterministic rule that cannot modify AtlasFeature."""

    rule_id: str
    version: str
    description: str

    def evaluate(
        self,
        feature: AtlasFeature,
        source: EvidenceSource,
        *,
        created_at: datetime,
    ) -> tuple[Evidence, ...]: ...


class EvidenceRuleRegistry:
    """Register unique rules and expose a stable execution order."""

    def __init__(self, rules: Iterable[EvidenceRule] = ()) -> None:
        self._rules: dict[tuple[str, str], EvidenceRule] = {}
        for rule in rules:
            self.register(rule)

    def register(self, rule: EvidenceRule) -> None:
        """Register one documented rule version exactly once."""
        if not rule.rule_id.strip() or not rule.version.strip():
            raise ValueError("EvidenceRule kräver rule_id och version")
        if not rule.description.strip():
            raise ValueError("EvidenceRule kräver description")
        key = (rule.rule_id, rule.version)
        if key in self._rules:
            raise ValueError(f"evidensregeln är redan registrerad: {key}")
        self._rules[key] = rule

    def list(self) -> tuple[EvidenceRule, ...]:
        """Return rules sorted by stable identity and semantic version text."""
        return tuple(self._rules[key] for key in sorted(self._rules))


class FeatureEvidenceRule:
    """Generic rule proving only that one traceable AtlasFeature exists."""

    rule_id = "atlas-feature-exists"
    version = "1.0.0"
    description = "Creates evidence for a traceable normalized source feature."

    def evaluate(
        self,
        feature: AtlasFeature,
        source: EvidenceSource,
        *,
        created_at: datetime,
    ) -> tuple[Evidence, ...]:
        """Create one custom evidence item without interpreting feature meaning."""
        identity = "|".join(
            (
                self.rule_id,
                self.version,
                str(feature.feature_id),
                source.dataset,
                source.snapshot,
                EvidenceType.CUSTOM.value,
            )
        )
        evidence_id = f"evidence:{sha256(identity.encode('utf-8')).hexdigest()}"
        return (
            Evidence(
                id=evidence_id,
                type=EvidenceType.CUSTOM,
                source=source,
                feature_id=feature.feature_id,
                geometry=feature.geometry,
                created_at=created_at,
                confidence=feature.confidence,
                strength=EvidenceStrength.from_confidence(feature.confidence),
                explanation=(
                    "Ett spårbart AtlasFeature finns i angiven dataset-snapshot; "
                    "ingen ytterligare historisk slutsats har skapats."
                ),
                rule_id=f"{self.rule_id}@{self.version}",
            ),
        )


class EvidenceEngine:
    """Execute registered rules deterministically against immutable features."""

    def __init__(
        self,
        registry: EvidenceRuleRegistry,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._registry = registry
        self._clock = clock or (lambda: datetime.now(UTC))

    def collect(
        self,
        features: Iterable[tuple[DatasetInstance, AtlasFeature]],
        *,
        created_at: datetime | None = None,
    ) -> EvidenceCollection:
        """Create evidence in stable rule order without mutating source features."""
        timestamp = created_at or self._clock()
        items: list[Evidence] = []
        for instance, feature in features:
            source = EvidenceSource.from_feature(instance, feature)
            for rule in self._registry.list():
                items.extend(rule.evaluate(feature, source, created_at=timestamp))
        return EvidenceCollection(tuple(items))


class EvidenceReportService:
    """Build bounded reports from dataset-aware feature query sources."""

    def __init__(
        self,
        sources: Iterable[tuple[DatasetInstance, FeatureQuerySource]],
        engine: EvidenceEngine,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sources = tuple(sources)
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(UTC))
        self._known: dict[str, Evidence] = {}

    def create_report(
        self, *, area: str, bbox: BoundingBox, limit: int
    ) -> EvidenceReport:
        """Create one deterministic report from bounded source queries."""
        if limit < 1:
            raise ValueError("limit måste vara minst 1")
        selected: list[tuple[DatasetInstance, AtlasFeature]] = []
        datasets: list[str] = []
        for instance, source in self._sources:
            remaining = limit - len(selected)
            if remaining <= 0:
                break
            result = source.in_bounds(bbox, limit=remaining)
            if result.features:
                datasets.append(instance.dataset_id)
            selected.extend((instance, feature) for feature in result.features)
        created_at = self._clock()
        collection = self._engine.collect(selected, created_at=created_at)
        self._known = {item.id: item for item in collection.items}
        used_datasets = tuple(sorted(dict.fromkeys(datasets)))
        unique_sources: dict[tuple[str, str], EvidenceSource] = {}
        for item in collection.items:
            unique_sources[(item.dataset, item.snapshot)] = item.source
        provenance = tuple(unique_sources[key] for key in sorted(unique_sources))
        return EvidenceReport(
            area=area,
            bbox=bbox,
            created_at=created_at,
            datasets=used_datasets,
            summary=(
                f"{len(collection)} verifierbara evidensobjekt från "
                f"{len(used_datasets)} dataset."
            ),
            confidence=EvidenceStrength.UNKNOWN,
            provenance=provenance,
            evidence=collection,
        )

    def get_evidence(self, evidence_id: str) -> Evidence:
        """Read one item from the latest explicitly generated report."""
        return self._known[evidence_id]
