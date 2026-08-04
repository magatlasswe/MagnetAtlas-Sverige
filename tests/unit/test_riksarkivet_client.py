"""Tests for the Riksarkivet HTTP adapter."""

from typing import Any

from magnetatlas.infrastructure.sources.riksarkivet.client import RiksarkivetClient


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "totalHits": 42,
            "items": [
                {
                    "id": "abc",
                    "objectType": "Topography",
                    "type": "SettlementUnit",
                    "caption": "Kvarnby",
                    "metadata": {"date": "1800-talet"},
                    "_links": {},
                }
            ],
        }


class FakeSession:
    def __init__(self) -> None:
        self.url = ""
        self.params: dict[str, object] = {}
        self.timeout = 0.0

    def get(
        self,
        url: str,
        *,
        params: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        self.url = url
        self.params = params
        self.timeout = timeout
        return FakeResponse()


def test_search_uses_documented_records_contract() -> None:
    session = FakeSession()
    client = RiksarkivetClient(
        "https://data.riksarkivet.se/api",
        timeout=3.0,
        session=session,  # type: ignore[arg-type]
    )

    result = client.search("kvarn", limit=5)

    assert session.url == "https://data.riksarkivet.se/api/records"
    assert session.params == {"text": "kvarn", "offset": 0, "limit": 5}
    assert session.timeout == 3.0
    assert result.total_hits == 42
    assert result.records[0].title == "Kvarnby"
