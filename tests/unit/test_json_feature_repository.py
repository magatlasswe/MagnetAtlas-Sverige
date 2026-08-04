"""Tests for the local AtlasFeature JSON adapter."""

import json
from pathlib import Path

import pytest

from magnetatlas.domain import BoundingBox, GeoPoint, LineString, Polygon
from magnetatlas.domain.exceptions import FeatureDataError
from magnetatlas.infrastructure.features import load_demo_features, load_features


def feature_payload(geometry: dict[str, object]) -> dict[str, object]:
    return {
        "feature_id": "demo:1",
        "title": "Demo: gammal bro",
        "feature_type": "bro",
        "description": "Syntetiskt demonstrationsobjekt.",
        "place": "Örebro",
        "geometry": geometry,
        "time_span": {
            "original_text": "1800-talet",
            "precision": "century",
            "certainty": {"value": 0.5, "rationale": "Demodata"},
        },
        "provenance": {
            "source": "magnetatlas-demo",
            "source_id": "1",
            "fetched_at": "2026-01-01T00:00:00Z",
            "license_info": {
                "name": "MagnetAtlas syntetiska demodata",
                "requires_attribution": True,
                "commercial_use_allowed": False,
            },
            "raw_data": {},
        },
        "confidence": {"value": 0.4, "rationale": "Syntetiskt objekt"},
        "geometry_confidence": {"value": 0.3},
        "properties": {"demo": True},
        "relationships": [],
    }


def write_document(path: Path, features: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"schema_version": 1, "features": features}), encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("geometry", "expected_type"),
    [
        ({"type": "Point", "coordinates": [18.0, 59.0]}, GeoPoint),
        (
            {"type": "BoundingBox", "coordinates": [17.0, 58.0, 18.0, 59.0]},
            BoundingBox,
        ),
        (
            {"type": "LineString", "coordinates": [[17.0, 58.0], [18.0, 59.0]]},
            LineString,
        ),
        (
            {
                "type": "Polygon",
                "coordinates": [
                    [[17.0, 58.0], [18.0, 58.0], [18.0, 59.0], [17.0, 58.0]]
                ],
            },
            Polygon,
        ),
    ],
)
def test_load_features_supports_every_geometry(
    tmp_path: Path,
    geometry: dict[str, object],
    expected_type: type[object],
) -> None:
    path = tmp_path / "features.json"
    write_document(path, [feature_payload(geometry)])

    feature = load_features(path)[0]

    assert isinstance(feature.geometry, expected_type)
    assert feature.time_span is not None
    assert feature.time_span.original_text == "1800-talet"
    assert feature.provenance.license_info is not None
    assert feature.provenance.license_info.requires_attribution is True


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"schema_version": 2, "features": []}),
        json.dumps({"schema_version": 1, "features": [{}]}),
        json.dumps(
            {
                "schema_version": 1,
                "features": [
                    feature_payload({"type": "Point", "coordinates": [999.0, 59.0]})
                ],
            }
        ),
    ],
)
def test_load_features_reports_invalid_documents(tmp_path: Path, content: str) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(FeatureDataError, match="Kunde inte läsa featuredata"):
        load_features(path)


def test_load_features_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FeatureDataError, match="Kunde inte läsa featuredata"):
        load_features(tmp_path / "missing.json")


def test_bundled_demo_dataset_is_usable_and_explicitly_synthetic() -> None:
    features = load_demo_features()

    assert len(features) == 60
    assert all(feature.properties.get("demo") is True for feature in features)
    assert all("Demo" in feature.title for feature in features)
    assert {type(feature.geometry) for feature in features} == {
        GeoPoint,
        BoundingBox,
        LineString,
        Polygon,
    }
