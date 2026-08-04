# Datakällor

Riksarkivets publika söktjänst är projektets första `Collector`-plugin. Den
annonserar capabilities för textsökning och resultatbegränsning och returnerar
`CollectionBatch` med normaliserade `ArchiveRecord`-objekt. Det äldre
`RiksarkivetClient.search` finns kvar för bakåtkompatibilitet.

Planerade adaptrar omfattar OpenStreetMap, Lantmäteriet,
Riksantikvarieämbetet, SGU och SMHI. Varje integration måste dokumentera API,
licens, attribueringskrav, uppdateringsfrekvens och kända kvalitetsbegränsningar.
De är inte implementerade eller registrerade i Sprint 2.1.
