# MagnetAtlas Sverige

**Status:** Public alpha (`v0.6.0-alpha`)

**Python:** 3.13 eller 3.14

MagnetAtlas Sverige är en lokal, användarvänlig historisk kartapplikation som
samlar och visar spårbar geografisk information från öppna datakällor.

## Projektbeskrivning

MagnetAtlas Sverige är en lokal historisk kartapplikation som samlar,
normaliserar och visar spårbar geografisk information från öppna datakällor.
Projektet är en modulär Python-applikation med CLI, SQLite, exportfunktioner och
ett mobilanpassat webbgränssnitt.

Projektet befinner sig i alpha. Demodatan är tydligt märkt, och den första
officiella datakällan kan importeras lokalt från RAÄ Kulturmiljöregistret.

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
- Valfri GPS-positionering med noggrannhet, centrering och följläge.
- Lokal lista över närmaste historiska objekt när GPS används.
- Favoriter, historik samt ljust och mörkt tema.
- Collector Framework och en gemensam `AtlasFeature`-domänmodell.
- Officiell RAÄ-basimport, inkrementell synk och lokal SQLite-cache.
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
magnetatlas import raa --county ostergotland
magnetatlas cache status
magnetatlas serve
```

För en första lokal provkörning:

1. Importera ett begränsat länsuttag, exempelvis
   `magnetatlas import raa --county ostergotland`, eller ett kommunuttag som
   `magnetatlas import raa --municipality vaxholm`.
2. Kontrollera resultatet med `magnetatlas cache status`.
3. Starta kartan med `magnetatlas serve`.
4. Sök eller filtrera platser, öppna ett objekt och läs källinformationen.
5. Välj **Centrera på mig** om du vill ge webbläsaren tillgång till din position.

En rikstäckande import startas uttryckligen med
`magnetatlas import raa --country sweden`. Den hämtar RAÄ:s totaluttag, kräver
minst 12 GiB ledigt i arbetskatalogen och kan ta lång tid. Börja normalt med ett
län eller en kommun. Endast ett av `--country`, `--county` och `--municipality`
får anges per import.

Om ingen RAÄ-cache finns visar `magnetatlas serve` tydligt märkt syntetisk
demodata, så att gränssnittet går att prova utan en nätverksimport.
När minst ett riktigt RAÄ-objekt finns används enbart den lokala RAÄ-cachen;
kartan visar då antal objekt, senaste import, datakälla och status **RAÄ**.

`magnetatlas serve` startar applikationen på `http://localhost:8000/` och öppnar
standardwebbläsaren. Stoppa servern med Ctrl+C. Baskartan kräver
internetanslutning; AtlasFeature-datan läses lokalt. Vid nätverks-, timeout-,
data- eller cachefel visas ett kort svenskt felmeddelande utan teknisk traceback.

GPS aktiveras först när användaren väljer **Centrera på mig** eller slår på
**Följ mig** och godkänner webbläsarens platsdialog. Positionen och den visade
noggrannheten stannar i webbläsaren och lagras inte av MagnetAtlas. Om
platsåtkomst redan är godkänd startar kartan vid användarens position.

RAÄ-importen hämtar ett officiellt GeoPackage. Därefter används det dokumenterade
REST-API:t enbart för förändringar. `magnetatlas serve` läser aldrig direkt från
RAÄ utan visar den senast lyckade lokala SQLite-versionen.

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
- [Roadmap](docs/roadmap.md)
- [Utvärdering av datakällor](docs/data-source-evaluation.md)

## Development Notes

Se [kända begränsningar i byggmiljön](docs/known-environment-limitations.md) om
verifiering i isolerade miljöer utan Setuptools eller åtkomst till PyPI.

## Licensstatus

En uttrycklig open source-licens har ännu inte valts. Fram till dess är ingen
återanvändningslicens för repositoryts innehåll beviljad. Externa datakällor och
kartlager omfattas av sina respektive licenser och attribueringskrav.

## Kontakt

Frågor, felrapporter och förslag hanteras via repositoryts issue tracker.
