"""Compatibility conversions between established and shared domain models."""

from magnetatlas.domain.features import (
    AtlasFeature,
    FeatureId,
    Provenance,
    TimeSpan,
)
from magnetatlas.domain.models import ArchiveRecord


def archive_record_to_atlas_feature(record: ArchiveRecord) -> AtlasFeature:
    """Convert an archive record without inventing missing source knowledge."""
    properties: dict[str, object] = {}
    if record.detail_type is not None:
        properties["detail_type"] = record.detail_type

    return AtlasFeature(
        feature_id=FeatureId(f"{record.source}:{record.source_id}"),
        title=record.title,
        feature_type=record.object_type,
        provenance=Provenance(
            source=record.source,
            source_id=record.source_id,
            source_url=record.source_url,
            fetched_at=record.fetched_at,
            raw_data=record.raw_data,
        ),
        description=record.description,
        place=record.place,
        time_span=(
            TimeSpan(original_text=record.date_text)
            if record.date_text is not None
            else None
        ),
        properties=properties,
    )
