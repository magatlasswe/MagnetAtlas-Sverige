"""Map composition policy layered above the existing Layer Engine."""

from __future__ import annotations

from collections.abc import Iterable

from magnetatlas.application.feature_queries import (
    DatasetSummary,
    FeatureQuerySource,
    ViewportResult,
)
from magnetatlas.application.features import FeatureSearchFilters
from magnetatlas.application.layers import LayerService, LayerStatus
from magnetatlas.domain.datasets import DatasetInstance
from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.domain.map_layers import ComposedLayer, MapLayer


class LayerCompositionService:
    """Combine engine state with rendering metadata, order and opacity."""

    def __init__(
        self, layer_service: LayerService, definitions: Iterable[MapLayer]
    ) -> None:
        self._layer_service = layer_service
        selected = tuple(definitions)
        self._definitions = {item.id: item for item in selected}
        if len(self._definitions) != len(selected):
            raise ValueError("Ett composition-lager-id är registrerat flera gånger")
        engine_ids = {
            status.definition.id for status in self._layer_service.list_layers()
        }
        if set(self._definitions) != engine_ids:
            raise ValueError("Composition-katalogen måste motsvara Layer Engine")
        self._opacity = {item.id: item.opacity for item in selected}

    def list_layers(self) -> tuple[ComposedLayer, ...]:
        """Return every layer in deterministic rendering order."""
        statuses = {
            status.definition.id: status for status in self._layer_service.list_layers()
        }
        definitions = sorted(
            self._definitions.values(), key=lambda item: (item.z_index, item.id)
        )
        return tuple(self._compose(item, statuses[item.id]) for item in definitions)

    def get_layer(self, layer_id: str) -> ComposedLayer:
        """Return one composed layer or raise KeyError for an unknown id."""
        definition = self._definitions[layer_id]
        return self._compose(definition, self._layer_service.get_layer(layer_id))

    def set_visibility(self, layer_id: str, visible: bool) -> ComposedLayer:
        """Delegate availability-aware visibility to the existing Layer Engine."""
        status = (
            self._layer_service.enable(layer_id)
            if visible
            else self._layer_service.disable(layer_id)
        )
        return self._compose(self._definitions[layer_id], status)

    def set_opacity(self, layer_id: str, opacity: float) -> ComposedLayer:
        """Set process-local opacity without changing dataset or engine state."""
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity måste vara mellan 0 och 1")
        self._opacity[layer_id] = opacity
        return self.get_layer(layer_id)

    def _compose(self, definition: MapLayer, status: LayerStatus) -> ComposedLayer:
        return ComposedLayer(
            definition=definition,
            description=status.definition.description,
            category=status.definition.category,
            enabled=status.definition.enabled,
            supported=status.supported,
            visible=status.active,
            opacity=self._opacity[definition.id],
        )


class ComposedFeatureQuerySource:
    """Merge bounded vector queries from multiple active dataset instances."""

    def __init__(
        self,
        sources: Iterable[tuple[DatasetInstance, FeatureQuerySource]],
        layer_service: LayerService,
    ) -> None:
        self._sources = tuple(sources)
        self._layer_service = layer_service
        if not self._sources:
            raise ValueError("Minst en datasetkälla krävs för kartkomposition")

    def summary(self) -> DatasetSummary:
        """Combine bounded dataset summaries without reading feature rows."""
        summaries = tuple(source.summary() for _, source in self._sources)
        latest = max(
            (item.latest_import for item in summaries if item.latest_import),
            default=None,
        )
        names = sorted({item.source for item in summaries if item.source})
        count = sum(item.count for item in summaries)
        return DatasetSummary(
            count=count,
            latest_import=latest,
            source=", ".join(names) if names else None,
            status="Officiell" if count else "Tom",
            is_demo=bool(summaries) and all(item.is_demo for item in summaries),
        )

    def in_bounds(self, bounds: BoundingBox, *, limit: int) -> ViewportResult:
        """Merge viewport results fairly while retaining a global response bound."""
        batches: list[tuple[AtlasFeature, ...]] = []
        truncated = False
        for instance, source in self._sources:
            result = source.in_bounds(bounds, limit=limit)
            batches.append(
                self._layer_service.filter_features(result.features, instance)
            )
            truncated = truncated or result.truncated
        selected = self._round_robin(batches, limit)
        return ViewportResult(
            selected,
            truncated or sum(len(batch) for batch in batches) > len(selected),
        )

    def get(self, feature_id: FeatureId | str) -> AtlasFeature:
        """Resolve an id across installed datasets without materializing them."""
        for instance, source in self._sources:
            try:
                feature = source.get(feature_id)
            except KeyError:
                continue
            if self._layer_service.filter_features((feature,), instance):
                return feature
            raise KeyError(f"AtlasFeature är dold av aktiva lager: {feature_id}")
        raise KeyError(f"Okänd AtlasFeature: {feature_id}")

    def search(
        self,
        query: str,
        *,
        filters: FeatureSearchFilters,
        limit: int,
    ) -> tuple[AtlasFeature, ...]:
        """Merge already bounded provider-neutral search results fairly."""
        batches = tuple(
            self._layer_service.filter_features(
                source.search(query, filters=filters, limit=limit), instance
            )
            for instance, source in self._sources
        )
        return self._round_robin(batches, limit)

    @staticmethod
    def _round_robin(
        batches: Iterable[tuple[AtlasFeature, ...]], limit: int
    ) -> tuple[AtlasFeature, ...]:
        iterators = [iter(batch) for batch in batches]
        selected: list[AtlasFeature] = []
        while iterators and len(selected) < limit:
            remaining = []
            for iterator in iterators:
                try:
                    selected.append(next(iterator))
                except StopIteration:
                    continue
                remaining.append(iterator)
                if len(selected) == limit:
                    break
            iterators = remaining
        return tuple(selected)
