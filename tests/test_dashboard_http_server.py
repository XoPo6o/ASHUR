import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from dashboard import http_server
from dashboard.read_model import BASELINE_ID, STRATEGY_IDS


class DashboardHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.status_file = self.directory / "ashur_shadow_status.json"
        self.preview_file = self.directory / "wall-preview.html"
        self.preview_file.write_text("<h1>ASHUR TEST PREVIEW</h1>", encoding="utf-8")
        self.now = datetime.now(timezone.utc)
        self.raw = {
            "updated_at": self.now.isoformat(),
            "mode": "PAPER_ONLY",
            "experiment": {
                "baseline_id": BASELINE_ID,
                "baseline_at": self.now.isoformat(),
                "starting_equity_per_strategy": 1000,
                "strategy_count": 6,
                "private_path": "/must/not/leak",
            },
            "worker_health": {
                "strategy_count": 6,
                "successful_strategies": 6,
                "error_count": 0,
                "intrabar_data_warnings_24h": 0,
                "all_strategies_ok": True,
                "protection_degraded_positions": 0,
                "protection_degraded_strategies": 0,
                "all_protections_ok": True,
            },
            "accounts": [],
            "secret": "must-not-leak",
        }
        for strategy_id in sorted(STRATEGY_IDS):
            self.raw["accounts"].append({
                "strategy_id": strategy_id,
                "label": strategy_id,
                "symbol": "BNB/USDT",
                "timeframe": "4h",
                "grade": "TEST",
                "protection_status": "NOT_REQUIRED",
                "starting_cash": 1000,
                "cash": 1000,
                "equity": 1000,
                "net_pnl": 0,
                "realized_pnl": 0,
                "unrealized_pnl": 0,
                "return_pct": 0,
                "trades": 0,
                "wins": 0,
                "win_rate_pct": 0,
                "profit_factor": None,
                "fees": 0,
                "last_price": None,
                "last_price_at": None,
                "position": None,
                "recent_trades_30d": [],
                "exchange_key": "must-not-leak",
            })
        self.status_file.write_text(json.dumps(self.raw), encoding="utf-8")
        self.old_status_file = http_server.STATUS_FILE
        self.old_preview_file = http_server.PREVIEW_FILE
        http_server.STATUS_FILE = self.status_file
        http_server.PREVIEW_FILE = self.preview_file
        self.server = http_server.make_server()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        http_server.STATUS_FILE = self.old_status_file
        http_server.PREVIEW_FILE = self.old_preview_file
        self.temp.cleanup()

    def request(self, path, method="GET", origin=None):
        headers = {}
        if origin:
            headers["Origin"] = origin
        req = Request(self.base_url + path, headers=headers, method=method)
        return urlopen(req, timeout=3)

    def test_status_is_sanitized_and_not_cached(self):
        with self.request("/api/dashboard/v1/status") as response:
            payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")
        self.assertEqual(payload["mode"], "PAPER_ONLY")
        self.assertEqual(payload["portfolio"]["equity"], 6000)
        self.assertNotIn("secret", payload)
        self.assertNotIn("private_path", payload["experiment"])
        self.assertNotIn("exchange_key", payload["accounts"][0])

    def test_preview_and_health_routes(self):
        with self.request("/") as response:
            self.assertIn(b"ASHUR TEST PREVIEW", response.read())
            self.assertTrue(response.headers["Content-Type"].startswith("text/html"))
        with self.request("/healthz") as response:
            self.assertEqual(json.loads(response.read()), {"status": "ok"})

    def test_invalid_source_is_unavailable_not_stale_data(self):
        self.raw["mode"] = "LIVE"
        self.status_file.write_text(json.dumps(self.raw), encoding="utf-8")
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/dashboard/v1/status")
        self.assertEqual(caught.exception.code, 503)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual(payload["status"], "UNAVAILABLE")
        self.assertNotIn("private_path", json.dumps(payload))

    def test_same_origin_request_is_allowed_without_cors_configuration(self):
        origin = self.base_url
        with self.request("/healthz", origin=origin) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], origin)

    def test_origin_allowlist_and_method_restriction(self):
        with patch.dict(os.environ, {"ASHUR_DASHBOARD_ALLOWED_ORIGINS": "https://ashur.example"}):
            with self.request("/healthz", origin="https://ashur.example") as response:
                self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://ashur.example")
            with self.assertRaises(HTTPError) as caught:
                self.request("/healthz", origin="https://evil.example")
            self.assertEqual(caught.exception.code, 403)
        with self.assertRaises(HTTPError) as caught:
            self.request("/api/dashboard/v1/status", method="POST")
        self.assertEqual(caught.exception.code, 405)


if __name__ == "__main__":
    unittest.main()
