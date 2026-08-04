"""Query and navigation use cases for locally available atlas features."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.geography import BoundingBox, GeoPoint, LineString

DEFAULT_SEARCH_LIMIT: Final = 20


@dataclass(frozen=True, slots=True)
class NavigationTarget:
    """A destination coordinate and whether it approximates the feature."""

    point: GeoPoint
    approximate: bool


class FeatureCatalog:
    """Provide deterministic local lookup and search over atlas features."""

    def __init__(self, features: list[AtlasFeature]) -> None:
        indexed: dict[FeatureId, AtlasFeature] = {}
        for feature in features:
            if feature.feature_id in indexed:
                raise ValueError(f"Duplicerat FeatureId: {feature.feature_id}")
            indexed[feature.feature_id] = feature
        self._features = tuple(features)
        self._indexed = indexed

    def list_all(self) -> tuple[AtlasFeature, ...]:
        """Return all features in source order."""
        return self._features

    def get(self, feature_id: FeatureId | str) -> AtlasFeature:
        """Return a selected feature by its stable ID."""
        normalized_id = (
            feature_id if isinstance(feature_id, FeatureId) else FeatureId(feature_id)
        )
        try:
            return self._indexed[normalized_id]
        except KeyError as exc:
            raise KeyError(f"Okänd AtlasFeature: {normalized_id}") from exc

    def search(
        self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> list[AtlasFeature]:
        """Search local user-facing text using case-insensitive term matching."""
        terms = query.strip().casefold().split()
        if not terms:
            return []
        if limit < 1:
            raise ValueError("Sökgränsen måste vara minst 1")

        matches = []
        for feature in self._features:
            haystack = " ".join(
                value
                for value in (
                    feature.title,
                    feature.place,
                    feature.feature_type,
                    feature.description,
                )
                if value
            ).casefold()
            if all(term in haystack for term in terms):
                matches.append(feature)
                if len(matches) == limit:
                    break
        return matches

    def navigation_target(self, feature_id: FeatureId | str) -> NavigationTarget | None:
        """Return a deterministic destination without performing GIS analysis."""
        geometry = self.get(feature_id).geometry
        if geometry is None:
            return None
        if isinstance(geometry, GeoPoint):
            return NavigationTarget(geometry, approximate=False)
        if isinstance(geometry, BoundingBox):
            return NavigationTarget(
                GeoPoint(
                    longitude=(geometry.west + geometry.east) / 2,
                    latitude=(geometry.south + geometry.north) / 2,
                ),
                approximate=True,
            )
        if isinstance(geometry, LineString):
            return NavigationTarget(
                geometry.points[len(geometry.points) // 2], approximate=True
            )

        exterior_ring = geometry.rings[0]
        longitudes = [point.longitude for point in exterior_ring]
        latitudes = [point.latitude for point in exterior_ring]
        return NavigationTarget(
            GeoPoint(
                longitude=(min(longitudes) + max(longitudes)) / 2,
                latitude=(min(latitudes) + max(latitudes)) / 2,
            ),
            approximate=True,
        )
