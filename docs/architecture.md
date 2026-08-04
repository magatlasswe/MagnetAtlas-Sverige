# Arkitektur

MagnetAtlas-Sverige är en modulär monolit med hexagonala gränser. Domänen är
oberoende av externa tjänster. Applikationslagret orkestrerar användningsfall,
medan infrastrukturen implementerar databas-, export- och källadaptrar. CLI:t är
ett gränssnitt ovanpå applikationslagret.

Datakällor implementerar det källoberoende `Collector`-protokollet och annonserar
stöd genom capabilities. `CollectorRegistry` kan ta emot collectors explicit vid
komposition eller upptäcka plugin-fabriker genom Python entry points i gruppen
`magnetatlas.collectors`. Domän- och applikationslagren importerar inte konkreta
källadaptrar. CLI:t är kompositionsrot och kopplar konfiguration till vald plugin.

En collector ansvarar för källprotokoll, defensiv parsning och översättning till
domänmodeller. Applikationslagret ansvarar för validering, orkestrering och
lagring; källadaptrar innehåller inte rankning eller annan affärslogik.

SQLite är Sprint 1-lagring. Repository-gränsen gör en framtida PostGIS-adapter
möjlig utan att ändra användningsfallen.
