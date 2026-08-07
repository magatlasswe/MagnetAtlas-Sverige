"""Tests for source-neutral map composition above the Layer Engine."""

import pytest

from magnetatlas.application.feature_queries import CatalogFeatureQuerySource
from magnetatlas.application.features import FeatureSearchFilters
from magnetatlas.application.layer_composition import (
    ComposedFeatureQuerySource,
    LayerCompositionService,
)
from magnetatlas.application.layers import LayerRegistry, LayerService
from magnetatlas.domain.datasets import DatasetInstance, DatasetScope, SourceDefinition
from magnetatlas.domain.features import AtlasFeature, FeatureId, Provenance
from magnetatlas.domain.geography import BoundingBox, GeoPoint
from magnetatlas.domain.layers import LayerDefinition
from magnetatlas.domain.map_layers import (
    LayerType,
    RasterLayer,
    RenderMode,
    VectorLayer,
)
from magnetatlas.interfaces.web.layer_composition import BUILT_IN_MAP_LAYERS
from magnetatlas.interfaces.web.serializers import serialize_layer

SOURCE = SourceDefinition("source-a", "Source A")
OTHER_SOURCE = SourceDefinition("source-b", "Source B")
INSTANCE = DatasetInstance.create(SOURCE, DatasetScope.country("sweden"))


def _engine_layer(
    layer_id: str, *, visible: bool = False, enabled: bool = True
) -> LayerDefinition:
    return LayerDefinition(
        id=layer_id,
        name=layer_id,
        description=f"Description for {layer_id}",
        icon="●",
        category="Test",
        supported_sources=frozenset({SOURCE.source_id}) if enabled else frozenset(),
        default_visibility=visible,
        enabled=enabled,
    )


def _vector(layer_id: str, z_index: int, opacity: float = 1.0) -> VectorLayer:
    return VectorLayer(
        id=layer_id,
        name=layer_id,
        provider="Provider",
        dataset="Dataset",
        layer_type=LayerType.VECTOR,
        geometry_type="point",
        render_mode=RenderMode.CLUSTER,
        opacity=opacity,
        z_index=z_index,
        icon="●",
        legend=(),
        attribution="Provider",
        license="CC0",
        source=SOURCE.source_id,
        min_zoom=1,
        max_zoom=20,
        default_enabled=True,
    )


def test_composition_orders_layers_by_z_index() -> None:
    engine = LayerService(
        LayerRegistry((_engine_layer("upper"), _engine_layer("lower"))),
        (INSTANCE,),
    )
    service = LayerCompositionService(
        engine, (_vector("upper", 20), _vector("lower", 10))
    )

    assert [item.definition.id for item in service.list_layers()] == [
        "lower",
        "upper",
    ]


def test_composition_controls_visibility_without_owning_engine_policy() -> None:
    engine = LayerService(
        LayerRegistry((_engine_layer("places", visible=False),)), (INSTANCE,)
    )
    service = LayerCompositionService(engine, (_vector("places", 10),))

    assert service.get_layer("places").visible is False
    assert service.set_visibility("places", True).visible is True
    assert engine.get_layer("places").active is True
    assert service.set_visibility("places", False).visible is False


def test_composition_validates_and_updates_opacity() -> None:
    engine = LayerService(LayerRegistry((_engine_layer("places"),)), (INSTANCE,))
    service = LayerCompositionService(engine, (_vector("places", 10, 0.6),))

    assert service.get_layer("places").opacity == 0.6
    assert service.set_opacity("places", 0.25).opacity == 0.25
    with pytest.raises(ValueError, match="mellan 0 och 1"):
        service.set_opacity("places", 1.1)


def test_disabled_raster_layer_remains_invisible() -> None:
    engine = LayerService(
        LayerRegistry((_engine_layer("historical", enabled=False),)), (INSTANCE,)
    )
    raster = RasterLayer(
        id="historical",
        name="Historical",
        provider="Provider",
        dataset="Maps",
        layer_type=LayerType.RASTER,
        geometry_type="raster",
        render_mode=RenderMode.FUTURE,
        opacity=0.75,
        z_index=1,
        icon="▧",
        legend=(),
        attribution="Provider",
        license="Future",
        source="historical",
        min_zoom=0,
        max_zoom=24,
        default_enabled=False,
    )
    service = LayerCompositionService(engine, (raster,))
    status = service.get_layer("historical")

    assert status.definition.layer_type is LayerType.RASTER
    assert status.enabled is False
    assert status.visible is False
    with pytest.raises(ValueError, match="ingen installerad"):
        service.set_visibility("historical", True)


def test_layer_metadata_serialization_is_complete_and_source_neutral() -> None:
    engine = LayerService(
        LayerRegistry((_engine_layer("places", visible=True),)), (INSTANCE,)
    )
    payload = serialize_layer(
        LayerCompositionService(engine, (_vector("places", 10),)).get_layer("places")
    )

    assert set(
        (
            "id",
            "name",
            "provider",
            "dataset",
            "layer_type",
            "geometry_type",
            "render_mode",
            "visible",
            "opacity",
            "z_index",
            "icon",
            "legend",
            "attribution",
            "license",
            "source",
            "min_zoom",
            "max_zoom",
            "default_enabled",
        )
    ).issubset(payload)
    assert payload["render_mode"] == "cluster"
    assert payload["active"] is payload["visible"] is True


def test_catalog_registers_historical_maps_as_first_raster_family() -> None:
    rasters = [
        item for item in BUILT_IN_MAP_LAYERS if item.layer_type is LayerType.RASTER
    ]
    historical = rasters[0]

    assert len(rasters) == 1
    assert historical.id == "historical-maps"
    assert historical.render_mode is RenderMode.FUTURE
    assert historical.default_enabled is False


def test_render_mode_contract_contains_all_planned_modes() -> None:
    assert {item.value for item in RenderMode} == {
        "vector",
        "raster",
        "tile",
        "heatmap",
        "cluster",
        "future",
    }


def _feature(feature_id: str, source: SourceDefinition) -> AtlasFeature:
    return AtlasFeature(
        feature_id=FeatureId(feature_id),
        title=f"Place {feature_id}",
        feature_type="place",
        geometry=GeoPoint(18.0, 59.0),
        provenance=Provenance(source.display_name, feature_id),
    )


def test_composed_query_source_merges_datasets_with_global_bounds() -> None:
    other_instance = DatasetInstance.create(
        OTHER_SOURCE, DatasetScope.country("sweden")
    )
    engine = LayerService(
        LayerRegistry(
            (
                LayerDefinition(
                    "first",
                    "First",
                    "First source",
                    "●",
                    "Test",
                    frozenset({SOURCE.source_id}),
                    default_visibility=True,
                ),
                LayerDefinition(
                    "second",
                    "Second",
                    "Second source",
                    "●",
                    "Test",
                    frozenset({OTHER_SOURCE.source_id}),
                    default_visibility=True,
                ),
            )
        ),
        (INSTANCE, other_instance),
    )
    source = ComposedFeatureQuerySource(
        (
            (
                INSTANCE,
                CatalogFeatureQuerySource(
                    [_feature("a1", SOURCE), _feature("a2", SOURCE)]
                ),
            ),
            (
                other_instance,
                CatalogFeatureQuerySource(
                    [_feature("b1", OTHER_SOURCE), _feature("b2", OTHER_SOURCE)]
                ),
            ),
        ),
        engine,
    )

    result = source.in_bounds(BoundingBox(17.0, 58.0, 19.0, 60.0), limit=3)

    assert [str(item.feature_id) for item in result.features] == ["a1", "b1", "a2"]
    assert result.truncated is True
    assert source.summary().count == 4
    assert source.get("b1").title == "Place b1"
    assert len(source.search("Place", filters=FeatureSearchFilters(), limit=3)) == 3
