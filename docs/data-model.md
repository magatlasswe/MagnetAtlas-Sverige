# Datamodell

`AtlasFeature` är den gemensamma, källoberoende modellen för geografiska och
historiska objekt. Varje feature har ett `FeatureId`, titel, objekttyp och
`Provenance`. Geometri, tidsintervall, plats, beskrivning, confidence och
framtida relationships är valfria. Källans identitet, URL, hämtningstid, licens
och rådata hålls samlade i proveniensen.

## Geografi

Domänen använder WGS84-koordinater och små egna värdeobjekt utan beroende på en
GIS-motor:

- `GeoPoint` lagrar longitud och latitud.
- `BoundingBox` lagrar väst, syd, öst och nord.
- `LineString` lagrar minst två ordnade punkter.
- `Polygon` lagrar en sluten yttre ring och eventuella slutna hål.
- `Geometry` är unionen av dessa geometriobjekt.

Bounding boxes som korsar antimeridianen stöds inte ännu. Geometrierna gör ingen
projektion, topologisk analys eller annan GIS-bearbetning.

## Tid och osäkerhet

`TimeSpan` kan innehålla start- och slutdatum, källans fria originaltext,
precision och certainty. Därmed kan exempelvis "1800-talet" bevaras utan att ett
exakt datum konstrueras. `Confidence` använder en valfri normaliserad nivå mellan
0 och 1 samt en förklaring; saknad nivå betyder uttryckligen okänd säkerhet.

`LicenseInfo` bevarar licensnamn, URL, attribuering, användningsanteckningar samt
om attribuering krävs och kommersiell användning är tillåten. De två villkoren
kan vara okända och ska då inte antas vara vare sig tillåtna eller förbjudna.

## Bakåtkompatibilitet

`ArchiveRecord` är fortsatt lagrings- och exportmodell för den befintliga
Riksarkivet-funktionen. Den kan konverteras förlustfritt för relevanta fält till
`AtlasFeature`, utan att okänd geometri, licens eller confidence hittas på.
Databasschemat ändras inte i Sprint 2.2.
