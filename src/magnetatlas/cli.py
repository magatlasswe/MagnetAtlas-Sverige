"""Typer command-line interface."""

from __future__ import annotations

import logging
import shutil
import webbrowser
from pathlib import Path
from typing import Annotated, Never

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.exc import SQLAlchemyError

from magnetatlas.application.collectors import CollectorRegistry
from magnetatlas.application.evidence import (
    EvidenceEngine,
    EvidenceReportService,
    EvidenceRuleRegistry,
    FeatureEvidenceRule,
)
from magnetatlas.application.evidence_rules import create_default_evidence_rules_library
from magnetatlas.application.feature_queries import CatalogFeatureQuerySource
from magnetatlas.application.layer_composition import ComposedFeatureQuerySource
from magnetatlas.application.search import SearchService
from magnetatlas.application.sync import SyncService
from magnetatlas.config.logging import configure_logging
from magnetatlas.config.settings import Settings
from magnetatlas.domain.datasets import DatasetInstance, DatasetScope, SourceDefinition
from magnetatlas.domain.exceptions import MagnetAtlasError
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.infrastructure.database.feature_queries import (
    SqlAlchemyFeatureQuerySource,
)
from magnetatlas.infrastructure.database.repositories import (
    SqlAlchemyArchiveRecordRepository,
    SqlAlchemyAtlasFeatureRepository,
)
from magnetatlas.infrastructure.database.session import create_session_factory
from magnetatlas.infrastructure.exporters.csv_exporter import export_csv
from magnetatlas.infrastructure.features import load_demo_features, load_features
from magnetatlas.infrastructure.sources.lantmateriet.client import LantmaterietClient
from magnetatlas.infrastructure.sources.lantmateriet.collector import (
    LANTMATERIET_SOURCE_DEFINITION,
    ORTNAMN_DATASET,
    LantmaterietCollector,
)
from magnetatlas.infrastructure.sources.lantmateriet.importer import (
    LantmaterietImporter,
)
from magnetatlas.infrastructure.sources.raa.client import RAAClient
from magnetatlas.infrastructure.sources.raa.collector import (
    RAA_SOURCE_DEFINITION,
    RAACollector,
)
from magnetatlas.infrastructure.sources.raa.importer import RAACache, RAAImporter
from magnetatlas.infrastructure.sources.riksarkivet.client import RiksarkivetClient
from magnetatlas.infrastructure.sources.sgu.client import SGUClient
from magnetatlas.infrastructure.sources.sgu.collector import (
    SGU_JORDARTER,
    SGU_SOURCE_DEFINITION,
    SGUCollector,
)
from magnetatlas.infrastructure.sources.sgu.importer import SGUImporter
from magnetatlas.interfaces.web.layers import create_layer_service
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
NATIONWIDE_MIN_FREE_BYTES = 12 * 1024**3
RAA_SOURCE = RAA_SOURCE_DEFINITION
SGU_SOURCE = SGU_SOURCE_DEFINITION
LANTMATERIET_SOURCE = LANTMATERIET_SOURCE_DEFINITION


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


def _create_raa_sync_service(
    settings: Settings, instance: DatasetInstance | None = None
) -> SyncService:
    repository = SqlAlchemyAtlasFeatureRepository(
        create_session_factory(settings.database_url)
    )
    selected = instance or repository.get_active_instance(RAA_SOURCE.source_id)
    if selected is None:
        selected = DatasetInstance.create(RAA_SOURCE, DatasetScope.country("sweden"))
    client = RAAClient(
        api_url=settings.raa_api_url,
        download_url=settings.raa_download_url,
        timeout=settings.http_timeout,
    )
    return SyncService(
        selected, RAACollector(client), repository, settings.raa_work_dir
    )


def _create_sgu_sync_service(
    settings: Settings, instance: DatasetInstance
) -> SyncService:
    repository = SqlAlchemyAtlasFeatureRepository(
        create_session_factory(settings.database_url)
    )
    client = SGUClient(
        base_url=settings.sgu_api_url,
        timeout=settings.http_timeout,
    )
    return SyncService(
        instance,
        SGUCollector(client, SGU_JORDARTER),
        repository,
        settings.sgu_work_dir,
    )


def _create_lantmateriet_sync_service(
    settings: Settings, instance: DatasetInstance
) -> SyncService:
    repository = SqlAlchemyAtlasFeatureRepository(
        create_session_factory(settings.database_url)
    )
    client = LantmaterietClient(
        base_url=settings.lantmateriet_stac_url,
        timeout=settings.http_timeout,
        client_id=settings.lantmateriet_client_id,
        client_secret=settings.lantmateriet_client_secret,
        token_url=settings.lantmateriet_token_url,
        username=settings.lantmateriet_username,
        password=settings.lantmateriet_password,
    )
    return SyncService(
        instance,
        LantmaterietCollector(client, ORTNAMN_DATASET),
        repository,
        settings.lantmateriet_work_dir,
    )


def _parse_bbox(value: str | None) -> BoundingBox | None:
    if value is None:
        return None
    try:
        west, south, east, north = (float(part) for part in value.split(","))
    except ValueError as exc:
        raise ValueError("--bbox ska anges som west,south,east,north") from exc
    return BoundingBox(west=west, south=south, east=east, north=north)


def _validate_raa_scope(
    country: str | None,
    county: str | None,
    municipality: str | None,
) -> None:
    selected = sum(value is not None for value in (country, county, municipality))
    if selected > 1:
        raise ValueError("Välj endast ett av --country, --county eller --municipality")
    if country is not None and country.strip().casefold() != "sweden":
        raise ValueError("--country stöder endast värdet sweden")


def _raa_dataset_instance(
    country: str | None,
    county: str | None,
    municipality: str | None,
    bbox: BoundingBox | None,
) -> DatasetInstance:
    if bbox is not None:
        parent = None
        if municipality is not None:
            parent = DatasetScope.municipality(municipality)
        elif county is not None:
            parent = DatasetScope.county(county)
        elif country is not None:
            parent = DatasetScope.country(country)
        scope = DatasetScope.bbox(bbox, parent=parent)
    elif municipality is not None:
        scope = DatasetScope.municipality(municipality)
    elif county is not None:
        scope = DatasetScope.county(county)
    else:
        scope = DatasetScope.country(country or "sweden")
    return DatasetInstance.create(RAA_SOURCE, scope)


def _sgu_dataset_instance(
    country: str | None,
    county: str | None,
    municipality: str | None,
    bbox: BoundingBox | None,
) -> DatasetInstance:
    if bbox is not None:
        parent = None
        if municipality is not None:
            parent = DatasetScope.municipality(municipality)
        elif county is not None:
            parent = DatasetScope.county(county)
        elif country is not None:
            parent = DatasetScope.country(country)
        scope = DatasetScope.bbox(bbox, parent=parent)
    elif municipality is not None:
        scope = DatasetScope.municipality(municipality)
    elif county is not None:
        scope = DatasetScope.county(county)
    else:
        scope = DatasetScope.country(country or "sweden")
    return DatasetInstance.create(SGU_SOURCE, scope)


def _lantmateriet_dataset_instance(
    country: str | None, bbox: BoundingBox | None
) -> DatasetInstance:
    parent = DatasetScope.country(country or "sweden")
    scope = DatasetScope.bbox(bbox, parent=parent) if bbox is not None else parent
    return DatasetInstance.create(LANTMATERIET_SOURCE, scope)


def _ensure_nationwide_disk_space(path: Path) -> None:
    free = shutil.disk_usage(path).free
    if free < NATIONWIDE_MIN_FREE_BYTES:
        required_gib = NATIONWIDE_MIN_FREE_BYTES // 1024**3
        available_gib = free / 1024**3
        raise ValueError(
            f"Sverigeimport kräver minst {required_gib} GiB ledigt diskutrymme; "
            f"endast {available_gib:.1f} GiB är tillgängligt."
        )


@import_app.command("raa")
def import_raa(
    country: Annotated[str | None, typer.Option("--country")] = None,
    county: Annotated[str | None, typer.Option("--county")] = None,
    municipality: Annotated[str | None, typer.Option("--municipality")] = None,
    bbox: Annotated[str | None, typer.Option("--bbox")] = None,
) -> None:
    """Importera en officiell KMR-bas till lokal SQLite."""
    try:
        _validate_raa_scope(country, county, municipality)
        settings = Settings.from_env()
        settings.prepare_directories()
        if country is not None:
            _ensure_nationwide_disk_space(settings.raa_work_dir)
        parsed_bbox = _parse_bbox(bbox)
        instance = _raa_dataset_instance(country, county, municipality, parsed_bbox)
        last_reported = 0

        def report_progress(imported: int) -> None:
            nonlocal last_reported
            if imported - last_reported >= 5_000:
                console.print(f"Bearbetade {imported} RAÄ-objekt…")
                last_reported = imported

        result = RAAImporter(_create_raa_sync_service(settings, instance)).run(
            county=county,
            municipality=municipality,
            bbox=parsed_bbox,
            progress=report_progress,
        )
        console.print(
            f"Importerade [bold]{result.imported}[/bold] RAÄ-objekt på "
            f"{result.duration_seconds:.1f} sekunder."
        )
    except EXPECTED_ERRORS as exc:
        _abort_with_error("RAÄ-importen misslyckades", exc)


@import_app.command("sgu")
def import_sgu(
    country: Annotated[str | None, typer.Option("--country")] = None,
    county: Annotated[str | None, typer.Option("--county")] = None,
    municipality: Annotated[str | None, typer.Option("--municipality")] = None,
    bbox: Annotated[str | None, typer.Option("--bbox")] = None,
) -> None:
    """Importera SGU Jordarter från myndighetens dokumenterade OGC API."""
    try:
        _validate_raa_scope(country, county, municipality)
        parsed_bbox = _parse_bbox(bbox)
        if (county or municipality) and parsed_bbox is None:
            raise ValueError(
                "SGU kräver --bbox tillsammans med --county eller --municipality"
            )
        settings = Settings.from_env()
        settings.prepare_directories()
        instance = _sgu_dataset_instance(country, county, municipality, parsed_bbox)
        last_reported = 0

        def report_progress(imported: int) -> None:
            nonlocal last_reported
            if imported - last_reported >= 5_000:
                console.print(f"Bearbetade {imported} SGU-objekt…")
                last_reported = imported

        result = SGUImporter(_create_sgu_sync_service(settings, instance)).run(
            county=county,
            municipality=municipality,
            bbox=parsed_bbox,
            progress=report_progress,
        )
        console.print(
            f"Importerade [bold]{result.imported}[/bold] SGU-objekt på "
            f"{result.duration_seconds:.1f} sekunder."
        )
    except EXPECTED_ERRORS as exc:
        _abort_with_error("SGU-importen misslyckades", exc)


@import_app.command("lantmateriet")
def import_lantmateriet(
    dataset: Annotated[str, typer.Option("--dataset")] = "ortnamn",
    country: Annotated[str | None, typer.Option("--country")] = None,
    bbox: Annotated[str | None, typer.Option("--bbox")] = None,
) -> None:
    """Importera Lantmäteriets reproducerbara vektornedladdning."""
    try:
        if dataset.casefold() != "ortnamn":
            raise ValueError("--dataset stöder endast värdet ortnamn")
        if country is not None and country.strip().casefold() != "sweden":
            raise ValueError("--country stöder endast värdet sweden")
        parsed_bbox = _parse_bbox(bbox)
        settings = Settings.from_env()
        settings.prepare_directories()
        instance = _lantmateriet_dataset_instance(country, parsed_bbox)
        last_reported = 0

        def report_progress(imported: int) -> None:
            nonlocal last_reported
            if imported - last_reported >= 5_000:
                console.print(f"Bearbetade {imported} ortnamn…")
                last_reported = imported

        result = LantmaterietImporter(
            _create_lantmateriet_sync_service(settings, instance)
        ).run(bbox=parsed_bbox, progress=report_progress)
        console.print(
            f"Importerade [bold]{result.imported}[/bold] ortnamn på "
            f"{result.duration_seconds:.1f} sekunder."
        )
    except EXPECTED_ERRORS as exc:
        _abort_with_error("Lantmäteriet-importen misslyckades", exc)


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
            active_instance = DatasetInstance.create(
                SourceDefinition("local-json", "Lokal JSON"),
                DatasetScope.country("sweden"),
            )
            instances = (active_instance,)
            raw_sources = (
                (
                    active_instance,
                    CatalogFeatureQuerySource(load_features(features_path)),
                ),
            )
        else:
            session_factory = create_session_factory(settings.database_url)
            repository = SqlAlchemyAtlasFeatureRepository(session_factory)
            discovered = repository.list_dataset_instances()
            source_ids = dict.fromkeys(
                instance.source.source_id for instance in discovered
            )
            instances = tuple(
                instance
                for source_id in source_ids
                if (instance := repository.get_active_instance(source_id)) is not None
            )
            if not instances:
                instances = (
                    DatasetInstance.create(RAA_SOURCE, DatasetScope.country("sweden")),
                )
            raw_sources = tuple(
                (
                    instance,
                    SqlAlchemyFeatureQuerySource(session_factory, instance.dataset_id),
                )
                for instance in instances
            )
            if not raw_sources or not any(
                source.summary().count for _, source in raw_sources
            ):
                active_instance = DatasetInstance.create(
                    SourceDefinition("magnetatlas-demo", "MagnetAtlas demo"),
                    DatasetScope.country("sweden"),
                )
                instances = (active_instance,)
                raw_sources = (
                    (active_instance, CatalogFeatureQuerySource(load_demo_features())),
                )
        layer_service = create_layer_service(instances)
        composed_source = ComposedFeatureQuerySource(raw_sources, layer_service)
        rules_library = create_default_evidence_rules_library()
        evidence_service = EvidenceReportService(
            raw_sources,
            EvidenceEngine(
                EvidenceRuleRegistry((FeatureEvidenceRule(), *rules_library.list()))
            ),
        )
        server = create_server(
            composed_source,
            layer_service,
            evidence_service=evidence_service,
            rules_library=rules_library,
            host=host,
            port=port,
        )
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
