"""Tests for the source-neutral Layer Engine."""

from datetime import UTC, datetime

import pytest

from magnetatlas.application.layers import LayerRegistry, LayerService
from magnetatlas.domain.datasets import DatasetInstance, DatasetScope, SourceDefinition
from magnetatlas.domain.features import AtlasFeature, FeatureId, Provenance
from magnetatlas.domain.layers import LayerDefinition
from magnetatlas.interfaces.web.layers import create_layer_service

SOURCE = SourceDefinition("official-a", "Official source A")
OTHER_SOURCE = SourceDefinition("official-b", "Official source B")
INSTANCE = DatasetInstance.create(SOURCE, DatasetScope.municipality("Vaxholm"))


def layer(
    layer_id: str = "heritage",
    *,
    sources: frozenset[str] = frozenset({SOURCE.source_id}),
    visible: bool = True,
    enabled: bool = True,
) -> LayerDefinition:
    return LayerDefinition(
        id=layer_id,
        name=layer_id.title(),
        description="A source-neutral test layer.",
        icon="◆",
        category="Test",
        supported_sources=sources,
        default_visibility=visible,
        enabled=enabled,
    )


def feature(feature_id: str, feature_type: str) -> AtlasFeature:
    return AtlasFeature(
        feature_id=FeatureId(feature_id),
        title=feature_id,
        feature_type=feature_type,
        provenance=Provenance(
            source="Test",
            source_id=feature_id,
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )


def test_layer_definition_rejects_invalid_availability() -> None:
    with pytest.raises(ValueError, match="synligt"):
        layer(visible=True, enabled=False)


def test_registry_registers_lists_enables_and_disables() -> None:
    registry = LayerRegistry()
    definition = layer(visible=False)

    registry.register(definition)
    assert registry.list() == (definition,)
    assert not registry.is_enabled(definition.id)

    registry.enable(definition.id)
    assert registry.is_enabled(definition.id)
    registry.disable(definition.id)
    assert not registry.is_enabled(definition.id)

    with pytest.raises(ValueError, match="redan registrerat"):
        registry.register(definition)


def test_registry_discovers_support_from_installed_sources() -> None:
    registry = LayerRegistry((layer(),))

    assert registry.is_supported("heritage", {SOURCE.source_id})
    assert not registry.is_supported("heritage", {OTHER_SOURCE.source_id})


def test_service_reports_dataset_aware_layer_state() -> None:
    registry = LayerRegistry((layer(), layer("future", sources=frozenset())))
    service = LayerService(registry, (INSTANCE,))

    statuses = {status.definition.id: status for status in service.list_layers()}

    assert service.dataset_instances == (INSTANCE,)
    assert statuses["heritage"].supported is True
    assert statuses["heritage"].active is True
    assert statuses["future"].supported is False
    assert statuses["future"].active is False


def test_service_filters_features_with_active_layer_predicates() -> None:
    registry = LayerRegistry(
        (
            layer("bridges"),
            layer("mills", visible=False),
        )
    )
    service = LayerService(
        registry,
        (INSTANCE,),
        predicates={
            "bridges": lambda item: item.feature_type == "bridge",
            "mills": lambda item: item.feature_type == "mill",
        },
    )
    features = (feature("one", "bridge"), feature("two", "mill"))

    assert service.filter_features(features, INSTANCE) == (features[0],)
    service.enable("mills")
    assert service.filter_features(features, INSTANCE) == features
    service.disable("bridges")
    assert service.filter_features(features, INSTANCE) == (features[1],)


def test_service_does_not_cross_dataset_source_boundaries() -> None:
    registry = LayerRegistry((layer(),))
    other_instance = DatasetInstance.create(
        OTHER_SOURCE, DatasetScope.country("sweden")
    )
    service = LayerService(registry, (INSTANCE, other_instance))

    assert service.filter_features((feature("one", "site"),), other_instance) == ()


def test_service_rejects_enabling_unavailable_layer() -> None:
    service = LayerService(
        LayerRegistry((layer("future", sources=frozenset(), visible=False),)),
        (INSTANCE,),
    )

    with pytest.raises(ValueError, match="ingen installerad"):
        service.enable("future")


def test_web_catalog_automatically_enables_sgu_soils_for_installed_dataset() -> None:
    instance = DatasetInstance.create(
        SourceDefinition("sgu-jordarter", "SGU Jordarter"),
        DatasetScope.country("sweden"),
    )

    statuses = {
        status.definition.id: status
        for status in create_layer_service((instance,)).list_layers()
    }

    assert statuses["soil-types"].supported is True
    assert statuses["soil-types"].active is True
    assert statuses["bedrock"].supported is False
