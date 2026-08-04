# Datakällor

Riksarkivets publika söktjänst är projektets första `Collector`-plugin. Den
annonserar capabilities för textsökning och resultatbegränsning och returnerar
`CollectionBatch` med normaliserade `ArchiveRecord`-objekt. Det äldre
`RiksarkivetClient.search` finns kvar för bakåtkompatibilitet.

Planerade adaptrar omfattar OpenStreetMap, Lantmäteriet,
Riksantikvarieämbetet, SGU och SMHI. Varje integration måste dokumentera API,
licens, attribueringskrav, uppdateringsfrekvens och kända kvalitetsbegränsningar.
De är inte implementerade eller registrerade i Sprint 2.3.

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
