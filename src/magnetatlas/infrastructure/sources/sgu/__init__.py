"""Official SGU open-data provider."""

from magnetatlas.infrastructure.sources.sgu.collector import (
    SGU_JORDARTER,
    SGU_SOURCE_DEFINITION,
    SGUCollector,
    SGUDatasetDefinition,
)
from magnetatlas.infrastructure.sources.sgu.importer import SGUImporter

__all__ = [
    "SGU_JORDARTER",
    "SGU_SOURCE_DEFINITION",
    "SGUCollector",
    "SGUDatasetDefinition",
    "SGUImporter",
]
