"""Small read-only HTTP surface for the ASHUR Paper/Shadow dashboard.

The server exposes only the dashboard HTML and a validated, allowlisted JSON
projection. It never serves the worker data directory, SQLite database, secrets,
or arbitrary filesystem paths.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from dashboard.read_model import StatusUnavailable, project_status

ROOT = Path(__file__).resolve().parents[1]
PREVIEW_FILE = ROOT / "wall-preview.html"
DATA_DIR = Path(os.environ.get("ASHUR_DATA_DIR", str(Path.home() / ".local" / "share" / "ashur")))
STATUS_FILE = DATA_DIR / "ashur_shadow_status.json"
MAX_STATUS_BYTES = 2_000_000


def _allowed_origins() -> set[str]:
    raw = os.environ.get("ASHUR_DASHBOARD_ALLOWED_ORIGINS", "")
    return {item.strip().rstrip("/") for item in raw.split(",") if item.strip()}


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "ASHUR-Dashboard"
    sys_version = ""

    def log_message(self, fmt, *args):
        # Avoid logging request query strings or user-supplied header values.
        print(f"ASHUR_DASHBOARD_HTTP {self.command} {self.path.split('?')[0]}")

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        normalized = origin.rstrip("/")
        if normalized in _allowed_origins():
            return True
        # The dashboard and API are served from this same listener by default.
        # Accept either scheme for the exact Host so an HTTPS tunnel/reverse proxy
        # can preserve same-origin requests without opening CORS to other sites.
        host = self.headers.get("Host", "").lower()
        return bool(host) and normalized in {f"http://{host}", f"https://{host}"}

    def _send(self, status: int, body: bytes, content_type: str, origin: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if origin and self._origin_ok():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict, origin: str | None = None):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", origin)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if not self._origin_ok():
            self._json(403, {"status": "FORBIDDEN", "message": "Origin is not allowed."})
            return
        self.send_response(204)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Allow", "GET, OPTIONS")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Accept")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        origin = self.headers.get("Origin")
        if not self._origin_ok():
            self._json(403, {"status": "FORBIDDEN", "message": "Origin is not allowed."})
            return

        path = urlsplit(self.path).path
        if path in ("/", "/wall-preview.html"):
            try:
                body = PREVIEW_FILE.read_bytes()
            except OSError:
                self._json(503, {"status": "UNAVAILABLE", "message": "Dashboard page is unavailable."}, origin)
                return
            self._send(200, body, "text/html; charset=utf-8", origin)
            return

        if path == "/healthz":
            self._json(200, {"status": "ok"}, origin)
            return

        if path != "/api/dashboard/v1/status":
            self._json(404, {"status": "NOT_FOUND"}, origin)
            return

        try:
            size = STATUS_FILE.stat().st_size
            if size <= 0 or size > MAX_STATUS_BYTES:
                raise StatusUnavailable("status file size outside allowed bounds")
            raw = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            result = project_status(raw)
        except (OSError, ValueError, json.JSONDecodeError, StatusUnavailable) as exc:
            print(f"ASHUR_DASHBOARD_STATUS_UNAVAILABLE reason={type(exc).__name__}")
            self._json(503, {
                "status": "UNAVAILABLE",
                "message": "Paper/Shadow status is unavailable or stale.",
            }, origin)
            return
        except Exception as exc:
            print(f"ASHUR_DASHBOARD_ADAPTER_ERROR reason={type(exc).__name__}")
            self._json(500, {
                "status": "ERROR",
                "message": "Dashboard status could not be processed.",
            }, origin)
            return

        self._json(200, result, origin)

    def do_POST(self):
        self._json(405, {"status": "METHOD_NOT_ALLOWED", "allowed": ["GET", "OPTIONS"]})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST


class DashboardHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(host: str = "127.0.0.1", port: int = 0) -> DashboardHTTPServer:
    """Create a server instance; port=0 is useful for isolated tests."""
    return DashboardHTTPServer((host, port), DashboardRequestHandler)


def start_dashboard_server(log=print):
    """Start the dashboard listener when the host provides SERVER_PORT.

    The listener runs in a daemon thread and does not block the trading supervisor.
    If no port is configured or binding fails, Paper/Shadow supervision continues.
    """
    raw_port = os.environ.get("SERVER_PORT")
    if not raw_port:
        log("DASHBOARD_HTTP_DISABLED reason=SERVER_PORT_not_set")
        return None
    try:
        port = int(raw_port)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        log("DASHBOARD_HTTP_DISABLED reason=invalid_SERVER_PORT")
        return None

    try:
        server = make_server("0.0.0.0", port)
    except OSError as exc:
        log(f"DASHBOARD_HTTP_START_FAILED reason={type(exc).__name__}")
        return None

    thread = Thread(target=server.serve_forever, name="ashur-dashboard-http", daemon=True)
    thread.start()
    log(f"DASHBOARD_HTTP_READY host=0.0.0.0 port={port} routes=/,/api/dashboard/v1/status,/healthz")
    return server
