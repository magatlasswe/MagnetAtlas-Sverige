# MagnetAtlas Sverige

**Status:** Alpha

**Python:** 3.13 eller 3.14

MagnetAtlas Sverige är en lokal, användarvänlig historisk kartapplikation som
samlar och visar spårbar geografisk information från öppna datakällor.

## Projektbeskrivning

MagnetAtlas Sverige är en lokal historisk kartapplikation som samlar,
normaliserar och visar spårbar geografisk information från öppna datakällor.
Projektet är en modulär Python-applikation med CLI, SQLite, exportfunktioner och
ett mobilanpassat webbgränssnitt.

Projektet befinner sig i alpha. Den medföljande datamängden är demonstrationsdata
och ska inte tolkas som verifierade historiska platser eller fyndplatser.

## Vision

MagnetAtlas ska bli Sveriges mest användarvänliga historiska kartplattform.
Användare ska kunna upptäcka historiskt intressanta platser genom officiella
datakällor utan att behöva förstå GIS eller avancerad kartteknik. Historisk
korrekthet, tydlig proveniens och ansvarsfull användning går alltid före mängden
data.

## Funktioner

- Lokal, responsiv webbkarta med OpenStreetMap som baskarta.
- Visning av punkter, områden, linjer och polygoner.
- Klustring, sökning och filter för typ, tidsperiod och källa.
- Objektkort med källa, licens, osäkerhet och navigation.
- Valfri positionering, favoriter, historik samt ljust och mörkt tema.
- Collector Framework och en gemensam `AtlasFeature`-domänmodell.
- CLI, lokal SQLite-lagring och CSV-export.

## Installation

Krav: Python 3.13 eller 3.14.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

`pyproject.toml` är den kanoniska källan för projektets beroenden och
verktygskonfiguration.

## Quick Start

```powershell
magnetatlas --help
magnetatlas search "bro"
magnetatlas serve
```

`magnetatlas serve` startar applikationen på `http://localhost:8000/` och öppnar
standardwebbläsaren. Stoppa servern med Ctrl+C. Baskartan kräver
internetanslutning; AtlasFeature-datan läses lokalt.

## Screenshot

TODO: Lägg till en aktuell skärmdump av kartvyn.

## Project Structure

```text
src/
docs/
tests/
data/
output/
PROJECT.md
README.md
AGENTS.md
```

## Dokumentation

- [Projektstatus och roadmap](PROJECT.md)
- [Instruktioner för bidragsgivare och agenter](AGENTS.md)
- [Produktprinciper](docs/product_principles.md)
- [Arkitektur](docs/architecture.md)
- [Utvärdering av datakällor](docs/data-source-evaluation.md)

## Licensstatus

En uttrycklig open source-licens har ännu inte valts. Fram till dess är ingen
återanvändningslicens för repositoryts innehåll beviljad. Externa datakällor och
kartlager omfattas av sina respektive licenser och attribueringskrav.

## Kontakt

Frågor, felrapporter och förslag hanteras via repositoryts issue tracker.
