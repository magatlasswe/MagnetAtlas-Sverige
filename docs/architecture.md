# Arkitektur

MagnetAtlas-Sverige är en modulär monolit med hexagonala gränser. Domänen är
oberoende av externa tjänster. Applikationslagret orkestrerar användningsfall,
medan infrastrukturen implementerar databas-, export- och källadaptrar. CLI:t är
ett gränssnitt ovanpå applikationslagret.

Datakällor implementerar det källoberoende `Collector`-protokollet och annonserar
stöd genom capabilities. `CollectorRegistry` kan ta emot collectors explicit vid
komposition eller upptäcka plugin-fabriker genom Python entry points i gruppen
`magnetatlas.collectors`. Domän- och applikationslagren importerar inte konkreta
källadaptrar. CLI:t är kompositionsrot och kopplar konfiguration till vald plugin.

En collector ansvarar för källprotokoll, defensiv parsning och översättning till
domänmodeller. Applikationslagret ansvarar för validering, orkestrering och
lagring; källadaptrar innehåller inte rankning eller annan affärslogik.

`AtlasFeature` är den gemensamma domänmodellen för geografiska objekt. Modellen
består av egna värdeobjekt för identitet, geometri, tid, proveniens, licens och
osäkerhet och har inga beroenden på collectors, SQLAlchemy eller GIS-motorer.
Den äldre `ArchiveRecord`-modellen finns kvar under en additiv övergång och kan
konverteras till `AtlasFeature` vid domängränsen.

SQLite är Sprint 1-lagring. Repository-gränsen gör en framtida PostGIS-adapter
möjlig utan att ändra användningsfallen.

## Lokalt webbgränssnitt

Sprint 2.3 lägger till ett läsande webbgränssnitt under `interfaces.web`.
`FeatureCatalog` i applikationslagret ansvarar för lokal sökning, featureval och
deterministiska navigationspunkter. En infrastrukturadapter läser versionerad
JSON och skapar validerade `AtlasFeature`-objekt. HTTP-servern serialiserar dem
till GeoJSON utan att exponera källans `raw_data`.

Webbservern använder endast fasta GET- och HEAD-routes, binder som standard till
loopback-adressen och serverar paketerade HTML-, CSS- och JavaScript-resurser.
Klienten använder MapLibre GL JS för presentation och OpenStreetMaps rastertiles
som enda baskarta. Domän- och applikationslagren känner inte till HTTP, JSON,
MapLibre eller webbläsarens DOM.

Det befintliga SQLite-schemat lagrar fortsatt `ArchiveRecord`. Det lokala
AtlasFeature-datasetet är en separat filgräns; Sprint 2.3 gör ingen
databasmigrering.

Sprint 2.4 utökar samma gränser utan nya datakällor. `FeatureCatalog` utför
stavfelstolerant boolesk matchning och explicita typ-, tids- och källfilter med
bibehållen källordning; den beräknar ingen relevanspoäng och rankar inte objekt.
Det lokala `/api/search` returnerar en filtrerad GeoJSON-samling.

Klienten ansvarar för MapLibre-klustring, kartkontroller och användarens privata
UI-tillstånd. Favoriter, senast besökta FeatureId:n och temaval lagras i
webbläsarens `localStorage` och skickas inte till servern. Geolokalisering
aktiveras bara av användaren genom MapLibre-kontrollen och efter webbläsarens
behörighetsdialog; positionen lagras inte av MagnetAtlas.
