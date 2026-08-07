"""Web composition for MagnetAtlas' built-in layer catalogue."""

from __future__ import annotations

from collections.abc import Iterable

from magnetatlas.application.layers import LayerRegistry, LayerService
from magnetatlas.domain.datasets import DatasetInstance
from magnetatlas.domain.layers import LayerDefinition

BUILT_IN_LAYERS = (
    LayerDefinition(
        id="cultural-heritage",
        name="Kulturhistoriska lämningar",
        description="Registrerade kulturhistoriska lämningar.",
        icon="◆",
        category="Kulturmiljö",
        supported_sources=frozenset({"raa-kmr", "magnetatlas-demo", "local-json"}),
        default_visibility=True,
    ),
    LayerDefinition(
        "listed-buildings",
        "Byggnadsminnen",
        "Skyddade byggnader och miljöer.",
        "□",
        "Kulturmiljö",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "archaeological-projects",
        "Arkeologiska uppdrag",
        "Arkeologiska undersökningar och uppdrag.",
        "◇",
        "Kulturmiljö",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "historical-maps",
        "Historiska kartor",
        "Historiska kartunderlag.",
        "▧",
        "Kartor",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "soil-types",
        "SGU Jordarter",
        "Geologiska jordartslager.",
        "▤",
        "Geologi",
        frozenset({"sgu-jordarter"}),
        default_visibility=True,
    ),
    LayerDefinition(
        "bedrock",
        "SGU Berggrund",
        "Geologiska berggrundslager.",
        "▰",
        "Geologi",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "wells",
        "Brunnar",
        "Registrerade brunnar.",
        "◉",
        "Geologi",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "groundwater",
        "Grundvatten",
        "Grundvattenförekomster och magasin.",
        "≈",
        "Geologi",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "mines",
        "Gruvor",
        "Historiska och registrerade gruvmiljöer.",
        "⬙",
        "Näringar",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "harbors",
        "Hamnar",
        "Historiska och nutida hamnlägen.",
        "⚓",
        "Infrastruktur",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "bridges",
        "Broar",
        "Historiska broar och brolägen.",
        "⌒",
        "Infrastruktur",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "locks",
        "Slussar",
        "Historiska och nutida slussar.",
        "≋",
        "Infrastruktur",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "mills",
        "Kvarnar",
        "Historiska kvarnar och kvarnlägen.",
        "✣",
        "Näringar",
        frozenset(),
        enabled=False,
    ),
    LayerDefinition(
        "place-names",
        "Lantmäteriet Ortnamn",
        "Granskade och fastställda ortnamn.",
        "●",
        "Kartinformation",
        frozenset({"lantmateriet-ortnamn"}),
        default_visibility=True,
    ),
)


def create_layer_service(
    dataset_instances: Iterable[DatasetInstance],
) -> LayerService:
    """Create the web layer service from built-in product definitions."""
    return LayerService(LayerRegistry(BUILT_IN_LAYERS), dataset_instances)
