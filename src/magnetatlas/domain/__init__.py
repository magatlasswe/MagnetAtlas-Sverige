"""Provider-independent domain models and contracts."""

from magnetatlas.domain.collectors import (
    CollectionBatch,
    CollectionRequest,
    Collector,
    CollectorCapability,
    CollectorDescriptor,
)
from magnetatlas.domain.conversions import archive_record_to_atlas_feature
from magnetatlas.domain.features import (
    AtlasFeature,
    Confidence,
    FeatureId,
    LicenseInfo,
    Provenance,
    TimeSpan,
)
from magnetatlas.domain.geography import (
    BoundingBox,
    Geometry,
    GeoPoint,
    LineString,
    Polygon,
)
from magnetatlas.domain.models import ArchiveRecord

__all__ = [
    "ArchiveRecord",
    "AtlasFeature",
    "BoundingBox",
    "CollectionBatch",
    "CollectionRequest",
    "Collector",
    "CollectorCapability",
    "CollectorDescriptor",
    "Confidence",
    "FeatureId",
    "GeoPoint",
    "Geometry",
    "LicenseInfo",
    "LineString",
    "Polygon",
    "Provenance",
    "TimeSpan",
    "archive_record_to_atlas_feature",
]
