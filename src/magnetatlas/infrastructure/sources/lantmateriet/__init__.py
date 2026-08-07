"""Lantmäteriet provider adapters for documented official datasets."""

from magnetatlas.infrastructure.sources.lantmateriet.client import LantmaterietClient
from magnetatlas.infrastructure.sources.lantmateriet.collector import (
    LANTMATERIET_SOURCE_DEFINITION,
    ORTNAMN_DATASET,
    LantmaterietCollector,
)
from magnetatlas.infrastructure.sources.lantmateriet.importer import (
    LantmaterietImporter,
)

__all__ = [
    "LANTMATERIET_SOURCE_DEFINITION",
    "ORTNAMN_DATASET",
    "LantmaterietClient",
    "LantmaterietCollector",
    "LantmaterietImporter",
]
