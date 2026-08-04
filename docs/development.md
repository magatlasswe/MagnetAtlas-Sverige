# Utveckling

Installera projektet med `python -m pip install -e ".[dev]"`. Kör sedan `pytest`,
`ruff check .` och `black --check .` före en ändring lämnas vidare.

Tester ska använda temporära databaser och mockad HTTP-trafik. Läs även
`AGENTS.md` i projektroten innan du bidrar.

## Lokal webbutveckling

Starta webbgränssnittet med:

```powershell
magnetatlas serve
```

Använd `--no-browser` vid automatisering och `--features` för att läsa en lokal
AtlasFeature-fil. Server- och API-tester använder en temporär loopback-port.
Tester får inte hämta MapLibre, OpenStreetMap-tiles eller andra nätresurser.

Statiska resurser ligger i `src/magnetatlas/interfaces/web/static/`. Ändringar i
HTML ska behålla semantiska element och tangentbordsstöd. Featuretext ska sättas
med säkra DOM-operationer, inte tolkas som HTML. Se även
[`UI_GUIDELINES.md`](UI_GUIDELINES.md).

Sökalgoritmens stavfelstolerans och filter testas i applikationslagret och via
det lokala API:t. Klustring, geolokalisering, skala, kompass, helskärm och lokal
lagring verifieras även som del av webbgränssnittets kontrakt. Om Node.js finns
kan JavaScript-syntax kontrolleras separat med:

```powershell
node --check src/magnetatlas/interfaces/web/static/app.js
```
