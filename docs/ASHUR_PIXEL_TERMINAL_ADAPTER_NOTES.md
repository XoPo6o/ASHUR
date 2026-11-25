# Runtime adapter implementation notes

Status: read-model implementation started on `ashur-pixel-terminal-ui`.
Runtime source audited: `trading-lab/live_shadow_worker.py` on `ashur-live-shadow`.

## Confirmed worker export shape

The worker writes one JSON object with:
- `updated_at`, `mode`, `experiment` (`baseline_id`, `baseline_at`, `starting_equity_per_strategy`, `strategy_count`);
- `worker_health` (strategy count, successful strategies, errors, intrabar warnings, protection counters/flags);
- `accounts[]` with identity, timeframe, grade, cash/equity/P&L/return, trades/wins/win_rate_pct/profit_factor/fees, recent_trades_30d, last_price/last_price_at, position and protection status.

Important corrections to the initial draft:
1. The source timestamp field is `updated_at`, not `source_updated_at`.
2. The worker has no portfolio aggregate; it must be derived from the six accounts.
3. A zero-trade account is exported with `win_rate_pct: 0`; the dashboard read model converts this to `null` so the UI can say “Not enough data”, not imply a measured 0% win rate.
4. Profit Factor may be a number, `null`, or the string `"inf"`; preserve and label this explicitly.
5. The worker's `recent_trades_30d` rows contain only the documented trade fields; the adapter uses an allowlist rather than forwarding arbitrary source keys.

## Implemented read-model boundary

`dashboard/read_model.py` is a pure standard-library projection:
- no filesystem, SQLite, network, environment, credentials, or write operations;
- strict PAPER_ONLY, baseline, six-account and 1,000 USDT-per-account checks;
- timezone-aware timestamps and 10/20-minute FRESH/STALE/OFFLINE policy;
- rejects OFFLINE/missing/invalid source instead of serving stale values as current;
- returns only an explicit allowlist of dashboard fields;
- derives portfolio aggregates from the six account records.

This read model now has a standard-library HTTP adapter in `dashboard/http_server.py`. The adapter serves `wall-preview.html` at `/`, a minimal `/healthz`, and the sanitized projection at `GET /api/dashboard/v1/status`. It reads only the active worker's `ashur_shadow_status.json`; it never exposes the raw file, the worker SQLite database, arbitrary filesystem paths, or write operations. The response is `no-store`, bounded to a 2 MB source file, and rejects unavailable/offline data rather than presenting stale values as current.

`trading-lab/ashur_supervisor.py` starts the HTTP listener in a daemon thread only when the host provides `SERVER_PORT`; it binds to `0.0.0.0` as required by Silly Development. Missing/invalid port or listener startup failure is logged and does not stop the Paper/Shadow supervisor. Same-origin requests are accepted; cross-origin requests require an exact comma-separated `ASHUR_DASHBOARD_ALLOWED_ORIGINS` entry. No wildcard CORS is used.

The endpoint is implemented only on `ashur-pixel-terminal-ui` and is not deployed. Silly Development exposes app ports over plain HTTP and does not provide TLS; production browser access from an HTTPS website therefore still requires a verified HTTPS tunnel/reverse proxy or another HTTPS server-side origin. Live host verification, history collection, automated test execution and UI data wiring remain open tasks.
