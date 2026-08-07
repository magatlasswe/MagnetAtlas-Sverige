"""Declarative rendering metadata for the built-in web layer catalogue."""

from __future__ import annotations

from magnetatlas.application.layer_composition import LayerCompositionService
from magnetatlas.application.layers import LayerService
from magnetatlas.domain.map_layers import (
    LayerType,
    LegendItem,
    MapLayer,
    RasterLayer,
    RenderMode,
    VectorLayer,
)


def _future(
    layer_id: str,
    name: str,
    provider: str,
    dataset: str,
    z_index: int,
    icon: str,
) -> VectorLayer:
    return VectorLayer(
        id=layer_id,
        name=name,
        provider=provider,
        dataset=dataset,
        layer_type=LayerType.VECTOR,
        geometry_type="future",
        render_mode=RenderMode.FUTURE,
        opacity=1.0,
        z_index=z_index,
        icon=icon,
        legend=(),
        attribution="Ej fastställd",
        license="Ej fastställd",
        source="future",
        min_zoom=0,
        max_zoom=24,
        default_enabled=False,
    )


BUILT_IN_MAP_LAYERS: tuple[MapLayer, ...] = (
    VectorLayer(
        id="cultural-heritage",
        name="Kulturhistoriska lämningar",
        provider="Riksantikvarieämbetet",
        dataset="Kulturmiljöregistret",
        layer_type=LayerType.VECTOR,
        geometry_type="mixed",
        render_mode=RenderMode.CLUSTER,
        opacity=1.0,
        z_index=10,
        icon="◆",
        legend=(LegendItem("Kulturhistorisk lämning", "#6f3028"),),
        attribution="Riksantikvarieämbetet KMR",
        license="CC0 1.0",
        source="raa-kmr",
        min_zoom=0,
        max_zoom=24,
        default_enabled=True,
    ),
    _future("listed-buildings", "Byggnadsminnen", "framtida", "framtida", 20, "□"),
    _future(
        "archaeological-projects",
        "Arkeologiska uppdrag",
        "framtida",
        "framtida",
        30,
        "◇",
    ),
    RasterLayer(
        id="historical-maps",
        name="Historiska kartor",
        provider="Lantmäteriet",
        dataset="Historiska kartor",
        layer_type=LayerType.RASTER,
        geometry_type="raster",
        render_mode=RenderMode.FUTURE,
        opacity=0.75,
        z_index=40,
        icon="▧",
        legend=(),
        attribution="Lantmäteriet",
        license="Produktberoende",
        source="historical-maps",
        min_zoom=0,
        max_zoom=24,
        default_enabled=False,
    ),
    VectorLayer(
        id="soil-types",
        name="SGU Jordarter",
        provider="Sveriges geologiska undersökning",
        dataset="Jordarter 1:25 000-1:100 000",
        layer_type=LayerType.VECTOR,
        geometry_type="polygon",
        render_mode=RenderMode.VECTOR,
        opacity=0.65,
        z_index=50,
        icon="▤",
        legend=(LegendItem("Jordart", "#8b6f47"),),
        attribution="Sveriges geologiska undersökning (SGU)",
        license="CC0 1.0",
        source="sgu-jordarter",
        min_zoom=0,
        max_zoom=24,
        default_enabled=True,
    ),
    _future("bedrock", "SGU Berggrund", "SGU", "berggrund", 60, "▰"),
    _future("wells", "Brunnar", "SGU", "brunnar", 70, "◉"),
    _future("groundwater", "Grundvatten", "SGU", "grundvatten", 80, "≈"),
    _future("mines", "Gruvor", "framtida", "framtida", 90, "⬙"),
    _future("harbors", "Hamnar", "framtida", "framtida", 100, "⚓"),
    _future("bridges", "Broar", "framtida", "framtida", 110, "⌒"),
    _future("locks", "Slussar", "framtida", "framtida", 120, "≋"),
    _future("mills", "Kvarnar", "framtida", "framtida", 130, "✣"),
    VectorLayer(
        id="place-names",
        name="Lantmäteriet Ortnamn",
        provider="Lantmäteriet",
        dataset="Ortnamn Nedladdning, vektor",
        layer_type=LayerType.VECTOR,
        geometry_type="point",
        render_mode=RenderMode.CLUSTER,
        opacity=1.0,
        z_index=140,
        icon="●",
        legend=(LegendItem("Ortnamn", "#315a7d"),),
        attribution="Lantmäteriet",
        license="CC BY 4.0",
        source="lantmateriet-ortnamn",
        min_zoom=0,
        max_zoom=24,
        default_enabled=True,
    ),
)


def create_layer_composition_service(
    layer_service: LayerService,
) -> LayerCompositionService:
    """Decorate the web Layer Engine with source-neutral map metadata."""
    return LayerCompositionService(layer_service, BUILT_IN_MAP_LAYERS)
