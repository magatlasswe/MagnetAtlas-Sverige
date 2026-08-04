"""Defensive parsing helpers for Riksarkivet's beta API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _link(links: object, name: str) -> str | None:
    if not isinstance(links, dict):
        return None
    value = links.get(name)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _optional_string(value.get("href")) or _optional_string(value.get("url"))
    return None


def _place(metadata: dict[str, Any]) -> str | None:
    direct = _optional_string(metadata.get("place")) or _optional_string(
        metadata.get("parish")
    )
    if direct:
        return direct
    part_of = metadata.get("partOf")
    if isinstance(part_of, list):
        captions = [
            caption
            for item in part_of
            if isinstance(item, dict)
            and (caption := _optional_string(item.get("caption"))) is not None
        ]
        return " / ".join(captions) or None
    return None


@dataclass(frozen=True, slots=True)
class RiksarkivetItem:
    """Validated subset of a Riksarkivet result item."""

    source_id: str
    caption: str
    object_type: str
    detail_type: str | None
    note: str | None
    date_text: str | None
    place: str | None
    html_url: str | None
    raw_data: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiksarkivetItem:
        source_id = _optional_string(data.get("id"))
        caption = _optional_string(data.get("caption"))
        object_type = _optional_string(data.get("objectType"))
        if source_id is None or caption is None or object_type is None:
            raise ValueError("Riksarkivet-post saknar id, caption eller objectType")

        metadata_value = data.get("metadata")
        metadata: dict[str, Any] = (
            metadata_value if isinstance(metadata_value, dict) else {}
        )
        return cls(
            source_id=source_id,
            caption=caption,
            object_type=object_type,
            detail_type=_optional_string(data.get("type")),
            note=_optional_string(metadata.get("note")),
            date_text=_optional_string(metadata.get("date")),
            place=_place(metadata),
            html_url=_link(data.get("_links"), "html"),
            raw_data=data,
        )
