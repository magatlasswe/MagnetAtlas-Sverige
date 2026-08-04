# AGENTS.md

## Projektets mål

MagnetAtlas-Sverige är ett långsiktigt open source-projekt för att bygga Sveriges
bästa historiska GIS-program för magnetfiske. Projektet ska samla in, normalisera,
analysera och presentera geografisk och historisk information från bland annat
Riksarkivet, OpenStreetMap, Lantmäteriet, Riksantikvarieämbetet, SGU och SMHI.

Programmet ska på sikt stödja historiska broar, färjelägen, kvarnar, slussar,
hamnar, gamla vägar och historiska kartor samt interaktiv karta, GPX-, GeoJSON-
och CSV-export, transparent platsrankning, PDF-atlas och desktopdistribution.

Projektet ska respektera källornas licenser, användningsvillkor, proveniens och
osäkerhet. Det får inte uppmuntra till olagligt, farligt eller kulturhistoriskt
skadligt magnetfiske.

Projektets officiella produktmanifest finns i
[`docs/product_principles.md`](docs/product_principles.md) och ska följas vid
produkt-, UX- och prioriteringsbeslut.

## Arkitektur

Projektet är en modulär monolit med principer från hexagonal arkitektur:

- `domain` innehåller myndighetsoberoende modeller, typer och gränssnitt.
- `application` innehåller användningsfall och orkestrering.
- `infrastructure` innehåller databas-, datakälls- och exportadaptrar.
- `interfaces` innehåller CLI och framtida API- eller desktopgränssnitt.
- `config` innehåller konfiguration och loggning.
- `plugins` är utbyggnadspunkten för valfria framtida tillägg.

Domän- och applikationslager får inte bero på Typer, Requests eller konkreta
SQLAlchemy-modeller. Externa datakällor ska isoleras i egna adaptrar och mappas
till projektets gemensamma domänmodell. SQLite används lokalt i första fasen;
databasgränser ska hållas tillräckligt tydliga för en framtida PostGIS-adapter.

`pyproject.toml` är den primära och kanoniska källan för projektmetadata,
beroenden, kommandon och verktygskonfiguration. `requirements.txt` är endast en
kompatibilitetsfil och får inte introducera beroenden som saknas i
`pyproject.toml`.

## Kodstandard

- Målversion är Python 3.13.
- Ny produktionskod ska vara typannoterad.
- Använd SQLAlchemy 2.x-stil och `pathlib.Path` för filsystemsvägar.
- Nätverksanrop ska alltid ha explicit timeout och begriplig felhantering.
- Logga inte autentiseringsuppgifter, tokens eller känslig rådata.
- Ruff används för lintning och importordning; Black används för formatering.
- Publika moduler och icke-triviala publika funktioner ska ha korta docstrings.
- Domänlogik ska vara oberoende av terminalpresentation och infrastruktur.
- Undvik abstraktioner som inte löser ett aktuellt eller tydligt nära behov.
- Kommentarer ska förklara varför, inte återge vad koden redan visar.

## Arbetsflöde

1. Läs detta dokument och relevant dokumentation före en ändring.
2. Inspektera arbetsytan och bevara orelaterade lokala ändringar.
3. Beskriv större planerade förändringar innan de genomförs.
4. Gör små, sammanhängande ändringar inom rätt arkitekturlager.
5. Lägg till eller uppdatera tester för förändrat beteende.
6. Kör relevanta tester först och därefter hela kvalitetssviten när möjligt.
7. Kör `pytest`, `ruff check .` och `black --check .` före leverans.
8. Uppdatera README och dokumentation när användning eller arkitektur ändras.
9. Redovisa vad som ändrades, vad som verifierades och eventuella begränsningar.

API-integrationstester ska normalt använda mockade svar. Tester får inte vara
beroende av nätverk, externa myndighetstjänsters tillgänglighet eller beständig
lokal användardata.

## Instruktioner för framtida AI-agenter

- Börja med att läsa hela `AGENTS.md` och följ instruktioner i djupare
  `AGENTS.md`-filer om sådana senare tillkommer.
- Anta inte att arbetsytan är ren. Skriv inte över eller återställ användarens
  ändringar utan uttryckligt godkännande.
- Sök efter befintlig funktionalitet innan ny kod eller nya beroenden läggs till.
- Håll leverantörsspecifika fält och protokoll i respektive källadapter.
- Bevara käll-ID, källhänvisning, licens, hämtningstid och osäkerhet när data
  normaliseras.
- Använd inga verkliga API-anrop i enhetstester och lagra aldrig hemligheter i
  repositoryt.
- Nya plugins får bero på publicerade projektgränssnitt men kärnan får inte
  importera konkreta plugins.
- Ett AI-baserat poängsystem ska vara förklarbart, versionsmärkt och testbart.
  Börja med transparenta regler innan maskininlärning införs.
- Kontrollera officiell dokumentation och licensvillkor innan en extern datakälla
  implementeras eller ändras.
- Gör inte destruktiva migreringar, publiceringar eller externa skrivoperationer
  utan uttryckligt mandat.
- Om krav är oklara: välj en liten, reversibel lösning och dokumentera antagandet;
  fråga användaren när valet får betydande produkt- eller datakonsekvenser.
