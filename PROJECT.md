# MagnetAtlas Sverige – Project Overview

Last updated: **2026-08-07**

Current version: **v1.4.0-alpha**

Current sprint: **Sprint 3.5b – Lantmäteriet Ortnamn Download (completed)**

Validation release: **Sprint 2.6.1 – Real World Validation (completed)**

Public alpha release: **Sprint 2.6.2 – Polish & Public Alpha (completed)**

Real user release: **Sprint 2.6.3 – First Real User Experience (completed)**

First real dataset: **Sprint 2.6.4 – First Real RAÄ Dataset (completed)**

## Project Status

Current Version: **v1.4.0-alpha**

The runnable alpha currently contains the project foundation, Collector
Framework, shared domain model, local web interface and user-experience
improvements. RAÄ Kulturmiljöregistret is the first implemented official
Collector, with local SQLite persistence and incremental synchronization.

Sprint 2.6.2 aligns package metadata with v0.6.0-alpha, polishes the responsive
map interface and provides concise Swedish errors for network, GPS, local data
and database failures.

Sprint 2.6.4 verifies the complete official RAÄ GeoPackage-to-SQLite chain
against the current municipality schema. The web interface uses imported RAÄ
features exclusively whenever the local cache contains real data and reports
dataset count, source, latest import and Demo/RAÄ status.

Sprint 2.7 replaces full in-memory base imports with bounded GeoPackage batches
and an isolated SQLite staging dataset. The previous cache remains active until
the final atomic activation and is preserved if any batch fails.

Sprint 2.8 removes global SQLite materialization from the web composition root.
The map requests bounded GeoJSON for its current viewport, dataset metadata is
served separately and complete feature details are loaded only when selected.

Sprint 2.9 adds additive query projections, RTree spatial lookup, FTS5 search
and measured SQLite indexes. Viewport queries now start in RTree instead of
scanning every stored feature document, while base and incremental writes keep
all indexes synchronized in batches.

Sprint 3.0 validates the complete nationwide RAÄ chain with 838,178 normalized
features. Country, county and municipality scopes are explicit, nationwide
imports are protected by a free-space preflight, and bounded web queries have
been measured against the full local dataset.

Sprint 3.1 separates source definitions, imported dataset instances and
geographical scopes. Every new import has a deterministic identity, active
instances are tracked per source and incremental deletions use indexed source
identities without loading the complete dataset. Collector capabilities and web
source properties are now source-neutral while the ArchiveRecord path remains
explicitly marked as the compatibility generation.

Sprint 3.2 adds a source-neutral `LayerDefinition`, runtime `LayerRegistry` and
dataset-aware `LayerService`. The local web API exposes eleven declarative
layers and the layer panel can toggle the currently implemented cultural
heritage layer without changing imported data.

Sprint 3.3 validates the provider architecture with SGU. A configurable SGU
provider reads the documented OGC API Features contract, maps Jordarter to
`AtlasFeature` with CC0 provenance and imports independent dataset instances.
The existing layer API discovers and activates SGU Jordarter without changes to
LayerRegistry, LayerService, DatasetInstance or the frontend.

Sprint 3.5b implements the first Lantmäteriet dataset without changing those
shared components. Ortnamn Nedladdning is discovered through the official STAC
vector catalogue, downloaded as a reproducible GeoPackage snapshot and streamed
into independent country or bbox dataset instances.

## Current Sprint

### Sprint 2.6 – First Official Collector

Goal: implement the first real Collector using an official Swedish data source.

Target: RAÄ Kulturmiljöregistret (KMR).

Completed deliverables:

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
- [x] GPS-noggrannhet, centrering och valfritt följläge
- [x] Tydliga laddnings-, tom- och feltillstånd
- [x] Kompletta spårbara kartpopuper
- [x] Förindexerad lokal sökning för större dataset
- [x] Public-alpha polish for phone, tablet and desktop
- [x] Swedish user-facing errors for offline, timeout and corrupt cache cases
- [x] Imported RAÄ data preferred over synthetic demo data
- [x] Previously granted GPS start and nearest-object list
- [x] Compact popup with complete details in the information panel
- [x] Faster RAÄ-ID, place, municipality and object-type discovery
- [x] Current official RAÄ municipality GeoPackage schema verified end to end
- [x] Dataset count, source, latest import and Demo/RAÄ status in the web view

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

### Sprint 2.7 – Streaming Import

- [x] Bounded RAÄ GeoPackage batches
- [x] Incremental SQLite staging writes
- [x] Atomic activation and rollback
- [x] Import progress and elapsed time

### Sprint 2.8 – Viewport API

- [x] Bounding-box API
- [x] Bounded compact GeoJSON responses
- [x] Separate dataset metadata
- [x] On-demand feature details
- [x] Debounced and cancellable client viewport requests
- [x] No global SQLite materialization at server start

### Sprint 2.9 – SQLite Optimization

- [x] RTree-indexed viewport queries
- [x] FTS5-indexed text candidates
- [x] Source, source-ID, feature-type and search indexes
- [x] Batch migration of existing JSON documents
- [x] Batched SQLite insert/upsert
- [x] EXPLAIN QUERY PLAN regression tests
- [x] Before/after benchmarks

### Sprint 3.0 – Nationwide RAÄ

- [x] Explicit Sweden, county and municipality imports
- [x] Nationwide import and web benchmarks
- [x] Memory, storage and latency validation

New data sources and map layers are postponed until the nationwide RAÄ chain
meets its scalability targets.

### Sprint 3.1 – Multi-source Foundation

- [x] Source, dataset instance and geographic scope identities
- [x] Country, county, municipality and bbox dataset scopes
- [x] Indexed incremental synchronization by source identity
- [x] Dataset-aware metadata, active cache status and instance discovery
- [x] One capability-based Collector foundation
- [x] Explicit ArchiveRecord-to-AtlasFeature migration path
- [x] Source-neutral API metadata and `source_properties`

### Sprint 3.2 – Layer Engine

- [x] Source-neutral layer definitions and runtime visibility state
- [x] Dataset-aware feature filtering through active layers
- [x] Registration, support discovery, enable and disable operations
- [x] Generic layer API and web layer panel
- [x] Eleven declarative product layers, with one currently available

### Sprint 3.3 – Offline Packages

Superseded by **Sprint 3.3 – First Additional Official Data Source (SGU)**:

- [x] Configurable SGU provider and Jordarter dataset definition
- [x] OGC API Features Collector with bounded pagination
- [x] AtlasFeature mapping with SGU provenance, CC0 and confidence
- [x] Country and bbox imports; named scopes preserve an explicit bbox parent
- [x] SGU Jordarter activated through the existing layer catalogue

Offline Packages moves to a later sprint.

Previous scope:

- Versioned and checksummed regional data packages
- Atomic installation, update and removal
- Local application assets and licensed offline-basemap contract

### Sprint 3.4 – Second Official Data Source

- Implement one separately evaluated official Swedish data source
- Validate Collector, dataset, layer, attribution and offline contracts
- Verify combined RAÄ and second-source map behavior end to end

### Sprint 3.5 – Mobile Foundation

- Installable PWA application shell
- Mobile-first layer, search and offline flows
- Native-shell validation with local SQLite and regional packages

### Sprint 4.0 – Explainable AI Assistant

Only after the multi-source model, Layer Engine, offline contract, second
official source and mobile foundation are stable. Every answer must be grounded
in displayed source data and provenance; AI must never invent historical facts.

### Version 1.0

A stable application capable of combining multiple official Swedish historical
datasets into one easy-to-use map without requiring GIS knowledge.

## Version History

- **v0.1.0-alpha:** Project Foundation
- **v0.2.0-alpha:** Collector Framework
- **v0.3.0-alpha:** AtlasFeature
- **v0.4.0-alpha:** Web Experience
- **v0.5.0-alpha:** Official Data Source Evaluation
- **v0.6.0-alpha:** First Official Collector

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
- First Official Collector completed
- Real World Validation completed
- Public Alpha polish completed
