"""Small GIS-engine-independent geography value objects."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _validate_longitude(value: float) -> None:
    if not isfinite(value) or not -180.0 <= value <= 180.0:
        raise ValueError("longitude måste vara mellan -180 och 180")


def _validate_latitude(value: float) -> None:
    if not isfinite(value) or not -90.0 <= value <= 90.0:
        raise ValueError("latitude måste vara mellan -90 och 90")


@dataclass(frozen=True, slots=True)
class GeoPoint:
    """A WGS84 longitude/latitude coordinate."""

    longitude: float
    latitude: float

    def __post_init__(self) -> None:
        _validate_longitude(self.longitude)
        _validate_latitude(self.latitude)


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A non-antimeridian-crossing WGS84 bounding box."""

    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        _validate_longitude(self.west)
        _validate_longitude(self.east)
        _validate_latitude(self.south)
        _validate_latitude(self.north)
        if self.west > self.east:
            raise ValueError("west får inte vara större än east")
        if self.south > self.north:
            raise ValueError("south får inte vara större än north")

    def contains(self, point: GeoPoint) -> bool:
        """Return whether a point is inside or on the box boundary."""
        return (
            self.west <= point.longitude <= self.east
            and self.south <= point.latitude <= self.north
        )


@dataclass(frozen=True, slots=True)
class LineString:
    """An ordered WGS84 path with at least two points."""

    points: tuple[GeoPoint, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("LineString kräver minst två punkter")


@dataclass(frozen=True, slots=True)
class Polygon:
    """A WGS84 polygon represented by one exterior ring and optional holes."""

    rings: tuple[tuple[GeoPoint, ...], ...]

    def __post_init__(self) -> None:
        if not self.rings:
            raise ValueError("Polygon kräver minst en ring")
        for ring in self.rings:
            if len(ring) < 4:
                raise ValueError("Varje polygonring kräver minst fyra punkter")
            if ring[0] != ring[-1]:
                raise ValueError("Varje polygonring måste vara sluten")


type Geometry = GeoPoint | BoundingBox | LineString | Polygon
