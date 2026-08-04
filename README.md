# MagnetAtlas-Sverige

MagnetAtlas-Sverige är ett historiskt GIS-projekt för att hitta, analysera och
exportera svenska platser av intresse för ansvarsfullt magnetfiske.

Projektet befinner sig i Sprint 2.3. Den körbara versionen erbjuder en lokal
webbkarta, CLI, SQLite-lagring, sökning mot Riksarkivets öppna söktjänst och
CSV-export.
Riksarkivet använder nu projektets gemensamma Collector-kontrakt och plugin
registry. En källoberoende `AtlasFeature`-modell beskriver geografiska objekt,
geometri, tid, proveniens, licens och osäkerhet. Fler datakällor är ännu inte
implementerade.

## Krav

- Python 3.13 eller 3.14

## Installation för utveckling

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

`pyproject.toml` är projektets primära källa för beroenden. Den medföljande
`requirements.txt` installerar samma projekt och finns endast för kompatibilitet.

## Användning

```powershell
magnetatlas --help
magnetatlas search "bro"
magnetatlas serve
```

Som standard sparas databasen under `data/database/` och exporter under
`output/csv/`. Använd `magnetatlas search --help` för samtliga alternativ.

`magnetatlas serve` startar kartan på `http://localhost:8000/` och öppnar
standardwebbläsaren. Stoppa den med Ctrl+C. Den bundlade kartan innehåller 60
tydligt märkta, syntetiska demoobjekt som visar gränssnittets funktioner; de är
inte verifierade historiska platser eller fyndplatser. Använd en egen lokal fil
med det versionerade AtlasFeature-formatet så här:

```powershell
magnetatlas serve --features path\to\features.json
magnetatlas serve --no-browser
```

OpenStreetMap används endast som baskarta och kräver internetanslutning. Ingen
adressökning eller annan AtlasFeature-data hämtas från OpenStreetMap.

## Kvalitetskontroller

```powershell
pytest
ruff check .
black --check .
```

## Dokumentation

- [Arkitektur](docs/architecture.md)
- [Datamodell](docs/data-model.md)
- [Datakällor](docs/data-sources.md)
- [Utveckling](docs/development.md)
- [Roadmap](docs/roadmap.md)
- [UI-riktlinjer](docs/UI_GUIDELINES.md)

## Projektstatus och licens

Projektet är pre-alpha. En uttrycklig open source-licens måste väljas innan den
första publika releasen; tills dess är ingen återanvändningslicens beviljad.
