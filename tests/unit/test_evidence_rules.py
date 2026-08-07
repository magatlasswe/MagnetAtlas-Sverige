"""Tests for the generic, deterministic evidence rules framework."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from magnetatlas.application.evidence_rules import (
    BridgeEvidenceRule,
    EvidenceRulesLibrary,
    HistoricalMapEvidenceRule,
    MatchedEvidenceRule,
    SoilEvidenceRule,
    create_default_evidence_rules_library,
)
from magnetatlas.domain.evidence import EvidenceSource, EvidenceType
from magnetatlas.domain.evidence_rules import (
    AttributeMatcher,
    EvidenceCategory,
    EvidenceContext,
    EvidenceRuleSet,
    FeatureTypeMatcher,
    RuleMetadata,
    RuleVersion,
)
from magnetatlas.domain.features import AtlasFeature, FeatureId, Provenance
from magnetatlas.interfaces.web.serializers import serialize_rule_metadata

NOW = datetime(2026, 8, 7, 12, tzinfo=UTC)


def _feature(feature_type: str = "bro") -> AtlasFeature:
    return AtlasFeature(
        FeatureId("official:1"),
        "Verifierbart objekt",
        feature_type,
        Provenance("official", "1", fetched_at=NOW),
        properties={"classification": "transport"},
    )


def _source(dataset: str = "official:country:sweden") -> EvidenceSource:
    provenance = _feature().provenance
    return EvidenceSource("Official", dataset, "snapshot-1", provenance, None, None)


def test_rule_version_is_strict_and_semantically_ordered() -> None:
    assert RuleVersion.parse("1.10.0") > RuleVersion.parse("1.2.9")
    assert str(RuleVersion(2, 1, 3)) == "2.1.3"
    with pytest.raises(ValueError, match=r"major\.minor\.patch"):
        RuleVersion.parse("1.0")


def test_metadata_requires_timezone_and_serializes_public_contract() -> None:
    metadata = BridgeEvidenceRule().metadata
    payload = serialize_rule_metadata(metadata)
    assert payload["id"] == "bridge"
    assert payload["version"] == "1.0.0"
    assert payload["category"] == "transport"
    assert "matcher" not in payload
    with pytest.raises(ValueError, match="tidszon"):
        RuleMetadata(
            "x",
            RuleVersion(1, 0, 0),
            EvidenceCategory.GENERIC,
            "X",
            "X",
            frozenset(),
            frozenset(),
            EvidenceType.CUSTOM,
            True,
            datetime(2026, 1, 1),
        )


def test_matchers_read_features_and_context_without_mutation() -> None:
    feature = _feature()
    context = EvidenceContext("official", "dataset", feature.properties)
    assert FeatureTypeMatcher(frozenset({"BRO"})).matches(feature, context)
    assert AttributeMatcher("classification", frozenset({"TRANSPORT"})).matches(
        feature, context
    )
    with pytest.raises(TypeError):
        context.attributes["classification"] = "changed"  # type: ignore[index]
    assert feature.properties == {"classification": "transport"}


def test_library_has_stable_order_and_rejects_duplicate_versions() -> None:
    first = BridgeEvidenceRule()
    library = EvidenceRulesLibrary((first,))
    later_metadata = replace(first.metadata, version=RuleVersion(2, 0, 0))
    later = MatchedEvidenceRule(later_metadata, first.matcher)
    library.register(later)
    assert library.get("bridge") is later
    assert [rule.version for rule in library.list()] == ["1.0.0", "2.0.0"]
    with pytest.raises(ValueError, match="redan registrerad"):
        library.register(BridgeEvidenceRule())


def test_rule_set_is_unweighted_sorted_and_duplicate_safe() -> None:
    bridge = BridgeEvidenceRule().metadata
    rules = EvidenceRuleSet("infra", "Infrastructure", "No scores.", (bridge,))
    assert rules.rules == (bridge,)
    with pytest.raises(ValueError, match="duplicerade"):
        EvidenceRuleSet("bad", "Bad", "Bad", (bridge, bridge))


def test_default_library_exposes_six_generic_rules_and_rule_sets() -> None:
    library = create_default_evidence_rules_library()
    assert [rule.metadata.id for rule in library.list()] == [
        "bridge",
        "harbour",
        "historical-map",
        "place-name",
        "road",
        "soil",
    ]
    assert [item.id for item in library.list_rule_sets()] == [
        "future-geological",
        "historical-infrastructure",
        "water-transport",
    ]


def test_matched_rule_is_deterministic_and_never_mutates_feature() -> None:
    feature = _feature()
    rule = BridgeEvidenceRule()
    first = rule.evaluate(feature, _source(), created_at=NOW)
    second = rule.evaluate(feature, _source(), created_at=NOW)
    assert first == second
    assert first[0].type is EvidenceType.HISTORICAL_BRIDGE
    assert "ingen historisk slutsats" in first[0].explanation
    assert feature.properties == {"classification": "transport"}
    assert rule.evaluate(_feature("hamn"), _source(), created_at=NOW) == ()


def test_disabled_rule_never_creates_evidence() -> None:
    rule = HistoricalMapEvidenceRule()
    assert rule.metadata.enabled is False
    assert rule.evaluate(_feature(), _source("historical-maps"), created_at=NOW) == ()


def test_provider_and_dataset_support_use_dataset_identity() -> None:
    rule = SoilEvidenceRule()
    assert rule.evaluate(
        _feature("soil"), _source("sgu-jordarter:country:sweden"), created_at=NOW
    )
    assert (
        rule.evaluate(_feature("soil"), _source("other:country:sweden"), created_at=NOW)
        == ()
    )
