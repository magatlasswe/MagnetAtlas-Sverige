"""Query and navigation use cases for locally available atlas features."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.geography import BoundingBox, GeoPoint, LineString

DEFAULT_SEARCH_LIMIT: Final = 20
WORD_PATTERN: Final = re.compile(r"[\wåäöÅÄÖ]+", re.UNICODE)


def searchable_property_values(feature: AtlasFeature) -> tuple[str, ...]:
    """Return searchable strings from legacy and namespaced source properties."""
    values = [value for value in feature.properties.values() if isinstance(value, str)]
    namespaces = feature.properties.get("source_properties")
    if isinstance(namespaces, dict):
        for properties in namespaces.values():
            if isinstance(properties, dict):
                values.extend(
                    value for value in properties.values() if isinstance(value, str)
                )
    return tuple(values)


@dataclass(frozen=True, slots=True)
class FeatureSearchFilters:
    """Optional, source-independent facets for local feature discovery."""

    feature_types: frozenset[str] = frozenset()
    periods: frozenset[str] = frozenset()
    sources: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class NavigationTarget:
    """A destination coordinate and whether it approximates the feature."""

    point: GeoPoint
    approximate: bool


def navigation_target(feature: AtlasFeature) -> NavigationTarget | None:
    """Return a deterministic navigation point for one feature."""
    geometry = feature.geometry
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


def feature_period(feature: AtlasFeature) -> str:
    """Group a feature into a coarse, explainable time facet."""
    time_span = feature.time_span
    if time_span is None:
        return "unknown"
    year = time_span.start.year if time_span.start is not None else None
    text = (time_span.original_text or "").casefold()
    if year is not None:
        if year < 1800:
            return "before_1800"
        if year < 1900:
            return "1800s"
        return "1900s_or_later"
    if any(value in text for value in ("1600", "1700", "medeltid")):
        return "before_1800"
    if "1800" in text:
        return "1800s"
    if any(value in text for value in ("1900", "2000")):
        return "1900s_or_later"
    return "unknown"


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def _fuzzy_term_matches(term: str, haystack: str, words: tuple[str, ...]) -> bool:
    if term in haystack:
        return True
    tolerance = 1 if len(term) <= 5 else 2
    return any(
        abs(len(term) - len(word)) <= tolerance
        and _edit_distance(term, word) <= tolerance
        for word in words
    )


def _searchable_text(feature: AtlasFeature) -> tuple[str, tuple[str, ...]]:
    haystack = " ".join(
        value
        for value in (
            feature.title,
            feature.place,
            feature.feature_type,
            feature.description,
            feature.provenance.source_id,
            *searchable_property_values(feature),
        )
        if isinstance(value, str) and value
    ).casefold()
    return haystack, tuple(WORD_PATTERN.findall(haystack))


def feature_matches_search(
    feature: AtlasFeature,
    query: str,
    filters: FeatureSearchFilters,
    *,
    searchable: tuple[str, tuple[str, ...]] | None = None,
) -> bool:
    """Apply the existing deterministic search behavior to one feature."""
    terms = query.strip().casefold().split()
    feature_types = {value.casefold() for value in filters.feature_types}
    sources = {value.casefold() for value in filters.sources}
    if feature_types and feature.feature_type.casefold() not in feature_types:
        return False
    if sources and feature.provenance.source.casefold() not in sources:
        return False
    if filters.periods and feature_period(feature) not in filters.periods:
        return False
    haystack, words = searchable or _searchable_text(feature)
    return all(_fuzzy_term_matches(term, haystack, words) for term in terms)


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
        self._search_index = tuple(
            self._searchable_text(feature) for feature in self._features
        )

    @staticmethod
    def _searchable_text(feature: AtlasFeature) -> tuple[str, tuple[str, ...]]:
        """Build reusable normalized text for repeated interactive searches."""
        return _searchable_text(feature)

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
        self,
        query: str,
        *,
        filters: FeatureSearchFilters | None = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> list[AtlasFeature]:
        """Search with typo tolerance and explicit facets, preserving source order."""
        if limit < 1:
            raise ValueError("Sökgränsen måste vara minst 1")
        active_filters = filters or FeatureSearchFilters()
        if not query.strip() and not any(
            (
                active_filters.feature_types,
                active_filters.periods,
                active_filters.sources,
            )
        ):
            return []

        matches = []
        for feature, (haystack, words) in zip(
            self._features, self._search_index, strict=True
        ):
            if feature_matches_search(
                feature,
                query,
                active_filters,
                searchable=(haystack, words),
            ):
                matches.append(feature)
                if len(matches) == limit:
                    break
        return matches

    def navigation_target(self, feature_id: FeatureId | str) -> NavigationTarget | None:
        """Return a deterministic destination without performing GIS analysis."""
        return navigation_target(self.get(feature_id))
