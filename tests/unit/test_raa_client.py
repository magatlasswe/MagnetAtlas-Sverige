"""Tests for RAÄ's documented network client."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
import requests

from magnetatlas.domain.exceptions import DataSourceError
from magnetatlas.infrastructure.sources.raa.client import MAX_PAGE_SIZE, RAAClient


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        content: bytes = b"",
    ) -> None:
        self.payload = payload
        self.content = content
        self.headers = {"ETag": '"v3"', "Last-Modified": "Wed, 05 Aug 2026"}

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any] | None:
        return self.payload

    def iter_content(self, *, chunk_size: int) -> list[bytes]:
        assert chunk_size == 1024 * 1024
        return [self.content]


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_geopackage_urls_use_documented_file_names() -> None:
    client = RAAClient()

    assert client.geopackage_url().endswith("l%C3%A4mningar_sverige.gpkg")
    assert client.geopackage_url(county="ostergotland").endswith(
        "lan/l%C3%A4mningar_l%C3%A4n_%C3%B6sterg%C3%B6tland.gpkg"
    )
    assert client.geopackage_url(municipality="kinda").endswith(
        "kommun/l%C3%A4mningar_kommun_kinda.gpkg"
    )


def test_download_geopackage_uses_timeout_and_atomic_destination(
    tmp_path: Path,
) -> None:
    session = FakeSession([FakeResponse(content=b"SQLite format 3\x00")])
    client = RAAClient(timeout=4, session=session)  # type: ignore[arg-type]
    destination = tmp_path / "base.gpkg"

    result = client.download_geopackage(destination, municipality="kinda")

    assert destination.read_bytes() == b"SQLite format 3\x00"
    assert result.etag == '"v3"'
    assert session.calls[0][1]["timeout"] == 4
    assert session.calls[0][1]["stream"] is True


def test_fetch_changes_paginates_official_contract() -> None:
    first = {"content": [{"id": "one"}], "last": False, "totalPages": 2}
    second = {"content": [{"id": "two"}], "last": True, "totalPages": 2}
    session = FakeSession([FakeResponse(first), FakeResponse(second)])
    client = RAAClient(timeout=3, session=session)  # type: ignore[arg-type]

    changes = client.fetch_changes(date(2026, 8, 1), date(2026, 8, 2))

    assert [item["id"] for item in changes] == ["one", "two"]
    assert session.calls[0][1]["params"] == {
        "from": "2026-08-01",
        "to": "2026-08-02",
        "page": 0,
        "size": MAX_PAGE_SIZE,
        "sort": "publiceringsdatum,asc",
    }
    assert session.calls[1][1]["params"]["page"] == 1  # type: ignore[index]


def test_fetch_changes_rejects_unexpected_payload() -> None:
    session = FakeSession([FakeResponse({"unexpected": []})])
    client = RAAClient(session=session)  # type: ignore[arg-type]

    with pytest.raises(DataSourceError, match="svarsformat"):
        client.fetch_changes(date(2026, 8, 1), date(2026, 8, 2))


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (requests.Timeout("technical"), "tidsgränsen"),
        (requests.ConnectionError("technical"), "internetanslutningen"),
    ],
)
def test_download_explains_transport_errors_in_swedish(
    tmp_path: Path, error: requests.RequestException, message: str
) -> None:
    class FailingSession:
        def get(self, *args: object, **kwargs: object) -> FakeResponse:
            raise error

    client = RAAClient(session=FailingSession())  # type: ignore[arg-type]

    with pytest.raises(DataSourceError, match=message) as raised:
        client.download_geopackage(tmp_path / "base.gpkg")

    assert "technical" not in str(raised.value)
