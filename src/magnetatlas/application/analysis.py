"""Deterministic orchestration for evidence-only analysis."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from hashlib import sha256

from magnetatlas.application.evidence import EvidenceReportService
from magnetatlas.domain.analysis import (
    Analysis,
    AnalysisCategory,
    AnalysisContext,
    AnalysisResult,
    AnalysisRule,
    AnalysisSummary,
    AnalysisVersion,
)
from magnetatlas.domain.evidence import Evidence, EvidenceReport, EvidenceType
from magnetatlas.domain.geography import BoundingBox

CURRENT_ANALYSIS_VERSION = AnalysisVersion(1, 0, 0)


class AnalysisRuleRegistry:
    """Register unique analysis rule versions in stable execution order."""

    def __init__(self, rules: Iterable[AnalysisRule] = ()) -> None:
        self._rules: dict[tuple[str, str], AnalysisRule] = {}
        for rule in rules:
            self.register(rule)

    def register(self, rule: AnalysisRule) -> None:
        """Register one documented rule version exactly once."""
        if (
            not rule.rule_id.strip()
            or not rule.version.strip()
            or not rule.description.strip()
        ):
            raise ValueError("AnalysisRule kräver id, version och description")
        key = (rule.rule_id, rule.version)
        if key in self._rules:
            raise ValueError(f"analysregeln är redan registrerad: {key}")
        self._rules[key] = rule

    def list(self) -> tuple[AnalysisRule, ...]:
        return tuple(self._rules[key] for key in sorted(self._rules))


class EvidenceCategoryAnalysisRule:
    """Classify explicit EvidenceType values without combining evidence."""

    def __init__(
        self,
        *,
        rule_id: str,
        category: AnalysisCategory,
        evidence_types: frozenset[EvidenceType],
        summary: str,
        reason_code: str,
    ) -> None:
        self.rule_id = rule_id
        self.version = "1.0.0"
        self.category = category
        self.description = "Classifies explicitly declared evidence types."
        self._evidence_types = evidence_types
        self._summary = summary
        self._reason_code = reason_code

    def evaluate(
        self,
        context: AnalysisContext,
        *,
        created_at: datetime,
        analysis_version: str,
    ) -> tuple[AnalysisResult, ...]:
        """Create one result per matching Evidence, preserving its confidence."""
        return tuple(
            self._result(evidence, created_at, analysis_version)
            for evidence in context.evidence
            if evidence.type in self._evidence_types
        )

    def _result(
        self, evidence: Evidence, created_at: datetime, analysis_version: str
    ) -> AnalysisResult:
        identity = "|".join((self.rule_id, self.version, analysis_version, evidence.id))
        return AnalysisResult(
            id=f"analysis-result:{sha256(identity.encode('utf-8')).hexdigest()}",
            category=self.category,
            created_at=created_at,
            evidence_references=(evidence.id,),
            summary=self._summary,
            confidence=evidence.strength,
            rule_id=self.rule_id,
            rule_version=self.version,
            analysis_version=analysis_version,
            reason_code=self._reason_code,
        )


class AnalysisEngine:
    """Execute analysis rules solely against a supplied EvidenceReport."""

    def __init__(
        self,
        registry: AnalysisRuleRegistry,
        *,
        version: AnalysisVersion = CURRENT_ANALYSIS_VERSION,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._registry = registry
        self._version = version
        self._clock = clock or (lambda: datetime.now(UTC))

    def analyze(
        self, report: EvidenceReport, *, created_at: datetime | None = None
    ) -> Analysis:
        """Create a stable, explainable analysis without raw feature access."""
        timestamp = created_at or self._clock()
        version = str(self._version)
        context = AnalysisContext(report)
        results = tuple(
            result
            for rule in self._registry.list()
            for result in rule.evaluate(
                context, created_at=timestamp, analysis_version=version
            )
        )
        ordered = tuple(sorted(results, key=lambda result: result.id))
        counts = Counter(result.category for result in ordered)
        identity = "|".join(
            (
                report.area,
                report.created_at.isoformat(),
                version,
                *(result.id for result in ordered),
            )
        )
        return Analysis(
            id=f"analysis:{sha256(identity.encode('utf-8')).hexdigest()}",
            area=report.area,
            created_at=timestamp,
            analysis_version=version,
            evidence_report_created_at=report.created_at,
            results=ordered,
            summary=AnalysisSummary(
                result_count=len(ordered),
                evidence_count=len(
                    {
                        reference
                        for result in ordered
                        for reference in result.evidence_references
                    }
                ),
                categories=tuple(counts.items()),
            ),
        )


class AnalysisService:
    """Create bounded analyses and retain the latest results for detail lookup."""

    def __init__(
        self, evidence_service: EvidenceReportService, engine: AnalysisEngine
    ) -> None:
        self._evidence_service = evidence_service
        self._engine = engine
        self._known: dict[str, AnalysisResult] = {}

    def create_analysis(self, *, area: str, bbox: BoundingBox, limit: int) -> Analysis:
        """Analyze a bounded EvidenceReport without reading source features here."""
        report = self._evidence_service.create_report(area=area, bbox=bbox, limit=limit)
        analysis = self._engine.analyze(report, created_at=report.created_at)
        self._known = {result.id: result for result in analysis.results}
        return analysis

    def get_result(self, result_id: str) -> AnalysisResult:
        return self._known[result_id]


def create_default_analysis_engine() -> AnalysisEngine:
    """Create generic unweighted category rules for declared evidence types."""
    rules = (
        EvidenceCategoryAnalysisRule(
            rule_id="transport-evidence",
            category=AnalysisCategory.TRANSPORT,
            evidence_types=frozenset(
                {EvidenceType.HISTORICAL_BRIDGE, EvidenceType.HISTORICAL_ROAD}
            ),
            summary="Verifierbart transportrelaterat evidens finns.",
            reason_code="evidence_type.transport",
        ),
        EvidenceCategoryAnalysisRule(
            rule_id="maritime-evidence",
            category=AnalysisCategory.MARITIME,
            evidence_types=frozenset(
                {
                    EvidenceType.FERRY_LOCATION,
                    EvidenceType.HARBOUR,
                    EvidenceType.QUAY,
                    EvidenceType.LOCK,
                }
            ),
            summary="Verifierbart sjöfartsrelaterat evidens finns.",
            reason_code="evidence_type.maritime",
        ),
        EvidenceCategoryAnalysisRule(
            rule_id="industry-evidence",
            category=AnalysisCategory.INDUSTRY,
            evidence_types=frozenset(
                {
                    EvidenceType.MILL,
                    EvidenceType.SAWMILL,
                    EvidenceType.INDUSTRIAL_SITE,
                }
            ),
            summary="Verifierbart industrirelaterat evidens finns.",
            reason_code="evidence_type.industry",
        ),
        EvidenceCategoryAnalysisRule(
            rule_id="geology-evidence",
            category=AnalysisCategory.GEOLOGY,
            evidence_types=frozenset({EvidenceType.SOIL_TYPE, EvidenceType.BEDROCK}),
            summary="Verifierbart geologiskt evidens finns.",
            reason_code="evidence_type.geology",
        ),
        EvidenceCategoryAnalysisRule(
            rule_id="cultural-heritage-evidence",
            category=AnalysisCategory.CULTURAL_HERITAGE,
            evidence_types=frozenset(
                {EvidenceType.ARCHAEOLOGICAL_SITE, EvidenceType.HISTORICAL_MAP}
            ),
            summary="Verifierbart kulturmiljöevidens finns.",
            reason_code="evidence_type.cultural_heritage",
        ),
        EvidenceCategoryAnalysisRule(
            rule_id="historical-activity-evidence",
            category=AnalysisCategory.HISTORICAL_ACTIVITY,
            evidence_types=frozenset({EvidenceType.PLACE_NAME}),
            summary="Verifierbart ortnamnsevidens finns.",
            reason_code="evidence_type.historical_activity",
        ),
        EvidenceCategoryAnalysisRule(
            rule_id="unknown-evidence",
            category=AnalysisCategory.UNKNOWN,
            evidence_types=frozenset({EvidenceType.CUSTOM}),
            summary="Verifierbart evidens utan särskild analyskategori finns.",
            reason_code="evidence_type.unknown",
        ),
    )
    return AnalysisEngine(AnalysisRuleRegistry(rules))
