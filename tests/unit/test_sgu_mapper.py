"""Tests for SGU GeoJSON normalization."""

from datetime import UTC, datetime

import pytest

from magnetatlas.domain.geography import Polygon
from magnetatlas.infrastructure.sources.sgu.mapper import map_sgu_feature


def raw_feature(*, geometry_type: str = "Polygon") -> dict[str, object]:
    coordinates: object = [[[18.0, 59.0], [18.1, 59.0], [18.1, 59.1], [18.0, 59.0]]]
    if geometry_type == "MultiPolygon":
        coordinates = [coordinates, coordinates]
    return {
        "type": "Feature",
        "id": "grundlager.42",
        "geometry": {"type": geometry_type, "coordinates": coordinates},
        "properties": {
            "jg2": 100,
            "jg2_tx": "Morän",
            "objectid": 42,
            "ignored": "provider-only",
        },
    }


def test_mapper_preserves_sgu_identity_license_confidence_and_properties() -> None:
    fetched_at = datetime(2026, 8, 7, tzinfo=UTC)

    feature = map_sgu_feature(
        raw_feature(),
        dataset_id="jordarter",
        dataset_name="Jordarter",
        collection_id="grundlager",
        source_url="https://api.sgu.se/items",
        fetched_at=fetched_at,
    )[0]

    assert str(feature.feature_id) == "sgu:jordarter:grundlager.42"
    assert feature.title == "Morän"
    assert feature.feature_type == "jordart"
    assert isinstance(feature.geometry, Polygon)
    assert feature.provenance.source_id == "grundlager.42"
    assert feature.provenance.fetched_at == fetched_at
    assert feature.provenance.license_info is not None
    assert feature.provenance.license_info.name == "Creative Commons CC0 1.0"
    assert feature.confidence.rationale is not None
    assert feature.properties["source_properties"]["sgu"] == {
        "jg2": 100,
        "jg2_tx": "Morän",
        "objectid": 42,
    }


def test_mapper_splits_multipolygons_without_losing_source_identity() -> None:
    features = map_sgu_feature(
        raw_feature(geometry_type="MultiPolygon"),
        dataset_id="jordarter",
        dataset_name="Jordarter",
        collection_id="grundlager",
        source_url="https://api.sgu.se/items",
    )

    assert len(features) == 2
    assert {feature.provenance.source_id for feature in features} == {"grundlager.42"}
    assert str(features[1].feature_id).endswith(":geometry:2")


def test_mapper_rejects_missing_stable_identity() -> None:
    raw = raw_feature()
    del raw["id"]

    with pytest.raises(ValueError, match="stabilt id"):
        map_sgu_feature(
            raw,
            dataset_id="jordarter",
            dataset_name="Jordarter",
            collection_id="grundlager",
            source_url="https://api.sgu.se/items",
        )
