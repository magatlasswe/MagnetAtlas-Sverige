"""HTTP client for Riksarkivet's public Search API."""

from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from magnetatlas.application.search import SourceSearchResult
from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.infrastructure.sources.riksarkivet.mapper import map_item
from magnetatlas.infrastructure.sources.riksarkivet.schemas import RiksarkivetItem

LOGGER = logging.getLogger(__name__)


def _default_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "MagnetAtlas-Sverige/0.1 (+https://github.com/)",
        }
    )
    return session


class RiksarkivetClient:
    """Search and normalize public records from Riksarkivet."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session or _default_session()

    def search(self, query: str, *, limit: int = 20) -> SourceSearchResult:
        try:
            response = self._session.get(
                f"{self._base_url}/records",
                params={"text": query, "offset": 0, "limit": limit},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError(f"Riksarkivet kunde inte nås: {exc}") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise DataSourceError("Riksarkivet returnerade ett oväntat svarsformat")

        records = []
        for raw_item in payload["items"]:
            if not isinstance(raw_item, dict):
                LOGGER.warning("Ignorerar en Riksarkivet-post som inte är ett objekt")
                continue
            try:
                records.append(map_item(RiksarkivetItem.from_dict(raw_item)))
            except ValueError as exc:
                LOGGER.warning("Ignorerar en ofullständig Riksarkivet-post: %s", exc)

        total_hits = payload.get("totalHits", len(records))
        if not isinstance(total_hits, int):
            total_hits = len(records)
        return SourceSearchResult(records=records, total_hits=total_hits)
