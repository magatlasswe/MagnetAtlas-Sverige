"""Source-neutral identities for sources, imported datasets and their scope."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from magnetatlas.domain.geography import BoundingBox


class DatasetScopeKind(StrEnum):
    """Supported geographical boundaries for one imported dataset."""

    COUNTRY = "country"
    COUNTY = "county"
    MUNICIPALITY = "municipality"
    BBOX = "bbox"


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    """Stable identity and display metadata for one official data product."""

    source_id: str
    display_name: str

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id får inte vara tomt")
        if not self.display_name.strip():
            raise ValueError("display_name får inte vara tomt")


@dataclass(frozen=True, slots=True)
class DatasetScope:
    """Normalized geographical scope attached to an imported dataset."""

    kind: DatasetScopeKind
    value: str | None = None
    bounds: BoundingBox | None = None
    parent_kind: DatasetScopeKind | None = None
    parent_value: str | None = None

    def __post_init__(self) -> None:
        if self.kind is DatasetScopeKind.BBOX:
            if self.bounds is None or self.value is not None:
                raise ValueError("bbox-scope kräver endast bounds")
            if (self.parent_kind is None) != (self.parent_value is None):
                raise ValueError("bbox-scope kräver både parent_kind och parent_value")
            if self.parent_kind is DatasetScopeKind.BBOX:
                raise ValueError("bbox-scope kan inte ha bbox som parent")
            if self.parent_value is not None:
                if not self.parent_value.strip():
                    raise ValueError("bbox-scope parent_value får inte vara tomt")
                object.__setattr__(
                    self, "parent_value", self.parent_value.strip().casefold()
                )
            return
        if (
            self.bounds is not None
            or self.parent_kind is not None
            or self.parent_value is not None
            or self.value is None
            or not self.value.strip()
        ):
            raise ValueError(f"{self.kind.value}-scope kräver ett värde")
        object.__setattr__(self, "value", self.value.strip().casefold())

    @classmethod
    def country(cls, value: str) -> DatasetScope:
        """Create a country scope."""
        return cls(DatasetScopeKind.COUNTRY, value=value)

    @classmethod
    def county(cls, value: str) -> DatasetScope:
        """Create a county scope."""
        return cls(DatasetScopeKind.COUNTY, value=value)

    @classmethod
    def municipality(cls, value: str) -> DatasetScope:
        """Create a municipality scope."""
        return cls(DatasetScopeKind.MUNICIPALITY, value=value)

    @classmethod
    def bbox(
        cls, bounds: BoundingBox, *, parent: DatasetScope | None = None
    ) -> DatasetScope:
        """Create an exact WGS84 bounding-box scope."""
        return cls(
            DatasetScopeKind.BBOX,
            bounds=bounds,
            parent_kind=parent.kind if parent else None,
            parent_value=parent.value if parent else None,
        )

    @property
    def identity(self) -> str:
        """Return the deterministic identity fragment used by dataset IDs."""
        if self.bounds is None:
            return f"{self.kind.value}:{self.value}"
        values = (
            self.bounds.west,
            self.bounds.south,
            self.bounds.east,
            self.bounds.north,
        )
        identity = "bbox:" + ",".join(format(value, ".12g") for value in values)
        if self.parent_kind is not None:
            identity += f":within:{self.parent_kind.value}:{self.parent_value}"
        return identity


@dataclass(frozen=True, slots=True)
class DatasetInstance:
    """One independently persisted import of a source at a defined scope."""

    dataset_id: str
    source: SourceDefinition
    scope: DatasetScope

    def __post_init__(self) -> None:
        if not self.dataset_id.strip():
            raise ValueError("dataset_id får inte vara tomt")

    @classmethod
    def create(cls, source: SourceDefinition, scope: DatasetScope) -> DatasetInstance:
        """Create a deterministic dataset identity from source and scope."""
        return cls(f"{source.source_id}:{scope.identity}", source, scope)
