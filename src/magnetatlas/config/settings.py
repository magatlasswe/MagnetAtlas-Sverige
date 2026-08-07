"""Typed settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


def _positive_float(value: str, variable: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{variable} måste vara ett tal") from exc
    if parsed <= 0:
        raise ValueError(f"{variable} måste vara större än noll")
    return parsed


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings with safe local defaults."""

    database_url: str = "sqlite:///data/database/magnetatlas.db"
    output_dir: Path = Path("output")
    log_level: str = "INFO"
    riksarkivet_base_url: str = "https://data.riksarkivet.se/api"
    raa_api_url: str = "https://pub.raa.se/datauttag"
    raa_download_url: str = "https://pub.raa.se/nedladdning/datauttag/lamningar_v1"
    raa_work_dir: Path = Path("data/cache/raa")
    sgu_api_url: str = "https://api.sgu.se/oppnadata"
    sgu_work_dir: Path = Path("data/cache/sgu")
    http_timeout: float = 20.0

    @classmethod
    def from_env(cls) -> Settings:
        """Create settings from `MAGNETATLAS_` environment variables."""
        timeout = _positive_float(
            os.getenv("MAGNETATLAS_HTTP_TIMEOUT", "20"),
            "MAGNETATLAS_HTTP_TIMEOUT",
        )
        settings = cls(
            database_url=os.getenv(
                "MAGNETATLAS_DATABASE_URL",
                "sqlite:///data/database/magnetatlas.db",
            ),
            output_dir=Path(os.getenv("MAGNETATLAS_OUTPUT_DIR", "output")),
            log_level=os.getenv("MAGNETATLAS_LOG_LEVEL", "INFO").upper(),
            riksarkivet_base_url=os.getenv(
                "MAGNETATLAS_RIKSARKIVET_BASE_URL",
                "https://data.riksarkivet.se/api",
            ).rstrip("/"),
            raa_api_url=os.getenv(
                "MAGNETATLAS_RAA_API_URL", "https://pub.raa.se/datauttag"
            ).rstrip("/"),
            raa_download_url=os.getenv(
                "MAGNETATLAS_RAA_DOWNLOAD_URL",
                "https://pub.raa.se/nedladdning/datauttag/lamningar_v1",
            ).rstrip("/"),
            raa_work_dir=Path(os.getenv("MAGNETATLAS_RAA_WORK_DIR", "data/cache/raa")),
            sgu_api_url=os.getenv(
                "MAGNETATLAS_SGU_API_URL", "https://api.sgu.se/oppnadata"
            ).rstrip("/"),
            sgu_work_dir=Path(os.getenv("MAGNETATLAS_SGU_WORK_DIR", "data/cache/sgu")),
            http_timeout=timeout,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """Reject unsafe or malformed runtime configuration."""
        parsed = urlparse(self.riksarkivet_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Riksarkivets bas-URL måste vara en giltig HTTP(S)-URL")
        for label, value in (
            ("RAÄ API-URL", self.raa_api_url),
            ("RAÄ nedladdnings-URL", self.raa_download_url),
            ("SGU API-URL", self.sgu_api_url),
        ):
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"{label} måste vara en giltig HTTP(S)-URL")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("MAGNETATLAS_LOG_LEVEL har ett ogiltigt värde")

    def prepare_directories(self) -> None:
        """Create local output and SQLite parent directories when needed."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            database_path = Path(self.database_url.removeprefix("sqlite:///"))
            if str(database_path) != ":memory:":
                database_path.parent.mkdir(parents=True, exist_ok=True)
