# Arkitektur

MagnetAtlas-Sverige är en modulär monolit med hexagonala gränser. Domänen är
oberoende av externa tjänster. Applikationslagret orkestrerar användningsfall,
medan infrastrukturen implementerar databas-, export- och källadaptrar. CLI:t är
ett gränssnitt ovanpå applikationslagret.

Plugins ligger under `magnetatlas.plugins`. Kärnan får inte importera konkreta
plugins; en framtida pluginmekanism ska använda dokumenterade kontrakt och
Python entry points.

SQLite är Sprint 1-lagring. Repository-gränsen gör en framtida PostGIS-adapter
möjlig utan att ändra användningsfallen.
