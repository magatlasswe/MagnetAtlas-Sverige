"""Tests for provider-independent collector contracts."""

from dataclasses import dataclass

import pytest

from magnetatlas.application import collectors as collector_module
from magnetatlas.application.collectors import CollectorRegistry
from magnetatlas.domain.collectors import (
    CollectionBatch,
    CollectionRequest,
    CollectorCapability,
    CollectorDescriptor,
)
from magnetatlas.domain.exceptions import CollectorRegistryError


@dataclass
class FakeCollector:
    descriptor = CollectorDescriptor(
        collector_id="fake",
        display_name="Fake source",
        version="1",
        capabilities=frozenset({CollectorCapability.TEXT_SEARCH}),
    )

    def collect(self, request: CollectionRequest) -> CollectionBatch:
        return CollectionBatch(records=[], total_hits=0)


def test_registry_registers_and_lists_collectors() -> None:
    collector = FakeCollector()
    registry = CollectorRegistry([collector])

    assert registry.get("fake") is collector
    assert registry.descriptors() == (collector.descriptor,)


def test_registry_rejects_duplicate_collector_ids() -> None:
    registry = CollectorRegistry([FakeCollector()])

    with pytest.raises(CollectorRegistryError, match="redan registrerat"):
        registry.register(FakeCollector())


def test_registry_reports_unknown_collector() -> None:
    with pytest.raises(CollectorRegistryError, match="Okänd collector"):
        CollectorRegistry().get("missing")


def test_registry_discovers_factory_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeEntryPoint:
        name = "fake"

        @staticmethod
        def load() -> type[FakeCollector]:
            return FakeCollector

    monkeypatch.setattr(
        collector_module.metadata,
        "entry_points",
        lambda *, group: [FakeEntryPoint()],
    )

    registry = CollectorRegistry.discover()

    assert registry.get("fake").descriptor.display_name == "Fake source"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"query": "  "}, "Sökfrågan"),
        ({"limit": 0}, "Antal träffar"),
        ({"cursor": ""}, "cursor"),
    ],
)
def test_collection_request_rejects_invalid_values(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        CollectionRequest(**kwargs)  # type: ignore[arg-type]


def test_request_derives_required_capabilities() -> None:
    request = CollectionRequest(query="bro", cursor="next")

    assert request.required_capabilities == frozenset(
        {
            CollectorCapability.TEXT_SEARCH,
            CollectorCapability.RESULT_LIMIT,
            CollectorCapability.CURSOR_PAGINATION,
        }
    )
