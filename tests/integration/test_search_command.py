"""CLI integration tests."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from magnetatlas.application.search import SourceSearchResult
from magnetatlas.cli import app
from magnetatlas.domain.models import ArchiveRecord
from magnetatlas.infrastructure.sources.riksarkivet.client import RiksarkivetClient


def test_search_command_persists_and_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    archive_record: ArchiveRecord,
) -> None:
    database_path = tmp_path / "data" / "atlas.db"
    csv_path = tmp_path / "result.csv"
    monkeypatch.setenv(
        "MAGNETATLAS_DATABASE_URL", f"sqlite:///{database_path.as_posix()}"
    )
    monkeypatch.setenv("MAGNETATLAS_OUTPUT_DIR", str(tmp_path / "output"))

    def fake_search(
        self: RiksarkivetClient,
        query: str,
        *,
        limit: int = 20,
    ) -> SourceSearchResult:
        assert query == "bro"
        assert limit == 3
        return SourceSearchResult(records=[archive_record], total_hits=1)

    monkeypatch.setattr(RiksarkivetClient, "search", fake_search)

    result = CliRunner().invoke(
        app,
        ["search", "bro", "--limit", "3", "--csv", str(csv_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Ritning över gammal bro" in result.output
    assert database_path.exists()
    assert csv_path.exists()
