"""Client for SGU's documented OGC API Features services."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.infrastructure.sources.errors import transport_error_message

CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
DEFAULT_BASE_URL = "https://api.sgu.se/oppnadata"
DEFAULT_PAGE_SIZE = 5_000
DEFAULT_RETRY_COUNT = 8


def _session_with_retry() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=DEFAULT_RETRY_COUNT,
        connect=DEFAULT_RETRY_COUNT,
        read=DEFAULT_RETRY_COUNT,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {"User-Agent": "MagnetAtlas-Sverige/0.6 (+https://github.com/)"}
    )
    return session


class SGUClient:
    """Read paginated GeoJSON from one configured SGU dataset collection."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        page_size: int = DEFAULT_PAGE_SIZE,
        session: requests.Session | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout måste vara större än noll")
        if page_size <= 0:
            raise ValueError("page_size måste vara större än noll")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._page_size = page_size
        self._session = session or _session_with_retry()

    def iter_features(
        self,
        dataset_path: str,
        collection_id: str,
        *,
        bbox: BoundingBox | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield all features while following documented OGC next links."""
        url = (
            f"{self._base_url}/{dataset_path}/ogc/features/v1/collections/"
            f"{collection_id}/items"
        )
        params: Mapping[str, object] | None = {
            "f": "application/geo+json",
            "limit": self._page_size,
            "crs": CRS84,
            **(
                {"bbox": f"{bbox.west},{bbox.south},{bbox.east},{bbox.north}"}
                if bbox is not None
                else {}
            ),
        }
        while url:
            payload = self._get(url, params)
            params = None
            features = payload.get("features")
            if not isinstance(features, list):
                raise DataSourceError("SGU returnerade ett oväntat GeoJSON-svar")
            for feature in features:
                if isinstance(feature, dict):
                    yield feature
            url = self._next_url(payload)

    def _get(self, url: str, params: Mapping[str, object] | None) -> dict[str, Any]:
        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self._timeout,
                headers={"Accept": "application/geo+json, application/json"},
            )
            response.raise_for_status()
            payload: object = response.json()
        except (requests.RequestException, ValueError) as exc:
            message = (
                transport_error_message("SGU:s OGC API Features", exc)
                if isinstance(exc, requests.RequestException)
                else "SGU:s OGC API Features returnerade ett ogiltigt svar."
            )
            raise DataSourceError(message) from exc
        if not isinstance(payload, dict):
            raise DataSourceError("SGU returnerade ett oväntat svarsformat")
        return payload

    def _next_url(self, payload: dict[str, Any]) -> str | None:
        links = payload.get("links")
        if not isinstance(links, list):
            return None
        expected = urlparse(self._base_url)
        for link in links:
            if not isinstance(link, dict) or link.get("rel") != "next":
                continue
            href = link.get("href")
            if not isinstance(href, str):
                continue
            parsed = urlparse(href)
            if parsed.scheme != expected.scheme or parsed.netloc != expected.netloc:
                raise DataSourceError("SGU returnerade en ogiltig pagineringslänk")
            return href
        return None
