"""CLI integration tests for the local web experience."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from magnetatlas.cli import app
from magnetatlas.infrastructure.features import load_demo_features


class FakeServer:
    server_address = ("127.0.0.1", 8123)

    def __init__(self) -> None:
        self.served = False
        self.closed = False

    def serve_forever(self) -> None:
        self.served = True

    def server_close(self) -> None:
        self.closed = True


def test_serve_starts_local_server_without_opening_browser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    server = FakeServer()

    def fake_create_server(*args: Any, **kwargs: Any) -> FakeServer:
        assert kwargs == {"host": "127.0.0.1", "port": 8123}
        return server

    monkeypatch.setattr("magnetatlas.cli.create_server", fake_create_server)
    monkeypatch.setenv("MAGNETATLAS_DATABASE_URL", f"sqlite:///{tmp_path / 'atlas.db'}")
    monkeypatch.setattr(
        "magnetatlas.cli.webbrowser.open",
        lambda url: pytest.fail(f"Webbläsaren öppnades oväntat: {url}"),
    )

    result = CliRunner().invoke(app, ["serve", "--port", "8123", "--no-browser"])

    assert result.exit_code == 0, result.output
    assert "http://localhost:8123/" in result.output
    assert server.served
    assert server.closed


def test_serve_opens_default_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = FakeServer()
    opened: list[str] = []
    monkeypatch.setattr("magnetatlas.cli.create_server", lambda *args, **kwargs: server)
    monkeypatch.setenv("MAGNETATLAS_DATABASE_URL", f"sqlite:///{tmp_path / 'atlas.db'}")
    monkeypatch.setattr("magnetatlas.cli.webbrowser.open", opened.append)

    result = CliRunner().invoke(app, ["serve"])

    assert result.exit_code == 0, result.output
    assert opened == ["http://localhost:8123/"]


def test_serve_prefers_imported_features_over_demo_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = FakeServer()
    imported = replace(
        load_demo_features()[0],
        properties={"raa_id": "L1947:8930"},
    )

    class FakeRepository:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def list_features(self) -> list[object]:
            return [imported]

    def fake_create_server(catalog: object, **kwargs: object) -> FakeServer:
        assert catalog.list_all() == (imported,)  # type: ignore[attr-defined]
        return server

    monkeypatch.setenv("MAGNETATLAS_DATABASE_URL", f"sqlite:///{tmp_path / 'atlas.db'}")
    monkeypatch.setattr(
        "magnetatlas.cli.SqlAlchemyAtlasFeatureRepository", FakeRepository
    )
    monkeypatch.setattr("magnetatlas.cli.create_server", fake_create_server)
    monkeypatch.setattr(
        "magnetatlas.cli.load_demo_features",
        lambda: pytest.fail("Demodata lästes trots importerade RAÄ-objekt"),
    )

    result = CliRunner().invoke(app, ["serve", "--no-browser"])

    assert result.exit_code == 0, result.output
