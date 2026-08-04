"""Provider-independent domain models and contracts."""

from magnetatlas.domain.collectors import (
    CollectionBatch,
    CollectionRequest,
    Collector,
    CollectorCapability,
    CollectorDescriptor,
)
from magnetatlas.domain.models import ArchiveRecord

__all__ = [
    "ArchiveRecord",
    "CollectionBatch",
    "CollectionRequest",
    "Collector",
    "CollectorCapability",
    "CollectorDescriptor",
]
