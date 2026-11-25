#!/usr/bin/env python3
"""Read-only public-origin smoke test for an ASHUR dashboard deployment.

Usage:
    python scripts/dashboard_runtime_smoke.py https://dashboard.example.com

The script sends GET requests plus one deliberately rejected POST and one
rejected cross-origin GET. It never sends credentials or mutating requests.
"""
from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

STRATEGY_IDS = {
    "BNB_15M_EMA_TREND",
    "BNB_1D_DONCHIAN55",
    "BNB_1H_DONCHIAN_ADX25",
    "BNB_4H_ADX_TREND",
    "BNB_4H_KELTNER_ADX",
    "SOL_4H_DONCHIAN_VOL",
}


class SmokeFailure(RuntimeError):
    pass


def request(base: str, path: str, *, method: str = "GET", origin: str | None = None):
    headers = {"Accept": "application/json"}
    if origin:
        headers["Origin"] = origin
    req = Request(base + path, headers=headers, method=method)
    try:
        with urlopen(req, timeout=12) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def json_body(body: bytes, label: str) -> dict:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmokeFailure(f"{label}: response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise SmokeFailure(f"{label}: expected a JSON object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/dashboard_runtime_smoke.py https://dashboard.example.com")
        return 2

    parsed = urlsplit(sys.argv[1].rstrip("/"))
    require(parsed.scheme == "https", "Refusing non-HTTPS URL; public dashboard must use HTTPS")
    require(bool(parsed.netloc) and not parsed.username and not parsed.password,
            "Provide a valid HTTPS origin without embedded credentials")
    require(not parsed.query and not parsed.fragment and parsed.path in ("", "/"),
            "Provide only the dashboard origin, without path/query/fragment")
    base = f"https://{parsed.netloc}"

    try:
        status, headers, body = request(base, "/healthz")
        require(status == 200, f"/healthz returned HTTP {status}")
        require(json_body(body, "/healthz").get("status") == "ok", "/healthz payload mismatch")
        require(headers.get("Cache-Control", "").startswith("no-store"),
                "/healthz is missing no-store cache policy")
        print("PASS HTTPS health endpoint")

        status, headers, body = request(base, "/api/dashboard/v1/status")
        require(status == 200, f"status API returned HTTP {status}; runtime data may be stale/unavailable")
        payload = json_body(body, "status API")
        require(payload.get("mode") == "PAPER_ONLY", "status API is not PAPER_ONLY")
        require(payload.get("freshness") == "FRESH", "worker status is not FRESH")
        accounts = payload.get("accounts")
        require(isinstance(accounts, list) and len(accounts) == 6,
                "status API must expose exactly six strategy accounts")
        ids = [item.get("strategy_id") for item in accounts if isinstance(item, dict)]
        require(len(ids) == 6 and set(ids) == STRATEGY_IDS,
                "status API strategy IDs do not match the approved six-strategy baseline")
        require(headers.get("Cache-Control", "").startswith("no-store"),
                "status API is missing no-store cache policy")
        health = payload.get("worker_health")
        require(isinstance(health, dict), "worker health block is missing")
        print("PASS fresh PAPER_ONLY status and six-strategy contract")

        status, _, body = request(base, "/api/dashboard/v1/history?days=1")
        require(status in (200, 503), f"history API returned unexpected HTTP {status}")
        history = json_body(body, "history API")
        if status == 200:
            require(history.get("timezone") == "UTC", "history timezone must be UTC")
            require(history.get("range_days") == 1, "history range contract mismatch")
            print("PASS observed history endpoint")
        else:
            require(history.get("status") == "HISTORY_UNAVAILABLE",
                    "history 503 did not use the documented unavailable state")
            print("PASS explicit history-not-yet-available state")

        status, _, body = request(base, "/api/dashboard/v1/status", method="POST")
        require(status == 405, f"POST must be rejected with HTTP 405, got {status}")
        require(json_body(body, "POST rejection").get("status") == "METHOD_NOT_ALLOWED",
                "POST rejection payload mismatch")
        print("PASS write methods rejected")

        status, _, body = request(
            base, "/healthz", origin="https://ashur-smoke-test.invalid"
        )
        require(status == 403, f"untrusted Origin must be rejected with HTTP 403, got {status}")
        require(json_body(body, "Origin rejection").get("status") == "FORBIDDEN",
                "Origin rejection payload mismatch")
        print("PASS untrusted Origin rejected")

    except (SmokeFailure, URLError, TimeoutError, OSError) as exc:
        print(f"FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("RESULT: all public-origin dashboard smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
