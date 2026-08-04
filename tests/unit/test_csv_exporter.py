"""Tests for CSV export."""

import csv
from pathlib import Path

from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.infrastructure.exporters.csv_exporter import export_csv


def test_export_csv_uses_utf8(
    tmp_path: Path,
    archive_record: ArchiveRecord,
) -> None:
    destination = tmp_path / "nested" / "records.csv"

    result = export_csv([archive_record], destination)

    assert result == destination
    with destination.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert rows[0]["title"] == "Ritning över gammal bro"
    assert rows[0]["source_id"] == "record-1"
