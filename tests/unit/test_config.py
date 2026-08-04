"""Tests for environment configuration."""

import pytest

from magnetatlas.config.settings import Settings


def test_settings_load_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGNETATLAS_HTTP_TIMEOUT", "7.5")
    monkeypatch.setenv("MAGNETATLAS_LOG_LEVEL", "debug")

    settings = Settings.from_env()

    assert settings.http_timeout == 7.5
    assert settings.log_level == "DEBUG"


def test_settings_reject_non_positive_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAGNETATLAS_HTTP_TIMEOUT", "0")

    with pytest.raises(ValueError, match="större än noll"):
        Settings.from_env()
