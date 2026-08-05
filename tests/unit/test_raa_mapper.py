"""Tests for RAÄ to AtlasFeature normalization."""

from datetime import UTC, datetime

import pytest

from magnetatlas.domain.geography import GeoPoint, LineString
from magnetatlas.infrastructure.sources.raa.mapper import (
    map_raa_record,
    sweref99tm_to_wgs84,
)


def test_sweref99tm_is_converted_to_wgs84() -> None:
    point = sweref99tm_to_wgs84(674571.866, 6580743.008)

    assert point.longitude == pytest.approx(18.0686, abs=0.0001)
    assert point.latitude == pytest.approx(59.3293, abs=0.0001)


def test_mapper_preserves_official_metadata_without_inventing_time() -> None:
    fetched_at = datetime(2026, 8, 5, tzinfo=UTC)
    raw = {
        "id": "00004af1-67e0-45a4-91d4-d374dbb98ad7",
        "lamningsnummer": "L1947:8930",
        "lamningstyp": {"id": 1037, "namn": "Fångstgrop"},
        "antikvariskBedomning": {"id": 1, "namn": "Fornlämning"},
        "publiceringsdatum": "2026-08-04T10:00:00+02:00",
        "version": 597505,
        "lan": [{"id": "05", "namn": "Östergötland"}],
        "geometri": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [674571.866, 6580743.008],
                    },
                }
            ],
        },
    }

    feature = map_raa_record(raw, fetched_at=fetched_at)[0]

    assert str(feature.feature_id) == f"raa:{raw['id']}"
    assert feature.title == "L1947:8930"
    assert feature.feature_type == "Fångstgrop"
    assert isinstance(feature.geometry, GeoPoint)
    assert feature.time_span is None
    assert feature.confidence.value is None
    assert feature.provenance.raw_data is raw
    assert feature.provenance.license_info is not None
    assert feature.provenance.license_info.name == "CC0 1.0"


def test_mapper_splits_multi_geometry_without_losing_components() -> None:
    raw = {
        "id": "id-1",
        "lamningsnummer": "L2026:1",
        "lamningstyp": "Hålväg",
        "geometri": {
            "type": "MultiLineString",
            "coordinates": [
                [[500000, 6500000], [500100, 6500100]],
                [[500200, 6500200], [500300, 6500300]],
            ],
        },
    }

    features = map_raa_record(raw)

    assert len(features) == 2
    assert all(isinstance(feature.geometry, LineString) for feature in features)
    assert [str(feature.feature_id) for feature in features] == [
        "raa:id-1:geometry:1",
        "raa:id-1:geometry:2",
    ]


def test_mapper_rejects_records_without_required_source_identity() -> None:
    with pytest.raises(ValueError, match="saknar"):
        map_raa_record({"lamningsnummer": "L2026:1", "lamningstyp": "Röse"})
