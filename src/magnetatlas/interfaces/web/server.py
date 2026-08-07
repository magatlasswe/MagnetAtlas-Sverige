"""Small localhost HTTP server for the MagnetAtlas map interface."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, unquote, urlsplit

from magnetatlas.application.feature_queries import FeatureQuerySource
from magnetatlas.application.features import FeatureSearchFilters
from magnetatlas.application.layers import LayerService
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.interfaces.web.serializers import (
    serialize_dataset_summary,
    serialize_feature,
    serialize_layer,
    serialize_search_results,
    serialize_viewport,
)

LOGGER = logging.getLogger(__name__)
MAX_VIEWPORT_FEATURES = 5_000
DEFAULT_VIEWPORT_FEATURES = 2_000

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self' https://unpkg.com",
        "style-src 'self' 'unsafe-inline' https://unpkg.com",
        "img-src 'self' data: blob: https://tile.openstreetmap.org",
        "connect-src 'self' https://tile.openstreetmap.org",
        "worker-src blob:",
        "child-src blob:",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
    )
)


def _static_content(filename: str) -> bytes:
    return (
        resources.files("magnetatlas.interfaces.web")
        .joinpath("static", filename)
        .read_bytes()
    )


def _bounds(parameters: dict[str, list[str]]) -> BoundingBox:
    values = parameters.get("bbox", [""])[0].split(",")
    if len(values) != 4:
        raise ValueError("bbox ska anges som west,south,east,north")
    try:
        west, south, east, north = (float(value) for value in values)
    except ValueError as exc:
        raise ValueError("bbox måste innehålla numeriska koordinater") from exc
    return BoundingBox(west=west, south=south, east=east, north=north)


def _limit(parameters: dict[str, list[str]]) -> int:
    raw = parameters.get("limit", [str(DEFAULT_VIEWPORT_FEATURES)])[0]
    try:
        limit = int(raw)
    except ValueError as exc:
        raise ValueError("limit måste vara ett heltal") from exc
    if not 1 <= limit <= MAX_VIEWPORT_FEATURES:
        raise ValueError(f"limit måste vara mellan 1 och {MAX_VIEWPORT_FEATURES}")
    return limit


def make_handler(
    source: FeatureQuerySource, layer_service: LayerService
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to one bounded feature query source."""

    class MagnetAtlasRequestHandler(BaseHTTPRequestHandler):
        server_version = "MagnetAtlas/0.6"

        def _headers(self, status: HTTPStatus, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
            self.end_headers()

        def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
            self._headers(status, content_type, len(body))
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(
            self,
            status: HTTPStatus,
            payload: object,
            *,
            content_type: str = "application/json; charset=utf-8",
        ) -> None:
            body = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            self._send(status, content_type, body)

        def _route(self) -> None:
            parsed_url = urlsplit(self.path)
            path = parsed_url.path
            if path in STATIC_FILES:
                filename, content_type = STATIC_FILES[path]
                self._send(HTTPStatus.OK, content_type, _static_content(filename))
                return
            parameters = parse_qs(parsed_url.query)
            if path == "/api/dataset":
                self._json(HTTPStatus.OK, serialize_dataset_summary(source.summary()))
                return
            if path == "/api/layers":
                self._json(
                    HTTPStatus.OK,
                    {
                        "layers": [
                            serialize_layer(item)
                            for item in layer_service.list_layers()
                        ]
                    },
                )
                return
            if path.startswith("/api/layers/"):
                layer_id = unquote(path.removeprefix("/api/layers/"))
                try:
                    layer = layer_service.get_layer(layer_id)
                except KeyError:
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {"error": "not_found", "message": "Lagret hittades inte."},
                    )
                    return
                self._json(HTTPStatus.OK, serialize_layer(layer))
                return
            if path == "/api/features":
                try:
                    result = source.in_bounds(
                        _bounds(parameters), limit=_limit(parameters)
                    )
                except ValueError as exc:
                    self._json(
                        HTTPStatus.BAD_REQUEST,
                        {"error": "invalid_request", "message": str(exc)},
                    )
                    return
                self._json(
                    HTTPStatus.OK,
                    serialize_viewport(result),
                    content_type="application/geo+json; charset=utf-8",
                )
                return
            if path.startswith("/api/features/"):
                feature_id = unquote(path.removeprefix("/api/features/"))
                try:
                    feature = source.get(feature_id)
                except (KeyError, ValueError):
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {"error": "not_found", "message": "Objektet hittades inte."},
                    )
                    return
                self._json(
                    HTTPStatus.OK,
                    serialize_feature(feature),
                    content_type="application/geo+json; charset=utf-8",
                )
                return
            if path == "/api/search":
                filters = FeatureSearchFilters(
                    feature_types=frozenset(parameters.get("type", [])),
                    periods=frozenset(parameters.get("period", [])),
                    sources=frozenset(parameters.get("source", [])),
                )
                matches = source.search(
                    parameters.get("q", [""])[0], filters=filters, limit=100
                )
                self._json(
                    HTTPStatus.OK,
                    serialize_search_results(matches),
                    content_type="application/geo+json; charset=utf-8",
                )
                return
            if path == "/health":
                self._send(
                    HTTPStatus.OK,
                    "application/json; charset=utf-8",
                    b'{"status":"ok"}',
                )
                return
            self._send(
                HTTPStatus.NOT_FOUND,
                "application/json; charset=utf-8",
                b'{"error":"not_found"}',
            )

        def do_GET(self) -> None:
            """Serve a supported local resource."""
            self._route()

        def do_HEAD(self) -> None:
            """Serve headers for a supported local resource."""
            self._route()

        def do_POST(self) -> None:
            """Change process-local layer visibility through supported endpoints."""
            path = urlsplit(self.path).path
            if path.startswith("/api/layers/"):
                relative = path.removeprefix("/api/layers/")
                layer_id, separator, action = relative.rpartition("/")
                if separator and action in {"enable", "disable"}:
                    try:
                        status = (
                            layer_service.enable(unquote(layer_id))
                            if action == "enable"
                            else layer_service.disable(unquote(layer_id))
                        )
                    except KeyError:
                        self._json(
                            HTTPStatus.NOT_FOUND,
                            {"error": "not_found", "message": "Lagret hittades inte."},
                        )
                        return
                    except ValueError as exc:
                        self._json(
                            HTTPStatus.CONFLICT,
                            {"error": "layer_unavailable", "message": str(exc)},
                        )
                        return
                    self._json(HTTPStatus.OK, serialize_layer(status))
                    return
            self._send(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "application/json; charset=utf-8",
                b'{"error":"method_not_allowed"}',
            )

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.debug("Web request: " + format, *args)

    return MagnetAtlasRequestHandler


def create_server(
    source: FeatureQuerySource,
    layer_service: LayerService,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    """Create a local threaded HTTP server without starting its event loop."""
    return ThreadingHTTPServer((host, port), make_handler(source, layer_service))
