"""Network-isolated integration tests for the localhost web server."""

import json
import threading
from collections.abc import Iterator
from http import HTTPStatus
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from magnetatlas.application.evidence import (
    EvidenceEngine,
    EvidenceReportService,
    EvidenceRuleRegistry,
    FeatureEvidenceRule,
)
from magnetatlas.application.evidence_rules import create_default_evidence_rules_library
from magnetatlas.application.feature_queries import CatalogFeatureQuerySource
from magnetatlas.application.layers import LayerFeatureQuerySource
from magnetatlas.domain.datasets import DatasetInstance, DatasetScope, SourceDefinition
from magnetatlas.domain.evidence_rules import EvidenceCategory
from magnetatlas.infrastructure.features import load_demo_features
from magnetatlas.interfaces.web.layers import create_layer_service
from magnetatlas.interfaces.web.server import create_server


@pytest.fixture
def local_server() -> Iterator[str]:
    instance = DatasetInstance.create(
        SourceDefinition("magnetatlas-demo", "MagnetAtlas demo"),
        DatasetScope.country("sweden"),
    )
    layer_service = create_layer_service((instance,))
    source = LayerFeatureQuerySource(
        CatalogFeatureQuerySource(load_demo_features()), layer_service, instance
    )
    evidence_service = EvidenceReportService(
        ((instance, CatalogFeatureQuerySource(load_demo_features())),),
        EvidenceEngine(EvidenceRuleRegistry((FeatureEvidenceRule(),))),
    )
    server = create_server(
        source,
        layer_service,
        evidence_service=evidence_service,
        rules_library=create_default_evidence_rules_library(),
        host="127.0.0.1",
        port=0,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_server_serves_html_static_assets_and_security_headers(
    local_server: str,
) -> None:
    with urlopen(f"{local_server}/", timeout=2) as response:
        html = response.read().decode("utf-8")
        assert response.status == HTTPStatus.OK
        assert response.headers.get_content_type() == "text/html"
        assert "MagnetAtlas" in html
        assert "feature-search" in html
        assert "type-filter" in html
        assert "period-filter" in html
        assert "source-filter" in html
        assert "favorite-button" in html
        assert "theme-button" in html
        assert "why-dialog" in html
        assert "center-location" in html
        assert "follow-location" in html
        assert "location-accuracy" in html
        assert "empty-state" in html
        assert "feature-provenance" in html
        assert "feature-coordinates" in html
        assert "nearest-content" in html
        assert "nearest-list" in html
        assert "demo-notice" in html
        assert "dataset-status" in html
        assert "dataset-count" in html
        assert "dataset-import" in html
        assert "dataset-source" in html
        assert "evidence-count" in html
        assert "evidence-list" in html
        assert "rules-count" in html
        assert "rules-list" in html
        assert "Varför visas denna plats?" in html
        assert "Navigera hit" in html
        assert "maplibre-gl@5.24.0" in html
        assert "Content-Security-Policy" in response.headers

    with urlopen(f"{local_server}/static/app.js", timeout=2) as response:
        assert response.headers.get_content_type() == "text/javascript"
        javascript = response.read()
        javascript_text = javascript.decode("utf-8")
        assert b"maplibregl.Map" in javascript
        assert b"https://tile.openstreetmap.org/{z}/{x}/{y}.png" in javascript
        assert b"OpenStreetMap contributors" in javascript
        assert b"cluster: true" in javascript
        assert b"navigator.geolocation.watchPosition" in javascript
        assert b"enableHighAccuracy: true" in javascript
        assert b"locationMarker" in javascript
        assert b"followLocation" in javascript
        assert b"startAtGrantedLocation" in javascript
        assert b"navigator.permissions.query" in javascript
        assert b"renderNearestFeatures" in javascript
        assert b"distanceKilometers" in javascript
        assert b"renderDatasetSummary" in javascript
        assert b"/api/dataset" in javascript
        assert b"/api/evidence-rules" in javascript
        assert b"viewportParameters" in javascript
        assert b"scheduleViewportLoad" in javascript
        assert b"AbortController" in javascript
        assert b"encodeURIComponent(featureId)" in javascript
        assert "Noggrannhet:" in javascript_text
        assert b"FullscreenControl" in javascript
        assert b"ScaleControl" in javascript
        assert b"localStorage" in javascript
        assert b"magnetatlas.favorites" in javascript
        assert b"magnetatlas.recents" in javascript
        assert b"magnetatlas.theme" in javascript
        assert b"getClusterExpansionZoom" in javascript
        assert b"showWhy" in javascript
        assert "Visa detaljer" in javascript_text
        assert "popup-history" not in javascript_text


def test_dataset_and_viewport_apis_are_separate_and_bounded(
    local_server: str,
) -> None:
    with urlopen(f"{local_server}/api/dataset", timeout=2) as response:
        dataset = json.load(response)
    with urlopen(
        f"{local_server}/api/features?bbox=10,55,25,70&limit=10", timeout=2
    ) as response:
        payload = json.load(response)

    assert dataset["is_demo"] is True
    assert dataset["status"] == "Demo"
    assert dataset["count"] == 100
    assert payload["type"] == "FeatureCollection"
    assert payload["summary"]["count"] == 10
    assert payload["summary"]["truncated"] is True
    assert len(payload["features"]) == 10
    assert "raw_data" not in json.dumps(payload)
    assert "description" not in payload["features"][0]["properties"]


def test_feature_details_are_loaded_on_demand(local_server: str) -> None:
    with urlopen(
        f"{local_server}/api/features?bbox=10,55,25,70&limit=1", timeout=2
    ) as response:
        feature_id = json.load(response)["features"][0]["id"]
    with urlopen(f"{local_server}/api/features/{feature_id}", timeout=2) as response:
        feature = json.load(response)

    assert feature["id"] == feature_id
    assert "description" in feature["properties"]
    assert "provenance" in feature["properties"]


def test_evidence_api_serves_reports_lists_and_traceable_items(
    local_server: str,
) -> None:
    query = "bbox=10,55,25,70&limit=10&area=test-area"
    with urlopen(f"{local_server}/api/evidence-report?{query}", timeout=2) as response:
        report = json.load(response)

    assert report["area"] == "test-area"
    assert report["evidence_count"] == 10
    assert report["confidence"] == "unknown"
    assert report["provenance"]
    assert all(item["feature_id"] for item in report["evidence"])
    assert all(item["provider"] for item in report["evidence"])

    evidence_id = report["evidence"][0]["id"]
    with urlopen(f"{local_server}/api/evidence/{evidence_id}", timeout=2) as response:
        evidence = json.load(response)
    assert evidence["id"] == evidence_id
    assert evidence["provenance"]["source_id"]

    with urlopen(f"{local_server}/api/evidence?{query}", timeout=2) as response:
        assert len(json.load(response)["evidence"]) == 10


def test_evidence_rule_api_exposes_metadata_categories_and_latest_rule(
    local_server: str,
) -> None:
    with urlopen(f"{local_server}/api/evidence-rules", timeout=2) as response:
        rules = json.load(response)["rules"]
    with urlopen(f"{local_server}/api/evidence-rules/bridge", timeout=2) as response:
        bridge = json.load(response)
    with urlopen(f"{local_server}/api/evidence-categories", timeout=2) as response:
        categories = json.load(response)["categories"]

    assert len(rules) == 6
    assert bridge["id"] == "bridge"
    assert bridge["version"] == "1.0.0"
    assert "implementation" not in bridge
    assert [item["id"] for item in categories] == [
        category.value for category in EvidenceCategory
    ]


def test_layer_api_lists_reads_disables_and_enables_layers(local_server: str) -> None:
    with urlopen(f"{local_server}/api/layers", timeout=2) as response:
        layers = json.load(response)["layers"]

    assert len(layers) == 14
    heritage = layers[0]
    assert heritage["id"] == "cultural-heritage"
    assert heritage["supported"] is True
    assert heritage["active"] is True
    assert heritage["layer_type"] == "vector"
    assert heritage["render_mode"] == "cluster"
    assert heritage["opacity"] == 1.0
    assert heritage["z_index"] == 10
    assert heritage["attribution"] == "Riksantikvarieämbetet KMR"
    assert all(not item["active"] for item in layers[1:])

    historical = next(item for item in layers if item["id"] == "historical-maps")
    assert historical["layer_type"] == "raster"
    assert historical["visible"] is False
    assert historical["enabled"] is False

    disable = Request(
        f"{local_server}/api/layers/cultural-heritage/disable",
        method="POST",
        data=b"",
    )
    with urlopen(disable, timeout=2) as response:
        assert json.load(response)["active"] is False
    with urlopen(
        f"{local_server}/api/features?bbox=10,55,25,70&limit=10", timeout=2
    ) as response:
        assert json.load(response)["features"] == []

    enable = Request(
        f"{local_server}/api/layers/cultural-heritage/enable",
        method="POST",
        data=b"",
    )
    with urlopen(enable, timeout=2) as response:
        assert json.load(response)["active"] is True
    with urlopen(f"{local_server}/api/layers/cultural-heritage", timeout=2) as response:
        assert json.load(response)["name"] == "Kulturhistoriska lämningar"


def test_layer_api_rejects_unknown_and_unavailable_layers(local_server: str) -> None:
    with pytest.raises(HTTPError) as missing:
        urlopen(f"{local_server}/api/layers/missing", timeout=2)
    assert missing.value.code == HTTPStatus.NOT_FOUND

    request = Request(
        f"{local_server}/api/layers/bridges/enable", method="POST", data=b""
    )
    with pytest.raises(HTTPError) as unavailable:
        urlopen(request, timeout=2)
    assert unavailable.value.code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    "query",
    ["", "?bbox=10,55,25", "?bbox=x,55,25,70", "?bbox=10,55,25,70&limit=5001"],
)
def test_viewport_api_rejects_unbounded_or_invalid_requests(
    local_server: str, query: str
) -> None:
    with pytest.raises(HTTPError) as error:
        urlopen(f"{local_server}/api/features{query}", timeout=2)

    assert error.value.code == HTTPStatus.BAD_REQUEST


def test_search_api_supports_typos_and_facets(local_server: str) -> None:
    with urlopen(
        f"{local_server}/api/search?q=historsk&type=bro&period=1800s"
        "&source=magnetatlas-demo",
        timeout=2,
    ) as response:
        payload = json.load(response)

    assert payload["features"]
    assert all(
        item["properties"]["feature_type"] == "bro" for item in payload["features"]
    )
    assert all(item["properties"]["period"] == "1800s" for item in payload["features"])


def test_health_unknown_route_and_read_only_behavior(local_server: str) -> None:
    with urlopen(f"{local_server}/health", timeout=2) as response:
        assert json.load(response) == {"status": "ok"}

    with pytest.raises(HTTPError) as not_found:
        urlopen(f"{local_server}/missing", timeout=2)
    assert not_found.value.code == HTTPStatus.NOT_FOUND

    request = Request(f"{local_server}/api/features", method="POST", data=b"{}")
    with pytest.raises(HTTPError) as method_not_allowed:
        urlopen(request, timeout=2)
    assert method_not_allowed.value.code == HTTPStatus.METHOD_NOT_ALLOWED
