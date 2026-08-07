# Roadmap

## Levererat i v0.6.0-alpha

- Körbar CLI-grund med SQLite och CSV-export.
- Gemensamt Collector-kontrakt, plugin registry och `AtlasFeature`-modell.
- Officiell RAÄ KMR-import med inkrementell synk och lokal cache.
- Lokal MapLibre-karta med klustring, sökning, filter, objektförklaring,
  favoriter, historik, GPS och tillgängliga kartkontroller.
- Responsiv public-alpha-upplevelse för mobil, surfplatta och desktop.

## Godkänd sprintordning

### Sprint 3.1 – Multi-source Foundation

Målet är att införa stabila identiteter för källa, datasetinstans och geografiskt
scope, förena Collector-generationerna och göra composition root, metadata och
serialisering källneutrala. Inkrementell synk ska arbeta indexerat med berörda
käll-ID:n i stället för att materialisera hela dataset.

Resultatet ska vara en verifierad grund där flera avgränsade dataset kan
samexistera utan att domänmodellen eller befintlig RAÄ-data blandas ihop.

### Sprint 3.2 – Layer Engine

Status: **slutförd**.

Sprinten levererar källneutrala lager ovanpå multi-source-modellen:
`LayerDefinition`, `LayerRegistry`, datasetmedveten `LayerService`, filtrering av
`AtlasFeature`, generella API-endpoints och en webbpanel med elva deklarerade
lager. Kulturhistoriska lämningar är det enda aktiva produktlagret; övriga visas
som kommande tills deras datakällor implementeras.

Layer Engine använder Sprint 3.1:s stabila dataset- och källidentiteter och
innehåller inga myndighetsspecifika regler.

### Sprint 3.3 – Offline Packages

Målet är versionsmärkta och checksummekontrollerade regionala datapaket med
atomisk installation, uppdatering och borttagning. Applikationens statiska
resurser ska kunna köras lokalt och baskartor ska följa ett separat, licenssäkert
offlinekontrakt.

Offline byggs ovanpå Layer Engine så att paket kan välja regioner och lager utan
att skapa alternativa domänmodeller.

### Sprint 3.4 – Second Official Data Source

Målet är att implementera en andra officiell svensk datakälla som har genomgått
separat API-, licens- och kvalitetsgranskning. Integrationen ska använda det
gemensamma Collector-kontraktet och verifiera datasetinstanser, lager,
attribuering, kombinerade frågor och regionala offlinepaket tillsammans med RAÄ.

Den andra källan är ett arkitekturtest: Layer Engine och multi-source-modellen
ska fungera utan nya källspecifika specialfall i kärnan eller frontend.

### Sprint 3.5 – Mobile Foundation

Målet är en installerbar PWA-app shell, mobilanpassade lager-, sök- och
offlineflöden samt validering av en tunn native shell med lokal SQLite och
regionala datapaket. Stora myndighetsimporter ska inte köras på telefonen.

Mobilversionen påbörjas först när lager- och offlinekontrakten har verifierats av
två officiella datakällor.

### Sprint 4.0 – Explainable AI Assistant

Målet är en assistent vars svar alltid grundas i valda lokala features,
proveniens och uttrycklig osäkerhet. Källfakta, regelbaserade slutsatser och
tolkningar ska kunna skiljas åt och granskas. AI får inte uppfinna historiska
fakta eller ge olagliga, farliga eller kulturhistoriskt skadliga råd.

Sprinten kräver stabil multi-source-, lager-, offline- och mobilarkitektur samt
en förklarbar och testbar sök- och analysgrund.

## Beroendeordning

```text
Multi-source Foundation
        ↓
Layer Engine
        ↓
Offline Packages
        ↓
Second Official Data Source
        ↓
Mobile Foundation
        ↓
Explainable AI Assistant
```

GeoJSON-, GPX- och PDF-export, historiska kartor och ytterligare datakällor
prioriteras separat och får inte bryta denna beroendeordning.
