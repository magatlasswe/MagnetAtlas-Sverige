# MagnetAtlas Sverige

**Status:** Public alpha (`v1.4.0-alpha`)

**Python:** 3.13 eller 3.14

MagnetAtlas Sverige är en lokal, användarvänlig historisk kartapplikation som
samlar och visar spårbar geografisk information från öppna datakällor.

## Projektbeskrivning

MagnetAtlas Sverige är en lokal historisk kartapplikation som samlar,
normaliserar och visar spårbar geografisk information från öppna datakällor.
Projektet är en modulär Python-applikation med CLI, SQLite, exportfunktioner och
ett mobilanpassat webbgränssnitt.

Projektet befinner sig i alpha. Demodatan är tydligt märkt. Officiella data kan
importeras lokalt från RAÄ Kulturmiljöregistret, SGU Jordarter och Lantmäteriets
Ortnamn Nedladdning.

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
- Källneutrala identiteter för datakällor, importerade dataset och geografiska
  urval.
- Generell Layer Engine med datasetmedveten filtrering, lagerregister och en
  webbpanel där kulturhistoriska lämningar kan visas eller döljas.
- Officiell RAÄ-basimport, inkrementell synk och lokal SQLite-cache.
- Generell SGU-provider med Jordarter som första dataset via dokumenterad OGC
  API Features och CC0.
- Generell Lantmäteriet-provider med reproducerbara Ortnamn-snapshotar via den
  dokumenterade STAC-vektorkatalogen och GeoPackage.
- Gemensamt lagerkompositionsramverk för vektor- och rastermetadata, ritordning,
  opacitet, synlighet, legend och attribution ovanpå Layer Engine.
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
magnetatlas import sgu --bbox 18.2,59.35,18.5,59.5
magnetatlas import lantmateriet --dataset ortnamn --country sweden
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

Varje import sparas som en egen datasetinstans. Identiteten byggs av källa och
scope, exempelvis `raa-kmr:municipality:vaxholm`. Country, county, municipality
och bbox har separata identiteter. Den senast lyckade instansen för en källa är
aktiv i befintliga cache- och kartflöden; andra instanser förblir isolerade och
kan upptäckas genom repositorygränsen och används av Layer Engine.

Webbens lagerpanel läser `GET /api/layers`. Ett tillgängligt lager kan växlas
med `POST /api/layers/{id}/enable` och `POST /api/layers/{id}/disable`.
Synligheten gäller den körande lokala serverprocessen och ändrar inte importerad
data. Tio planerade lager visas som **Kommer senare**.

Lager-API:t levererar även `provider`, `dataset`, `layer_type`, `geometry_type`,
`render_mode`, `opacity`, `z_index`, legend, attribution, licens och zoomintervall.
Panelen och framtida renderers använder endast dessa generella fält. Historiska
kartor är registrerat som det första rasterlagret men är inaktiverat och har
ännu ingen importer eller renderer.

Layer Engine avgör vilka produktlager som finns, är aktiva och stöds av
installerade `DatasetInstance`. `LayerCompositionService` kombinerar aktiva
vektordataset till samma bounded kartfråga och dekorerar lagren med
renderingsmetadata. En framtida renderer omsätter metadata till MapLibre-källor
och lager; renderingslogik ingår inte i Layer Engine.

SGU Jordarter importeras från den officiella samlingen `grundlager`:

```powershell
magnetatlas import sgu --country sweden
magnetatlas import sgu --bbox 18.2,59.35,18.5,59.5
magnetatlas import sgu --county stockholm --bbox 17.7,58.7,19.4,60.3
magnetatlas import sgu --municipality vaxholm --bbox 18.2,59.35,18.5,59.5
```

Lantmäteriets Ortnamn importeras från en versionsidentifierad, rikstäckande
STAC-asset. Bbox filtreras lokalt under den strömmande normaliseringen:

```powershell
magnetatlas import lantmateriet --dataset ortnamn --country sweden
magnetatlas import lantmateriet --dataset ortnamn --bbox 18.2,59.35,18.5,59.5
```

OAuth2 konfigureras med `MAGNETATLAS_LANTMATERIET_CLIENT_ID`,
`MAGNETATLAS_LANTMATERIET_CLIENT_SECRET` och
`MAGNETATLAS_LANTMATERIET_TOKEN_URL`. Alternativ Basic-auth använder
`MAGNETATLAS_LANTMATERIET_USERNAME` och `MAGNETATLAS_LANTMATERIET_PASSWORD`.
Hemligheter lagras eller loggas inte.

SGU:s dokumenterade OGC-gränssnitt filtrerar geografiskt med bbox. Därför måste
`--county` och `--municipality` kombineras med `--bbox`; namnet bevaras som
datasetets överordnade scope. Varje import får en egen identitet, exempelvis
`sgu-jordarter:country:sweden`. Rikstäckande `grundlager` innehöll 2 956 837
objekt vid valideringen 2026-08-07 och är därför en stor lokal import.

Om ingen RAÄ-cache finns visar `magnetatlas serve` tydligt märkt syntetisk
demodata, så att gränssnittet går att prova utan en nätverksimport.
När minst ett riktigt RAÄ-objekt finns används enbart den lokala RAÄ-cachen;
kartan visar då antal objekt, senaste import, datakälla och status **Officiell**.

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
