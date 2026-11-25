# ASHUR Pixel Trading Terminal — read-only data contract

Status: draft for implementation.
Consumer: The Wall / Pixel Trading Terminal.
Producer: active Paper/Shadow worker status export.
Baseline: `ashur-paper-30d-2026-11-25-v2`.

## Source of truth
The active worker writes `ashur_shadow_status.json` to its persistent `DATA_DIR`. The worker builds it in `export_status()` from the active Paper/Shadow SQLite state.

The dashboard must NOT:
- read or write the worker SQLite database directly from the browser;
- use `trading-lab/ashur_shadow_status.json` from Git as a live source (the checked-in copy is stale);
- use the old `trading-lab/ashur_paper.db` / Streamlit MVP (it is a different 10,000 USDT single-account prototype);
- call exchange order endpoints or expose exchange credentials.

## Proposed browser-facing contract
A server-side read-only adapter should expose:

`GET /api/dashboard/v1/status`

The adapter reads the worker's current status file and returns a validated, sanitized JSON projection. It must never return filesystem paths, secrets, process environment, raw SQL, or write-capable operations.

Top-level response:
- `schema_version`: string, initially `1.0`
- `generated_at`: UTC ISO-8601 timestamp
- `source_updated_at`: original worker `updated_at`
- `mode`: must equal `PAPER_ONLY`
- `experiment`: `baseline_id`, `baseline_at`, `starting_equity_per_strategy`, `strategy_count`
- `portfolio`: derived aggregate equity, cash, realized P&L, unrealized P&L, net P&L, return percentage, trade count and fees
- `worker_health`: existing worker health projection
- `accounts`: six strategy account projections
- `recent_events`: sanitized, bounded event summaries (only if separately exposed by a trusted source)

Each account projection should preserve:
- `strategy_id`, `label`, `symbol`, `timeframe`, `grade`
- `starting_cash`, `cash`, `equity`, `net_pnl`, `realized_pnl`, `unrealized_pnl`, `return_pct`
- `trades`, `wins`, `win_rate_pct`, `profit_factor`, `fees`
- `last_price`, `last_price_at`, `position`, `recent_trades_30d`

## Validation and stale-data behavior
Reject or mark the response unavailable when:
- `mode` is not `PAPER_ONLY`;
- baseline ID does not match the active experiment;
- strategy count is not six or IDs are missing/duplicated;
- any account starting balance differs from 1,000 USDT;
- timestamp is malformed or materially in the future;
- status file cannot be read or JSON validation fails.

Freshness labels (initial proposal; confirm against measured production cadence):
- FRESH: source age up to 10 minutes;
- STALE: older than 10 minutes, keep last known values but show warning;
- OFFLINE: older than 20 minutes or missing, do not present old values as current.

The UI must show the source timestamp and freshness state. Never silently replace unavailable live values with prototype constants.

## History and daily reports
The current status export is a current-state projection; it does not provide a complete historical equity time series. The dashboard cannot truthfully draw a historical Equity Curve or Drawdown from one status JSON file.

Proposed solution: a separate append-only dashboard history store, isolated from the trading database:
- a collector reads and validates the worker status JSON at a safe interval;
- it writes portfolio and per-account equity snapshots to a separate `ashur_dashboard_history.sqlite`;
- it records daily aggregates and report-generation timestamps;
- the dashboard API reads this history store and returns time series for charts and date-filtered daily reports.

The collector may read the worker status file, but it must not write to the trading DB or change strategy state. Retention and backup policy must be specified before deployment.

## Aggregation rules
- Portfolio equity = sum of six account equities.
- Portfolio starting equity = 6,000 USDT.
- Net P&L since baseline = portfolio equity - 6,000 USDT.
- Return % = net P&L / 6,000 * 100.
- Closed trades = sum of per-account closed trade counts.
- Realized P&L, unrealized P&L and fees = sums of per-account values.
- Win rate = total wins / total closed trades; if there are no closed trades, return null and render “Not enough data”.
- Profit Factor = total gross profit / absolute total gross loss; if there are no losses or no trades, preserve null/inf semantics and render a clearly qualified state.
- Drawdown requires a chronological equity time series; do not infer it from current balance alone.
- Daily P&L should be baseline-relative and timezone-explicit. Store canonical timestamps in UTC; let the UI display local time only as a presentation choice.

## Security and deployment
- The browser only receives the sanitized read-only projection.
- No API keys or server-panel credentials in HTML, JavaScript, query strings, or browser storage.
- If the site remains on GitHub Pages, the data adapter must live on a server-side origin with explicit CORS allowlisting and a read-only route; alternatively publish sanitized snapshots through a controlled server-side workflow. Do not expose the SillyDev panel file API directly to browsers.
- Use HTTPS, bounded response size, rate limiting and a strict allowlist of fields.
- The first prototype is static and intentionally does not make network requests.
