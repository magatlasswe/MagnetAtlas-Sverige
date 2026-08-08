"""Tests for deterministic evidence-only analysis."""

from datetime import UTC, datetime

import pytest

from magnetatlas.application.analysis import (
    AnalysisRuleRegistry,
    EvidenceCategoryAnalysisRule,
    create_default_analysis_engine,
)
from magnetatlas.domain.analysis import (
    AnalysisCategory,
    AnalysisContext,
    AnalysisResult,
    AnalysisSummary,
)
from magnetatlas.domain.evidence import (
    Evidence,
    EvidenceCollection,
    EvidenceReport,
    EvidenceSource,
    EvidenceStrength,
    EvidenceType,
)
from magnetatlas.domain.features import Confidence, FeatureId, Provenance
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.interfaces.web.serializers import (
    serialize_analysis,
    serialize_analysis_result,
)

NOW = datetime(2026, 8, 7, 12, tzinfo=UTC)


def _evidence(
    evidence_id: str = "evidence:bridge",
    evidence_type: EvidenceType = EvidenceType.HISTORICAL_BRIDGE,
) -> Evidence:
    provenance = Provenance("official", evidence_id, fetched_at=NOW)
    source = EvidenceSource(
        "Official", "official:country:sweden", "v1", provenance, None, None
    )
    return Evidence(
        evidence_id,
        evidence_type,
        source,
        FeatureId(f"feature:{evidence_id}"),
        None,
        NOW,
        Confidence(0.8, "Source confidence"),
        EvidenceStrength.HIGH,
        "Verifierbart källobjekt.",
        "evidence-rule@1.0.0",
    )


def _report(*items: Evidence) -> EvidenceReport:
    selected = items or (_evidence(),)
    return EvidenceReport(
        "Vaxholm",
        BoundingBox(18.0, 59.0, 18.5, 59.5),
        NOW,
        ("official:country:sweden",),
        "Verifierbart underlag.",
        EvidenceStrength.UNKNOWN,
        tuple(item.source for item in selected),
        EvidenceCollection(tuple(selected)),
    )


def test_analysis_context_exposes_evidence_report_only() -> None:
    report = _report()
    context = AnalysisContext(report)
    assert context.report is report
    assert context.evidence == report.evidence.items
    assert not hasattr(context, "features")


def test_default_analysis_is_deterministic_and_traceable() -> None:
    report = _report()
    engine = create_default_analysis_engine()
    first = engine.analyze(report, created_at=NOW)
    second = engine.analyze(report, created_at=NOW)
    assert first == second
    assert len(first.results) == 1
    result = first.results[0]
    assert result.category is AnalysisCategory.TRANSPORT
    assert result.evidence_references == ("evidence:bridge",)
    assert result.confidence is EvidenceStrength.HIGH
    assert result.rule_version == "1.0.0"
    assert result.analysis_version == "1.0.0"


def test_rules_never_modify_evidence() -> None:
    evidence = _evidence()
    before = evidence
    create_default_analysis_engine().analyze(_report(evidence), created_at=NOW)
    assert evidence == before


def test_rule_registry_orders_and_rejects_duplicate_versions() -> None:
    rule = EvidenceCategoryAnalysisRule(
        rule_id="transport",
        category=AnalysisCategory.TRANSPORT,
        evidence_types=frozenset({EvidenceType.HISTORICAL_BRIDGE}),
        summary="Verifierbart transportevidens finns.",
        reason_code="evidence_type.transport",
    )
    registry = AnalysisRuleRegistry((rule,))
    assert registry.list() == (rule,)
    with pytest.raises(ValueError, match="redan registrerad"):
        registry.register(rule)


def test_results_have_stable_order_independent_of_evidence_order() -> None:
    bridge = _evidence("evidence:z")
    road = _evidence("evidence:a", EvidenceType.HISTORICAL_ROAD)
    first = create_default_analysis_engine().analyze(
        _report(bridge, road), created_at=NOW
    )
    second = create_default_analysis_engine().analyze(
        _report(road, bridge), created_at=NOW
    )
    assert [item.id for item in first.results] == [item.id for item in second.results]


def test_summary_contains_counts_without_scores_or_ranking() -> None:
    analysis = create_default_analysis_engine().analyze(_report(), created_at=NOW)
    assert analysis.summary == AnalysisSummary(1, 1, ((AnalysisCategory.TRANSPORT, 1),))
    assert not hasattr(analysis.summary, "score")
    assert not hasattr(analysis.summary, "rank")


def test_result_requires_traceable_evidence_reference() -> None:
    with pytest.raises(ValueError, match="evidensreferens"):
        AnalysisResult(
            "result",
            AnalysisCategory.UNKNOWN,
            NOW,
            (),
            "Fast sammanfattning.",
            EvidenceStrength.UNKNOWN,
            "rule",
            "1.0.0",
            "1.0.0",
            "reason",
        )


def test_serialization_exposes_metadata_but_no_evidence_payload() -> None:
    analysis = create_default_analysis_engine().analyze(_report(), created_at=NOW)
    result_payload = serialize_analysis_result(analysis.results[0])
    report_payload = serialize_analysis(analysis)
    assert result_payload["evidence_references"] == ["evidence:bridge"]
    assert "evidence" not in result_payload
    assert report_payload["summary"]["result_count"] == 1
    assert "features" not in report_payload
