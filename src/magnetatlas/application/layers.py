"""Registration and orchestration for source-neutral map layers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from threading import RLock

from magnetatlas.application.feature_queries import (
    DatasetSummary,
    FeatureQuerySource,
    ViewportResult,
)
from magnetatlas.application.features import FeatureSearchFilters
from magnetatlas.domain.datasets import DatasetInstance
from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.domain.layers import LayerDefinition

FeaturePredicate = Callable[[AtlasFeature], bool]


@dataclass(frozen=True, slots=True)
class LayerStatus:
    """Frontend-facing state for one registered layer."""

    definition: LayerDefinition
    supported: bool
    active: bool


class LayerRegistry:
    """Register layers and maintain their process-local visibility state."""

    def __init__(self, layers: Iterable[LayerDefinition] = ()) -> None:
        self._layers: dict[str, LayerDefinition] = {}
        self._visible: set[str] = set()
        self._lock = RLock()
        for layer in layers:
            self.register(layer)

    def register(self, layer: LayerDefinition) -> None:
        """Register a unique layer definition."""
        with self._lock:
            if layer.id in self._layers:
                raise ValueError(f"lagret är redan registrerat: {layer.id}")
            self._layers[layer.id] = layer
            if layer.default_visibility:
                self._visible.add(layer.id)

    def list(self) -> tuple[LayerDefinition, ...]:
        """Return definitions in deterministic registration order."""
        with self._lock:
            return tuple(self._layers.values())

    def get(self, layer_id: str) -> LayerDefinition:
        """Return one definition or raise KeyError."""
        with self._lock:
            return self._layers[layer_id]

    def enable(self, layer_id: str) -> None:
        """Make an available layer visible."""
        with self._lock:
            layer = self._layers[layer_id]
            if not layer.enabled:
                raise ValueError(f"lagret är inte tillgängligt ännu: {layer_id}")
            self._visible.add(layer_id)

    def disable(self, layer_id: str) -> None:
        """Hide a registered layer."""
        with self._lock:
            self._layers[layer_id]
            self._visible.discard(layer_id)

    def is_enabled(self, layer_id: str) -> bool:
        """Return whether a layer is currently visible."""
        with self._lock:
            self._layers[layer_id]
            return layer_id in self._visible

    def is_supported(self, layer_id: str, installed_sources: Iterable[str]) -> bool:
        """Check whether at least one installed source supports a layer."""
        layer = self.get(layer_id)
        return bool(layer.supported_sources.intersection(installed_sources))


class LayerService:
    """Resolve active layers and filter features for imported datasets."""

    def __init__(
        self,
        registry: LayerRegistry,
        dataset_instances: Iterable[DatasetInstance],
        *,
        predicates: Mapping[str, FeaturePredicate] | None = None,
    ) -> None:
        self._registry = registry
        self._instances = {
            instance.dataset_id: instance for instance in dataset_instances
        }
        self._predicates = dict(predicates or {})

    @property
    def dataset_instances(self) -> tuple[DatasetInstance, ...]:
        """Return dataset instances known to the engine."""
        return tuple(self._instances.values())

    def list_layers(self) -> tuple[LayerStatus, ...]:
        """Return all layers with support and visibility state."""
        sources = self._installed_sources()
        return tuple(
            LayerStatus(
                definition=layer,
                supported=self._registry.is_supported(layer.id, sources),
                active=self._is_active(layer, sources),
            )
            for layer in self._registry.list()
        )

    def get_layer(self, layer_id: str) -> LayerStatus:
        """Return frontend state for one layer."""
        layer = self._registry.get(layer_id)
        sources = self._installed_sources()
        return LayerStatus(
            definition=layer,
            supported=self._registry.is_supported(layer_id, sources),
            active=self._is_active(layer, sources),
        )

    def active_layers(
        self, dataset_instance: DatasetInstance | None = None
    ) -> tuple[LayerDefinition, ...]:
        """Return active layers, optionally restricted to one dataset instance."""
        sources = (
            {dataset_instance.source.source_id}
            if dataset_instance is not None
            else self._installed_sources()
        )
        return tuple(
            layer for layer in self._registry.list() if self._is_active(layer, sources)
        )

    def enable(self, layer_id: str) -> LayerStatus:
        """Enable a supported layer and return its new state."""
        if not self._registry.is_supported(layer_id, self._installed_sources()):
            raise ValueError(f"ingen installerad datakälla stöder lagret: {layer_id}")
        self._registry.enable(layer_id)
        return self.get_layer(layer_id)

    def disable(self, layer_id: str) -> LayerStatus:
        """Disable a layer and return its new state."""
        self._registry.disable(layer_id)
        return self.get_layer(layer_id)

    def filter_features(
        self,
        features: Iterable[AtlasFeature],
        dataset_instance: DatasetInstance,
    ) -> tuple[AtlasFeature, ...]:
        """Keep features matched by any active layer for the given dataset."""
        layers = self.active_layers(dataset_instance)
        if not layers:
            return ()
        return tuple(
            feature
            for feature in features
            if any(self._matches(layer, feature) for layer in layers)
        )

    def _installed_sources(self) -> set[str]:
        return {instance.source.source_id for instance in self._instances.values()}

    def _is_active(self, layer: LayerDefinition, sources: Iterable[str]) -> bool:
        return (
            layer.enabled
            and self._registry.is_enabled(layer.id)
            and bool(layer.supported_sources.intersection(sources))
        )

    def _matches(self, layer: LayerDefinition, feature: AtlasFeature) -> bool:
        predicate = self._predicates.get(layer.id)
        return predicate(feature) if predicate is not None else True


class LayerFeatureQuerySource:
    """Apply active layer filtering to an existing bounded query source."""

    def __init__(
        self,
        source: FeatureQuerySource,
        service: LayerService,
        dataset_instance: DatasetInstance,
    ) -> None:
        self._source = source
        self._service = service
        self._instance = dataset_instance

    def summary(self) -> DatasetSummary:
        return self._source.summary()

    def in_bounds(self, bounds: BoundingBox, *, limit: int) -> ViewportResult:
        result = self._source.in_bounds(bounds, limit=limit)
        return ViewportResult(
            self._service.filter_features(result.features, self._instance),
            result.truncated,
        )

    def get(self, feature_id: FeatureId | str) -> AtlasFeature:
        return self._source.get(feature_id)

    def search(
        self,
        query: str,
        *,
        filters: FeatureSearchFilters,
        limit: int,
    ) -> tuple[AtlasFeature, ...]:
        matches = self._source.search(query, filters=filters, limit=limit)
        return self._service.filter_features(matches, self._instance)
