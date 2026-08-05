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
aktiveras bara genom användarens centrera- eller följåtgärd och efter
webbläsarens behörighetsdialog. Klienten visar aktuell position och rapporterad
GPS-noggrannhet men skickar eller lagrar aldrig positionen. Kartklustring sker i
MapLibre, popupinnehåll skapas först vid val och `FeatureCatalog` förindexerar
söktext för att undvika upprepad normalisering vid interaktiv sökning.

Webbklienten skiljer mellan tom lokal data, resultatlösa filter, API-fel,
baskartefel och nekad eller otillgänglig GPS. Meddelandena är svenska och
användarinriktade. CLI-kompositionsroten översätter på motsvarande sätt förväntade
käll-, fil-, validerings- och databasfel utan att visa tekniska undantag; full
felinformation finns endast i debugloggning.

## RAÄ Collector och lokal synkronisering

Sprint 2.6 följer Riksantikvarieämbetets rekommenderade integrationsmodell.
RAÄ:s officiella GeoPackage är primär källa för grundladdningen. Det
dokumenterade REST-API:t används därefter endast för förändringar sedan den
senaste lyckade synkroniseringen.

```text
                SyncScheduler
                      │
                      ▼
RAÄ GeoPackage → Collector → Mapper
                          │
                          ▼
                     AtlasFeature
                          │
                          ▼
                     SyncService
                          │
                          ▼
                     Repository
                          │
                          ▼
                        SQLite
                          │
                          ▼
                       Web API
                          │
                          ▼
                      Frontend
```

SQLite är den lokala sanningskällan efter import. CLI och webb-API läser aldrig
direkt från RAÄ. Därmed påverkas inte användarupplevelsen av nätverksfel,
driftstopp eller svarstider hos källan, och samma lagrade data används av alla
lokala gränssnitt.

### Grundimport

Grundimporten använder ett officiellt nattligt GeoPackage från RAÄ:s
nedladdningstjänst. Ett läns- eller kommunuttag väljs när användaren har gjort en
sådan avgränsning; annars används det dokumenterade totaluttaget. Geografisk
bounding-box-filtrering sker lokalt mot officiellt hämtade data eftersom RAÄ:s
REST-API inte erbjuder ett dokumenterat bbox-filter.

Collectorn läser källformatet, använder sin källspecifika mapper och returnerar
endast validerade `AtlasFeature`. RAÄ-specifika attribut och geometrier hanteras
i adaptern och mappern. Saknad information lämnas tom och ingen confidence,
datering eller beskrivning konstrueras.

När hela uttaget har lästs skriver `SyncService` resultatet atomärt genom
repository-gränsen och sparar synkmetadata först efter en lyckad import. En
avbruten grundimport får inte göra ett ofullständigt dataset till aktiv lokal
sanningskälla.

### Inkrementell synkronisering

Efter grundimport använder `SyncService` RAÄ:s dokumenterade `/lamningar`-API
med intervallet efter den senast lyckade synkroniseringen. Tjänsten paginerar
hela förändringsmängden och behandlar RAÄ:s svar som ersättningsposter, inte som
fältvisa patchar.

Endast nya, uppdaterade eller utgångna käll-ID:n berörs. En ny eller uppdaterad
lämning mappas till en fullständig `AtlasFeature` och skrivs med upsert. En post
som RAÄ markerar som utgången tas bort eller inaktiveras enligt repositoryts
domänneutrala kontrakt. Synkmarkören flyttas först när hela intervallet har
slutförts och lagrats utan fel.

### Ansvarsfördelning

`SyncScheduler` schemalägger och triggar endast `SyncService`. Den innehåller
ingen nätverkskod, SQL, Collector-logik eller Mapper-logik. Schemaläggaren fattar
inte beslut om vilken sorts synkronisering som ska utföras och lagrar ingen
synkstatus.

`RAACollector` ansvarar för att hämta officiella källdata, använda `RAAMapper`
och returnera `AtlasFeature`. Den skriver aldrig till databasen, uppdaterar inte
cache och känner inte till `SyncService`, SQLite, webbservern, frontend eller
terminalpresentationen.

`RAAClient` äger all nätverkskommunikation, timeout, begränsad retry,
det dokumenterade transportkontraktet och begripliga transportfel. Den använder
endast dokumenterade RAÄ-adresser och parametrar.

`RAAMapper` översätter RAÄ:s källschema och SWEREF 99 TM-geometri till den
källoberoende domänmodellen och WGS84. Den innehåller ingen lagring,
synkorkestrering eller produktlogik.

`SyncService` är ett applikationsanvändningsfall och den enda komponent som
känner till grundimport, inkrementell synkronisering, synkmarkörer,
versionshantering och cachepolicy. Det väljer synkstrategi, orkestrerar Collector
och repository och ser till att bara ändrade objekt uppdateras. Det utför inga
nätverksanrop eller SQL-frågor direkt. Övriga komponenter tillhandahåller endast
mekanismer; de fattar inga beslut om synkflödet.

Repositoryt ansvarar för beständig lagring, upsert, borttagning/inaktivering,
sökning och beständig synkmetadata på uppdrag av applikationslagret. Kontraktet
är fullständigt domänneutralt och arbetar endast med `AtlasFeature` och generell
lagringsmetadata. Det känner aldrig till RAÄ, GeoPackage, REST eller Collectors.
Den konkreta SQLite-adaptern implementerar kontraktet och transaktionsgränserna.

Webb-API och CLI använder endast applikationstjänster ovanpå repositoryt.
Frontend känner enbart till MagnetAtlas serialiserade featureformat och kan
aldrig se RAÄ:s interna datamodell.

### Versions- och cachemetadata

På uppdrag av `SyncService` bevarar repositoryt minst dataset-/API-version,
källans publicerings- eller versionsvärde per objekt, tidpunkt för senaste
lyckade grundimport, senaste slutförda REST-intervall och lokal hämtningstid.
Endast `SyncService` tolkar metadata och använder den för att:

- undvika en ny grundhämtning medan cachen är giltig,
- återuppta från den senaste helt genomförda synkgränsen,
- hoppa över oförändrade objekt,
- visa cache-status utan att kontakta RAÄ,
- spåra varje lokalt objekt tillbaka till källa och källversion.

Vid `cache clear` identifierar `SyncService` den aktuella källans lokala features
och instruerar repositoryt genom dess generella kontrakt. `cache refresh`
initierar `SyncService`; det innebär grundimport när en giltig bas saknas och
annars inkrementell synkronisering.

Cache är uttryckligen den lokala SQLite-databasen tillsammans med dess
synkmetadata. Ingen separat cachemotor eller parallell cachelagring ska införas.

### Geometri

All intern geometri i MagnetAtlas lagras i WGS84 (EPSG:4326). Varje Collector
ansvarar, genom sin källadapter eller mapper, för nödvändig konvertering från
externa referenssystem. För RAÄ innebär det konvertering från SWEREF 99 TM
(EPSG:3006) innan ett `AtlasFeature` returneras.

Ingen annan komponent får utföra koordinatkonvertering. `SyncService`,
repositoryt, SQLite-adaptern, webb-API:t och frontend ska alltid kunna behandla
domängeometri som WGS84.

### Felhantering och atomisk aktivering

Den senast lyckade SQLite-databasen ska fortsätta vara lokal sanningskälla om
GeoPackage saknas, nätverket är nere, REST-anrop misslyckas eller en import
avbryts. Ett misslyckat import- eller synkförsök får aldrig ersätta ett
fungerande dataset med ett tomt eller partiellt dataset.

Grundimport byggs och valideras innan den aktiveras atomärt. Inkrementella
förändringar och tillhörande synkmarkör lagras i samma transaktionsgräns. Vid fel
återställs hela försöket, den tidigare synkmarkören behålls och CLI/webb fortsätter
läsa den senaste lyckade lokala versionen. Felet rapporteras tydligt utan att
göra RAÄ:s tillgänglighet till ett krav för normal läsning.

## Gemensamt ramverk för framtida Collectors

```text
                 Collector Framework
                         │
     ┌──────────┬─────────┬─────────┬──────────┬──────────┐
     │          │         │         │          │
    RAÄ        SGU   Lantmäteriet  SMHI   OpenStreetMap
     │          │         │         │          │
     └──────────┴─────────┴─────────┴──────────┘
                         │
                    AtlasFeature
                         │
                    Repository
                         │
                      SQLite
```

Alla framtida datakällor ska implementera samma publicerade Collector-kontrakt.
Varje adapter isolerar sin leverantörs protokoll, schema, licensmetadata och
koordinatsystem och returnerar endast `AtlasFeature`. Kärnan importerar aldrig
en konkret Collector, och repositoryt behöver inte ändras när en ny datakälla
läggs till.
