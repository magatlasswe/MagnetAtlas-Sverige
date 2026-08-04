"""Riksarkivet Search API adapter."""

from magnetatlas.infrastructure.sources.riksarkivet.client import (
    RiksarkivetClient,
    create_collector,
)

__all__ = ["RiksarkivetClient", "create_collector"]
