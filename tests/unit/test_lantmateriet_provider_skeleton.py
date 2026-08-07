"""Guard the intentionally inactive Lantmäteriet provider design."""

import importlib
import json
from importlib import resources

from magnetatlas.interfaces.web.layers import BUILT_IN_LAYERS


def test_provider_skeleton_has_no_public_implementation() -> None:
    modules = (
        "client",
        "collector",
        "mapper",
        "importer",
    )

    for name in modules:
        module = importlib.import_module(
            f"magnetatlas.infrastructure.sources.lantmateriet.{name}"
        )
        assert not [item for item in vars(module) if not item.startswith("_")]


def test_lantmateriet_catalog_is_declarative_and_inactive() -> None:
    document = json.loads(
        resources.files("magnetatlas.data")
        .joinpath("dataset_catalog.json")
        .read_text(encoding="utf-8")
    )

    source = next(item for item in document["sources"] if item["id"] == "lantmateriet")
    datasets = {item["id"]: item for item in source["datasets"]}

    assert source["status"] == "planned"
    assert datasets["ortnamn"]["status"] == "recommended-next"
    assert datasets["historiska-kartor"]["layer_id"] == "historical-maps"
    assert all(not item["import_enabled"] for item in datasets.values())


def test_historical_maps_remains_a_declarative_future_layer() -> None:
    layer = next(item for item in BUILT_IN_LAYERS if item.id == "historical-maps")

    assert layer.name == "Historiska kartor"
    assert layer.supported_sources == frozenset()
    assert layer.enabled is False
