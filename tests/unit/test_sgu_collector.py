"""Network-isolated tests for the configurable SGU provider."""

from pathlib import Path
from typing import Any

import pytest

from magnetatlas.domain.collectors import CollectorCapability, CollectorOutputModel
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.infrastructure.sources.sgu.client import (
    CRS84,
    DEFAULT_PAGE_SIZE,
    DEFAULT_RETRY_COUNT,
    SGUClient,
)
from magnetatlas.infrastructure.sources.sgu.collector import (
    SGU_JORDARTER,
    SGU_SOURCE_DEFINITION,
    SGUCollector,
    SGUDatasetDefinition,
)


def raw_feature(number: int) -> dict[str, object]:
    return {
        "type": "Feature",
        "id": f"grundlager.{number}",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[18.0, 59.0], [18.1, 59.0], [18.1, 59.1], [18.0, 59.0]]],
        },
        "properties": {"jg2_tx": "Morän", "objectid": number},
    }


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self._payload


class FakeSession:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = iter(payloads)
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(next(self.payloads))


def test_national_transport_defaults_stay_within_sgu_contract() -> None:
    assert 1_000 < DEFAULT_PAGE_SIZE <= 10_000
    assert DEFAULT_RETRY_COUNT == 8


def test_client_uses_documented_ogc_parameters_and_next_links() -> None:
    next_url = "https://api.sgu.se/next"
    session = FakeSession(
        [
            {
                "features": [raw_feature(1)],
                "links": [{"rel": "next", "href": next_url}],
            },
            {"features": [raw_feature(2)], "links": []},
        ]
    )
    client = SGUClient(session=session, page_size=25)  # type: ignore[arg-type]
    bounds = BoundingBox(18.0, 59.0, 19.0, 60.0)

    features = list(client.iter_features("dataset", "collection", bbox=bounds))

    assert len(features) == 2
    assert session.calls[0]["params"] == {
        "f": "application/geo+json",
        "limit": 25,
        "crs": CRS84,
        "bbox": "18.0,59.0,19.0,60.0",
    }
    assert session.calls[1]["url"] == next_url
    assert session.calls[1]["params"] is None


class FakeClient:
    def iter_features(self, *args: object, **kwargs: object) -> Any:
        yield from (raw_feature(1), raw_feature(2), raw_feature(3))


def test_collector_is_dataset_configurable_and_streams_bounded_batches(
    tmp_path: Path,
) -> None:
    future = SGUDatasetDefinition(
        "future",
        "Future dataset",
        "future-path",
        "future-collection",
        "v1",
        SGU_SOURCE_DEFINITION,
    )
    collector = SGUCollector(FakeClient(), future, batch_size=2)  # type: ignore[arg-type]

    batches = list(collector.fetch_base_batches(tmp_path / "unused"))

    assert [len(batch) for batch in batches] == [2, 1]
    assert collector.descriptor.output_model is CollectorOutputModel.ATLAS_FEATURE
    assert collector.descriptor.source == SGU_SOURCE_DEFINITION
    assert collector.descriptor.supports(CollectorCapability.BASE_IMPORT)
    assert collector.base_schema_version == "v1"


def test_jordarter_definition_uses_official_collection() -> None:
    assert SGU_JORDARTER.api_path == "jordarter25k-100k"
    assert SGU_JORDARTER.collection_id == "grundlager"
    assert SGU_JORDARTER.source.source_id == "sgu-jordarter"


def test_named_scope_requires_an_explicit_official_bbox(tmp_path: Path) -> None:
    collector = SGUCollector(FakeClient())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="kräver --bbox"):
        next(collector.fetch_base_batches(tmp_path / "unused", county="stockholm"))
