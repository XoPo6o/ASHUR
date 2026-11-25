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
The current status export is a current-state projection; it does not provide a complete historical equity time series. The dashboard therefore uses a separate append-only dashboard history store, isolated from the trading database:
- `dashboard/history_store.py` polls the worker status JSON every 30 seconds and validates it through the strict read model;
- only FRESH observations are stored, one per unique worker `updated_at` timestamp;
- portfolio and six per-account snapshots are written transactionally to `ashur_dashboard_history.sqlite3` under `ASHUR_DATA_DIR`;
- the dashboard API reads the history store in SQLite read-only mode and returns portfolio/per-strategy time series, running-high-water drawdown and UTC daily intraday summaries;
- the collector runs as an independent supervisor thread and does not depend on the HTTP listener.

The collector may read the worker status file, but it must not write to the trading DB or change strategy state. History is append-only at the application layer; no pruning is currently performed. Backup/retention policy must be specified before deployment.

## Aggregation rules
- Portfolio equity = sum of six account equities.
- Portfolio starting equity = 6,000 USDT.
- Net P&L since baseline = portfolio equity - 6,000 USDT.
- Return % = net P&L / 6,000 * 100.
- Closed trades = sum of per-account closed trade counts.
- Realized P&L, unrealized P&L and fees = sums of per-account values.
- Win rate = total wins / total closed trades; if there are no closed trades, return null and render “Not enough data”.
- Profit Factor = total gross profit / absolute total gross loss; if there are no losses or no trades, preserve null/inf semantics and render a clearly qualified state.
- Drawdown requires a chronological equity time series; the history API calculates percentage decline from the running portfolio-equity high-water mark.
- Daily intraday P&L is the last observed equity minus the first observed equity within each UTC date; realized P&L, closed trades and fees are also reported as deltas between those observations. Intraday drawdown is measured from that UTC day's observed equity high. At least two same-day observations are required before the UI reports daily metrics.
- Store canonical timestamps in UTC; let the UI display local time only as a presentation choice.

## Security and deployment
- The browser only receives the sanitized read-only projection.
- No API keys or server-panel credentials in HTML, JavaScript, query strings, or browser storage.
- If the site remains on GitHub Pages, the data adapter must live on a server-side origin with explicit CORS allowlisting and a read-only route; alternatively publish sanitized snapshots through a controlled server-side workflow. Do not expose the SillyDev panel file API directly to browsers.
- Use HTTPS, bounded response size, rate limiting and a strict allowlist of fields.
- The first prototype is static and intentionally does not make network requests.


## Implemented history API
`GET /api/dashboard/v1/history?days=30` supports 1, 7, 30 or 90 days. The response contains:
- `equity_curve[]`: UTC timestamp, portfolio equity, baseline-relative net P&L/return and running-high-water drawdown;
- `strategies[]`: six strategy IDs with their own timestamped equity/P&L/return points;
- `daily[]`: UTC date, first/last observed equity, intraday equity P&L/return, realized P&L delta, closed-trade delta, fees delta, intraday drawdown and observation count;
- summary values and total/sample point counts.

If no valid history exists, the API returns HTTP 503 with `HISTORY_UNAVAILABLE`; unsupported ranges return HTTP 400. The browser never receives a database path or raw SQLite content.
