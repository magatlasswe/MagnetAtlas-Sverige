"""HTTP and authentication client for Lantmäteriet STAC vector downloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.infrastructure.sources.errors import transport_error_message

DEFAULT_STAC_URL = "https://api.lantmateriet.se/stac-vektor/v1"


@dataclass(frozen=True, slots=True)
class DownloadedArchive:
    """One immutable STAC item asset downloaded to a local file."""

    path: Path
    source_url: str
    item_id: str
    published_at: str | None


def _session_with_retry() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {"User-Agent": "MagnetAtlas-Sverige/1.4 (+https://github.com/)"}
    )
    return session


class LantmaterietClient:
    """Discover and download authorized files from the official STAC API."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_STAC_URL,
        timeout: float = 30.0,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout måste vara större än noll")
        if bool(client_id) != bool(client_secret):
            raise ValueError("OAuth2 kräver både client id och client secret")
        if client_id and not token_url:
            raise ValueError("OAuth2 kräver en konfigurerad token-URL")
        if bool(username) != bool(password):
            raise ValueError("Basic-autentisering kräver användarnamn och lösenord")
        if client_id and username:
            raise ValueError("Välj antingen OAuth2 eller Basic-autentisering")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._basic_auth = (
            HTTPBasicAuth(username, password) if username and password else None
        )
        self._session = session or _session_with_retry()
        self._access_token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)

    def latest_asset(self, collection_id: str) -> tuple[str, str, str | None]:
        """Return URL, stable item id and publication time for the latest ZIP."""
        payload = self._get_json(
            f"{self._base_url}/collections/{collection_id}/items",
            params={"limit": 100, "sortby": "-datetime"},
        )
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            raise DataSourceError("Lantmäteriets STAC-katalog saknar datasetversioner")
        candidates: list[tuple[str, str, str | None]] = []
        for item in features:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            assets = item.get("assets")
            properties = item.get("properties")
            if not isinstance(item_id, str) or not isinstance(assets, dict):
                continue
            published = (
                properties.get("datetime")
                if isinstance(properties, dict)
                and isinstance(properties.get("datetime"), str)
                else None
            )
            for asset in assets.values():
                if not isinstance(asset, dict):
                    continue
                href = asset.get("href")
                media_type = str(asset.get("type", "")).casefold()
                if isinstance(href, str) and (
                    href.casefold().endswith(".zip") or "zip" in media_type
                ):
                    candidates.append((href, item_id, published))
        if not candidates:
            raise DataSourceError("Lantmäteriets STAC-post saknar en ZIP-asset")
        return max(candidates, key=lambda value: (value[2] or "", value[1]))

    def download_archive(
        self, collection_id: str, destination: Path
    ) -> DownloadedArchive:
        """Download the latest dataset archive atomically."""
        url, item_id, published = self.latest_asset(collection_id)
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise DataSourceError("Lantmäteriet returnerade en osäker asset-URL")
        temporary = destination.with_suffix(f"{destination.suffix}.part")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._session.get(
                url,
                timeout=self._timeout,
                stream=True,
                headers=self._headers("application/zip, application/octet-stream"),
                auth=self._basic_auth,
            ) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            output.write(chunk)
            temporary.replace(destination)
        except (OSError, requests.RequestException) as exc:
            temporary.unlink(missing_ok=True)
            message = (
                transport_error_message("Lantmäteriets nedladdningstjänst", exc)
                if isinstance(exc, requests.RequestException)
                else "Lantmäteriets arkiv kunde inte sparas lokalt."
            )
            raise DataSourceError(message) from exc
        return DownloadedArchive(destination, url, item_id, published)

    def _get_json(self, url: str, *, params: dict[str, object]) -> dict[str, Any]:
        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self._timeout,
                headers=self._headers("application/geo+json, application/json"),
                auth=self._basic_auth,
            )
            response.raise_for_status()
            payload: object = response.json()
        except (requests.RequestException, ValueError) as exc:
            message = (
                transport_error_message("Lantmäteriets STAC-katalog", exc)
                if isinstance(exc, requests.RequestException)
                else "Lantmäteriets STAC-katalog returnerade ogiltig JSON."
            )
            raise DataSourceError(message) from exc
        if not isinstance(payload, dict):
            raise DataSourceError("Lantmäteriets STAC-katalog gav oväntat svar")
        return payload

    def _headers(self, accept: str) -> dict[str, str]:
        headers = {"Accept": accept}
        token = self._token()
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _token(self) -> str | None:
        if self._client_id is None:
            return None
        now = datetime.now(UTC)
        if self._access_token and now < self._token_expires_at:
            return self._access_token
        assert self._client_secret is not None
        assert self._token_url is not None
        try:
            response = self._session.post(
                self._token_url,
                data={"grant_type": "client_credentials"},
                auth=HTTPBasicAuth(self._client_id, self._client_secret),
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError(
                "OAuth2-inloggningen mot Lantmäteriet misslyckades"
            ) from exc
        token = payload.get("access_token") if isinstance(payload, dict) else None
        expires_in = (
            payload.get("expires_in", 300) if isinstance(payload, dict) else 300
        )
        if not isinstance(token, str) or not token:
            raise DataSourceError("Lantmäteriets OAuth2-svar saknar access token")
        lifetime = float(expires_in) if isinstance(expires_in, int | float) else 300.0
        self._access_token = token
        self._token_expires_at = now + timedelta(seconds=max(1.0, lifetime - 30.0))
        return token
