import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dashboard.history_store import (
    ALLOWED_RANGES_DAYS,
    HistoryUnavailable,
    collect_once,
    read_history,
)
from dashboard.read_model import BASELINE_ID, STRATEGY_IDS


class DashboardHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.status_file = self.directory / "worker-status.json"
        self.history_db = self.directory / "dashboard-history.sqlite3"
        self.start = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
        self.raw = self.make_status(self.start, [1000.0] * 6)

    def tearDown(self):
        self.temp.cleanup()

    def make_status(self, stamp, equities, trade_counts=None, win_counts=None):
        accounts = []
        for strategy_id, equity in zip(sorted(STRATEGY_IDS), equities):
            delta = equity - 1000.0
            accounts.append({
                "strategy_id": strategy_id,
                "label": strategy_id,
                "symbol": "BNB/USDT",
                "timeframe": "4h",
                "grade": "TEST",
                "protection_status": "NOT_REQUIRED",
                "starting_cash": 1000.0,
                "cash": equity,
                "equity": equity,
                "net_pnl": delta,
                "realized_pnl": delta,
                "unrealized_pnl": 0.0,
                "return_pct": delta / 1000.0 * 100,
                "trades": (trade_counts or {}).get(strategy_id, 0),
                "wins": (win_counts or {}).get(strategy_id, 0),
                "win_rate_pct": 0,
                "profit_factor": None,
                "fees": 0.0,
                "last_price": None,
                "last_price_at": None,
                "position": None,
                "recent_trades_30d": [],
            })
        return {
            "updated_at": stamp.isoformat(),
            "mode": "PAPER_ONLY",
            "experiment": {
                "baseline_id": BASELINE_ID,
                "baseline_at": self.start.isoformat(),
                "starting_equity_per_strategy": 1000.0,
                "strategy_count": 6,
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
            "accounts": accounts,
        }

    def save_status(self, raw):
        self.status_file.write_text(json.dumps(raw), encoding="utf-8")

    def test_collects_unique_fresh_snapshots_and_calculates_drawdown(self):
        observations = [
            (self.start, [1000, 1000, 1000, 1000, 1000, 1000]),
            (self.start + timedelta(minutes=5), [1010, 1010, 1010, 1010, 1030, 1030]),
            (self.start + timedelta(minutes=10), [1005, 1005, 1005, 1005, 1020, 1020]),
        ]
        for stamp, equities in observations:
            self.save_status(self.make_status(stamp, equities))
            self.assertTrue(collect_once(self.status_file, self.history_db, now=stamp))
        self.save_status(self.make_status(observations[-1][0], observations[-1][1]))
        self.assertFalse(collect_once(
            self.status_file, self.history_db,
            now=observations[-1][0] + timedelta(seconds=5),
        ))

        result = read_history(self.history_db, days=30, now=self.start + timedelta(minutes=11))
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["summary"]["latest_equity"], 6060.0)
        self.assertAlmostEqual(result["summary"]["max_drawdown_pct"], (6060 / 6100 - 1) * 100, places=3)
        self.assertEqual(len(result["strategies"]), 6)
        self.assertEqual(len(result["equity_curve"]), 3)
        self.assertEqual(result["daily"][0]["pnl"], 60.0)
        self.assertEqual(result["daily"][0]["realized_pnl"], 60.0)
        self.assertEqual(result["daily"][0]["closed_trades"], 0)
        self.assertEqual(result["daily"][0]["fees"], 0.0)
        self.assertAlmostEqual(result["daily"][0]["max_drawdown_pct"], (6060 / 6100 - 1) * 100, places=3)

    def test_strategy_trade_stats_report_observed_wins_and_losses(self):
        first_counts = {strategy_id: 0 for strategy_id in STRATEGY_IDS}
        first_wins = dict(first_counts)
        last_counts = dict(first_counts)
        last_wins = dict(first_wins)
        strategy_ids = sorted(STRATEGY_IDS)
        last_counts[strategy_ids[0]] = 5
        last_wins[strategy_ids[0]] = 3
        last_counts[strategy_ids[1]] = 2
        last_wins[strategy_ids[1]] = 2

        observations = [
            (self.start, [1000] * 6, first_counts, first_wins),
            (self.start + timedelta(minutes=5), [1005] * 6, last_counts, last_wins),
        ]
        for stamp, equities, trades, wins in observations:
            self.save_status(self.make_status(stamp, equities, trades, wins))
            self.assertTrue(collect_once(self.status_file, self.history_db, now=stamp))

        result = read_history(self.history_db, days=30, now=self.start + timedelta(minutes=6))
        stats = {item["strategy_id"]: item for item in result["strategy_trade_stats"]}
        self.assertEqual(stats[strategy_ids[0]]["closed_trades"], 5)
        self.assertEqual(stats[strategy_ids[0]]["wins"], 3)
        self.assertEqual(stats[strategy_ids[0]]["losses"], 2)
        self.assertEqual(stats[strategy_ids[1]]["closed_trades"], 2)
        self.assertEqual(stats[strategy_ids[1]]["wins"], 2)
        self.assertEqual(stats[strategy_ids[1]]["losses"], 0)
        self.assertEqual(len(stats), 6)

    def test_rolling_24h_uses_snapshot_at_or_before_boundary(self):
        observations = [
            (self.start, [1000] * 6),
            (self.start + timedelta(hours=24, minutes=5), [1010] * 6),
            (self.start + timedelta(hours=24, minutes=10), [1005] * 6),
        ]
        for stamp, equities in observations:
            self.save_status(self.make_status(stamp, equities))
            self.assertTrue(collect_once(self.status_file, self.history_db, now=stamp))

        result = read_history(
            self.history_db,
            days=30,
            now=observations[-1][0] + timedelta(minutes=1),
        )
        report = result["rolling_24h"]
        self.assertTrue(report["available"])
        self.assertEqual(report["pnl"], 30.0)
        self.assertEqual(report["realized_pnl"], 30.0)
        self.assertEqual(report["closed_trades"], 0)
        self.assertEqual(report["fees"], 0.0)
        self.assertAlmostEqual(report["max_drawdown_pct"], (6030 / 6060 - 1) * 100, places=3)
        self.assertEqual(report["snapshots"], 3)
        self.assertGreaterEqual(report["elapsed_hours"], 24.0)

    def test_stale_offline_and_wrong_baseline_are_not_collected(self):
        stale_at = self.start - timedelta(minutes=11)
        self.save_status(self.make_status(stale_at, [1000] * 6))
        self.assertFalse(collect_once(self.status_file, self.history_db, now=self.start))
        offline_at = self.start - timedelta(minutes=21)
        self.save_status(self.make_status(offline_at, [1000] * 6))
        self.assertFalse(collect_once(self.status_file, self.history_db, now=self.start))
        wrong = self.make_status(self.start, [1000] * 6)
        wrong["experiment"]["baseline_id"] = "wrong-baseline"
        self.save_status(wrong)
        self.assertFalse(collect_once(self.status_file, self.history_db, now=self.start))
        self.assertFalse(self.history_db.exists())

    def test_history_is_append_only_and_read_only(self):
        self.save_status(self.raw)
        self.assertTrue(collect_once(self.status_file, self.history_db, now=self.start))
        with sqlite3.connect(self.history_db) as conn:
            before = conn.execute("SELECT COUNT(*) FROM dashboard_snapshots").fetchone()[0]
        read_history(self.history_db, days=7, now=self.start + timedelta(seconds=10))
        with sqlite3.connect(self.history_db) as conn:
            after = conn.execute("SELECT COUNT(*) FROM dashboard_snapshots").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(before, 1)
        self.assertFalse(read_history(self.history_db, days=7, now=self.start + timedelta(seconds=10))["rolling_24h"]["available"])

    def test_missing_history_and_invalid_ranges_are_explicit(self):
        with self.assertRaises(HistoryUnavailable):
            read_history(self.history_db, days=30, now=self.start)
        self.save_status(self.raw)
        collect_once(self.status_file, self.history_db, now=self.start)
        with self.assertRaises(ValueError):
            read_history(self.history_db, days=2, now=self.start)
        self.assertEqual(ALLOWED_RANGES_DAYS, {1, 7, 30, 90})


if __name__ == "__main__":
    unittest.main()
