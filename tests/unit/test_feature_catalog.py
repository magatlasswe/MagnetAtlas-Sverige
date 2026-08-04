"""Tests for local feature search, selection and navigation."""

from datetime import UTC, date, datetime

import pytest

from magnetatlas.application.features import (
    FeatureCatalog,
    FeatureSearchFilters,
    feature_period,
)
from magnetatlas.domain import (
    AtlasFeature,
    BoundingBox,
    FeatureId,
    GeoPoint,
    LineString,
    Polygon,
    Provenance,
    TimeSpan,
)


def make_feature(
    feature_id: str,
    *,
    title: str = "Gammal bro",
    feature_type: str = "bro",
    place: str | None = "Örebro",
    description: str | None = "Historisk passage över ån",
    geometry: GeoPoint | BoundingBox | LineString | Polygon | None = None,
    source: str = "test",
    time_span: TimeSpan | None = None,
) -> AtlasFeature:
    return AtlasFeature(
        feature_id=FeatureId(feature_id),
        title=title,
        feature_type=feature_type,
        provenance=Provenance(
            source=source,
            source_id=feature_id,
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        place=place,
        description=description,
        geometry=geometry,
        time_span=time_span,
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
    "query",
    ["Örebrp", "historisk passsage", "gmamal bro"],
)
def test_search_tolerates_small_spelling_errors_without_ranking(query: str) -> None:
    feature = make_feature("1")

    assert FeatureCatalog([feature]).search(query) == [feature]


def test_search_filters_by_type_period_and_source() -> None:
    matching = make_feature(
        "1",
        source="demo-archive",
        time_span=TimeSpan(start=date(1850, 1, 1), precision="year"),
    )
    other = make_feature(
        "2",
        feature_type="kvarn",
        source="other-source",
        time_span=TimeSpan(original_text="1700-talet"),
    )
    filters = FeatureSearchFilters(
        feature_types=frozenset({"bro"}),
        periods=frozenset({"1800s"}),
        sources=frozenset({"demo-archive"}),
    )

    assert FeatureCatalog([matching, other]).search("", filters=filters) == [matching]


@pytest.mark.parametrize(
    ("time_span", "expected"),
    [
        (None, "unknown"),
        (TimeSpan(original_text="medeltid"), "before_1800"),
        (TimeSpan(original_text="1800-talet"), "1800s"),
        (TimeSpan(start=date(1920, 1, 1)), "1900s_or_later"),
    ],
)
def test_feature_period_is_coarse_and_explainable(
    time_span: TimeSpan | None, expected: str
) -> None:
    assert feature_period(make_feature("1", time_span=time_span)) == expected


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
