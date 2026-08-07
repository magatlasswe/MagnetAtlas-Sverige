"""Tests for deterministic and traceable Evidence Engine behavior."""

from datetime import UTC, datetime

import pytest

from magnetatlas.application.evidence import (
    EvidenceEngine,
    EvidenceReportService,
    EvidenceRuleRegistry,
    FeatureEvidenceRule,
)
from magnetatlas.application.feature_queries import CatalogFeatureQuerySource
from magnetatlas.domain.datasets import DatasetInstance, DatasetScope, SourceDefinition
from magnetatlas.domain.evidence import (
    EvidenceCollection,
    EvidenceStrength,
    EvidenceType,
)
from magnetatlas.domain.features import (
    AtlasFeature,
    Confidence,
    FeatureId,
    LicenseInfo,
    Provenance,
)
from magnetatlas.domain.geography import BoundingBox, GeoPoint
from magnetatlas.interfaces.web.serializers import (
    serialize_evidence,
    serialize_evidence_report,
)

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
INSTANCE = DatasetInstance.create(
    SourceDefinition("official", "Official provider"),
    DatasetScope.country("sweden"),
)


def _feature() -> AtlasFeature:
    return AtlasFeature(
        feature_id=FeatureId("feature-1"),
        title="Traceable feature",
        feature_type="site",
        geometry=GeoPoint(18.0, 59.0),
        confidence=Confidence(0.8, "Source-reported confidence."),
        properties={"source_version": "snapshot-42"},
        provenance=Provenance(
            source="Official source",
            source_id="source-1",
            source_url="https://example.test/features/1",
            fetched_at=NOW,
            license_info=LicenseInfo("CC0 1.0"),
            raw_data={"private": "not serialized"},
        ),
    )


def _engine() -> EvidenceEngine:
    return EvidenceEngine(
        EvidenceRuleRegistry((FeatureEvidenceRule(),)), clock=lambda: NOW
    )


def test_generic_rule_creates_traceable_evidence_for_exact_feature() -> None:
    feature = _feature()

    evidence = _engine().collect(((INSTANCE, feature),)).items[0]

    assert evidence.feature_id == feature.feature_id
    assert evidence.geometry is feature.geometry
    assert evidence.provider == "Official provider"
    assert evidence.dataset == INSTANCE.dataset_id
    assert evidence.snapshot == "snapshot-42"
    assert evidence.provenance is feature.provenance
    assert evidence.license is feature.provenance.license_info
    assert evidence.source_url == feature.provenance.source_url
    assert evidence.strength is EvidenceStrength.HIGH
    assert evidence.rule_id == "atlas-feature-exists@1.0.0"


def test_evidence_engine_is_deterministic_and_does_not_modify_feature() -> None:
    feature = _feature()
    original_properties = dict(feature.properties)

    first = _engine().collect(((INSTANCE, feature),))
    second = _engine().collect(((INSTANCE, feature),))

    assert first == second
    assert feature.properties == original_properties


def test_rule_registry_orders_versions_and_rejects_duplicates() -> None:
    first = FeatureEvidenceRule()

    class LaterRule(FeatureEvidenceRule):
        rule_id = "z-rule"
        version = "2.0.0"
        description = "A later deterministic test rule."

    registry = EvidenceRuleRegistry((LaterRule(), first))

    assert [rule.rule_id for rule in registry.list()] == [
        "atlas-feature-exists",
        "z-rule",
    ]
    with pytest.raises(ValueError, match="redan registrerad"):
        registry.register(FeatureEvidenceRule())


def test_evidence_collection_rejects_duplicate_identities() -> None:
    evidence = _engine().collect(((INSTANCE, _feature()),)).items[0]

    with pytest.raises(ValueError, match="duplicerade"):
        EvidenceCollection((evidence, evidence))


def test_evidence_types_include_the_prepared_generic_contract() -> None:
    assert {item.value for item in EvidenceType} == {
        "historical_bridge",
        "historical_road",
        "ferry_location",
        "harbour",
        "quay",
        "lock",
        "mill",
        "sawmill",
        "industrial_site",
        "archaeological_site",
        "soil_type",
        "bedrock",
        "place_name",
        "historical_map",
        "custom",
    }


def test_report_contains_area_datasets_summary_and_provenance() -> None:
    service = EvidenceReportService(
        ((INSTANCE, CatalogFeatureQuerySource([_feature()])),),
        _engine(),
        clock=lambda: NOW,
    )
    bbox = BoundingBox(17.0, 58.0, 19.0, 60.0)

    report = service.create_report(area="Vaxholm", bbox=bbox, limit=10)

    assert report.area == "Vaxholm"
    assert report.bbox == bbox
    assert report.created_at == NOW
    assert report.datasets == (INSTANCE.dataset_id,)
    assert report.evidence_count == 1
    assert report.summary == "1 verifierbara evidensobjekt från 1 dataset."
    assert report.confidence is EvidenceStrength.UNKNOWN
    assert report.provenance[0].snapshot == "snapshot-42"
    assert service.get_evidence(report.evidence.items[0].id) == report.evidence.items[0]


def test_evidence_serialization_excludes_provider_raw_data() -> None:
    service = EvidenceReportService(
        ((INSTANCE, CatalogFeatureQuerySource([_feature()])),),
        _engine(),
        clock=lambda: NOW,
    )
    report = service.create_report(
        area="bbox", bbox=BoundingBox(17.0, 58.0, 19.0, 60.0), limit=10
    )

    evidence_payload = serialize_evidence(report.evidence.items[0])
    report_payload = serialize_evidence_report(report)

    assert evidence_payload["feature_id"] == "feature-1"
    assert evidence_payload["provenance"]["source_id"] == "source-1"
    assert "raw_data" not in str(report_payload)
    assert report_payload["evidence_count"] == 1
