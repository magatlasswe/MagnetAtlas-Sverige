"""Tests for Riksarkivet normalization."""

from magnetatlas.infrastructure.sources.riksarkivet.mapper import map_item
from magnetatlas.infrastructure.sources.riksarkivet.schemas import RiksarkivetItem


def test_map_riksarkivet_item() -> None:
    payload = {
        "id": "abc123",
        "objectType": "Record",
        "type": "MapDrawing",
        "caption": "Bro över Fyrisån",
        "metadata": {
            "date": "1888",
            "note": "Ritning",
            "partOf": [{"caption": "Sverige"}, {"caption": "Uppsala"}],
        },
        "_links": {"html": "https://sok.riksarkivet.se/post"},
    }

    record = map_item(RiksarkivetItem.from_dict(payload))

    assert record.source == "riksarkivet"
    assert record.source_id == "abc123"
    assert record.title == "Bro över Fyrisån"
    assert record.place == "Sverige / Uppsala"
    assert record.source_url == "https://sok.riksarkivet.se/post"
