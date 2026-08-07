"""Configurable SGU provider implementing the shared Collector contract."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from magnetatlas.domain.collectors import (
    CollectorCapability,
    CollectorDescriptor,
    CollectorOutputModel,
)
from magnetatlas.domain.datasets import SourceDefinition
from magnetatlas.domain.features import AtlasFeature
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.infrastructure.sources.sgu.client import SGUClient
from magnetatlas.infrastructure.sources.sgu.mapper import map_sgu_feature

SGU_SOURCE_DEFINITION = SourceDefinition(
    "sgu-jordarter", "SGU Jordarter 1:25 000-1:100 000"
)


@dataclass(frozen=True, slots=True)
class SGUDatasetDefinition:
    """Provider configuration for one documented SGU OGC feature collection."""

    dataset_id: str
    name: str
    api_path: str
    collection_id: str
    schema_version: str
    source: SourceDefinition


SGU_JORDARTER = SGUDatasetDefinition(
    dataset_id="jordarter",
    name="Jordarter 1:25 000-1:100 000",
    api_path="jordarter25k-100k",
    collection_id="grundlager",
    schema_version="ogc-api-features-v1:grundlager",
    source=SGU_SOURCE_DEFINITION,
)


class SGUCollector:
    """Collect one configured SGU dataset without persistence concerns."""

    def __init__(
        self,
        client: SGUClient,
        dataset: SGUDatasetDefinition = SGU_JORDARTER,
        *,
        batch_size: int = 500,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size måste vara större än noll")
        self._client = client
        self._dataset = dataset
        self._batch_size = batch_size

    @property
    def descriptor(self) -> CollectorDescriptor:
        return CollectorDescriptor(
            collector_id=f"sgu-{self._dataset.dataset_id}",
            display_name=f"SGU {self._dataset.name}",
            version="1.0",
            capabilities=frozenset(
                {
                    CollectorCapability.BASE_IMPORT,
                    CollectorCapability.COUNTRY_SCOPE,
                    CollectorCapability.COUNTY_SCOPE,
                    CollectorCapability.MUNICIPALITY_SCOPE,
                    CollectorCapability.BBOX_SCOPE,
                }
            ),
            output_model=CollectorOutputModel.ATLAS_FEATURE,
            source=self._dataset.source,
        )

    @property
    def base_schema_version(self) -> str:
        return self._dataset.schema_version

    def fetch_base_batches(
        self,
        destination: Path,
        *,
        county: str | None = None,
        municipality: str | None = None,
        bbox: BoundingBox | None = None,
    ) -> Iterator[tuple[AtlasFeature, ...]]:
        """Stream mapped SGU features in bounded batches."""
        del destination
        if (county or municipality) and bbox is None:
            raise ValueError("SGU:s OGC-tjänst kräver --bbox för läns- och kommunurval")
        source_url = (
            f"https://api.sgu.se/oppnadata/{self._dataset.api_path}/ogc/features/v1/"
            f"collections/{self._dataset.collection_id}/items"
        )
        batch: list[AtlasFeature] = []
        for raw in self._client.iter_features(
            self._dataset.api_path, self._dataset.collection_id, bbox=bbox
        ):
            batch.extend(
                map_sgu_feature(
                    raw,
                    dataset_id=self._dataset.dataset_id,
                    dataset_name=self._dataset.name,
                    collection_id=self._dataset.collection_id,
                    source_url=source_url,
                )
            )
            while len(batch) >= self._batch_size:
                yield tuple(batch[: self._batch_size])
                del batch[: self._batch_size]
        if batch:
            yield tuple(batch)

    def collect_changes(self, start: date, end: date) -> list[AtlasFeature]:
        """Reject incremental sync; this dataset advertises base import only."""
        del start, end
        raise ValueError(
            "SGU Jordarter saknar dokumenterat inkrementellt ändringsflöde"
        )
