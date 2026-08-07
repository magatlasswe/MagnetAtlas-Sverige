"""CLI integration tests for Lantmäteriet snapshot imports."""

from pathlib import Path
from typing import ClassVar

import pytest
from typer.testing import CliRunner

from magnetatlas.application.sync import SyncResult
from magnetatlas.cli import _lantmateriet_dataset_instance, app
from magnetatlas.domain.datasets import DatasetScope
from magnetatlas.domain.geography import BoundingBox


class FakeImporter:
    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, service: object) -> None:
        del service

    def run(self, **kwargs: object) -> SyncResult:
        self.calls.append(kwargs)
        return SyncResult("base", 41, 0, "2026-08-01", 1.0)


@pytest.fixture(autouse=True)
def isolate_import(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    FakeImporter.calls.clear()
    monkeypatch.setenv(
        "MAGNETATLAS_DATABASE_URL", f"sqlite:///{tmp_path / 'db.sqlite'}"
    )
    monkeypatch.setattr("magnetatlas.cli.LantmaterietImporter", FakeImporter)
    monkeypatch.setattr(
        "magnetatlas.cli._create_lantmateriet_sync_service",
        lambda settings, instance: object(),
    )


def test_import_lantmateriet_country_creates_dataset_instance() -> None:
    result = CliRunner().invoke(
        app,
        ["import", "lantmateriet", "--dataset", "ortnamn", "--country", "sweden"],
    )

    assert result.exit_code == 0, result.output
    assert "41" in result.output
    instance = _lantmateriet_dataset_instance("sweden", None)
    assert instance.dataset_id == "lantmateriet-ortnamn:country:sweden"
    assert instance.scope == DatasetScope.country("sweden")


def test_import_lantmateriet_bbox_preserves_country_parent() -> None:
    result = CliRunner().invoke(
        app,
        [
            "import",
            "lantmateriet",
            "--dataset",
            "ortnamn",
            "--bbox",
            "18.2,59.35,18.5,59.5",
        ],
    )

    assert result.exit_code == 0, result.output
    bounds = BoundingBox(18.2, 59.35, 18.5, 59.5)
    assert FakeImporter.calls[0]["bbox"] == bounds
    assert _lantmateriet_dataset_instance(None, bounds).dataset_id.endswith(
        "within:country:sweden"
    )


def test_import_lantmateriet_rejects_unknown_dataset() -> None:
    result = CliRunner().invoke(
        app, ["import", "lantmateriet", "--dataset", "historiska-kartor"]
    )

    assert result.exit_code == 1
    assert "endast värdet ortnamn" in result.output
    assert not FakeImporter.calls
