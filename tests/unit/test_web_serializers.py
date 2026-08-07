"""Tests for safe AtlasFeature web serialization."""

from datetime import UTC, datetime

import pytest

from magnetatlas.application.features import FeatureCatalog
from magnetatlas.domain import (
    AtlasFeature,
    BoundingBox,
    FeatureId,
    GeoPoint,
    LineString,
    Polygon,
    Provenance,
)
from magnetatlas.interfaces.web.serializers import serialize_feature_collection


@pytest.mark.parametrize(
    ("geometry", "geojson_type"),
    [
        (GeoPoint(18.0, 59.0), "Point"),
        (BoundingBox(17.0, 58.0, 18.0, 59.0), "Polygon"),
        (LineString((GeoPoint(17.0, 58.0), GeoPoint(18.0, 59.0))), "LineString"),
        (
            Polygon(
                (
                    (
                        GeoPoint(17.0, 58.0),
                        GeoPoint(18.0, 58.0),
                        GeoPoint(18.0, 59.0),
                        GeoPoint(17.0, 58.0),
                    ),
                )
            ),
            "Polygon",
        ),
    ],
)
def test_serializer_supports_geometries_and_omits_raw_data(
    geometry: GeoPoint | BoundingBox | LineString | Polygon,
    geojson_type: str,
) -> None:
    feature = AtlasFeature(
        feature_id=FeatureId("demo:1"),
        title="Demo",
        feature_type="bro",
        provenance=Provenance(
            source="demo",
            source_id="1",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            raw_data={"secret": "not for web"},
        ),
        geometry=geometry,
        properties={
            "source_properties": {
                "example": {
                    "external_id": "abc",
                    "category": "Fornlämning",
                    "last_updated": "2026-01-01",
                }
            },
        },
    )
    payload = serialize_feature_collection(FeatureCatalog([feature]))

    serialized = payload["features"][0]
    assert serialized["geometry"]["type"] == geojson_type
    assert "raw_data" not in str(serialized)
    assert serialized["properties"]["navigation"]["url"].startswith(
        "https://www.openstreetmap.org/directions?"
    )
    assert serialized["properties"]["period"] == "unknown"
    assert payload["is_demo"] is False
    assert payload["summary"] == {
        "count": 1,
        "latest_import": "2026-01-01T00:00:00+00:00",
        "source": "demo",
        "status": "Officiell",
    }
    assert serialized["properties"]["provenance"] == {
        "source": "demo",
        "source_id": "1",
        "source_url": None,
        "fetched_at": "2026-01-01T00:00:00+00:00",
    }
    assert serialized["properties"]["source_properties"] == {
        "example": {
            "external_id": "abc",
            "category": "Fornlämning",
            "last_updated": "2026-01-01",
        }
    }
    assert serialized["properties"]["discovery"] == {
        "supporting_sources": ["demo"],
        "estimated": True,
        "data_source": "demo",
    }
