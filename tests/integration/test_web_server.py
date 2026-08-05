"""Network-isolated integration tests for the localhost web server."""

import json
import threading
from collections.abc import Iterator
from http import HTTPStatus
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from magnetatlas.application.features import FeatureCatalog
from magnetatlas.infrastructure.features import load_demo_features
from magnetatlas.interfaces.web.server import create_server


@pytest.fixture
def local_server() -> Iterator[str]:
    server = create_server(
        FeatureCatalog(load_demo_features()), host="127.0.0.1", port=0
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


def test_features_api_returns_geojson_without_raw_data(local_server: str) -> None:
    with urlopen(f"{local_server}/api/features", timeout=2) as response:
        payload = json.load(response)

    assert payload["type"] == "FeatureCollection"
    assert payload["is_demo"] is True
    assert payload["summary"]["status"] == "Demo"
    assert payload["summary"]["count"] == 100
    assert len(payload["features"]) == 100
    assert "raw_data" not in json.dumps(payload)


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
