# ASHUR intrabar protection (Paper/Shadow)

This document describes the fail-safe protection path used by the six-strategy
ASHUR runtime on the `ashur-live-shadow` branch.

## Minute cursor and history

- `shadow_intrabar_state.last_checked_open_ms` stores the last fully closed
  one-minute candle open time.
- A new position starts with the previous fully closed minute as its cursor,
  so the first minute after entry is not silently skipped.
- The worker backfills every closed one-minute candle after the cursor.
  Requests are paginated in bounded windows; Bybit is primary and Binance
  public market data is the fallback.
- The reconstructed sequence must start at the exact expected minute and be
  continuous, ordered, valid, and closed.
- The maximum reconstructable outage window is seven days. A longer gap is
  treated as unrecoverable rather than silently advancing the cursor.

## Fail-safe behavior

If an open position has no cursor, the minute history cannot be reconstructed,
either market-data source fails, or candle continuity validation fails:

1. The Paper position is closed at the current validated ticker mark using the
   configured Paper slippage and fee model.
2. The event ledger records `INTRABAR_DATA_WARNING` and
   `PROTECTION_GAP_FAILSAFE`.
3. The strategy's protection health stores the error and keeps its entry
   circuit breaker active.
4. No new position is opened while the circuit breaker is active.
5. The worker probes a fresh closed one-minute candle. A successful recovery
   clears the error, but entry is deferred until the next worker cycle.

A strategy with no recent successful minute-feed validation must also probe
before opening its first Paper position. A successful validation expires after
240 seconds and must be refreshed before another entry.

## Runtime status and monitoring

The exported status includes:

- `worker_health.all_protections_ok`
- `protection_degraded_positions`
- `protection_degraded_strategies`
- per-account `protection_status`
- per-position `protection_status`, `last_intrabar_success_at`, and
  `last_intrabar_error`

The SillyDev deployment monitor must reject a runtime status that reports a
degraded protection state, a position without `protection_status=OK`, an
unhealthy strategy, a stale heartbeat, or a mode other than `PAPER_ONLY`.

## Important limitation

`PROTECTION_GAP_FAILSAFE` is a conservative simulation close at the current
validated ticker mark. It is not a historical exchange fill and is not an
exchange-native stop order. This runtime remains Paper/Shadow only; no real
orders are sent.
