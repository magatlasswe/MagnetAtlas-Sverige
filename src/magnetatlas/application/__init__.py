"""Application use cases."""

from magnetatlas.application.collectors import CollectorRegistry
from magnetatlas.application.features import FeatureCatalog, NavigationTarget
from magnetatlas.application.search import SearchResult, SearchService

__all__ = [
    "CollectorRegistry",
    "FeatureCatalog",
    "NavigationTarget",
    "SearchResult",
    "SearchService",
]
