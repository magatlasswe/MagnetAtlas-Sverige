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

## Multi-source-grund

Sprint 3.1 skiljer mellan tre domänidentiteter:

- `SourceDefinition` beskriver en stabil officiell datakälla eller dataprodukt.
- `DatasetInstance` beskriver en självständigt importerad lokal instans.
- `DatasetScope` beskriver instansens geografiska urval: country, county,
  municipality eller WGS84-bbox.

En datasetidentitet är deterministisk och kombinerar källa med normaliserat
scope, exempelvis `raa-kmr:municipality:vaxholm`. Metadata lagrar både denna
identitet och källans visningsnamn, scopevärden, schemaversion, synkmarkör och
aktiv status. Repositoryt kan bevara flera instanser och markerar högst den
senast atomiskt aktiverade instansen per källa som aktiv. Befintliga cache- och
kartflöden fortsätter läsa den aktiva RAÄ-instansen; lagerkombination införs
först i Sprint 3.2.

Äldre `raa-kmr`-metadata migreras additivt till country-scope `sweden` och
behåller både featuredata och aktiv status. Nya importer får alltid sin fulla
scopebaserade identitet.

`AtlasFeature` är den gemensamma domänmodellen för geografiska objekt. Modellen
består av egna värdeobjekt för identitet, geometri, tid, proveniens, licens och
osäkerhet och har inga beroenden på collectors, SQLAlchemy eller GIS-motorer.
Den äldre `ArchiveRecord`-modellen finns kvar under en additiv övergång och kan
konverteras till `AtlasFeature` vid domängränsen.

Collector-descriptorn anger nu både output generation och capabilities.
Gemensamma capabilities omfattar base import, incremental changes, remote
search samt country-, county-, municipality- och bbox-scope. Riksarkivets
befintliga sökväg är uttryckligen märkt `archive_record`; nya geografiska
integrationer ska producera `atlas_feature`. Den befintliga konverteringen är
utfasningsvägen och ingen ny kärnfunktion ska byggas enbart för ArchiveRecord.

SQLite är Sprint 1-lagring. Repository-gränsen gör en framtida PostGIS-adapter
möjlig utan att ändra användningsfallen.

Sprint 2.9 behåller det fullständiga `AtlasFeature`-dokumentet som källneutral
lagringsrepresentation men projicerar ofta efterfrågade värden till separata
SQLite-kolumner: feature-ID, source, source-ID, feature-typ, normaliserad söktext
och geometrins WGS84-bounding-box. Projektionerna är ett databasindex och aldrig
en alternativ domänmodell.

Geografiska projektioner synkroniseras till en virtuell SQLite RTree-tabell via
triggers. Viewportfrågan börjar uttryckligen i RTree och slår därefter upp endast
matchande dokument via rowid och dataset-ID. Textkandidater hämtas genom FTS5;
source, source-ID och feature-typ har sammansatta B-tree-index med dataset-ID.
Stavfelstolerans bevaras genom en minnesbegränsad linjär kompatibilitetsväg när
FTS saknar direkta kandidater; exakt och prefixbaserad sökning använder indexet.

En additiv, versionsmärkt migration backfillar befintliga JSON-dokument i
batchar. Nya basimporter skriver alla projektioner tillsammans med dokumentet,
och inkrementella förändringar använder ett batchat SQLite-upsert. RTree och FTS
uppdateras i samma transaktionsgräns som feature-raden. `ANALYZE` körs efter
atomisk stagingaktivering så att query planner har aktuell statistik.

## Lokalt webbgränssnitt

Sprint 2.3 lägger till ett läsande webbgränssnitt under `interfaces.web`.
`FeatureCatalog` i applikationslagret ansvarar för lokal sökning, featureval och
deterministiska navigationspunkter. En infrastrukturadapter läser versionerad
JSON och skapar validerade `AtlasFeature`-objekt. HTTP-servern serialiserar dem
till GeoJSON utan att exponera källans `raw_data`.

Webbservern använder fasta GET- och HEAD-routes samt avgränsade POST-routes för
processlokal lagersynlighet. Den binder som standard till loopback-adressen och
serverar paketerade HTML-, CSS- och JavaScript-resurser.
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

När platsbehörighet redan är beviljad startar klienten GPS-bevakningen utan en ny
dialog och sorterar lokalt de fem närmaste objekten i det synliga kartutsnittet
med ett enkelt WGS84-fågelvägsavstånd. Positionen lämnar aldrig webbläsaren.
Popupen innehåller bara snabb identifiering och åtgärder; full proveniens,
licens, confidence och koordinater hämtas först när objektet väljs och visas i
sidopanelen.

Sprint 2.8 inför en källneutral `FeatureQuerySource` för webbens läsmodell.
SQLite-adaptern itererar lagrade dokument och materialiserar endast matchande
features upp till en fast svarsgräns. Den bygger aldrig en global
`FeatureCatalog`. Den första implementationen gör en minnesbegränsad skanning;
bbox- och sökindex tillkommer i Sprint 2.9 utan att HTTP-kontraktet ändras.

Webb-API:t delar upp läsningen i tre ansvar:

- `/api/dataset` returnerar endast antal, importtid, källa och datasetstatus.
- `/api/features?bbox=west,south,east,north` returnerar ett kompakt och hårt
  begränsat GeoJSON-svar för aktuell viewport.
- `/api/features/<feature-id>` returnerar fullständig information för ett valt
  objekt.

Klienten debounce:ar `moveend`, avbryter inaktuella HTTP-anrop och ersätter
MapLibre-källan med det senaste synliga utsnittet. MapLibre fortsätter ansvara
för klustring i klienten; servern returnerar aldrig serverkluster.

Webbklienten skiljer mellan tom lokal data, resultatlösa filter, API-fel,
baskartefel och nekad eller otillgänglig GPS. Meddelandena är svenska och
användarinriktade. CLI-kompositionsroten översätter på motsvarande sätt förväntade
käll-, fil-, validerings- och databasfel utan att visa tekniska undantag; full
felinformation finns endast i debugloggning.

## Layer Engine

Sprint 3.2 delar lagerarkitekturen i tre källneutrala delar:

- `LayerDefinition` beskriver stabil identitet, presentation, kategori,
  kompatibla källor, standardsynlighet och tillgänglighetsflaggor.
- `LayerRegistry` registrerar definitioner och äger processlokal synlighet.
- `LayerService` använder importerade `DatasetInstance` för att avgöra stöd,
  läsa aktiva lager och filtrera `AtlasFeature` med injicerade predikat.

`LayerFeatureQuerySource` dekorerar webbens befintliga bounded-query-gräns. Det
gör att viewport och sökresultat följer aktiva lager utan att Layer Engine
behöver känna till en konkret databas eller Collector. Lagerstöd avgörs genom
datasetinstansens `SourceDefinition`, inte genom leverantörsspecifika featurefält.

Produktens elva lagerdefinitioner sätts samman under `interfaces.web`. Därmed
innehåller domän- och applikationsmotorn inga myndighetsnamn eller särskilda
regler för en datakälla. Endast kulturhistoriska lämningar är tillgängligt i
Sprint 3.2; resterande definitioner exponeras inaktiverade som kommande lager.

Lager-API:t består av `GET /api/layers`, `GET /api/layers/{id}`,
`POST /api/layers/{id}/enable` och `POST /api/layers/{id}/disable`.
POST-operationerna ändrar endast registryt i den lokala serverprocessen och
skriver inte till dataset, repository eller användarens lokala lagring.

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

GeoPackage-adaptern förenar geometritabeller, fullständiga vyer och
kvalitetslagret via RAÄ:s `uuid`/`lamning_uuid`. Dubbletter av samma WKB-geometri
tas bort innan mappning. Kvalitetsuppgifter bevaras som confidence-underlag men
kvalitetslagrets hjälpgeometri publiceras inte som ett eget historiskt objekt.

Collectorn strömmar normaliserade objekt i begränsade batchar. `SyncService`
skriver varje batch genom en källneutral importsessionsgräns till ett isolerat
stagingdataset i SQLite; varken Collector, applikationstjänst eller repository
behöver materialisera hela uttaget i arbetsminnet. När hela uttaget har lästs
och validerats aktiveras stagingdatasetet och synkmetadata atomärt. En avbruten
grundimport tar bort stagingraderna och lämnar den tidigare lokala sanningskällan
oförändrad.

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

Repositoryt projicerar käll-ID per feature och erbjuder indexerad lookup och
batchborttagning inom en uttrycklig datasetinstans. `SyncService` skickar den
begränsade mängden utgångna source-ID:n direkt till samma transaktion som
upserts och synkmetadata. Inkrementell synk använder därför aldrig
`list_features` och dess databasarbete växer med förändringsmängden i stället
för hela datasetets storlek.

Generella webbmodeller exponerar källans stabila proveniens-ID och placerar
adapterfält under `source_properties`, grupperade med källans namespace.
Frontend använder aldrig RAÄ-specifika fältnamn för identifiering.

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

Sprint 3.5b verifierar samma gräns med en filbaserad STAC-provider.
`LantmaterietClient` äger HTTP, autentisering och atomisk ZIP-hämtning;
`LantmaterietCollector` äger säker extraktion och strömmande GeoPackage-läsning;
mappern normaliserar EPSG:3006-punkter till `AtlasFeature`; importern delegerar
till oförändrad `SyncService`. Lagerkomponenterna, `DatasetInstance` och
frontend är oförändrade.

## Unified Map Layer Framework

Sprint 3.6 lägger `LayerCompositionService` ovanpå den oförändrade Layer Engine.
Ansvarsgränsen är:

- **Layer Engine** känner till `LayerDefinition`, aktiv status och vilka
  `DatasetInstance` som stöder lagret. Den filtrerar `AtlasFeature` men innehåller
  ingen renderingslogik.
- **LayerCompositionService** kombinerar bounded frågor från flera aktiva
  datasetinstanser och tillför källneutral metadata för synlighet, opacitet,
  z-index, legend, attribution, licens, zoom och render mode.
- **Renderer** är en nuvarande eller framtida gränssnittsadapter som översätter
  composition-metadata till MapLibre-lager. Raster-, tile-, heatmap- och annan
  ny rendering implementeras inte i Sprint 3.6.

```text
RAÄ query ──────────┐
SGU query ──────────┼── ComposedFeatureQuerySource ── gemensam GeoJSON-karta
Lantmäteriet query ─┘                 │
                                      │ filtrering/synlighet
DatasetInstance ── Layer Engine ──────┤
                                      │
Render metadata ─ LayerCompositionService ── lager-API ── Renderer
                                      │
                         VectorLayer / RasterLayer
```

`VectorLayer` beskriver AtlasFeature-baserade lager. `RasterLayer` använder
samma metadataavtal men förutsätter inte AtlasFeature. Historiska kartor är den
första rasterfamiljen och har status disabled samt `render_mode=future`.

## Evidence Engine

Evidence Engine ligger ovanpå `AtlasFeature`, `DatasetInstance` och det
sammansatta bounded query-flödet. Motorn ändrar aldrig källfeatures. Ett
`EvidenceRule` har stabilt regel-ID, explicit version och dokumenterad
beskrivning; registret kör regler i deterministiskt sorterad ordning.

```text
Providers → AtlasFeature
                ↓
        versionerade EvidenceRule
                ↓
             Evidence
                ↓
         EvidenceCollection
                ↓
          EvidenceReport
                ↓
          Future Search
                ↓
         Future Ranking
                ↓
            Future AI
```

`Evidence` bevarar exakt `feature_id`, geometri, provider, datasetinstans,
snapshot, confidence, proveniens, licens, source URL, explanation och det
versionsmärkta regel-ID som skapade objektet. ID:t är en deterministisk SHA-256
över regelversion, feature, dataset, snapshot och evidenstyp. `created_at` kommer
från en injicerbar klocka så tester och rapportkörningar är reproducerbara.

`EvidenceReport` innehåller område, bbox, skapad tid, använda dataset,
evidensantal, statisk sammanfattning, explicit icke-aggregerad confidence,
proveniens och en `EvidenceCollection`. Motorn kombinerar aldrig confidence
probabilistiskt och genererar ingen fri text.

AI-kontraktet är en enkelriktad säkerhetsgräns: en framtida AI-adapter får endast
läsa `EvidenceReport`. Den får inte läsa råa `AtlasFeature`, providerobjekt,
rådata eller datasetfiler. Sprint 3.7 innehåller ingen AI-, ranking- eller
maskininlärningsimplementation.

## Evidence Rules Framework

Sprint 3.8 lägger ett separat regelbibliotek ovanpå den oförändrade Evidence
Engine. `RuleMetadata` är det publika kontraktet och innehåller stabilt ID,
semantisk `RuleVersion`, kategori, käll- och datasetstöd, evidenstyp, status och
skapad tid. `EvidenceMatcher` är ett rent predikat som endast får läsa
`AtlasFeature` och ett skrivskyddat `EvidenceContext`. Matchers får aldrig ändra
features, skapa ranking eller generera AI-text.

`EvidenceRulesLibrary` skyddar mot duplicerade `(rule_id, version)` och listar
regler stabilt. Uppslag på ID väljer senaste installerade semantiska version.
`EvidenceRuleSet` grupperar exakta regelversioner utan vikter eller poäng. API:t
serialiserar enbart metadata; matcherimplementationer lämnar aldrig
applikationslagret.

```text
AtlasFeature
    ↓
Evidence
    ↓
Evidence Rules (metadata + rena matchers + oviktade rulesets)
    ↓
EvidenceReport
    ↓
Future Analysis
    ↓
Future Ranking
    ↓
Future AI (får endast läsa EvidenceReport)
```

De initiala reglerna för bro, väg, hamn, jordart, ortnamn och historisk karta
identifierar endast uttryckliga normaliserade egenskaper eller deklarerat
dataset. De drar inga historiska slutsatser. Regeln för historiska kartor är
förberedd men inaktiverad tills ett verifierbart dataset finns.

## Långsiktiga arkitekturprinciper

Följande principer styr framtida utbyggnad men innebär ingen produktfunktion i
den nuvarande versionen:

1. Alla framtida datakällor implementeras som lager ovanpå `AtlasFeature`.
   Leverantörsspecifika modeller, protokoll och geometrier stannar i respektive
   Collector och adapter.
2. Kartan arbetar alltid viewport-baserat och hämtar endast det aktuella
   kartutsnittet. Klustring är ett presentationsansvar och sker i klienten, inte
   på servern.
3. Offline-användning är ett långsiktigt designmål. Importerade dataset och
   deras metadata ska kunna användas utan internet; externa baskartor kan ha
   separata tillgänglighetsbegränsningar.
4. Framtida användarprofiler, exempelvis Magnetfiske, Metalldetektering,
   Släktforskning, Arkeologi och Utflykt, ska endast aktivera lager och filter.
   De får inte skapa alternativa domänmodeller eller ändra lagrad källdata.
5. Framtida Collectors läggs till som plugins genom publicerade kontrakt. En ny
   Collector får inte kräva ändringar i kärnans domän- eller
   applikationsarkitektur.
