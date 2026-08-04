"""Domain-level exceptions."""


class MagnetAtlasError(Exception):
    """Base exception for expected MagnetAtlas failures."""


class DataSourceError(MagnetAtlasError):
    """Raised when an external data source cannot satisfy a request."""


class CollectorRegistryError(MagnetAtlasError):
    """Raised when collector registration or lookup fails."""


class FeatureDataError(MagnetAtlasError):
    """Raised when a local AtlasFeature dataset is invalid."""
