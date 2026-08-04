# Utvärdering av officiella datakällor

Status: beslutsunderlag för Sprint 2.5  
Senast verifierat: 2026-08-04

## Syfte och avgränsning

Detta dokument utvärderar officiella API:er och öppna datamängder som kan bli
framtida Collectors i MagnetAtlas. Ingen integration har implementerats. Bedömningen
gäller dokumenterade gränssnitt och publicerade villkor; ett nätverksanrop som råkar
användas av en myndighets webbgränssnitt räknas inte som ett offentligt API.

Riksantikvarieämbetet (RAÄ), Fornsök och Kringla redovisas separat eftersom de har
olika roller, men de är inte tre oberoende datakällor. Fornsök visar data ur
Kulturmiljöregistret (KMR), medan Kringla använder K-samsök. RAÄ:s öppna dataportal
och K-samsök är de dokumenterade maskinella ingångarna.

Bedömningen prioriterar:

1. relevans för historiska platser,
2. dokumenterad och stabil maskinåtkomst,
3. spårbar metadata och användbar geometri,
4. tydliga återanvändningsvillkor,
5. enkel och förlustfri mappning till `AtlasFeature`.

## Sammanfattning

| Placering | Källa | Maskinåtkomst | Nyckel | Huvudlicens | Passning till `AtlasFeature` |
|---:|---|---|---|---|---|
| 1 | Fornsök/Kulturmiljöregistret | Öppna geodata, nedladdning och karttjänster | Nej för läsning | Fri användning; källa bör anges | Mycket hög |
| 2 | RAÄ K-samsök | Dokumenterat sök-API | Nej | CC0 för metadata | Mycket hög |
| 3 | OpenStreetMap | Overpass API och datautdrag | Nej för normala läsfrågor | ODbL 1.0 | Hög |
| 4 | SGU | Dokumenterade OGC API Features och nedladdning | Nej | CC0 | Medel |
| 5 | SMHI | Flera dokumenterade REST-API:er | Nej | CC BY 4.0 SE | Låg–medel |
| 6 | Kringla | Ingen separat dokumenterad data-API; använder K-samsök | Ej tillämpligt | K-samsöks villkor per objekt/media | Låg som egen Collector |
| 7 | Lantmäteriets Historiska kartor | Publik söktjänst, inget publicerat metadata-API verifierat | Ej tillämpligt | Varierar med produkt/arkiv | Hög ämnesrelevans, låg integrationsmognad |

Placeringen väger genomförbarhet och rättssäker återanvändning lika tungt som
innehållsrelevans. Därför hamnar Lantmäteriets historiska kartor sist trots att
materialet i sig är mycket relevant.

## 1. Fornsök och Kulturmiljöregistret

### Åtkomst

- **Dokumenterat API:** Inte som ett separat allmänt REST-API för Fornsöks
  webbgränssnitt. RAÄ publicerar i stället KMR som öppna geodata via sin öppna
  dataportal, med nedladdningsbara datamängder och karttjänster.
- **Offentligt:** Ja, läsning och nedladdning av de publicerade datamängderna är
  offentlig. Fornsök är också öppet för alla. Skrivning i Fornreg kräver däremot
  behörighet och är inte relevant för en Collector.
- **API-nyckel:** Ingen nyckel har dokumenterats för den öppna läsåtkomsten.
- **Licens:** RAÄ anger att nedladdningsbara KMR-dataset och WMS-tjänster är fria
  att använda och ber användaren ange RAÄ/Kulturmiljöregistret som källa. Länkade
  bilder och rapporter har egna rättighetsmärkningar och får inte ärva datasetets
  villkor automatiskt.

Källor: [Fornsök – frågor och svar](https://www.raa.se/hitta-information/fornsok/fragor-och-svar-om-fornsok/),
[RAÄ:s öppna data](https://www.raa.se/hitta-information/oppna-data/) och
[Fornsök – sökhjälp](https://www.raa.se/hitta-information/fornsok/hjalp/).

### Innehåll och begränsningar

- **Datatyper:** registrerade fornlämningar, övriga kulturhistoriska lämningar,
  antikvarisk bedömning, status, lämningstyp, beskrivningar, administrativa
  områden och arkeologiska uppdrag.
- **Geometri:** geografiska lämningar och uppdrag; punkt-, linje- och
  ytgeometrier förekommer. Koordinatsystem och exakt schema ska låsas mot den
  valda dataproduktens metadata när en Collector planeras.
- **Metadata:** stabil KMR-identitet, lämningstyp, beskrivning, status,
  geografiska uppgifter, registrerings-/ändringsuppgifter och länkar till
  relaterade dokument där sådana finns.
- **Begränsningar:** registret innehåller kända och registrerade lämningar, inte
  alla lämningar som existerar. Lägesosäkerhet och informationskvalitet varierar.
  Objektens rättsliga status och känslighet måste visas korrekt. MagnetAtlas får
  aldrig omvandla närhet till en fornlämning till en rekommendation att
  magnetfiska där.

### JSON-exempel

RAÄ publicerar inte ett separat, dokumenterat Fornsök-JSON-kontrakt som bör
byggas mot. Därför visas inget konstruerat API-svar här. En framtida Collector
ska utgå från den valda öppna dataproduktens officiella schema, inte från
Fornsöks interna webbanrop.

### Passning till `AtlasFeature`

**Mycket hög.** KMR-identiteten passar `FeatureId`/käll-ID, lämningstyp och
beskrivning passar objektets kärnmetadata och geometrierna passar `Point`,
`LineString` och `Polygon`. Registreringsuppgifter och ursprungslänk passar
`Provenance`; publicerade villkor passar `LicenseInfo`. Lägesosäkerhet och
antikvarisk bedömning måste mappas försiktigt till `Confidence` utan att hitta
på ett numeriskt värde.

## 2. Riksantikvarieämbetet – K-samsök

### Åtkomst

- **Dokumenterat API:** Ja. K-samsök har dokumenterade sök-, statistik-, facett-
  och relationsmetoder samt protokoll och parametrar.
- **Offentligt:** Ja. RAÄ beskriver API:t som öppet för den som vill bygga egna
  tjänster.
- **API-nyckel:** Nej för K-samsöks läs-API. En nyckel som förekommer i
  dokumentation för UGC-hubben gäller en annan skrivtjänst och ska inte blandas
  ihop med sök-API:t.
- **Licens:** K-samsöks metadata är CC0. Bilder och andra mediefiler kan ha andra
  villkor från respektive leverantör; vissa saknar komplett rättighetsmärkning.

Källor: [K-samsöks API](https://www.raa.se/hitta-information/k-samsok/att-anvanda-k-samsok/api/),
[kom igång](https://www.raa.se/hitta-information/k-samsok/att-anvanda-k-samsok/kom-igang-med-k-samsoks-api/),
[metoder](https://www.raa.se/hitta-information/k-samsok/att-anvanda-k-samsok/metoder/) och
[RAÄ:s licensöversikt](https://www.raa.se/hitta-information/oppna-data/riksantikvarieambetets-oppna-data/).

### Innehåll och begränsningar

- **Datatyper:** fornlämningar, byggnader, fotografier, föremål, dokument och
  andra kulturarvsobjekt från många anslutna institutioner.
- **Geometri:** koordinater för en delmängd av objekten och geografisk sökning
  med bland annat bounding box. RAÄ anger över 1,8 miljoner objekt med
  koordinater, men koordinattäckningen är inte fullständig.
- **Metadata:** beständiga URI:er, etiketter, typer, beskrivningar, tidsuppgifter,
  institution, relationer, rättighetsinformation och länkar till originalposten.
- **Begränsningar:** heterogena leverantörer ger varierande fält, vokabulärer,
  detaljnivå, geometri och datakvalitet. Sökmetoden returnerar högst 1 000 träffar
  per sida. En robust import måste paginera, deduplicera och bevara leverantörens
  ursprungliga identitet.

### JSON-exempel

K-samsök kan leverera JSON och JSON-LD. Följande är ett **förenklat
strukturexempel**, inte ett komplett eller ordagrant svar:

```json
{
  "@id": "http://kulturarvsdata.se/raa/fmi/10240200820001",
  "@type": "Item",
  "itemLabel": "Exempelobjekt",
  "serviceName": "fmi"
}
```

Exakt fältnamn och struktur ska verifieras mot aktuell svarstyp och K-samsöks
datamodell innan implementation.

### Passning till `AtlasFeature`

**Mycket hög.** Beständiga URI:er och leverantörsinformation ger utmärkt
proveniens. Titel, typ, beskrivning, tid och koordinater har naturliga
motsvarigheter. Adaptern måste dock normalisera många källvokabulärer och lämna
geometri, tid eller confidence tomma när källdata saknas.

## 3. OpenStreetMap

### Åtkomst

- **Dokumenterat API:** Ja. OSM:s huvud-API är främst för redigering. För
  selektiv läsning är Overpass API det lämpliga dokumenterade gränssnittet;
  regionala utdrag och planet-filer är bättre för stora importer.
- **Offentligt:** Ja. Publika Overpass-instanser drivs som delade tjänster,
  delvis av tredje parter.
- **API-nyckel:** Nej för normala publika läsfrågor utan användarmetadata.
  Leverantörsspecifika instanser kan kräva nyckel eller betalning.
- **Licens:** OSM-data är ODbL 1.0. Attribution till OpenStreetMap och dess
  bidragsgivare krävs; en offentligt distribuerad bearbetad databas kan omfattas
  av share-alike-villkor.

Källor: [OSM:s licenssida](https://www.openstreetmap.org/copyright),
[Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) och
[OSM Foundations API-policy](https://operations.osmfoundation.org/policies/api/).

### Innehåll och begränsningar

- **Datatyper:** vägar, broar, färjelinjer, hamnar, vatten, byggnader,
  verksamheter, platser och fria taggar, inklusive vissa `historic=*`-objekt.
- **Geometri:** noder (punkter), ways (linjer eller ytor) och relationsbaserade
  multipolygoner/rutter. Geometrin behöver sättas samman och valideras vid
  normalisering.
- **Metadata:** element-ID, typ, version/tidsstämpel beroende på frågeläge och
  fria nyckel–värde-taggar såsom `name`, `historic`, `bridge` och `source`.
- **Begränsningar:** communityproducerad och ojämn täckning; fria taggar är inte
  ett myndighetskontrollerat register. Publika Overpass-servrar har kvoter,
  timeout, minnesgränser och kan svara med 429. De ska inte belastas med
  landsomfattande återkommande fullimporter; använd utdrag och lokal cache.

### JSON-exempel

Förenklad Overpass JSON-struktur:

```json
{
  "version": 0.6,
  "elements": [
    {
      "type": "node",
      "id": 123,
      "lat": 58.0,
      "lon": 16.0,
      "tags": {"historic": "ruins", "name": "Exempel"}
    }
  ]
}
```

### Passning till `AtlasFeature`

**Hög.** OSM har bred, direkt användbar geometri och stabila element-ID:n.
`Provenance` och `LicenseInfo` måste alltid bära ODbL och korrekt attribution.
Historisk tid och källhänvisningar är ofta ofullständiga; `Confidence` får därför
inte härledas enbart från att objektet finns i OSM.

## 4. Sveriges geologiska undersökning (SGU)

### Åtkomst

- **Dokumenterat API:** Ja. Flera datamängder publiceras som standardiserade OGC
  API Features med OpenAPI-beskrivning; nedladdningsbara GeoPackage- och andra
  filer finns också.
- **Offentligt:** Ja.
- **API-nyckel:** Ingen nyckel anges för de öppna OGC-gränssnitten.
- **Licens:** SGU anger att alla geologiska data som myndigheten tillhandahåller
  är öppna och sedan 9 juni 2024 licensieras under CC0. Äldre
  produktbeskrivningar kan fortfarande visa tidigare licens; aktuellt villkor
  ska sparas per hämtad produkt.

Källor: [SGU:s licensvillkor](https://www.sgu.se/produkter-och-tjanster/geologiska-data/om-geologiska-data/licensvillkor/)
och [OGC API Features – exempel Jordarter 1:200 000](https://api.sgu.se/oppnadata/jordarter200k/ogc/features/v1/openapi?f=text%2Fhtml).

### Innehåll och begränsningar

- **Datatyper:** jordarter, berggrund, jorddjup, grundvatten, brunnar,
  geokemi, mineralresurser och andra geologiska observationer/modeller.
- **Geometri:** OGC/GeoJSON Point, MultiPoint, LineString, MultiLineString,
  Polygon, MultiPolygon och GeometryCollection beroende på produkt.
- **Metadata:** feature-ID, produktspecifika attribut, enheter, klassificering,
  datamängdsbeskrivning, kvalitet, skala/upplösning, tidsstämpel och länkar.
- **Begränsningar:** egenskaper och kvalitet skiljer sig mellan produkter.
  Geologiska kartor kan vara generaliserade modeller, inte observationer på varje
  punkt. Multi-geometrier och GeometryCollection ryms inte direkt i nuvarande
  `Geometry` och kräver uppdelning eller en framtida domänutökning.

### JSON-exempel

OGC API Features använder GeoJSON. Förenklad struktur:

```json
{
  "type": "Feature",
  "id": "feature-id",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[16.0, 58.0], [16.1, 58.0], [16.0, 58.0]]]
  },
  "properties": {"produktattribut": "värde"}
}
```

### Passning till `AtlasFeature`

**Medel.** Tekniskt är passningen stark tack vare standardiserad geometri,
identifierare och metadata. Produktmässigt beskriver SGU främst geologiska
förhållanden, inte historiska objekt. SGU bör därför senare bli ett förklarande
kontextlager eller relaterad feature, aldrig en ogrundad indikator på fyndplats.

## 5. Sveriges meteorologiska och hydrologiska institut (SMHI)

### Åtkomst

- **Dokumenterat API:** Ja. SMHI dokumenterar separata REST-API:er för bland
  annat meteorologiska och oceanografiska observationer, prognoser, hydrologi
  och modellerade tidsserier.
- **Offentligt:** Ja för öppna datamängder.
- **API-nyckel:** Ingen nyckel krävs för de dokumenterade öppna API:erna som
  granskats.
- **Licens:** SMHI:s öppna data använder CC BY 4.0 SE. SMHI ska anges som källa
  och ändringar ska anges. Varningar har särskilda villkor.

Källor: [SMHI:s användningsvillkor](https://www.smhi.se/data/om-smhis-data/villkor-for-anvandning),
[API för meteorologiska observationer](https://opendata.smhi.se/metobs/api) och
[API-introduktion](https://opendata.smhi.se/metobs/introduction).

### Innehåll och begränsningar

- **Datatyper:** väder- och havsobservationer, stationer, prognoser,
  hydrologiska data, nederbörd, temperatur och kvalitetskoder.
- **Geometri:** stationspositioner och GeoJSON Point/MultiPoint/Polygon i vissa
  API:er. Historiska modellerade serier kan frågas för koordinater och flera
  referenssystem.
- **Metadata:** parameter, enhet, station/ägare, tidsperiod, uppdateringstid,
  kvalitetskod, referenstid och länkar mellan API-resurser.
- **Begränsningar:** API-versioner har begränsad livslängd, stora svar kan kräva
  gzip och masshämtning ska undvikas. Realtidsdata kan vara ogranskade. SMHI
  instruerar klienter att använda dokumenterade API:er, cache och aktuella data.

### JSON-exempel

Förenklat från SMHI:s dokumenterade observationsstruktur:

```json
{
  "updated": 1756458000000,
  "parameter": {"key": "5", "name": "Havstemperatur", "unit": "°C"},
  "station": {"key": "2545", "name": "ARKÖ", "owner": "SMHI"}
}
```

### Passning till `AtlasFeature`

**Låg–medel.** Stationer kan representeras som `AtlasFeature` med punkt,
proveniens och tidsmetadata, men mätvärden och tidsserier är inte naturliga
egenskaper hos den nuvarande featuremodellen. En framtida SMHI-integration bör
snarare vara ett separat kontext-/observationsflöde än att skapa ett objekt per
mätvärde.

## 6. Kringla

### Åtkomst

- **Dokumenterat API:** Nej, inte som en separat publik data-API för Kringla.
  Kringla är en publik samsöktjänst och objektinformationen hämtas via K-samsök.
- **Offentligt:** Webbgränssnittet är offentligt; den dokumenterade maskinella
  vägen är K-samsöks publika API.
- **API-nyckel:** Ej tillämpligt för Kringla. K-samsöks läs-API kräver ingen
  nyckel.
- **Licens:** Samma grundprincip som K-samsök: aggregerad metadata är CC0, medan
  mediefilers rättigheter bestäms av respektive leverantör och objekt.

Källa: [Om Kringla](https://www.raa.se/hitta-information/kringla/om-kringla/) och
[vad K-samsök är](https://www.raa.se/hitta-information/k-samsok/sa-fungerar-k-samsokl/vad-ar-k-samsok/).

### Innehåll och begränsningar

- **Datatyper:** samma breda kulturarvsinnehåll som visas från K-samsök:
  föremål, fotografier, byggnader, fornlämningar och arkivmaterial.
- **Geometri:** karta och geografisk sökning för objekt som har koordinater;
  täckningen beror på ursprungskällan.
- **Metadata:** titel, typ, institution, beskrivning, tid, objektlänk och
  rättighetsuppgifter när de finns.
- **Begränsningar:** Kringla tillför inget fristående maskinkontrakt och skulle
  dubblera K-samsök som Collector. Att anropa odokumenterade interna endpoints
  vore instabilt och strider mot projektets integrationsprinciper.

### JSON-exempel

Inget separat Kringla-JSON-kontrakt finns dokumenterat. Använd K-samsöks
JSON/JSON-LD-exempel ovan; skapa inte ett Kringla-specifikt svarsschema.

### Passning till `AtlasFeature`

**Låg som egen Collector, mycket hög via K-samsök.** Kringla är värdefull som
referens för användarupplevelse och som originallänk, men Collector-gränsen ska
ligga vid K-samsök för att undvika dubblerad och odokumenterad integration.

## 7. Lantmäteriets Historiska kartor

### Åtkomst

- **Dokumenterat API:** Nej för sökning och metadata i tjänsten Historiska
  kartor, så långt den officiella dokumentationen kunnat verifieras. Det finns
  andra dokumenterade Lantmäteri-API:er och öppna geodataprodukter, men de gör
  inte webbgränssnittets interna metadataanrop till ett publicerat API.
- **Offentligt:** Självservicetjänsten är publik och gratis att använda, med
  begränsat material. Publik visning är inte samma sak som rätt till automatiserad
  masshämtning.
- **API-nyckel:** Ej tillämpligt när ett publicerat metadata-API saknas. Andra
  Geotorget-produkter kan kräva konto, systemkonto, beställning eller behörighet.
- **Licens:** Villkoren varierar. Lantmäteriets öppna geodata är normalt CC0,
  men detta kan inte automatiskt appliceras på all metadata och allt material i
  Historiska kartor. Kartor äldre än 70 år kan publiceras fritt enligt
  Lantmäteriets villkorssida, och myndigheten har avstått upphovsrättsanspråk för
  kartor i Rikets allmänna kartverks arkiv. Villkoret ska ändå fastställas per
  arkiv/dataprodukt.

Källor: [Historiska kartor](https://historiskakartor.lantmateriet.se/),
[tjänstebeskrivning](https://www2.lantmateriet.se/sv/kartor/vara-karttjanster/Historiska-kartor/),
[villkor och avgifter](https://www.lantmateriet.se/sv/geodata/vara-produkter/Villkor-och-avgifter/),
[öppna data](https://www.lantmateriet.se/sv/geodata/vara-produkter/oppna-data/) och
[information om begränsad åtkomst](https://www.lantmateriet.se/sv/om-lantmateriet/om-webbplatsen/tekniska-fragor/information-om-nedstangda-eller-begransade-digitala-tjanster/nyheter-kring-nedstangda-eller-begransade-digitala-akter/).

### Innehåll och begränsningar

- **Datatyper:** historiska kartor och akter från Lantmäteristyrelsens,
  lantmäterimyndigheternas och Rikets allmänna kartverks arkiv; exempelvis
  storskifte, laga skifte, ekonomiska kartan samt läns- och landskapskartor.
- **Geometri:** tjänsten kan söka via karta, men Lantmäteriet varnar för att den
  sökningen använder ortnamn och inte enbart georefererade kartor. Verifierad
  maskinläsbar geometri kan därför inte antas finnas för varje akt.
- **Metadata:** titel/benämning, år, arkiv, aktbeteckning, geografisk anknytning,
  karttyp och länkar kan visas i tjänsten, men något stabilt offentligt
  metadata-schema har inte verifierats.
- **Begränsningar:** endast delar av materialet är tillgängliga; årtal och åtkomst
  skiljer sig mellan arkiv. Digitala akter har begränsats av säkerhets- och
  sekretesskäl. Ett internt endpoint får inte reverse-engineeras eller skrapas
  utan uttryckligt publicerade villkor och teknisk dokumentation.

### JSON-exempel

Det finns inget verifierat officiellt JSON-svar för Historiska kartors metadata.
Inget exempel konstrueras, eftersom det skulle ge en falsk bild av ett stabilt
kontrakt.

### Passning till `AtlasFeature`

**Hög semantisk passning men låg integrationsmognad.** Aktbeteckning, titel,
årtal, arkiv och originallänk passar modellen väl. Problemet är inte
normaliseringen utan avsaknaden av ett verifierat publikt gränssnitt, enhetligt
schema, heltäckande geometri och entydiga villkor för den avsedda automatiserade
användningen.

## Rangordning och motivering

1. **Fornsök/Kulturmiljöregistret** – bäst kombination av svensk
   kulturhistorisk relevans, officiell proveniens, geometri och öppna geodata.
2. **RAÄ K-samsök** – bästa dokumenterade kulturarvs-API:t och bredast metadata,
   men mer heterogent och med ofullständig koordinattäckning.
3. **OpenStreetMap** – tekniskt moget och geometriskt starkt, men
   communitykvalitet och ODbL kräver mer kvalitets- och licenshantering.
4. **SGU** – föredömligt standardiserade OGC-API:er och CC0, men geologisk
   kontext är sekundär till MagnetAtlas historiska kärna.
5. **SMHI** – väl dokumenterat och kvalitetsmärkt, men tidsserier passar dåligt
   i dagens `AtlasFeature` och bidrar främst med framtida kontext.
6. **Kringla** – relevant innehåll men ingen egen lämplig Collector-gräns; samma
   data bör hämtas via K-samsök.
7. **Lantmäteriets Historiska kartor** – starkast kartinnehåll men för svag
   dokumenterad maskinåtkomst för en robust integration i nuläget.

## Rekommendation

Implementera **Fornsök/Kulturmiljöregistret först**, genom en uttryckligen
publicerad datamängd eller geodatatjänst i RAÄ:s öppna dataportal – inte genom
Fornsöks interna webbanrop.

Skälen är:

- objekten är direkt relevanta för historisk platsupptäckt,
- identiteter, källmyndighet och geometri ger stark `Provenance`,
- punkt-, linje- och ytobjekt passar den befintliga domänmodellen,
- läsning kräver ingen användarhemlighet,
- data kan användas för att både informera och tydligt varna om skyddade eller
  känsliga kulturmiljöer.

Före implementation ska ett kort tekniskt förarbete låsa exakt dataprodukt,
schema, koordinatsystem, uppdateringsfrekvens, licenstext och citeringsformat.
Collector-tester ska använda sparade, licensmässigt tillåtna fixtures och aldrig
kräva nätverk. `Confidence` ska bygga på uttrycklig kvalitets- eller
lägesosäkerhetsmetadata; saknas sådan lämnas värdet okänt. KMR-data får inte
användas som ranking eller uppmaning till aktivitet vid fornlämningar.

**Andrahandsval:** K-samsök, om RAÄ:s valda KMR-produkt visar sig sakna ett
stabilt maskinellt uttag för den avgränsning MagnetAtlas behöver. K-samsök har
det tydligaste dokumenterade sök-API:t och bör då implementeras med strikt
leverantörsfiltrering, paginering och separat rättighetshantering för media.
