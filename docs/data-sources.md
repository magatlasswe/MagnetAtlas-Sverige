# Datakällor

Riksarkivets publika söktjänst är projektets första `Collector`-plugin. Den
annonserar capabilities för textsökning och resultatbegränsning och returnerar
`CollectionBatch` med normaliserade `ArchiveRecord`-objekt. Det äldre
`RiksarkivetClient.search` finns kvar för bakåtkompatibilitet.

Planerade adaptrar omfattar OpenStreetMap och SMHI. Varje integration måste dokumentera API,
licens, attribueringskrav, uppdateringsfrekvens och kända kvalitetsbegränsningar.
RAÄ Kulturmiljöregistret är implementerat i Sprint 2.6, SGU i Sprint 3.3 och
Lantmäteriet Ortnamn Nedladdning i Sprint 3.5b.

## Lantmäteriet Provider

Providern använder den officiella STAC-vektorkatalogen på
`https://api.lantmateriet.se/stac-vektor/v1`. Datasetet `ortnamn` väljer den
senast publicerade katalogpostens ZIP-asset, bevarar item-ID och publiceringstid
som snapshotidentitet och extraherar exakt en GeoPackage säkert. Den
rikstäckande leveransen används för country; bbox filtreras lokalt efter
konvertering från SWEREF 99 TM till WGS84.

Den stabila objektidentiteten är löpnummer och språkkod. Originalfält,
hämtningsadress, snapshotversion, CC BY 4.0-attribution och koordinatens
kartografiska osäkerhet bevaras i `AtlasFeature`. OAuth2 eller Basic-auth läses
endast från miljökonfiguration. Historiska kartor är fortsatt inaktiverade.

## SGU Provider

SGU-integrationen är en konfigurerbar provider för flera framtida geologiska
dataset. Providerkonfigurationen håller datasetnamn, API-sökväg, collection-ID,
schemaversion och `SourceDefinition`; Collector-, mapper- och importflödet är
gemensamt. Sprint 3.3 registrerar endast **Jordarter 1:25 000-1:100 000** och
samlingen `grundlager`. Berggrund, brunnar, grundvatten, gruvor och
mineralinformation är ännu inte implementerade.

Datat läses från SGU:s dokumenterade OGC API Features:
`https://api.sgu.se/oppnadata/jordarter25k-100k/ogc/features/v1`. GeoJSON begärs
i CRS84/WGS84, `next`-länkar följs och normaliserade features skrivs i begränsade
batchar genom samma `SyncService` och repositorykontrakt som RAÄ. Collectorn
annonserar basimport men inte inkrementella ändringar, eftersom produkten saknar
ett dokumenterat ändringsflöde.

Varje SGU-objekt bevarar feature-ID, produkt- och collectionidentitet,
originalattribut, hämtningsdatum och källänk. `Confidence` förklarar att
kartskalan är översiktlig och inte lämpad för detaljerade markbedömningar. SGU
anger att dess öppna geologiska data sedan den 9 juni 2024 har licensen CC0.

OGC-tjänsten erbjuder bbox som dokumenterad geografisk avgränsning men inga
namngivna läns- eller kommunparametrar. `--county` och `--municipality` kräver
därför även `--bbox`; namnet sparas som bbox-scopeets parent. Det förhindrar att
ett rikstäckande uttag felaktigt identifieras som ett lokalt dataset.

Kommandon:

```text
magnetatlas import sgu --country sweden
magnetatlas import sgu --bbox 18.2,59.35,18.5,59.5
magnetatlas import sgu --county stockholm --bbox 17.7,58.7,19.4,60.3
magnetatlas import sgu --municipality vaxholm --bbox 18.2,59.35,18.5,59.5
```

Vid kontroll 2026-08-07 rapporterade `grundlager` 2 956 837 objekt. Samtliga
automatiska tester använder mockade HTTP-svar och kräver aldrig internet.

## RAÄ Kulturmiljöregistret

RAÄ-integrationen använder myndighetens rekommenderade tvåstegsmodell:

1. En officiell, nattligt publicerad GeoPackage-bas importeras från
   `pub.raa.se/nedladdning/datauttag/lamningar_v1`.
2. Det dokumenterade Datauttag REST API v1.2.0 används endast för förändringar
   efter basimportens synkmarkör via `GET /lamningar`.

GeoPackage-produktens schema är version 3.0. Collectorn läser punkter, linjer
och polygoner, konverterar SWEREF 99 TM (EPSG:3006) till intern WGS84 och
returnerar enbart `AtlasFeature`. RAÄ-specifika fält hålls i adaptern och i
feature-egenskaper som behövs för spårbar visning.

Den kompletta kedjan verifierades 2026-08-05 mot RAÄ:s aktuella officiella
kommunuttag för Vaxholm. Aktuella fullständiga vyer identifierar lämningen med
`uuid`, medan kvalitetslagret använder `lamning_uuid`; collectorn hanterar båda
formerna och kopplar lägesosäkerhet till rätt objekt utan att skapa en separat
kartgeometri. Ett uttag som inte kan normaliseras får inte ersätta aktiv cache.

SQLite-databasen och dess synkmetadata är cache och lokal sanningskälla. En
basimport ersätter datasetet atomärt; inkrementell synk uppdaterar bara ändrade
objekt. Misslyckad hämtning eller mappning aktiverar aldrig ett halvfärdigt
dataset, så senast lyckade databas fortsätter användas.

Basimporten läser GeoPackage-vyerna i begränsade batchar. Normaliserade
`AtlasFeature` skrivs fortlöpande till ett isolerat stagingdataset i SQLite och
hålls inte samlade i arbetsminnet. När hela källfilen har validerats aktiveras
stagingdatasetet i en kort transaktion. Vid avbrott tas endast stagingraderna
bort och den tidigare cachen förblir tillgänglig.

Datauttaget anges av RAÄ som public domain/CC0. MagnetAtlas bevarar källa,
käll-ID, hämtningsdatum och originalhänvisning när den finns. Saknade värden
uppfinns inte. REST-uttaget släpar normalt till nästa nattliga publicering och
har ingen dokumenterad bbox-, läns- eller kommunparameter; geografiska
basurval använder därför RAÄ:s publicerade läns- och kommunfiler och bbox
filtreras lokalt.

Kommandon:

```text
magnetatlas import raa
magnetatlas import raa --country sweden
magnetatlas import raa --county ostergotland
magnetatlas import raa --municipality kinda
magnetatlas import raa --bbox 14,57,17,59
magnetatlas cache status
magnetatlas cache refresh
magnetatlas cache clear
```

`--country sweden` väljer uttryckligen RAÄ:s rikstäckande totaluttag och gör en
kontroll av att arbetskatalogen har minst 12 GiB ledigt innan hämtningen börjar.
Land, län och kommun är ömsesidigt uteslutande importomfång. Utan geografiskt
alternativ finns det äldre totaluttagsbeteendet kvar för bakåtkompatibilitet.

Se [Sprint 3.0-valideringen](sprint-3.0-validation.md) för verifierad datamängd,
lagringskostnad, minnesprofil och lokala frågelatenser.

## OpenStreetMap-baskarta

OpenStreetMap används i Sprint 2.3 endast som visuell rasterbaskarta och är inte
en Collector eller källa till AtlasFeatures. Klienten begär enbart tiles som en
människa visar interaktivt från
`https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Kartan visar alltid
`© OpenStreetMap contributors` med länk till licensinformationen.

MagnetAtlas erbjuder ingen bulk-, prefetch- eller offlinehämtning av OSM-tiles.
Tile-adressen hålls samlad i kartkonfigurationen så att en annan tillåten tjänst
kan väljas senare. Se OpenStreetMap Foundations
[Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/) och
[copyright- och licensinformation](https://www.openstreetmap.org/copyright).
