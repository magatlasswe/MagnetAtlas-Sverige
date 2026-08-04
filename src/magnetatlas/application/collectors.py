"""Discovery and lookup of collector plugins."""

from __future__ import annotations

from collections.abc import Iterable
from importlib import metadata
from typing import Any, Final

from magnetatlas.domain.collectors import Collector, CollectorDescriptor
from magnetatlas.domain.exceptions import CollectorRegistryError

COLLECTOR_ENTRY_POINT_GROUP: Final = "magnetatlas.collectors"


class CollectorRegistry:
    """Register collectors explicitly or discover them through entry points."""

    def __init__(self, collectors: Iterable[Collector] = ()) -> None:
        self._collectors: dict[str, Collector] = {}
        for collector in collectors:
            self.register(collector)

    def register(self, collector: Collector) -> None:
        """Register a validated collector under its stable identifier."""
        descriptor = getattr(collector, "descriptor", None)
        if not isinstance(descriptor, CollectorDescriptor) or not callable(
            getattr(collector, "collect", None)
        ):
            raise CollectorRegistryError("Pluginet implementerar inte Collector")
        if descriptor.collector_id in self._collectors:
            raise CollectorRegistryError(
                f"Collector-ID är redan registrerat: {descriptor.collector_id}"
            )
        self._collectors[descriptor.collector_id] = collector

    def get(self, collector_id: str) -> Collector:
        """Return a collector by ID or raise an expected application error."""
        try:
            return self._collectors[collector_id]
        except KeyError as exc:
            raise CollectorRegistryError(f"Okänd collector: {collector_id}") from exc

    def descriptors(self) -> tuple[CollectorDescriptor, ...]:
        """List descriptors in deterministic collector-ID order."""
        return tuple(
            self._collectors[key].descriptor for key in sorted(self._collectors)
        )

    @classmethod
    def discover(
        cls,
        *,
        group: str = COLLECTOR_ENTRY_POINT_GROUP,
    ) -> CollectorRegistry:
        """Load collector instances or zero-argument factories from entry points."""
        registry = cls()
        for entry_point in metadata.entry_points(group=group):
            try:
                loaded: Any = entry_point.load()
                candidate = loaded() if callable(loaded) else loaded
                registry.register(candidate)
            except CollectorRegistryError:
                raise
            except Exception as exc:
                raise CollectorRegistryError(
                    f"Kunde inte ladda collector-plugin: {entry_point.name}"
                ) from exc
        return registry
