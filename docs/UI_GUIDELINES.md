# UI-riktlinjer

MagnetAtlas ska vara begripligt för en ny användare utan kunskap om GIS eller
arkivsystem. Gränssnittet ska samtidigt vara ärligt om källor, precision,
licenser och säkerhet.

## Grundprinciper

1. Visa kartan först. Undvik dashboards och introduktionsflöden med flera steg.
2. Ge varje vy ett tydligt huvudsyfte och högst en primär åtgärd.
3. Använd vardaglig svenska. Visa inte interna modell- eller leverantörstermer.
4. Hitta inte på information. Saknad position, tid, licens eller confidence ska
   uttryckligen visas som okänd.
5. En AtlasFeature är information, inte en rekommendation eller ett löfte om
   fynd.

## Kartan

- OpenStreetMap-attribuering ska alltid vara synlig och klickbar.
- Grundkartan ska vara visuellt underordnad AtlasFeatures.
- Punkt, yta och linje ska vara klickbara och ha tydligt valt tillstånd.
- Närliggande punktobjekt ska klustras vid låg zoom och expanderas vid klick.
- Val av sökresultat eller kartobjekt ska automatiskt visa hela objektet.
- “Min plats” får endast aktiveras efter en uttrycklig användaråtgärd och
  webbläsarens behörighetsdialog. Positionen får inte lagras.
- Skala, kompass och helskärmskontroll ska ha tillgängliga namn.
- Färg får inte ensam uttrycka objekttyp, säkerhet eller status.
- Historisk eller osäker position ska beskrivas som ungefärlig.
- Inga dolda kartlager, högerklicksmenyer eller GIS-verktygsfält införs utan ett
  verifierat användarbehov.

## Sökning

- Sökfältet ska ligga synligt i sidhuvudet.
- Lokal sökning omfattar titel, plats, objekttyp och beskrivning.
- Svenska tecken och skiftlägesvariationer ska fungera.
- Enter väljer första resultatet och Escape stänger resultatlistan.
- Ett resultatlöst sökresultat ska ge en tydlig tomtext.
- Stavfelstolerans får avgöra om ett objekt matchar men får inte användas för
  ranking eller poängsättning. Källordningen ska bevaras.
- Filter för objekttyp, tidsperiod och källa ska påverka både sökresultat och
  synliga kartobjekt.

## Platsinformation

Information visas i följande ordning:

1. titel och objekttyp
2. plats och tid
3. beskrivning
4. confidence för position och uppgift
5. källa och käll-ID
6. licens och attribuering
7. “Varför visas denna plats?” med stödjande källa och uppskattningsstatus
8. navigation
9. ansvarsfullhetsnotis

Källhänvisningar och licenser får inte gömmas bakom avancerade inställningar.
Leverantörens rådata ska aldrig visas direkt som HTML.

## Navigation

“Navigera hit” öppnar en extern OpenStreetMap-vy. Om målet representerar en yta
eller linje ska det märkas som ungefärligt. Saknad geometri innebär att knappen
döljs. Den separata “Min plats”-kontrollen får fråga webbläsaren om position
först efter användarens klick; MagnetAtlas lagrar inte positionen.

## Personligt lokalt tillstånd

- Favoriter och högst åtta senast besökta objekt lagras som FeatureId:n i
  webbläsarens lokala lagring.
- Tillståndet skickas inte till servern och kräver inget konto.
- Användaren ska kunna öppna sparade objekt från ett enkelt kort, inte en ny
  komplex navigationsnivå.
- Ljust eller mörkt tema ska kunna väljas och sparas lokalt.

## Tillgänglighet

- Använd semantisk HTML och synliga formuläretiketter eller tillgängliga namn.
- Alla funktioner ska gå att använda med tangentbord.
- Fokusmarkering ska vara tydlig och får inte tas bort.
- Interaktiva touchytor ska vara minst 44 × 44 pixlar.
- Text och kontroller ska uppfylla minst WCAG AA-kontrast.
- Information får inte förmedlas enbart genom färg.
- Respektera `prefers-reduced-motion`.
- Mobilvyn får inte kräva horisontell scroll.

## Ton och säkerhet

Språket ska vara lugnt, konkret och icke-sensationalistiskt. Undvik ord som
“skattplats”, “garanterat fynd” och liknande påståenden. Följande kärnbudskap ska
finnas nära platsinformationen:

> Kontrollera tillstånd, lokala regler, vattenförhållanden och
> kulturmiljöhänsyn innan du besöker platsen.

Demodata ska alltid vara synligt märkt som syntetisk och får inte kunna
förväxlas med verifierade historiska objekt.

## Visuell grund

- Ljus, lugn bakgrund med mörk grön grundfärg.
- Varm accentfärg för primära åtgärder och valt kartobjekt.
- Begränsad typografisk skala och systemtypsnitt för snabb laddning.
- Kort med måttlig rundning och skugga; kartan ska fortfarande dominera.
- Mobil först: informationspanel som bottenkort, sidopanel på större skärmar.
- Popup- och panelanimationer ska vara korta och avaktiveras av
  `prefers-reduced-motion`.
