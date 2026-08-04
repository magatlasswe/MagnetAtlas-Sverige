"""Map Riksarkivet payloads to the shared domain."""

from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.infrastructure.sources.riksarkivet.schemas import RiksarkivetItem


def map_item(item: RiksarkivetItem) -> ArchiveRecord:
    """Convert a validated source item into a normalized archive record."""
    return ArchiveRecord(
        source="riksarkivet",
        source_id=item.source_id,
        title=item.caption,
        object_type=item.object_type,
        detail_type=item.detail_type,
        description=item.note,
        date_text=item.date_text,
        place=item.place,
        source_url=item.html_url,
        raw_data=item.raw_data,
    )
