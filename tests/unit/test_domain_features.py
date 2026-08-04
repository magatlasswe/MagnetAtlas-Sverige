"""Tests for the shared geographical feature domain model."""

from datetime import UTC, date, datetime

import pytest

from magnetatlas.domain import (
    AtlasFeature,
    BoundingBox,
    Confidence,
    FeatureId,
    GeoPoint,
    LicenseInfo,
    LineString,
    Polygon,
    Provenance,
    TimeSpan,
    archive_record_to_atlas_feature,
)
from magnetatlas.domain.models import ArchiveRecord


@pytest.mark.parametrize(
    ("longitude", "latitude"),
    [(181.0, 0.0), (-181.0, 0.0), (0.0, 91.0), (0.0, -91.0)],
)
def test_geo_point_rejects_coordinates_outside_wgs84(
    longitude: float, latitude: float
) -> None:
    with pytest.raises(ValueError):
        GeoPoint(longitude=longitude, latitude=latitude)


def test_bounding_box_contains_boundary_point() -> None:
    bounding_box = BoundingBox(west=10.0, south=55.0, east=25.0, north=70.0)

    assert bounding_box.contains(GeoPoint(longitude=10.0, latitude=70.0))
    assert not bounding_box.contains(GeoPoint(longitude=9.0, latitude=60.0))


@pytest.mark.parametrize(
    "bounding_box",
    [
        {"west": 20.0, "south": 55.0, "east": 10.0, "north": 70.0},
        {"west": 10.0, "south": 70.0, "east": 20.0, "north": 55.0},
    ],
)
def test_bounding_box_rejects_reversed_bounds(
    bounding_box: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        BoundingBox(**bounding_box)


def test_line_string_requires_two_points() -> None:
    with pytest.raises(ValueError, match="minst två"):
        LineString(points=(GeoPoint(18.0, 59.0),))


def test_polygon_requires_closed_rings() -> None:
    ring = (
        GeoPoint(18.0, 59.0),
        GeoPoint(19.0, 59.0),
        GeoPoint(19.0, 60.0),
        GeoPoint(18.0, 60.0),
    )

    with pytest.raises(ValueError, match="sluten"):
        Polygon(rings=(ring,))


def test_time_span_preserves_imprecise_historical_text() -> None:
    span = TimeSpan(
        original_text="1800-talet",
        precision="century",
        certainty=Confidence(0.6, "Källans egen datering"),
    )

    assert span.original_text == "1800-talet"
    assert span.certainty.value == 0.6


def test_time_span_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError, match="start"):
        TimeSpan(start=date(1900, 1, 1), end=date(1800, 1, 1))


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_confidence_rejects_values_outside_normalized_range(value: float) -> None:
    with pytest.raises(ValueError, match="mellan 0 och 1"):
        Confidence(value)


def test_provenance_requires_timezone_aware_retrieval_time() -> None:
    with pytest.raises(ValueError, match="tidszon"):
        Provenance(
            source="source",
            source_id="id",
            fetched_at=datetime(2026, 1, 1),
        )


def test_atlas_feature_supports_license_geometry_and_relationships() -> None:
    related_id = FeatureId("related:1")
    feature = AtlasFeature(
        feature_id=FeatureId("source:1"),
        title="Historisk bro",
        feature_type="bridge",
        provenance=Provenance(
            source="source",
            source_id="1",
            license_info=LicenseInfo(
                name="Example license",
                requires_attribution=True,
                commercial_use_allowed=False,
            ),
        ),
        geometry=GeoPoint(longitude=18.0686, latitude=59.3293),
        relationships=(related_id,),
    )

    assert feature.relationships == (related_id,)
    assert feature.provenance.license_info is not None
    assert feature.provenance.license_info.requires_attribution is True


def test_archive_record_conversion_preserves_existing_information(
    archive_record: ArchiveRecord,
) -> None:
    feature = archive_record_to_atlas_feature(archive_record)

    assert feature.feature_id == FeatureId("riksarkivet:record-1")
    assert feature.title == archive_record.title
    assert feature.feature_type == archive_record.object_type
    assert feature.time_span == TimeSpan(original_text="1890")
    assert feature.provenance.source_url == archive_record.source_url
    assert feature.provenance.fetched_at == datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    assert feature.provenance.raw_data == archive_record.raw_data
    assert feature.provenance.license_info is None
    assert feature.geometry is None
