"""Strict, read-only projection of the ASHUR Paper/Shadow worker status export.

This module deliberately does not read SQLite, access the filesystem, or make network
requests. A trusted server-side caller must supply the worker JSON. Never import this
module into browser code or pass credentials through it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

BASELINE_ID = "ashur-paper-30d-2026-11-25-v2"
STARTING_CASH = 1000.0
STRATEGY_IDS = {
    "BNB_15M_EMA_TREND",
    "BNB_1D_DONCHIAN55",
    "BNB_1H_DONCHIAN_ADX25",
    "BNB_4H_ADX_TREND",
    "BNB_4H_KELTNER_ADX",
    "SOL_4H_DONCHIAN_VOL",
}
FRESH_SECONDS = 600
OFFLINE_SECONDS = 1200
MAX_FUTURE_SECONDS = 60


class StatusUnavailable(ValueError):
    """Raised when the source cannot safely be represented as current experiment data."""


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise StatusUnavailable(f"missing or invalid {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StatusUnavailable(f"malformed {field}") from exc
    if parsed.tzinfo is None:
        raise StatusUnavailable(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _number(value: Any, field: str, *, nullable: bool = False) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StatusUnavailable(f"invalid numeric field: {field}")
    result = float(value)
    if not isfinite(result):
        raise StatusUnavailable(f"non-finite numeric field: {field}")
    return result


def _safe_trade(trade: Mapping[str, Any]) -> dict[str, Any]:
    # Explicit allowlist: never forward arbitrary worker event/details fields.
    return {
        "id": int(trade["id"]),
        "entry": _number(trade.get("entry"), "trade.entry"),
        "exit": _number(trade.get("exit"), "trade.exit"),
        "qty": _number(trade.get("qty"), "trade.qty"),
        "fees": _number(trade.get("fees"), "trade.fees"),
        "net_pnl": _number(trade.get("net_pnl"), "trade.net_pnl"),
        "reason": str(trade.get("reason", ""))[:80],
        "opened_at": _timestamp(trade.get("opened_at"), "trade.opened_at").isoformat(),
        "closed_at": _timestamp(trade.get("closed_at"), "trade.closed_at").isoformat(),
    }


def project_status(raw: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Validate and return a minimal browser-safe status projection."""
    if not isinstance(raw, Mapping):
        raise StatusUnavailable("status document must be an object")
    if raw.get("mode") != "PAPER_ONLY":
        raise StatusUnavailable("source is not PAPER_ONLY")

    experiment = raw.get("experiment")
    if not isinstance(experiment, Mapping):
        raise StatusUnavailable("missing experiment metadata")
    if experiment.get("baseline_id") != BASELINE_ID:
        raise StatusUnavailable("baseline ID mismatch")
    if experiment.get("strategy_count") != 6:
        raise StatusUnavailable("strategy count mismatch")
    if _number(experiment.get("starting_equity_per_strategy"), "starting_equity_per_strategy") != STARTING_CASH:
        raise StatusUnavailable("starting equity mismatch")

    source_time = _timestamp(raw.get("updated_at"), "updated_at")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise StatusUnavailable("now must be timezone-aware")
    age = (current.astimezone(timezone.utc) - source_time).total_seconds()
    if age < -MAX_FUTURE_SECONDS:
        raise StatusUnavailable("source timestamp is materially in the future")
    freshness = "FRESH" if age <= FRESH_SECONDS else ("STALE" if age <= OFFLINE_SECONDS else "OFFLINE")
    if freshness == "OFFLINE":
        raise StatusUnavailable("source heartbeat is offline")

    source_accounts = raw.get("accounts")
    if not isinstance(source_accounts, list) or len(source_accounts) != 6:
        raise StatusUnavailable("expected exactly six accounts")
    by_id = {}
    for account in source_accounts:
        if not isinstance(account, Mapping):
            raise StatusUnavailable("invalid account record")
        sid = account.get("strategy_id")
        if sid not in STRATEGY_IDS or sid in by_id:
            raise StatusUnavailable("unknown or duplicate strategy ID")
        by_id[sid] = account
    if set(by_id) != STRATEGY_IDS:
        raise StatusUnavailable("strategy set mismatch")

    accounts = []
    for sid in sorted(STRATEGY_IDS):
        source = by_id[sid]
        starting = _number(source.get("starting_cash"), f"{sid}.starting_cash")
        if starting != STARTING_CASH:
            raise StatusUnavailable(f"{sid}: starting cash mismatch")
        trades = int(source.get("trades", 0))
        wins = int(source.get("wins", 0))
        if trades < 0 or wins < 0 or wins > trades:
            raise StatusUnavailable(f"{sid}: invalid trade counters")
        recent = source.get("recent_trades_30d", [])
        if not isinstance(recent, list):
            raise StatusUnavailable(f"{sid}: invalid recent trades")
        position = source.get("position")
        safe_position = None
        if position is not None:
            if not isinstance(position, Mapping):
                raise StatusUnavailable(f"{sid}: invalid position")
            safe_position = {
                "symbol": str(position.get("symbol", ""))[:24],
                "qty": _number(position.get("qty"), f"{sid}.position.qty"),
                "entry": _number(position.get("entry"), f"{sid}.position.entry"),
                "mark": _number(position.get("mark"), f"{sid}.position.mark"),
                "stop": _number(position.get("stop"), f"{sid}.position.stop"),
                "target": _number(position.get("target"), f"{sid}.position.target"),
                "unrealized_pnl": _number(position.get("unrealized_pnl"), f"{sid}.position.unrealized_pnl"),
                "opened_at": _timestamp(position.get("opened_at"), f"{sid}.position.opened_at").isoformat(),
                "protection_status": str(position.get("protection_status", "UNKNOWN"))[:24],
            }
        pf = source.get("profit_factor")
        if pf not in (None, "inf"):
            pf = _number(pf, f"{sid}.profit_factor")
            if pf < 0:
                raise StatusUnavailable(f"{sid}: negative profit factor")
        accounts.append({
            "strategy_id": sid,
            "label": str(source.get("label", sid))[:80],
            "symbol": str(source.get("symbol", ""))[:24],
            "timeframe": str(source.get("timeframe", ""))[:12],
            "grade": str(source.get("grade", ""))[:48],
            "protection_status": str(source.get("protection_status", "UNKNOWN"))[:24],
            "starting_cash": starting,
            "cash": _number(source.get("cash"), f"{sid}.cash"),
            "equity": _number(source.get("equity"), f"{sid}.equity"),
            "net_pnl": _number(source.get("net_pnl"), f"{sid}.net_pnl"),
            "realized_pnl": _number(source.get("realized_pnl"), f"{sid}.realized_pnl"),
            "unrealized_pnl": _number(source.get("unrealized_pnl"), f"{sid}.unrealized_pnl"),
            "return_pct": _number(source.get("return_pct"), f"{sid}.return_pct"),
            "trades": trades,
            "wins": wins,
            # Worker exports 0 for zero trades; dashboard represents this as unknown.
            "win_rate_pct": (wins / trades * 100) if trades else None,
            "profit_factor": pf,
            "fees": _number(source.get("fees"), f"{sid}.fees"),
            "last_price": _number(source.get("last_price"), f"{sid}.last_price", nullable=True),
            "last_price_at": (_timestamp(source["last_price_at"], f"{sid}.last_price_at").isoformat()
                              if source.get("last_price_at") else None),
            "position": safe_position,
            "recent_trades_30d": [_safe_trade(t) for t in recent[:100]],
        })

    health = raw.get("worker_health")
    if not isinstance(health, Mapping):
        raise StatusUnavailable("missing worker health")
    safe_health = {
        "strategy_count": int(health.get("strategy_count", 0)),
        "successful_strategies": int(health.get("successful_strategies", 0)),
        "error_count": int(health.get("error_count", 0)),
        "intrabar_data_warnings_24h": int(health.get("intrabar_data_warnings_24h", 0)),
        "all_strategies_ok": health.get("all_strategies_ok") is True,
        "protection_degraded_positions": int(health.get("protection_degraded_positions", 0)),
        "protection_degraded_strategies": int(health.get("protection_degraded_strategies", 0)),
        "all_protections_ok": health.get("all_protections_ok") is True,
    }

    equity = sum(a["equity"] for a in accounts)
    realized = sum(a["realized_pnl"] for a in accounts)
    unrealized = sum(a["unrealized_pnl"] for a in accounts)
    trades = sum(a["trades"] for a in accounts)
    wins = sum(a["wins"] for a in accounts)
    fees = sum(a["fees"] for a in accounts)
    pnl = equity - STARTING_CASH * len(STRATEGY_IDS)
    return {
        "schema_version": "1.0",
        "generated_at": current.astimezone(timezone.utc).isoformat(),
        "source_updated_at": source_time.isoformat(),
        "freshness": freshness,
        "mode": "PAPER_ONLY",
        "experiment": {
            "baseline_id": BASELINE_ID,
            "baseline_at": _timestamp(experiment.get("baseline_at"), "baseline_at").isoformat(),
            "starting_equity_per_strategy": STARTING_CASH,
            "strategy_count": 6,
        },
        "portfolio": {
            "starting_equity": STARTING_CASH * 6,
            "equity": round(equity, 4),
            "cash": round(sum(a["cash"] for a in accounts), 4),
            "realized_pnl": round(realized, 4),
            "unrealized_pnl": round(unrealized, 4),
            "net_pnl": round(pnl, 4),
            "return_pct": round(pnl / (STARTING_CASH * 6) * 100, 4),
            "trades": trades,
            "wins": wins,
            "win_rate_pct": round(wins / trades * 100, 2) if trades else None,
            "fees": round(fees, 4),
        },
        "worker_health": safe_health,
        "accounts": accounts,
    }
