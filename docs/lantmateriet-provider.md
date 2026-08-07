# Lantmäteriet-provider: research och rekommendation

Research genomförd: **2026-08-07**  
Implementerad: **Sprint 3.5b**

> **Reviderat beslut:** Sprint 3.5 avbröts innan kod. Ortnamn Direkt är ett
> fråga–svar-API som kräver namn eller punkt och kan inte skapa fullständiga
> country- eller bbox-importer. Sprint 3.5b implementerar därför Ortnamn
> Nedladdning, vektor via den officiella STAC-vektorkatalogen.

## Avgränsning

Sprint 3.4 implementerar inget Lantmäteri-API. Syftet är att skilja mellan
öppna data, avgiftsfria men behörighetsstyrda produkter och rena
visningstjänster innan ett transport- och autentiseringskontrakt väljs.

Lantmäteriets [produktlista](https://www.lantmateriet.se/sv/geodata/vara-produkter/produktlista/)
omfattar geografisk information, kartor, bilder, höjddata, hydrografi,
administrativ indelning, ortnamn och fastighetsinformation. Alla avgiftsfria
produkter är inte öppna i samma juridiska eller tekniska mening.

## Licens- och åtkomstklasser

Lantmäteriets [öppna data](https://www.lantmateriet.se/sv/geodata/vara-produkter/avgiftsfria-produkter/oppna-data/)
publiceras under CC0 och får användas, bearbetas och spridas även kommersiellt.
Källangivelse uppskattas men krävs inte.

Sedan 2025 finns även avgiftsfria **värdefulla datamängder**. De kan kräva konto
i Geotorget, godkända produktvillkor, systemkonto och särskild behörighet. Vissa
innehåller personuppgifter eller kräver ändamålsprövning. De får därför inte
automatiskt behandlas som anonyma CC0-flöden. Aktuella villkor måste läsas per
produkt i Geotorget.

## Relevanta dataset och gränssnitt

| Produktfamilj | API/leverans | Format | Autentisering | Bedömning |
|---|---|---|---|---|
| Ortnamn Direkt | Dokumenterat REST-API | GeoJSON eller GML/XML | OAuth2 och produktbehörighet | Bäst anpassning till `AtlasFeature` |
| Kommun, län och rike Direkt | Direktåtkomst | Strukturerade geometrier | Konto och produktbehörighet | Bra framtida scope-resolver |
| Hydrografi Direkt | Inspire-baserad direktåtkomst | GML/vektor | Konto och produktbehörighet | Relevant men större och mer komplext |
| Ortofoto historiska Visning | OGC WMS 1.1.1 | PNG/JPEG | Produktbehörighet | Bra framtida rasterlager, inte `AtlasFeature` |
| Ortofoto Nedladdning | STAC API | Rasterfiler och STAC-metadata | Konto och produktbehörighet | Standardiserat men datatungt |
| NGP-dataset | STAC och OGC API Features | Datasetberoende | Basic Auth eller OAuth2 | Generell standard, men egna villkor och behörighet |
| Ekonomiska kartan (1935-1978) | Filnedladdning | Georefererad raster/TIFF | Öppen FTP-leverans | Historiskt relevant men saknar objekt-API |
| Häradsekonomiska kartan (1859-1934) | Filnedladdning | TIFF | Öppen FTP-leverans | CC0 och relevant, men olämplig som första Collector |
| Generalstabskartan (1827-1971) | Filnedladdning | Raster/TIFF | Produktens leveransvillkor | Relevant men kräver raster-/kaklingskontrakt |
| Historiska flygbilder | Filnedladdning | Rasterbilder och orienteringsdata | Konto/produktbehörighet kan krävas | Datatung och inte första integration |
| Topografi och höjddata | Nedladdning, WMS/WMTS, vector tiles eller STAC beroende på produkt | Vektor, raster, tiles, punktmoln | Produktberoende | Flera framtida adaptrar, inte ett gemensamt schema |

Lantmäteriets visningsprodukter använder främst OGC WMS och WMTS.
Nationella geodataplattformen använder STAC och OGC API Features. Flera
direktåtkomstprodukter använder dokumenterade REST-gränssnitt med GeoJSON eller
GML. Produktens API-typ får därför vara metadata i providerns datasetkatalog;
providern får inte anta att alla Lantmäteri-dataset använder samma transport.

## Historiska kartor

Det framtida lagret **Historiska kartor** bör initialt beskriva en produktfamilj,
inte lova en viss transport. De tre centrala kartserierna är:

- Häradsekonomiska kartan, 1859-1934: markanvändning, vegetation, bebyggelse,
  kommunikationer och gränser.
- Generalstabskartan, 1827-1971: naturlandskap, höjdförhållanden,
  kommunikationer, bebyggelse och översiktlig markanvändning.
- Ekonomiska kartan, 1935-1978: fastigheter, byggnader, odlingsmark,
  fornminnen och ortnamn.

Kartserierna är mycket relevanta för MagnetAtlas men levereras som rasterfiler,
inte som avgränsade historiska objekt. En korrekt implementation kräver först
ett separat kontrakt för kartblad/indexmetadata, rasterlagring, projektion,
kakling, skala och attribution. Att pressa TIFF-filerna genom
`AtlasFeatureCollector` skulle skapa fel abstraktion.

Historiska ortofoton har ett dokumenterat WMS, men WMS returnerar renderade
bilder. Det är ett visningslager och inte en importerbar featurekälla.

## Ursprunglig rekommendation (ersatt)

**Ortnamn Direkt rekommenderas som första implementerade Lantmäteri-dataset i
Sprint 3.5.**

Motivering:

1. API:t är dokumenterat och versionerat, med produktions- och verifieringsmiljö.
2. JSON-svar är GeoJSON FeatureCollections med stabila objektidentiteter.
3. Enskilda ID:n, fritext och komplexa geografiska kriterier stöds.
4. Punkter och metadata kan mappas direkt till `AtlasFeature`, `Provenance`,
   `LicenseInfo` och `Confidence` utan ändringar i kärnan eller frontend.
5. Datasetet är användbart för sökning, platsnamn, historisk kontext och framtida
   scope-upplösning.
6. Det verifierar providerns OAuth2-, timeout-, fel- och versionshantering innan
   betydligt större raster- eller hydrografiflöden introduceras.

Nackdelen är att åtkomst kräver Geotorget-behörighet och OAuth2. Sprint 3.5
måste därför först verifiera aktuella produktvillkor och implementera säker
tokenhantering utan att lagra eller logga hemligheter.

## Providerdesign

Providern ska följa samma lagerindelning som SGU:

```text
client.py     transport, autentisering, timeout och leverantörsfel
collector.py  datasetval, capabilities och bounded collection
mapper.py     Lantmäteriets schema/geometri till AtlasFeature
importer.py   tunn fasad över gemensam SyncService
```

Datasetmetadata ska vara deklarativ och minst innehålla stabilt dataset-ID,
produktnamn, transporttyp, format, API-version, autentiseringsklass, licensklass,
geometrityp och framtida lager-ID. Ingen importer eller autentisering aktiveras i
Sprint 3.4.

## Beslut efter Sprint 3.5b

- Använd Ortnamn Nedladdning för reproducerbara fulluttag och lokala bbox-urval.
- Reservera Ortnamn Direkt för ett eventuellt framtida fjärrsökningsfall.
- Behåll Historiska kartor som inaktiv deklaration tills rasterkontraktet finns.
- Behandla WMS/WMTS, STAC, OGC API Features och produkt-REST som separata
  transportcapabilities inom samma provider.
- Lägg aldrig API-nycklar, OAuth2-klienthemligheter eller tokens i repositoryt.
- Implementera inte FTP-skrapning; historiska raster ska använda uttryckligt
  dokumenterad leverans och verifierbar kartbladsmetadata.

## Officiella källor

- [Lantmäteriets produktlista](https://www.lantmateriet.se/sv/geodata/vara-produkter/produktlista/)
- [Öppna data och CC0](https://www.lantmateriet.se/sv/geodata/vara-produkter/avgiftsfria-produkter/oppna-data/)
- [Avgiftsfria produkter och behörighet](https://www.lantmateriet.se/sv/geodata/vara-produkter/avgiftsfria-produkter/)
- [NGP:s teknik, STAC och OGC API Features](https://www.lantmateriet.se/sv/nationella-geodataplattformen/konsument/teknik--konsument/)
- [Ortnamn Direkt](https://geotorget.lantmateriet.se/geodataprodukter/ortnamn-direkt-api)
- [Historiska ortofoton, WMS](https://geotorget.lantmateriet.se/link/ortofoto-historiska-visning)
- [Häradsekonomiska kartan](https://geotorget.lantmateriet.se/geodataprodukter/haradsekonomiska-kartan)
