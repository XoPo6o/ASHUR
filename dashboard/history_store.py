"""Append-only, isolated history store for ASHUR Paper/Shadow dashboard.

This module reads only the worker's sanitized status export. It never opens the
trading SQLite database and never writes to worker state.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
from typing import Any

from dashboard.read_model import BASELINE_ID, STARTING_CASH, StatusUnavailable, project_status

DATA_DIR = Path(os.environ.get("ASHUR_DATA_DIR", str(Path.home() / ".local" / "share" / "ashur"))).expanduser()
STATUS_FILE = DATA_DIR / "ashur_shadow_status.json"
HISTORY_DB = DATA_DIR / "ashur_dashboard_history.sqlite3"
COLLECT_INTERVAL_SECONDS = 30
MAX_RESPONSE_POINTS = 1000
ALLOWED_RANGES_DAYS = {1, 7, 30, 90}


class HistoryUnavailable(ValueError):
    """Raised when no valid history exists for the active Paper/Shadow baseline."""


def _utc(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return result.astimezone(timezone.utc)


def init_history_db(path: Path = HISTORY_DB) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path), timeout=10) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS dashboard_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            source_updated_at TEXT NOT NULL,
            baseline_id TEXT NOT NULL,
            portfolio_equity REAL NOT NULL,
            cash REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            unrealized_pnl REAL NOT NULL,
            net_pnl REAL NOT NULL,
            return_pct REAL NOT NULL,
            trades INTEGER NOT NULL,
            wins INTEGER NOT NULL,
            fees REAL NOT NULL,
            UNIQUE (baseline_id, source_updated_at)
        );
        CREATE INDEX IF NOT EXISTS idx_dashboard_snapshots_baseline_time
            ON dashboard_snapshots(baseline_id, captured_at);
        CREATE TABLE IF NOT EXISTS dashboard_account_snapshots (
            snapshot_id INTEGER NOT NULL,
            strategy_id TEXT NOT NULL,
            equity REAL NOT NULL,
            cash REAL NOT NULL,
            net_pnl REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            unrealized_pnl REAL NOT NULL,
            return_pct REAL NOT NULL,
            trades INTEGER NOT NULL,
            wins INTEGER NOT NULL,
            fees REAL NOT NULL,
            PRIMARY KEY (snapshot_id, strategy_id),
            FOREIGN KEY (snapshot_id) REFERENCES dashboard_snapshots(id)
        );
        CREATE INDEX IF NOT EXISTS idx_dashboard_account_strategy
            ON dashboard_account_snapshots(strategy_id, snapshot_id);
        """)
        conn.commit()


def collect_once(
    status_file: Path = STATUS_FILE,
    history_db: Path = HISTORY_DB,
    now: datetime | None = None,
) -> bool:
    """Persist one fresh worker snapshot; return False for duplicate/unusable input."""
    current = _utc(now)
    try:
        raw = json.loads(Path(status_file).read_text(encoding="utf-8"))
        status = project_status(raw, current)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, StatusUnavailable):
        return False

    # Do not turn a stale heartbeat into a new historical observation.
    if status["freshness"] != "FRESH":
        return False

    portfolio = status["portfolio"]
    accounts = status["accounts"]
    init_history_db(history_db)
    with sqlite3.connect(str(history_db), timeout=10) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        cursor = conn.execute(
            """INSERT OR IGNORE INTO dashboard_snapshots
            (captured_at, source_updated_at, baseline_id, portfolio_equity, cash,
             realized_pnl, unrealized_pnl, net_pnl, return_pct, trades, wins, fees)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                current.isoformat(),
                status["source_updated_at"],
                BASELINE_ID,
                portfolio["equity"],
                portfolio["cash"],
                portfolio["realized_pnl"],
                portfolio["unrealized_pnl"],
                portfolio["net_pnl"],
                portfolio["return_pct"],
                portfolio["trades"],
                portfolio["wins"],
                portfolio["fees"],
            ),
        )
        if cursor.rowcount != 1:
            return False
        snapshot_id = cursor.lastrowid
        conn.executemany(
            """INSERT INTO dashboard_account_snapshots
            (snapshot_id, strategy_id, equity, cash, net_pnl, realized_pnl,
             unrealized_pnl, return_pct, trades, wins, fees)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    snapshot_id, account["strategy_id"], account["equity"],
                    account["cash"], account["net_pnl"], account["realized_pnl"],
                    account["unrealized_pnl"], account["return_pct"],
                    account["trades"], account["wins"], account["fees"],
                )
                for account in accounts
            ],
        )
        conn.commit()
    return True


def _downsample(rows: list[dict[str, Any]], limit: int = MAX_RESPONSE_POINTS) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return rows
    indexes = {round(i * (len(rows) - 1) / (limit - 1)) for i in range(limit)}
    return [row for i, row in enumerate(rows) if i in indexes]


def read_history(
    history_db: Path = HISTORY_DB,
    days: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read baseline-relative portfolio and six-strategy time series without writes."""
    if days not in ALLOWED_RANGES_DAYS:
        raise ValueError("days must be one of 1, 7, 30 or 90")
    current = _utc(now)
    if not Path(history_db).is_file():
        raise HistoryUnavailable("history collection has not started")

    since = (current - timedelta(days=days)).isoformat()
    uri = Path(history_db).resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """WITH ranked AS (
                    SELECT id, captured_at, source_updated_at, portfolio_equity,
                           cash, realized_pnl, unrealized_pnl, net_pnl, return_pct,
                           trades, wins, fees,
                           MAX(portfolio_equity) OVER (
                               PARTITION BY baseline_id ORDER BY captured_at, id
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                           ) AS high_water
                    FROM dashboard_snapshots
                    WHERE baseline_id=?
                )
                SELECT * FROM ranked WHERE captured_at >= ? ORDER BY captured_at, id""",
                (BASELINE_ID, since),
            ).fetchall()
            if not rows:
                raise HistoryUnavailable("no snapshots collected in the requested range")

            account_rows = conn.execute(
                """SELECT a.snapshot_id, a.strategy_id, a.equity, a.net_pnl, a.return_pct,
                          a.trades, a.wins, a.fees
                   FROM dashboard_account_snapshots AS a
                   JOIN dashboard_snapshots AS s ON s.id=a.snapshot_id
                   WHERE s.baseline_id=? AND s.captured_at>=?
                   ORDER BY a.snapshot_id, a.strategy_id""",
                (BASELINE_ID, since),
            ).fetchall()
            latest_source_at = datetime.fromisoformat(str(rows[-1]["source_updated_at"]))
            rolling_cutoff = latest_source_at - timedelta(hours=24)
            rolling_anchor = conn.execute(
                """SELECT source_updated_at, portfolio_equity, realized_pnl, trades, fees
                   FROM dashboard_snapshots
                   WHERE baseline_id=? AND source_updated_at<=?
                   ORDER BY source_updated_at DESC, id DESC LIMIT 1""",
                (BASELINE_ID, rolling_cutoff.isoformat()),
            ).fetchone()
            rolling_recent = conn.execute(
                """SELECT source_updated_at, portfolio_equity, realized_pnl, trades, fees
                   FROM dashboard_snapshots
                   WHERE baseline_id=? AND source_updated_at>? AND source_updated_at<=?
                   ORDER BY source_updated_at, id""",
                (BASELINE_ID, rolling_cutoff.isoformat(), latest_source_at.isoformat()),
            ).fetchall()
    except sqlite3.Error as exc:
        raise HistoryUnavailable("history store could not be read") from exc

    account_by_snapshot: dict[int, list[dict[str, Any]]] = {}
    for row in account_rows:
        account_by_snapshot.setdefault(int(row["snapshot_id"]), []).append({
            "strategy_id": row["strategy_id"],
            "equity": round(float(row["equity"]), 4),
            "net_pnl": round(float(row["net_pnl"]), 4),
            "return_pct": round(float(row["return_pct"]), 4),
            "trades": int(row["trades"]),
            "wins": int(row["wins"]),
            "fees": round(float(row["fees"]), 4),
        })

    curve = []
    daily_groups: dict[str, list[sqlite3.Row]] = {}
    strategy_points: dict[str, list[dict[str, Any]]] = {}
    max_drawdown = 0.0
    for row in rows:
        equity = float(row["portfolio_equity"])
        high_water = float(row["high_water"])
        drawdown = ((equity / high_water) - 1) * 100 if high_water else 0.0
        max_drawdown = min(max_drawdown, drawdown)
        at = str(row["source_updated_at"])
        curve.append({
            "at": at,
            "equity": round(equity, 4),
            "net_pnl": round(float(row["net_pnl"]), 4),
            "return_pct": round(float(row["return_pct"]), 4),
            "drawdown_pct": round(drawdown, 4),
        })
        daily_groups.setdefault(at[:10], []).append(row)
        for account in account_by_snapshot.get(int(row["id"]), []):
            strategy_points.setdefault(account["strategy_id"], []).append({
                "at": at,
                "equity": account["equity"],
                "net_pnl": account["net_pnl"],
                "return_pct": account["return_pct"],
            })

    daily = []
    for day, observations in sorted(daily_groups.items()):
        first, last = observations[0], observations[-1]
        start_equity = float(first["portfolio_equity"])
        end_equity = float(last["portfolio_equity"])
        # Intraday P&L is measured from the first observed snapshot of that UTC day.
        day_peak = 0.0
        day_drawdown = 0.0
        for item in observations:
            observed_equity = float(item["portfolio_equity"])
            day_peak = max(day_peak, observed_equity)
            if day_peak:
                day_drawdown = min(day_drawdown, ((observed_equity / day_peak) - 1) * 100)
        daily.append({
            "date": day,
            "first_equity": round(start_equity, 4),
            "last_equity": round(end_equity, 4),
            "pnl": round(end_equity - start_equity, 4),
            "return_pct": round((end_equity / start_equity - 1) * 100, 4) if start_equity else 0.0,
            "realized_pnl": round(float(last["realized_pnl"]) - float(first["realized_pnl"]), 4),
            "closed_trades": int(last["trades"]) - int(first["trades"]),
            "fees": round(float(last["fees"]) - float(first["fees"]), 4),
            "max_drawdown_pct": round(day_drawdown, 4),
            "snapshots": len(observations),
        })

    strategy_trade_stats = []
    for strategy_id in sorted(strategy_points):
        observed = [
            next(item for item in account_by_snapshot[snapshot_id] if item["strategy_id"] == strategy_id)
            for snapshot_id in sorted(account_by_snapshot)
            if any(item["strategy_id"] == strategy_id for item in account_by_snapshot[snapshot_id])
        ]
        if len(observed) < 2:
            strategy_trade_stats.append({
                "strategy_id": strategy_id, "available": False,
                "closed_trades": 0, "wins": 0, "losses": 0,
            })
            continue
        first_stats, last_stats = observed[0], observed[-1]
        trades_delta = last_stats["trades"] - first_stats["trades"]
        wins_delta = last_stats["wins"] - first_stats["wins"]
        valid = trades_delta >= 0 and wins_delta >= 0 and wins_delta <= trades_delta
        strategy_trade_stats.append({
            "strategy_id": strategy_id,
            "available": valid,
            "closed_trades": trades_delta if valid else 0,
            "wins": wins_delta if valid else 0,
            "losses": trades_delta - wins_delta if valid else 0,
        })

    rolling_24h: dict[str, Any] = {
        "available": False,
        "reason": "INSUFFICIENT_24H_HISTORY",
    }
    if rolling_anchor is not None:
        rolling_points = [rolling_anchor, *rolling_recent]
        first_24h, last_24h = rolling_points[0], rolling_points[-1]
        start_equity = float(first_24h["portfolio_equity"])
        end_equity = float(last_24h["portfolio_equity"])
        peak = start_equity
        rolling_drawdown = 0.0
        for point in rolling_points:
            observed = float(point["portfolio_equity"])
            peak = max(peak, observed)
            if peak:
                rolling_drawdown = min(rolling_drawdown, (observed / peak - 1) * 100)
        start_at = datetime.fromisoformat(str(first_24h["source_updated_at"]))
        end_at = datetime.fromisoformat(str(last_24h["source_updated_at"]))
        rolling_24h = {
            "available": True,
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "elapsed_hours": round((end_at - start_at).total_seconds() / 3600, 3),
            "snapshots": len(rolling_points),
            "pnl": round(end_equity - start_equity, 4),
            "return_pct": round((end_equity / start_equity - 1) * 100, 4) if start_equity else 0.0,
            "realized_pnl": round(float(last_24h["realized_pnl"]) - float(first_24h["realized_pnl"]), 4),
            "closed_trades": int(last_24h["trades"]) - int(first_24h["trades"]),
            "fees": round(float(last_24h["fees"]) - float(first_24h["fees"]), 4),
            "max_drawdown_pct": round(rolling_drawdown, 4),
        }

    sampled_curve = _downsample(curve)
    sampled_strategies = [
        {"strategy_id": sid, "points": _downsample(points)}
        for sid, points in sorted(strategy_points.items())
    ]
    return {
        "schema_version": "1.0",
        "baseline_id": BASELINE_ID,
        "timezone": "UTC",
        "range_days": days,
        "sample_count": len(curve),
        "returned_point_count": len(sampled_curve),
        "first_snapshot_at": curve[0]["at"],
        "last_snapshot_at": curve[-1]["at"],
        "summary": {
            "latest_equity": curve[-1]["equity"],
            "latest_net_pnl": curve[-1]["net_pnl"],
            "latest_return_pct": curve[-1]["return_pct"],
            "max_drawdown_pct": round(max_drawdown, 4),
        },
        "equity_curve": sampled_curve,
        "strategies": sampled_strategies,
        "strategy_trade_stats": strategy_trade_stats,
        "daily": daily,
        "rolling_24h": rolling_24h,
    }


def collect_forever(
    status_file: Path = STATUS_FILE,
    history_db: Path = HISTORY_DB,
    interval_seconds: int = COLLECT_INTERVAL_SECONDS,
    log=print,
) -> None:
    """Poll the exported status independently; never blocks the worker process."""
    while True:
        try:
            if collect_once(status_file=status_file, history_db=history_db):
                log("DASHBOARD_HISTORY_SNAPSHOT_SAVED")
        except Exception as exc:
            log(f"DASHBOARD_HISTORY_COLLECTOR_ERROR reason={type(exc).__name__}")
        time.sleep(max(5, int(interval_seconds)))


def start_history_collector(log=print, interval_seconds: int = COLLECT_INTERVAL_SECONDS) -> Thread:
    thread = Thread(
        target=collect_forever,
        kwargs={"log": log, "interval_seconds": interval_seconds},
        name="ashur-dashboard-history",
        daemon=True,
    )
    thread.start()
    log(f"DASHBOARD_HISTORY_COLLECTOR_STARTED interval={max(5, int(interval_seconds))}s")
    return thread
