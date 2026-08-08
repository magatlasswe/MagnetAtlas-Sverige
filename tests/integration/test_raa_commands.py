"""CLI tests for RAÄ import and cache commands."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DatabaseError
from typer.testing import CliRunner

from magnetatlas.application.sync import CacheStatus, SyncResult
from magnetatlas.cli import RAA_SOURCE, _raa_dataset_instance, app
from magnetatlas.domain.datasets import DatasetScope
from magnetatlas.domain.geography import BoundingBox


class FakeSyncService:
    """Record facade calls without network or persistent state."""

    def __init__(self) -> None:
        self.import_args: dict[str, object] | None = None

    def base_import(self, **kwargs: object) -> SyncResult:
        self.import_args = kwargs
        return SyncResult("base", 12, 0, "2026-08-04")

    def status(self) -> CacheStatus:
        return CacheStatus(True, 12, sync_marker="2026-08-04")

    def refresh(self, *, force: bool = False) -> SyncResult:
        assert force
        return SyncResult("incremental", 2, 1, "2026-08-04")

    def clear(self) -> int:
        return 12


@pytest.fixture
def fake_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeSyncService:
    service = FakeSyncService()
    monkeypatch.setenv("MAGNETATLAS_DATABASE_URL", f"sqlite:///{tmp_path / 'atlas.db'}")
    monkeypatch.setattr(
        "magnetatlas.cli._create_raa_sync_service",
        lambda settings, instance=None: service,
    )
    return service


def test_import_raa_passes_geographic_scope(fake_service: FakeSyncService) -> None:
    result = CliRunner().invoke(
        app,
        ["import", "raa", "--county", "ostergotland", "--bbox", "14,57,17,59"],
    )

    assert result.exit_code == 0, result.output
    assert "12" in result.output
    assert "Import klar" in result.output
    assert "DatasetInstance:" in result.output
    assert fake_service.import_args is not None
    assert fake_service.import_args["county"] == "ostergotland"
    assert fake_service.import_args["bbox"] is not None


def test_import_country_sweden_uses_official_total_package(
    fake_service: FakeSyncService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "magnetatlas.cli._ensure_nationwide_disk_space", lambda path: None
    )

    result = CliRunner().invoke(app, ["import", "raa", "--country", "sweden"])

    assert result.exit_code == 0, result.output
    assert fake_service.import_args is not None
    assert fake_service.import_args["county"] is None
    assert fake_service.import_args["municipality"] is None


def test_raa_import_scopes_have_independent_dataset_identities() -> None:
    instances = {
        _raa_dataset_instance("sweden", None, None, None),
        _raa_dataset_instance(None, "ostergotland", None, None),
        _raa_dataset_instance(None, None, "vaxholm", None),
        _raa_dataset_instance(None, None, None, BoundingBox(14, 57, 17, 59)),
    }

    assert {instance.dataset_id for instance in instances} == {
        "raa-kmr:country:sweden",
        "raa-kmr:county:ostergotland",
        "raa-kmr:municipality:vaxholm",
        "raa-kmr:bbox:14,57,17,59",
    }
    assert all(instance.source == RAA_SOURCE for instance in instances)
    assert {instance.scope for instance in instances} == {
        DatasetScope.country("sweden"),
        DatasetScope.county("ostergotland"),
        DatasetScope.municipality("vaxholm"),
        DatasetScope.bbox(BoundingBox(14, 57, 17, 59)),
    }
    combined = _raa_dataset_instance(
        None, "ostergotland", None, BoundingBox(14, 57, 17, 59)
    )
    assert combined.dataset_id.endswith("within:county:ostergotland")


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (["cache", "status"], "12 objekt"),
        (["cache", "refresh"], "2 ändrade"),
        (["cache", "clear"], "Rensade 12"),
    ],
)
def test_cache_commands(
    fake_service: FakeSyncService, command: list[str], expected: str
) -> None:
    result = CliRunner().invoke(app, command)

    assert result.exit_code == 0, result.output
    assert expected in result.output


def test_import_rejects_conflicting_scope(fake_service: FakeSyncService) -> None:
    result = CliRunner().invoke(
        app,
        ["import", "raa", "--country", "sweden", "--municipality", "y"],
    )

    assert result.exit_code == 1
    assert "endast ett" in result.output
    assert fake_service.import_args is None


def test_import_rejects_unknown_country(fake_service: FakeSyncService) -> None:
    result = CliRunner().invoke(app, ["import", "raa", "--country", "finland"])

    assert result.exit_code == 1
    assert "endast värdet sweden" in result.output
    assert fake_service.import_args is None


def test_country_import_checks_disk_before_source_call(
    fake_service: FakeSyncService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "magnetatlas.cli.shutil.disk_usage",
        lambda path: SimpleNamespace(free=1),
    )

    result = CliRunner().invoke(app, ["import", "raa", "--country", "sweden"])

    assert result.exit_code == 1
    assert "12 GiB" in result.output
    assert fake_service.import_args is None


@pytest.mark.parametrize("command", [["cache", "status"], ["cache", "clear"]])
def test_cache_commands_explain_corrupt_database(
    fake_service: FakeSyncService,
    monkeypatch: pytest.MonkeyPatch,
    command: list[str],
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise DatabaseError("SELECT", {}, RuntimeError("broken"))

    monkeypatch.setattr(fake_service, command[1], fail)

    result = CliRunner().invoke(app, command)

    assert result.exit_code == 1
    assert "lokala databasen kunde inte läsas" in result.output
    assert "broken" not in result.output
