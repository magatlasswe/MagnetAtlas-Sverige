"""Network-isolated CLI tests for production database diagnostics."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from magnetatlas.cli import LANTMATERIET_SOURCE, RAA_SOURCE, SGU_SOURCE, app
from magnetatlas.domain.datasets import DatasetInstance, DatasetScope
from magnetatlas.domain.features import AtlasFeature, FeatureId, LicenseInfo, Provenance
from magnetatlas.domain.repositories import DatasetMetadata, StoredFeature
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyAtlasFeatureRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory

NOW = datetime(2026, 8, 8, 8, tzinfo=UTC)


def _store(
    repository: SqlAlchemyAtlasFeatureRepository,
    instance: DatasetInstance,
    identifier: str,
    *,
    version: str,
    license_name: str,
) -> None:
    feature = AtlasFeature(
        FeatureId(identifier),
        identifier,
        "test",
        Provenance(
            instance.source.display_name,
            identifier,
            fetched_at=NOW,
            license_info=LicenseInfo(license_name),
        ),
    )
    repository.replace_dataset(
        DatasetMetadata(instance, "1", NOW, "2026-08-07"),
        (StoredFeature(feature, version),),
    )


@pytest.fixture
def production_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "production.db"
    repository = SqlAlchemyAtlasFeatureRepository(
        create_session_factory(f"sqlite:///{path}")
    )
    _store(
        repository,
        DatasetInstance.create(RAA_SOURCE, DatasetScope.country("sweden")),
        "raa:1",
        version="raa-v1",
        license_name="CC0",
    )
    _store(
        repository,
        DatasetInstance.create(SGU_SOURCE, DatasetScope.country("sweden")),
        "sgu:1",
        version="sgu-v1",
        license_name="CC0",
    )
    _store(
        repository,
        DatasetInstance.create(LANTMATERIET_SOURCE, DatasetScope.country("sweden")),
        "lantmateriet:1",
        version="lm-v1",
        license_name="CC BY 4.0",
    )
    monkeypatch.setenv("MAGNETATLAS_DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("MAGNETATLAS_RAA_WORK_DIR", str(tmp_path / "raa"))
    monkeypatch.setenv("MAGNETATLAS_SGU_WORK_DIR", str(tmp_path / "sgu"))
    monkeypatch.setenv(
        "MAGNETATLAS_LANTMATERIET_WORK_DIR", str(tmp_path / "lantmateriet")
    )
    monkeypatch.setenv("MAGNETATLAS_LANTMATERIET_USERNAME", "test-user")
    monkeypatch.setenv("MAGNETATLAS_LANTMATERIET_PASSWORD", "test-password")
    return path


def test_status_reports_database_counts_and_active_layers(
    production_database: Path,
) -> None:
    result = CliRunner().invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert production_database.name in result.output
    assert "AtlasFeatures: 3" in result.output
    assert "DatasetInstances: 3" in result.output
    assert "Providers: 3" in result.output
    assert "Aktiva lager: 3" in result.output


def test_datasets_reports_scope_snapshot_license_and_activation(
    production_database: Path,
) -> None:
    result = CliRunner().invoke(app, ["datasets"], terminal_width=240)
    assert result.exit_code == 0, result.output
    for heading in (
        "Provider",
        "Dataset",
        "Scope",
        "Aktiv",
        "Objekt",
        "Importerad",
        "Snapshot",
        "Licens",
    ):
        assert heading in result.output
    assert "country:" in result.output


def test_providers_reports_installed_imported_and_active(
    production_database: Path,
) -> None:
    result = CliRunner().invoke(app, ["providers"])
    assert result.exit_code == 0, result.output
    for provider in ("RAÄ", "SGU", "Lantmäteriet"):
        assert provider in result.output
    assert result.output.count("Ja") == 9


def test_doctor_verifies_complete_production_database(
    production_database: Path,
) -> None:
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0, result.output
    for check in (
        "Databas hittad",
        "Schema OK",
        "Layer Engine",
        "API",
        "DatasetInstances",
        "Feature-antal",
        "Saknade importer",
        "Miljövariabler",
        "OAuth2-konfiguration",
        "Cache",
    ):
        assert f"[OK] {check}" in result.output


def test_doctor_fails_clearly_when_official_imports_are_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "incomplete.db"
    repository = SqlAlchemyAtlasFeatureRepository(
        create_session_factory(f"sqlite:///{path}")
    )
    _store(
        repository,
        DatasetInstance.create(RAA_SOURCE, DatasetScope.municipality("kinda")),
        "raa:1",
        version="raa-v1",
        license_name="CC0",
    )
    monkeypatch.setenv("MAGNETATLAS_DATABASE_URL", f"sqlite:///{path}")

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "[FEL] Saknade importer" in result.output
    assert "RAÄ Sverige" in result.output
    assert "SGU Jordarter" in result.output
    assert "Lantmäteriet Ortnamn" in result.output


def test_doctor_requires_lantmateriet_authentication(
    production_database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MAGNETATLAS_LANTMATERIET_USERNAME")
    monkeypatch.delenv("MAGNETATLAS_LANTMATERIET_PASSWORD")

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "[FEL] OAuth2-konfiguration" in result.output
    assert "kräver" in result.output
    assert "behörighet" in result.output
