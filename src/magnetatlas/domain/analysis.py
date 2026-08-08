"""Deterministic analysis contracts that consume evidence reports only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from magnetatlas.domain.evidence import Evidence, EvidenceReport, EvidenceStrength


class AnalysisCategory(StrEnum):
    """Stable, unweighted categories for evidence-only analysis."""

    HISTORICAL_ACTIVITY = "historical_activity"
    TRANSPORT = "transport"
    MARITIME = "maritime"
    INDUSTRY = "industry"
    GEOLOGY = "geology"
    CULTURAL_HERITAGE = "cultural_heritage"
    USER_FINDS = "user_finds"
    UNKNOWN = "unknown"


@dataclass(frozen=True, order=True, slots=True)
class AnalysisVersion:
    """Comparable semantic version for the analysis contract."""

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        values = (self.major, self.minor, self.patch)
        if any(isinstance(value, bool) or value < 0 for value in values):
            raise ValueError("AnalysisVersion kräver tre icke-negativa heltal")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Immutable input boundary exposing an EvidenceReport and nothing raw."""

    report: EvidenceReport

    @property
    def evidence(self) -> tuple[Evidence, ...]:
        return self.report.evidence.items


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """One explainable result traceable to its exact evidence inputs."""

    id: str
    category: AnalysisCategory
    created_at: datetime
    evidence_references: tuple[str, ...]
    summary: str
    confidence: EvidenceStrength
    rule_id: str
    rule_version: str
    analysis_version: str
    reason_code: str

    def __post_init__(self) -> None:
        required = (
            self.id,
            self.summary,
            self.rule_id,
            self.rule_version,
            self.analysis_version,
            self.reason_code,
        )
        if not all(value.strip() for value in required):
            raise ValueError("AnalysisResult kräver komplett förklaringsmetadata")
        if not self.evidence_references:
            raise ValueError("AnalysisResult kräver minst en evidensreferens")
        if len(set(self.evidence_references)) != len(self.evidence_references):
            raise ValueError("AnalysisResult innehåller duplicerade evidensreferenser")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("AnalysisResult created_at måste innehålla tidszon")
        object.__setattr__(
            self, "evidence_references", tuple(sorted(self.evidence_references))
        )


@dataclass(frozen=True, slots=True)
class AnalysisSummary:
    """Count-only summary without scoring, ranking, or generated prose."""

    result_count: int
    evidence_count: int
    categories: tuple[tuple[AnalysisCategory, int], ...]

    def __post_init__(self) -> None:
        if self.result_count < 0 or self.evidence_count < 0:
            raise ValueError("AnalysisSummary kan inte innehålla negativa antal")
        if any(count < 1 for _, count in self.categories):
            raise ValueError("AnalysisSummary kategorier måste ha positiva antal")
        object.__setattr__(self, "categories", tuple(sorted(self.categories)))


@dataclass(frozen=True, slots=True)
class Analysis:
    """One deterministic analysis report derived from one EvidenceReport."""

    id: str
    area: str
    created_at: datetime
    analysis_version: str
    evidence_report_created_at: datetime
    results: tuple[AnalysisResult, ...]
    summary: AnalysisSummary

    def __post_init__(self) -> None:
        if (
            not self.id.strip()
            or not self.area.strip()
            or not self.analysis_version.strip()
        ):
            raise ValueError("Analysis kräver id, area och analysis_version")
        for value in (self.created_at, self.evidence_report_created_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Analysis-tider måste innehålla tidszon")
        identities = [result.id for result in self.results]
        if len(set(identities)) != len(identities):
            raise ValueError("Analysis innehåller duplicerade resultat")
        object.__setattr__(
            self, "results", tuple(sorted(self.results, key=lambda item: item.id))
        )


class AnalysisRule(Protocol):
    """Versioned rule that can read only evidence through AnalysisContext."""

    rule_id: str
    version: str
    category: AnalysisCategory
    description: str

    def evaluate(
        self, context: AnalysisContext, *, created_at: datetime, analysis_version: str
    ) -> tuple[AnalysisResult, ...]: ...
