# Datakällor

Riksarkivets publika söktjänst är projektets första `Collector`-plugin. Den
annonserar capabilities för textsökning och resultatbegränsning och returnerar
`CollectionBatch` med normaliserade `ArchiveRecord`-objekt. Det äldre
`RiksarkivetClient.search` finns kvar för bakåtkompatibilitet.

Planerade adaptrar omfattar OpenStreetMap, Lantmäteriet,
Riksantikvarieämbetet, SGU och SMHI. Varje integration måste dokumentera API,
licens, attribueringskrav, uppdateringsfrekvens och kända kvalitetsbegränsningar.
RAÄ Kulturmiljöregistret är implementerat i Sprint 2.6. Övriga källor är ännu
inte implementerade.

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
magnetatlas import raa --county ostergotland
magnetatlas import raa --municipality kinda
magnetatlas import raa --bbox 14,57,17,59
magnetatlas cache status
magnetatlas cache refresh
magnetatlas cache clear
```

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
