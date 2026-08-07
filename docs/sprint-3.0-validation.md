# Sprint 3.0 – rikstäckande RAÄ-validering

Validerad: **2026-08-07** på Windows, Python 3.14.6 och lokal SQLite.

## Datamängd och importkedja

Den fullständiga officiella RAÄ-basen importerades genom den batchade
GeoPackage-till-staging-kedjan och aktiverades atomiskt. Den lokala cachen
innehöll efter import och indexmigration:

- 838 178 normaliserade `AtlasFeature`-objekt
- 838 178 RTree-rader
- 838 178 FTS5-rader
- geografisk täckning 10,3841–24,1663°E och 55,0131–69,0530°N
- 6 397 874 176 byte SQLite-lagring, cirka 7 633 byte per objekt

Körningen bekräftar att hela totaluttaget ryms i den minnesbegränsade,
batchade importvägen. Den tidigare aktiva cachen ligger kvar tills staging är
fullständigt validerad. CLI:t kräver minst 12 GiB ledigt före en uttrycklig
`--country sweden`-import, så både källfil, staging och aktiv databas får
arbetsutrymme.

Den avbrutna sprintkörningen sparade inte total importtid eller processens
residenta toppminne. Dessa två värden kan därför inte redovisas retroaktivt
utan att hämta och importera myndighetens totaluttag på nytt. Ingen sådan
nätverksberoende omkörning gjordes vid slutrevisionen. Bounded-memory-egenskapen
täcks i stället av importens batchkontrakt och integrationstester.

## Webb- och frågemätning

Mätningen kördes direkt mot den fullständiga lokala cachen. Varje fall värmdes
upp en gång och kördes därefter tio gånger. Tabellen visar median, observerad
95-percentil och Python-allokeringarnas topp enligt `tracemalloc`.

| Fråga | Svar | Median | P95 | Python-topp |
|---|---:|---:|---:|---:|
| Sverige-viewport, gräns 2 000 | 2 000 | 902 ms | 947 ms | 52,73 MiB |
| Stockholm-viewport, gräns 2 000 | 2 000 | 818 ms | 862 ms | 51,64 MiB |
| Sökning `bro`, gräns 100 | 100 | 220 ms | 243 ms | 11,80 MiB |
| Exakt RAÄ-ID `L1981:6702` | 1 | 2,6 ms | 2,8 ms | 0,05 MiB |

Svarsstorleken är hårt begränsad och frågeplanstester verifierar RTree/FTS5
utan full tabellskanning eller temporär global sortering. Under valideringen
upptäcktes att `ORDER BY` före `LIMIT` gav cirka 11,4 sekunders median för hela
Sverige och mer än 120 sekunder för den breda sökningen. Den sorteringen togs
bort; tabellens ordning är inte en del av webb-API-kontraktet.

Värdena är en lokal baslinje, inte universella prestandalöften. Diskcache,
processor och objektdokumentens storlek påverkar resultatet.
