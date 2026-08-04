"""Small localhost HTTP server for the MagnetAtlas map interface."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import urlsplit

from magnetatlas.application.features import FeatureCatalog
from magnetatlas.interfaces.web.serializers import serialize_feature_collection

LOGGER = logging.getLogger(__name__)

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


def make_handler(catalog: FeatureCatalog) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to one immutable feature catalog."""

    class MagnetAtlasRequestHandler(BaseHTTPRequestHandler):
        server_version = "MagnetAtlas/0.1"

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

        def _route(self) -> None:
            path = urlsplit(self.path).path
            if path in STATIC_FILES:
                filename, content_type = STATIC_FILES[path]
                self._send(HTTPStatus.OK, content_type, _static_content(filename))
                return
            if path == "/api/features":
                body = json.dumps(
                    serialize_feature_collection(catalog),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                self._send(HTTPStatus.OK, "application/geo+json; charset=utf-8", body)
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
            """Reject writes because the first web interface is read-only."""
            self._send(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "application/json; charset=utf-8",
                b'{"error":"method_not_allowed"}',
            )

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.debug("Web request: " + format, *args)

    return MagnetAtlasRequestHandler


def create_server(
    catalog: FeatureCatalog,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    """Create a local threaded HTTP server without starting its event loop."""
    return ThreadingHTTPServer((host, port), make_handler(catalog))
