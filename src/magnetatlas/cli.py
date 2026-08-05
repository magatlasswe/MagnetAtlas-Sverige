"""Typer command-line interface."""

from __future__ import annotations

import logging
import webbrowser
from pathlib import Path
from typing import Annotated, Never

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.exc import SQLAlchemyError

from magnetatlas.application.collectors import CollectorRegistry
from magnetatlas.application.features import FeatureCatalog
from magnetatlas.application.search import SearchService
from magnetatlas.application.sync import SyncService
from magnetatlas.config.logging import configure_logging
from magnetatlas.config.settings import Settings
from magnetatlas.domain.exceptions import MagnetAtlasError
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyArchiveRecordRepository,
    SqlAlchemyAtlasFeatureRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory
from magnetatlas.infrastructure.exporters.csv_exporter import export_csv
from magnetatlas.infrastructure.features import load_demo_features, load_features
from magnetatlas.infrastructure.sources.raa.client import RAAClient
from magnetatlas.infrastructure.sources.raa.collector import RAACollector
from magnetatlas.infrastructure.sources.raa.importer import RAACache, RAAImporter
from magnetatlas.infrastructure.sources.riksarkivet.client import RiksarkivetClient
from magnetatlas.interfaces.web.server import create_server

app = typer.Typer(
    name="magnetatlas",
    help="Historiskt GIS-verktyg för magnetfiske i Sverige.",
    no_args_is_help=True,
)
console = Console()
error_console = Console(stderr=True)
LOGGER = logging.getLogger(__name__)
import_app = typer.Typer(help="Importera officiella datamängder.")
cache_app = typer.Typer(help="Hantera den lokala SQLite-cachen.")
app.add_typer(import_app, name="import")
app.add_typer(cache_app, name="cache")

EXPECTED_ERRORS = (MagnetAtlasError, ValueError, OSError, SQLAlchemyError)


def _abort_with_error(context: str, error: Exception) -> Never:
    """Report an expected CLI failure without exposing a traceback."""
    LOGGER.debug(context, exc_info=True)
    if isinstance(error, SQLAlchemyError):
        message = (
            "Den lokala databasen kunde inte läsas. Kontrollera databasfilen "
            "eller återställ RAÄ-cachen och försök igen."
        )
    else:
        message = str(error)
    error_console.print(f"[red]Fel:[/red] {message}")
    raise typer.Exit(code=1) from error


def _create_raa_sync_service(settings: Settings) -> SyncService:
    repository = SqlAlchemyAtlasFeatureRepository(
        create_session_factory(settings.database_url)
    )
    client = RAAClient(
        api_url=settings.raa_api_url,
        download_url=settings.raa_download_url,
        timeout=settings.http_timeout,
    )
    return SyncService(
        "raa-kmr", RAACollector(client), repository, settings.raa_work_dir
    )


def _parse_bbox(value: str | None) -> BoundingBox | None:
    if value is None:
        return None
    try:
        west, south, east, north = (float(part) for part in value.split(","))
    except ValueError as exc:
        raise ValueError("--bbox ska anges som west,south,east,north") from exc
    return BoundingBox(west=west, south=south, east=east, north=north)


@import_app.command("raa")
def import_raa(
    county: Annotated[str | None, typer.Option("--county")] = None,
    municipality: Annotated[str | None, typer.Option("--municipality")] = None,
    bbox: Annotated[str | None, typer.Option("--bbox")] = None,
) -> None:
    """Importera en officiell KMR-bas till lokal SQLite."""
    try:
        if county and municipality:
            raise ValueError("Välj antingen --county eller --municipality")
        settings = Settings.from_env()
        settings.prepare_directories()
        result = RAAImporter(_create_raa_sync_service(settings)).run(
            county=county, municipality=municipality, bbox=_parse_bbox(bbox)
        )
        console.print(f"Importerade [bold]{result.imported}[/bold] RAÄ-objekt.")
    except EXPECTED_ERRORS as exc:
        _abort_with_error("RAÄ-importen misslyckades", exc)


@cache_app.command("status")
def cache_status() -> None:
    """Visa lokal cache utan nätverksanrop."""
    try:
        settings = Settings.from_env()
        status = RAACache(_create_raa_sync_service(settings)).status()
        console.print(
            f"RAÄ-cache: {'tillgänglig' if status.available else 'saknas'}, "
            f"{status.feature_count} objekt, markör {status.sync_marker or '-'}"
        )
    except EXPECTED_ERRORS as exc:
        _abort_with_error("Cache-status kunde inte läsas", exc)


@cache_app.command("refresh")
def cache_refresh() -> None:
    """Uppdatera lokal cache enligt synkpolicyn."""
    try:
        settings = Settings.from_env()
        settings.prepare_directories()
        result = RAACache(_create_raa_sync_service(settings)).refresh()
        console.print(f"Cache uppdaterad: {result.imported} ändrade objekt.")
    except EXPECTED_ERRORS as exc:
        _abort_with_error("Cache-uppdateringen misslyckades", exc)


@cache_app.command("clear")
def cache_clear() -> None:
    """Rensa RAÄ-dataset och synkmetadata från SQLite."""
    try:
        settings = Settings.from_env()
        removed = RAACache(_create_raa_sync_service(settings)).clear()
        console.print(f"Rensade {removed} RAÄ-objekt.")
    except EXPECTED_ERRORS as exc:
        _abort_with_error("Cachen kunde inte rensas", exc)


@app.callback()
def main() -> None:
    """Run MagnetAtlas-Sverige commands."""


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Sökord för Riksarkivet.")],
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", min=1, max=100, help="Max antal träffar."),
    ] = 20,
    csv_path: Annotated[
        Path | None,
        typer.Option("--csv", help="Exportera träffarna till angiven CSV-fil."),
    ] = None,
) -> None:
    """Search Riksarkivet, persist results and optionally export CSV."""
    try:
        settings = Settings.from_env()
        configure_logging(settings.log_level)
        settings.prepare_directories()

        repository = SqlAlchemyArchiveRecordRepository(
            create_session_factory(settings.database_url)
        )
        client = RiksarkivetClient(
            settings.riksarkivet_base_url,
            timeout=settings.http_timeout,
        )
        registry = CollectorRegistry([client])
        collector = registry.get("riksarkivet")
        result = SearchService(collector, repository).search(query, limit=limit)

        table = Table(title=f"Riksarkivet: {query}")
        table.add_column("ID", style="dim")
        table.add_column("Titel")
        table.add_column("Typ")
        table.add_column("Datering")
        for record in result.records:
            table.add_row(
                record.source_id,
                record.title,
                record.detail_type or record.object_type,
                record.date_text or "-",
            )
        console.print(table)
        console.print(
            f"Sparade [bold]{len(result.records)}[/bold] av "
            f"[bold]{result.total_hits}[/bold] möjliga träffar."
        )

        if csv_path is not None:
            destination = export_csv(result.records, csv_path)
            console.print(f"CSV skapad: [green]{destination}[/green]")
    except EXPECTED_ERRORS as exc:
        _abort_with_error("Sökkommandot misslyckades", exc)


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option(help="Värdadress. Standardvärdet är endast lokalt."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(min=1, max=65535, help="Lokal webbserverport."),
    ] = 8000,
    features_path: Annotated[
        Path | None,
        typer.Option(
            "--features",
            help="Läs AtlasFeatures från en lokal JSON-fil i stället för demodata.",
        ),
    ] = None,
    browser: Annotated[
        bool,
        typer.Option("--browser/--no-browser", help="Öppna standardwebbläsaren."),
    ] = True,
) -> None:
    """Start the first local MagnetAtlas map experience."""
    server = None
    try:
        settings = Settings.from_env()
        configure_logging(settings.log_level)
        if features_path is not None:
            features = load_features(features_path)
        else:
            repository = SqlAlchemyAtlasFeatureRepository(
                create_session_factory(settings.database_url)
            )
            features = repository.list_features()
            if not features:
                features = load_demo_features()
        catalog = FeatureCatalog(features)
        server = create_server(catalog, host=host, port=port)
        actual_host, actual_port = server.server_address
        display_host = (
            "localhost" if actual_host in {"127.0.0.1", "::1"} else actual_host
        )
        url = f"http://{display_host}:{actual_port}/"
        console.print(f"MagnetAtlas är öppet på [link={url}]{url}[/link]")
        console.print("Stoppa servern med Ctrl+C.")
        if browser:
            webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\nMagnetAtlas har stoppats.")
    except EXPECTED_ERRORS as exc:
        _abort_with_error("Webbservern misslyckades", exc)
    finally:
        if server is not None:
            server.server_close()
