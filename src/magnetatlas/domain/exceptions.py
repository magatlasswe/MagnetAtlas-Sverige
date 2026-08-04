"""Domain-level exceptions."""


class MagnetAtlasError(Exception):
    """Base exception for expected MagnetAtlas failures."""


class DataSourceError(MagnetAtlasError):
    """Raised when an external data source cannot satisfy a request."""
