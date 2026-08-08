"""Network-isolated verification of the complete national import boundary."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

from magnetatlas.application.layer_composition import ComposedFeatureQuerySource
from magnetatlas.application.sync import SyncService
from magnetatlas.cli import LANTMATERIET_SOURCE, RAA_SOURCE, SGU_SOURCE
from magnetatlas.domain.datasets import DatasetInstance, DatasetScope
from magnetatlas.domain.features import AtlasFeature, FeatureId, Provenance
from magnetatlas.domain.geography import BoundingBox, GeoPoint
from magnetatlas.infrastructure.database.feature_queries import (
    SqlAlchemyFeatureQuerySource,
)
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyAtlasFeatureRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory
from magnetatlas.interfaces.web.layer_composition import (
    create_layer_composition_service,
)
from magnetatlas.interfaces.web.layers import create_layer_service
from magnetatlas.interfaces.web.serializers import serialize_layer


class NationalCollector:
    """Deterministic provider stand-in at the shared Collector boundary."""

    base_schema_version = "test-v1"

    def __init__(self, feature: AtlasFeature) -> None:
        self._feature = feature

    def fetch_base_batches(
        self,
        destination: Path,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
    ) -> Iterator[tuple[AtlasFeature, ...]]:
        del destination, county, municipality, bbox
        yield (self._feature,)

    def collect_changes(self, start: date, end: date) -> list[AtlasFeature]:
        del start, end
        return []


def test_all_official_sources_reach_sqlite_layers_and_api_contract(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(f"sqlite:///{tmp_path / 'production.db'}")
    repository = SqlAlchemyAtlasFeatureRepository(session_factory)
    sources = (RAA_SOURCE, SGU_SOURCE, LANTMATERIET_SOURCE)

    for index, source in enumerate(sources):
        instance = DatasetInstance.create(source, DatasetScope.country("sweden"))
        feature = AtlasFeature(
            feature_id=FeatureId(f"{source.source_id}:feature-1"),
            title=source.display_name,
            feature_type="official-test",
            provenance=Provenance(
                source=source.display_name,
                source_id=f"{source.source_id}:source-1",
            ),
            geometry=GeoPoint(longitude=15.0 + index, latitude=60.0),
        )
        result = SyncService(
            instance,
            NationalCollector(feature),
            repository,
            tmp_path / source.source_id,
        ).base_import()

        assert result.imported == 1
        assert repository.get_active_instance(source.source_id) == instance
        assert repository.lookup(
            feature.provenance.source_id, dataset_id=instance.dataset_id
        ) == (feature.feature_id,)

    instances = tuple(
        repository.get_active_instance(source.source_id) for source in sources
    )
    assert all(instance is not None for instance in instances)
    active_instances = tuple(instance for instance in instances if instance is not None)
    layer_service = create_layer_service(active_instances)
    active_layer_ids = {
        layer.definition.id for layer in layer_service.list_layers() if layer.active
    }
    assert {"cultural-heritage", "soil-types", "place-names"} <= active_layer_ids

    composition = create_layer_composition_service(layer_service)
    payload = tuple(serialize_layer(layer) for layer in composition.list_layers())
    visible_ids = {str(layer["id"]) for layer in payload if layer["visible"]}
    assert {"cultural-heritage", "soil-types", "place-names"} <= visible_ids

    query_sources = tuple(
        (
            instance,
            SqlAlchemyFeatureQuerySource(session_factory, instance.dataset_id),
        )
        for instance in active_instances
    )
    map_source = ComposedFeatureQuerySource(query_sources, layer_service)
    result = map_source.in_bounds(BoundingBox(10, 55, 20, 70), limit=10)
    assert len(result.features) == 3
    assert map_source.summary().count == 3
