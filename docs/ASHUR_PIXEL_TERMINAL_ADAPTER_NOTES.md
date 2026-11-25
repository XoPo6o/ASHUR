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

This is not yet an HTTP endpoint and is not deployed. A trusted server-side host must call it after securely obtaining the status JSON. Do not point the browser at the SillyDev panel file API and do not publish raw status JSON. The hosting decision and authenticated server-side retrieval remain separate deployment tasks.
