"""CLI tests for the SGU provider import."""

from pathlib import Path
from typing import ClassVar

import pytest
from typer.testing import CliRunner

from magnetatlas.application.sync import SyncResult
from magnetatlas.cli import SGU_SOURCE, _sgu_dataset_instance, app
from magnetatlas.domain.datasets import DatasetScope
from magnetatlas.domain.geography import BoundingBox


class FakeImporter:
    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, service: object) -> None:
        pass

    def run(self, **kwargs: object) -> SyncResult:
        self.calls.append(kwargs)
        return SyncResult("base", 37, 0, "2026-08-06", 1.5)


@pytest.fixture(autouse=True)
def isolate_import(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    FakeImporter.calls.clear()
    monkeypatch.setenv("MAGNETATLAS_DATABASE_URL", f"sqlite:///{tmp_path / 'atlas.db'}")
    monkeypatch.setattr("magnetatlas.cli.SGUImporter", FakeImporter)
    monkeypatch.setattr(
        "magnetatlas.cli._create_sgu_sync_service", lambda settings, instance: object()
    )


def test_import_sgu_country_uses_an_independent_dataset_instance() -> None:
    result = CliRunner().invoke(app, ["import", "sgu", "--country", "sweden"])

    assert result.exit_code == 0, result.output
    assert "37" in result.output
    assert "Import klar" in result.output
    assert "Provider: SGU" in result.output
    assert FakeImporter.calls[0]["bbox"] is None
    instance = _sgu_dataset_instance("sweden", None, None, None)
    assert instance.dataset_id == "sgu-jordarter:country:sweden"
    assert instance.source == SGU_SOURCE
    assert instance.scope == DatasetScope.country("sweden")


def test_import_sgu_bbox_preserves_municipality_parent_scope() -> None:
    result = CliRunner().invoke(
        app,
        [
            "import",
            "sgu",
            "--municipality",
            "vaxholm",
            "--bbox",
            "18.2,59.35,18.5,59.5",
        ],
    )

    assert result.exit_code == 0, result.output
    bounds = FakeImporter.calls[0]["bbox"]
    assert bounds == BoundingBox(18.2, 59.35, 18.5, 59.5)
    instance = _sgu_dataset_instance(None, None, "vaxholm", bounds)
    assert instance.dataset_id.endswith("within:municipality:vaxholm")


def test_import_sgu_rejects_named_scope_without_bbox() -> None:
    result = CliRunner().invoke(app, ["import", "sgu", "--county", "stockholm"])

    assert result.exit_code == 1
    assert "kräver --bbox" in result.output
    assert not FakeImporter.calls
