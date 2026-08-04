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
        assert "Navigera hit" in html
        assert "maplibre-gl@5.24.0" in html
        assert "Content-Security-Policy" in response.headers

    with urlopen(f"{local_server}/static/app.js", timeout=2) as response:
        assert response.headers.get_content_type() == "text/javascript"
        javascript = response.read()
        assert b"maplibregl.Map" in javascript
        assert b"https://tile.openstreetmap.org/{z}/{x}/{y}.png" in javascript
        assert b"OpenStreetMap contributors" in javascript


def test_features_api_returns_geojson_without_raw_data(local_server: str) -> None:
    with urlopen(f"{local_server}/api/features", timeout=2) as response:
        payload = json.load(response)

    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 60
    assert "raw_data" not in json.dumps(payload)


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
