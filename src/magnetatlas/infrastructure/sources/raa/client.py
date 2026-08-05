"""Network client for RAÄ's documented open-data services."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.infrastructure.sources.errors import transport_error_message

DEFAULT_API_URL = "https://pub.raa.se/datauttag"
DEFAULT_DOWNLOAD_URL = "https://pub.raa.se/nedladdning/datauttag/lamningar_v1"
API_VERSION = "1.2.0"
GEOPACKAGE_SCHEMA_VERSION = "3.0"
MAX_PAGE_SIZE = 10_000
SAFE_NAME = re.compile(r"^[a-zA-ZåäöÅÄÖéÉ -]+$")
COUNTY_ALIASES = {
    "ostergotland": "östergötland",
    "vastra gotaland": "västra götaland",
    "sodermanland": "södermanland",
    "orebro": "örebro",
    "jonkoping": "jönköping",
    "gavleborg": "gävleborg",
    "vasternorrland": "västernorrland",
    "vasterbotten": "västerbotten",
    "norrbotten": "norrbotten",
}


@dataclass(frozen=True, slots=True)
class DownloadedGeoPackage:
    """A downloaded official base dataset and its HTTP version signals."""

    path: Path
    source_url: str
    etag: str | None = None
    last_modified: str | None = None


def _session_with_retry() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": "MagnetAtlas-Sverige/0.6 (+https://github.com/)",
        }
    )
    return session


def _official_name(value: str) -> str:
    normalized = " ".join(value.strip().casefold().replace("_", "-").split())
    normalized = COUNTY_ALIASES.get(normalized, normalized)
    if not normalized or not SAFE_NAME.fullmatch(normalized):
        raise ValueError("Geografiskt namn innehåller otillåtna tecken")
    return normalized.replace(" ", "_")


class RAAClient:
    """Fetch official RAÄ base packages and incremental change documents."""

    def __init__(
        self,
        *,
        api_url: str = DEFAULT_API_URL,
        download_url: str = DEFAULT_DOWNLOAD_URL,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout måste vara större än noll")
        self._api_url = api_url.rstrip("/")
        self._download_url = download_url.rstrip("/")
        self._timeout = timeout
        self._session = session or _session_with_retry()

    def geopackage_url(
        self,
        *,
        county: str | None = None,
        municipality: str | None = None,
    ) -> str:
        """Build a URL from RAÄ's documented deterministic file convention."""
        if county and municipality:
            raise ValueError("Välj antingen län eller kommun, inte båda")
        if county:
            name = _official_name(county)
            path = f"lan/lämningar_län_{name}.gpkg"
        elif municipality:
            name = _official_name(municipality)
            path = f"kommun/lämningar_kommun_{name}.gpkg"
        else:
            path = "lämningar_sverige.gpkg"
        return f"{self._download_url}/{quote(path, safe='/')}"

    def download_geopackage(
        self,
        destination: Path,
        *,
        county: str | None = None,
        municipality: str | None = None,
    ) -> DownloadedGeoPackage:
        """Download one official GeoPackage atomically to a local path."""
        url = self.geopackage_url(county=county, municipality=municipality)
        temporary = destination.with_suffix(f"{destination.suffix}.part")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._session.get(
                url,
                timeout=self._timeout,
                stream=True,
                headers={
                    "Accept": "application/geopackage+sqlite3, application/octet-stream"
                },
            ) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            output.write(chunk)
                headers = response.headers
            temporary.replace(destination)
            return DownloadedGeoPackage(
                path=destination,
                source_url=url,
                etag=headers.get("ETag"),
                last_modified=headers.get("Last-Modified"),
            )
        except (OSError, requests.RequestException) as exc:
            temporary.unlink(missing_ok=True)
            if isinstance(exc, requests.RequestException):
                message = transport_error_message("RAÄ:s nedladdningstjänst", exc)
            else:
                message = (
                    "RAÄ-filen kunde inte sparas lokalt. "
                    "Kontrollera sökväg och utrymme."
                )
            raise DataSourceError(message) from exc

    def fetch_changes(self, start: date, end: date) -> list[dict[str, Any]]:
        """Fetch every page of documented changes in an inclusive date interval."""
        if start > end:
            raise ValueError("Synkintervallets start får inte ligga efter slut")
        page = 0
        changes: list[dict[str, Any]] = []
        while True:
            payload = self._get_change_page(start, end, page)
            content = payload.get("content")
            if not isinstance(content, list):
                raise DataSourceError("RAÄ returnerade ett oväntat svarsformat")
            changes.extend(item for item in content if isinstance(item, dict))
            if payload.get("last") is True or not content:
                return changes
            total_pages = payload.get("totalPages")
            page += 1
            if isinstance(total_pages, int) and page >= total_pages:
                return changes

    def _get_change_page(self, start: date, end: date, page: int) -> dict[str, Any]:
        try:
            response = self._session.get(
                f"{self._api_url}/lamningar",
                params={
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "page": page,
                    "size": MAX_PAGE_SIZE,
                    "sort": "publiceringsdatum,asc",
                },
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload: object = response.json()
        except (requests.RequestException, ValueError) as exc:
            if isinstance(exc, requests.RequestException):
                message = transport_error_message("RAÄ:s förändringstjänst", exc)
            else:
                message = "RAÄ:s förändringstjänst returnerade ett ogiltigt svar."
            raise DataSourceError(message) from exc
        if not isinstance(payload, dict):
            raise DataSourceError("RAÄ returnerade ett oväntat svarsformat")
        return payload
