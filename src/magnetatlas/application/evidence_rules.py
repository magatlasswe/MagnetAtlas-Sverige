"""Registration and execution adapters for generic evidence rules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256

from magnetatlas.domain.evidence import (
    Evidence,
    EvidenceSource,
    EvidenceStrength,
    EvidenceType,
)
from magnetatlas.domain.evidence_rules import (
    AnyEvidenceMatcher,
    EvidenceCategory,
    EvidenceContext,
    EvidenceMatcher,
    EvidenceRuleSet,
    FeatureTypeMatcher,
    RuleMetadata,
    RuleVersion,
)
from magnetatlas.domain.features import AtlasFeature

RULES_CREATED_AT = datetime(2026, 8, 7, tzinfo=UTC)


class MatchedEvidenceRule:
    """Adapt public rule metadata and a pure matcher to EvidenceRule."""

    def __init__(self, metadata: RuleMetadata, matcher: EvidenceMatcher) -> None:
        self.metadata = metadata
        self.matcher = matcher
        self.rule_id = metadata.id
        self.version = str(metadata.version)
        self.description = metadata.description

    def evaluate(
        self,
        feature: AtlasFeature,
        source: EvidenceSource,
        *,
        created_at: datetime,
    ) -> tuple[Evidence, ...]:
        """Create evidence only when declared source support and matcher agree."""
        if not self.metadata.enabled or not self._supports(feature, source):
            return ()
        context = EvidenceContext(
            provider=source.provider,
            dataset=source.dataset,
            attributes=feature.properties,
        )
        if not self.matcher.matches(feature, context):
            return ()
        identity = "|".join(
            (
                self.rule_id,
                self.version,
                str(feature.feature_id),
                source.dataset,
                source.snapshot,
                self.metadata.evidence_type.value,
            )
        )
        return (
            Evidence(
                id=f"evidence:{sha256(identity.encode('utf-8')).hexdigest()}",
                type=self.metadata.evidence_type,
                source=source,
                feature_id=feature.feature_id,
                geometry=feature.geometry,
                created_at=created_at,
                confidence=feature.confidence,
                strength=EvidenceStrength.from_confidence(feature.confidence),
                explanation=(
                    f"Källobjektets normaliserade egenskaper matchar regeln "
                    f"{self.metadata.title}; ingen historisk slutsats, viktning "
                    "eller rekommendation har skapats."
                ),
                rule_id=f"{self.rule_id}@{self.version}",
            ),
        )

    def _supports(self, feature: AtlasFeature, source: EvidenceSource) -> bool:
        providers = {value.casefold() for value in self.metadata.provider_support}
        provider_values = {
            source.provider.casefold(),
            feature.provenance.source.casefold(),
        }
        dataset = source.dataset.casefold()
        provider_matches_dataset = any(
            dataset == provider
            or dataset.startswith(f"{provider}-")
            or dataset.startswith(f"{provider}:")
            for provider in providers
        )
        if (
            providers
            and providers.isdisjoint(provider_values)
            and not provider_matches_dataset
        ):
            return False
        datasets = {value.casefold() for value in self.metadata.dataset_support}
        return not datasets or any(
            dataset == supported or dataset.startswith(f"{supported}:")
            for supported in datasets
        )


class EvidenceRulesLibrary:
    """Discover versioned rules and unweighted rule sets in stable order."""

    def __init__(
        self,
        rules: Iterable[MatchedEvidenceRule] = (),
        rule_sets: Iterable[EvidenceRuleSet] = (),
    ) -> None:
        self._rules: dict[tuple[str, RuleVersion], MatchedEvidenceRule] = {}
        self._rule_sets: dict[str, EvidenceRuleSet] = {}
        for rule in rules:
            self.register(rule)
        for rule_set in rule_sets:
            self.register_rule_set(rule_set)

    def register(self, rule: MatchedEvidenceRule) -> None:
        """Register one unique rule version."""
        key = (rule.metadata.id, rule.metadata.version)
        if key in self._rules:
            raise ValueError(f"regelversionen är redan registrerad: {key}")
        self._rules[key] = rule

    def register_rule_set(self, rule_set: EvidenceRuleSet) -> None:
        """Register one uniquely identified, unweighted grouping."""
        if rule_set.id in self._rule_sets:
            raise ValueError(f"ruleset är redan registrerat: {rule_set.id}")
        known = set(self._rules)
        if any((rule.id, rule.version) not in known for rule in rule_set.rules):
            raise ValueError("ruleset refererar till en oregistrerad regelversion")
        self._rule_sets[rule_set.id] = rule_set

    def list(self) -> tuple[MatchedEvidenceRule, ...]:
        """List every rule version by stable identity and semantic version."""
        return tuple(self._rules[key] for key in sorted(self._rules))

    def get(self, rule_id: str) -> MatchedEvidenceRule:
        """Get the latest installed semantic version of a rule."""
        matches = [
            rule
            for (identifier, _), rule in self._rules.items()
            if identifier == rule_id
        ]
        if not matches:
            raise KeyError(rule_id)
        return max(matches, key=lambda rule: rule.metadata.version)

    def list_rule_sets(self) -> tuple[EvidenceRuleSet, ...]:
        return tuple(self._rule_sets[key] for key in sorted(self._rule_sets))


def _metadata(
    rule_id: str,
    category: EvidenceCategory,
    title: str,
    description: str,
    evidence_type: EvidenceType,
    *,
    providers: frozenset[str] = frozenset(),
    datasets: frozenset[str] = frozenset(),
    enabled: bool = True,
) -> RuleMetadata:
    return RuleMetadata(
        id=rule_id,
        version=RuleVersion(1, 0, 0),
        category=category,
        title=title,
        description=description,
        provider_support=providers,
        dataset_support=datasets,
        evidence_type=evidence_type,
        enabled=enabled,
        created_at=RULES_CREATED_AT,
    )


class BridgeEvidenceRule(MatchedEvidenceRule):
    def __init__(self) -> None:
        super().__init__(
            _metadata(
                "bridge",
                EvidenceCategory.TRANSPORT,
                "Bro",
                "Identifierar objekt uttryckligen klassificerade som bro.",
                EvidenceType.HISTORICAL_BRIDGE,
            ),
            FeatureTypeMatcher(frozenset({"bridge", "bro"})),
        )


class RoadEvidenceRule(MatchedEvidenceRule):
    def __init__(self) -> None:
        super().__init__(
            _metadata(
                "road",
                EvidenceCategory.TRANSPORT,
                "Väg",
                "Identifierar objekt uttryckligen klassificerade som väg.",
                EvidenceType.HISTORICAL_ROAD,
            ),
            FeatureTypeMatcher(frozenset({"road", "väg"})),
        )


class HarbourEvidenceRule(MatchedEvidenceRule):
    def __init__(self) -> None:
        super().__init__(
            _metadata(
                "harbour",
                EvidenceCategory.WATER,
                "Hamn",
                "Identifierar objekt uttryckligen klassificerade som hamn.",
                EvidenceType.HARBOUR,
            ),
            FeatureTypeMatcher(frozenset({"harbour", "harbor", "hamn"})),
        )


class SoilEvidenceRule(MatchedEvidenceRule):
    def __init__(self) -> None:
        super().__init__(
            _metadata(
                "soil",
                EvidenceCategory.GEOLOGY,
                "Jordart",
                "Identifierar verifierbara objekt i ett deklarerat jordartsdataset.",
                EvidenceType.SOIL_TYPE,
                providers=frozenset({"sgu"}),
                datasets=frozenset({"sgu-jordarter"}),
            ),
            AnyEvidenceMatcher(),
        )


class PlaceNameEvidenceRule(MatchedEvidenceRule):
    def __init__(self) -> None:
        super().__init__(
            _metadata(
                "place-name",
                EvidenceCategory.PLACE_NAMES,
                "Ortnamn",
                "Identifierar verifierbara objekt i ett deklarerat ortnamnsdataset.",
                EvidenceType.PLACE_NAME,
                providers=frozenset({"lantmateriet"}),
                datasets=frozenset({"lantmateriet-ortnamn"}),
            ),
            AnyEvidenceMatcher(),
        )


class HistoricalMapEvidenceRule(MatchedEvidenceRule):
    def __init__(self) -> None:
        super().__init__(
            _metadata(
                "historical-map",
                EvidenceCategory.HISTORICAL_MAPS,
                "Historisk karta",
                "Förberedd regel för ett framtida historiskt kartdataset.",
                EvidenceType.HISTORICAL_MAP,
                datasets=frozenset({"historical-maps"}),
                enabled=False,
            ),
            AnyEvidenceMatcher(),
        )


def create_default_evidence_rules_library() -> EvidenceRulesLibrary:
    """Create the built-in generic library without weights or scores."""
    rules = (
        BridgeEvidenceRule(),
        RoadEvidenceRule(),
        HarbourEvidenceRule(),
        SoilEvidenceRule(),
        PlaceNameEvidenceRule(),
        HistoricalMapEvidenceRule(),
    )
    by_id = {rule.metadata.id: rule.metadata for rule in rules}
    rule_sets = (
        EvidenceRuleSet(
            "historical-infrastructure",
            "Historical Infrastructure",
            "Verifierbara transportobjekt.",
            (by_id["bridge"], by_id["road"]),
        ),
        EvidenceRuleSet(
            "water-transport",
            "Water Transport",
            "Verifierbara vattenanknutna transportobjekt.",
            (by_id["harbour"],),
        ),
        EvidenceRuleSet(
            "future-geological",
            "Future Geological",
            "Verifierbara geologiska datasetobjekt.",
            (by_id["soil"],),
        ),
    )
    return EvidenceRulesLibrary(rules, rule_sets)
