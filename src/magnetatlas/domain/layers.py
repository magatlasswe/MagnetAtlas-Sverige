"""Source-neutral definitions for map layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LayerDefinition:
    """Stable metadata and availability rules for one map layer."""

    id: str
    name: str
    description: str
    icon: str
    category: str
    supported_sources: frozenset[str]
    default_visibility: bool = False
    enabled: bool = True
    experimental: bool = False

    def __post_init__(self) -> None:
        for field_name in ("id", "name", "description", "icon", "category"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} får inte vara tomt")
        if any(not source_id.strip() for source_id in self.supported_sources):
            raise ValueError("supported_sources får inte innehålla tomma ID:n")
        if self.default_visibility and not self.enabled:
            raise ValueError("ett inaktiverat lager kan inte vara synligt som standard")
