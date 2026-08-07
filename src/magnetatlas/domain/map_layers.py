"""Source-neutral map composition metadata for vector and raster layers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LayerType(StrEnum):
    """Storage and rendering family of a composed map layer."""

    VECTOR = "vector"
    RASTER = "raster"


class RenderMode(StrEnum):
    """Renderer capability requested by a map layer."""

    VECTOR = "vector"
    RASTER = "raster"
    TILE = "tile"
    HEATMAP = "heatmap"
    CLUSTER = "cluster"
    FUTURE = "future"


@dataclass(frozen=True, slots=True)
class LegendItem:
    """One source-neutral label and color pair in a layer legend."""

    label: str
    color: str

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.color.strip():
            raise ValueError("Legendposter kräver label och color")


@dataclass(frozen=True, slots=True)
class MapLayer:
    """Immutable rendering metadata attached to one Layer Engine id."""

    id: str
    name: str
    provider: str
    dataset: str
    layer_type: LayerType
    geometry_type: str
    render_mode: RenderMode
    opacity: float
    z_index: int
    icon: str
    legend: tuple[LegendItem, ...]
    attribution: str
    license: str
    source: str
    min_zoom: float
    max_zoom: float
    default_enabled: bool

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Kartlager kräver id och name")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("opacity måste vara mellan 0 och 1")
        if self.min_zoom < 0 or self.max_zoom < self.min_zoom:
            raise ValueError("zoomintervallet är ogiltigt")


@dataclass(frozen=True, slots=True)
class VectorLayer(MapLayer):
    """Metadata for an AtlasFeature-backed vector layer."""

    def __post_init__(self) -> None:
        MapLayer.__post_init__(self)
        if self.layer_type is not LayerType.VECTOR:
            raise ValueError("VectorLayer måste ha layer_type vector")


@dataclass(frozen=True, slots=True)
class RasterLayer(MapLayer):
    """Metadata for a raster family that does not use AtlasFeature."""

    def __post_init__(self) -> None:
        MapLayer.__post_init__(self)
        if self.layer_type is not LayerType.RASTER:
            raise ValueError("RasterLayer måste ha layer_type raster")


@dataclass(frozen=True, slots=True)
class ComposedLayer:
    """Composition metadata combined with current Layer Engine state."""

    definition: MapLayer
    description: str
    category: str
    enabled: bool
    supported: bool
    visible: bool
    opacity: float
