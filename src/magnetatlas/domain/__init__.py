"""Provider-independent domain models and contracts."""

from magnetatlas.domain.collectors import (
    CollectionBatch,
    CollectionRequest,
    Collector,
    CollectorCapability,
    CollectorDescriptor,
    CollectorOutputModel,
    CollectorPlugin,
)
from magnetatlas.domain.conversions import archive_record_to_atlas_feature
from magnetatlas.domain.datasets import (
    DatasetInstance,
    DatasetScope,
    DatasetScopeKind,
    SourceDefinition,
)
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
from magnetatlas.domain.layers import LayerDefinition
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
    "CollectorOutputModel",
    "CollectorPlugin",
    "Confidence",
    "DatasetInstance",
    "DatasetScope",
    "DatasetScopeKind",
    "FeatureId",
    "GeoPoint",
    "Geometry",
    "LayerDefinition",
    "LicenseInfo",
    "LineString",
    "Polygon",
    "Provenance",
    "SourceDefinition",
    "TimeSpan",
    "archive_record_to_atlas_feature",
]
