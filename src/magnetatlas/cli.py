"""Typer command-line interface."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from magnetatlas.application.collectors import CollectorRegistry
from magnetatlas.application.search import SearchService
from magnetatlas.config.logging import configure_logging
from magnetatlas.config.settings import Settings
from magnetatlas.domain.exceptions import MagnetAtlasError
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyArchiveRecordRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory
from magnetatlas.infrastructure.exporters.csv_exporter import export_csv
from magnetatlas.infrastructure.sources.riksarkivet.client import RiksarkivetClient

app = typer.Typer(
    name="magnetatlas",
    help="Historiskt GIS-verktyg för magnetfiske i Sverige.",
    no_args_is_help=True,
)
console = Console()
LOGGER = logging.getLogger(__name__)


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
    except (MagnetAtlasError, ValueError, OSError) as exc:
        LOGGER.debug("Kommandot misslyckades", exc_info=True)
        console.print(f"[red]Fel:[/red] {exc}", stderr=True)
        raise typer.Exit(code=1) from exc
