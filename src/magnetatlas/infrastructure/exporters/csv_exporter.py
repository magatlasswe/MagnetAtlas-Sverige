"""CSV export for normalized records."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from magnetatlas.domain.models import ArchiveRecord

FIELDS = (
    "id",
    "source",
    "source_id",
    "title",
    "object_type",
    "detail_type",
    "description",
    "date",
    "place",
    "source_url",
    "fetched_at",
)


def export_csv(records: Iterable[ArchiveRecord], destination: Path) -> Path:
    """Write records as deterministic UTF-8 CSV and return the destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "id": record.id,
                    "source": record.source,
                    "source_id": record.source_id,
                    "title": record.title,
                    "object_type": record.object_type,
                    "detail_type": record.detail_type,
                    "description": record.description,
                    "date": record.date_text,
                    "place": record.place,
                    "source_url": record.source_url,
                    "fetched_at": record.fetched_at.isoformat(),
                }
            )
    return destination
