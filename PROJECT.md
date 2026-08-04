# MagnetAtlas Sverige – Project Overview

Last updated: **2026-08-05**

Current version: **v0.5.0-alpha (Planning)**

Current sprint: **Sprint 2.6 – First Official Collector**

## Project Status

Current Version: **v0.5.0-alpha (Planning)**

The runnable alpha currently contains the project foundation, Collector
Framework, shared domain model, local web interface and user-experience
improvements. The first official Collector is planned but not yet implemented.

## Current Sprint

### Sprint 2.6 – First Official Collector

Goal: implement the first real Collector using an official Swedish data source.

Target: RAÄ Kulturmiljöregistret (KMR).

Deliverables:

- Collector
- Importer
- Cache
- CLI
- Tests
- Documentation

## Development Status

### Foundation

- [x] Sprint 1 – Project Foundation
- [x] Python project structure
- [x] SQLite
- [x] CLI
- [x] CSV export
- [x] Test framework

### Collector Framework

- [x] Sprint 2.1
- [x] Collector Protocol
- [x] Registry
- [x] Plugin architecture

### Domain Model

- [x] Sprint 2.2
- [x] AtlasFeature
- [x] Geometry
- [x] TimeSpan
- [x] Provenance
- [x] Confidence
- [x] LicenseInfo

### Web

- [x] Sprint 2.3
- [x] First web interface

### User Experience

- [x] Sprint 2.4
- [x] Marker clustering
- [x] Filters and improved search
- [x] My Location
- [x] Favorites and recent history
- [x] Light and dark mode
- [x] Mobile UI
- [x] Demo dataset

### Data Source Evaluation

- [x] Sprint 2.5
- [x] Official API evaluation
- [x] Licensing review
- [x] AtlasFeature compatibility review
- [x] Architecture recommendations

Recommended first Collector: **RAÄ Kulturmiljöregistret (KMR)**.

Second choice: **RAÄ K-samsök**.

Lantmäteriets Historical Maps is postponed until an official machine-readable
API becomes available.

## Future Roadmap

### Sprint 2.7 – SGU

- Geological context

### Sprint 2.8 – Historical Maps

Only if an official machine-readable API becomes available.

### Sprint 2.9 – OpenStreetMap Collector

- Historic bridges
- Historic ferries
- Harbours
- Mills
- Locks

### Sprint 3.0 – Advanced Map Layers

- Multiple overlays
- Layer manager
- Offline cache

### Sprint 3.5 – Search Engine

- Ranking
- Combined searches
- Better filtering

### Sprint 4.0 – AI Assistant

Only after the data model, Collectors and APIs are stable. AI must never invent
historical facts.

### Version 1.0

A stable application capable of combining multiple official Swedish historical
datasets into one easy-to-use map without requiring GIS knowledge.

## Version History

- **v0.1.0-alpha:** Project Foundation
- **v0.2.0-alpha:** Collector Framework
- **v0.3.0-alpha:** AtlasFeature
- **v0.4.0-alpha:** Web Experience
- **v0.5.0-alpha:** Official Data Source Evaluation
- **v0.6.0-alpha:** First Official Collector (planned)

## Quality Rules

Every sprint must finish with:

```text
pytest
ruff check .
black --check .
git diff --check
```

No TODOs, no FIXMEs and no broken tests may remain at sprint completion.

## Current Architecture

```text
Foundation
    ↓
Collector Framework
    ↓
AtlasFeature
    ↓
Collectors
    ↓
Repository
    ↓
Export
    ↓
Web
```

## Milestones

- Foundation completed
- Collector Framework completed
- AtlasFeature completed
- Web Interface completed
- UX completed
- Official Data Source Evaluation completed
- First Official Collector (planned)
