"""Tests for local feature search, selection and navigation."""

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


def make_feature(
    feature_id: str,
    *,
    title: str = "Gammal bro",
    feature_type: str = "bro",
    place: str | None = "Örebro",
    description: str | None = "Historisk passage över ån",
    geometry: GeoPoint | BoundingBox | LineString | Polygon | None = None,
) -> AtlasFeature:
    return AtlasFeature(
        feature_id=FeatureId(feature_id),
        title=title,
        feature_type=feature_type,
        provenance=Provenance(
            source="test",
            source_id=feature_id,
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        place=place,
        description=description,
        geometry=geometry,
    )


def test_catalog_selects_feature_and_rejects_duplicate_ids() -> None:
    feature = make_feature("feature:1")
    catalog = FeatureCatalog([feature])

    assert catalog.get("feature:1") is feature
    with pytest.raises(KeyError, match="Okänd AtlasFeature"):
        catalog.get("missing")
    with pytest.raises(ValueError, match="Duplicerat"):
        FeatureCatalog([feature, feature])


def test_search_is_swedish_case_insensitive_and_checks_user_facing_fields() -> None:
    features = [
        make_feature("1"),
        make_feature(
            "2",
            title="Kvarnlämning",
            feature_type="kvarn",
            place="Uppsala",
            description="Vid Fyrisån",
        ),
    ]
    catalog = FeatureCatalog(features)

    assert catalog.search("ÖREBRO") == [features[0]]
    assert catalog.search("uppsala kvarn") == [features[1]]
    assert catalog.search("fyrisån") == [features[1]]
    assert catalog.search("  ") == []


def test_search_preserves_source_order_and_applies_limit() -> None:
    features = [make_feature(str(index), title=f"Bro {index}") for index in range(3)]

    assert FeatureCatalog(features).search("bro", limit=2) == features[:2]


@pytest.mark.parametrize(
    ("geometry", "expected", "approximate"),
    [
        (GeoPoint(18.0, 59.0), GeoPoint(18.0, 59.0), False),
        (
            BoundingBox(16.0, 58.0, 18.0, 60.0),
            GeoPoint(17.0, 59.0),
            True,
        ),
        (
            LineString((GeoPoint(16.0, 58.0), GeoPoint(17.0, 59.0))),
            GeoPoint(17.0, 59.0),
            True,
        ),
        (
            Polygon(
                (
                    (
                        GeoPoint(16.0, 58.0),
                        GeoPoint(18.0, 58.0),
                        GeoPoint(18.0, 60.0),
                        GeoPoint(16.0, 58.0),
                    ),
                )
            ),
            GeoPoint(17.0, 59.0),
            True,
        ),
    ],
)
def test_navigation_target_supports_every_geometry(
    geometry: GeoPoint | BoundingBox | LineString | Polygon,
    expected: GeoPoint,
    approximate: bool,
) -> None:
    feature = make_feature("1", geometry=geometry)

    target = FeatureCatalog([feature]).navigation_target("1")

    assert target is not None
    assert target.point == expected
    assert target.approximate is approximate


def test_navigation_target_is_absent_without_geometry() -> None:
    assert FeatureCatalog([make_feature("1")]).navigation_target("1") is None
