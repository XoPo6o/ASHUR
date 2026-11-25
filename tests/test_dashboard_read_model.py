import unittest
from datetime import datetime, timezone, timedelta

from dashboard.read_model import (
    BASELINE_ID, STRATEGY_IDS, StatusUnavailable, project_status,
)


class ReadModelTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
        self.raw = {
            "updated_at": self.now.isoformat(),
            "mode": "PAPER_ONLY",
            "experiment": {
                "baseline_id": BASELINE_ID,
                "baseline_at": "2026-11-25T10:51:24.754378+00:00",
                "starting_equity_per_strategy": 1000,
                "strategy_count": 6,
                "secret_must_not_leak": "nope",
            },
            "worker_health": {
                "strategy_count": 6, "successful_strategies": 6,
                "error_count": 0, "intrabar_data_warnings_24h": 0,
                "all_strategies_ok": True, "protection_degraded_positions": 0,
                "protection_degraded_strategies": 0, "all_protections_ok": True,
            },
            "accounts": [],
            "private_path": "/not-for-browser",
        }
        for sid in sorted(STRATEGY_IDS):
            self.raw["accounts"].append({
                "strategy_id": sid, "label": sid, "symbol": "BNB/USDT",
                "timeframe": "4h", "grade": "TEST", "protection_status": "NOT_REQUIRED",
                "starting_cash": 1000, "cash": 1000, "equity": 1000,
                "net_pnl": 0, "realized_pnl": 0, "unrealized_pnl": 0,
                "return_pct": 0, "trades": 0, "wins": 0, "win_rate_pct": 0,
                "profit_factor": None, "fees": 0, "last_price": None,
                "last_price_at": None, "position": None, "recent_trades_30d": [],
                "exchange_key": "must-not-leak",
            })

    def test_baseline_aggregate_and_allowlist(self):
        result = project_status(self.raw, self.now)
        self.assertEqual(result["portfolio"]["equity"], 6000)
        self.assertIsNone(result["portfolio"]["win_rate_pct"])
        self.assertIsNone(result["accounts"][0]["win_rate_pct"])
        self.assertNotIn("private_path", result)
        self.assertNotIn("exchange_key", result["accounts"][0])
        self.assertNotIn("secret_must_not_leak", result["experiment"])
        self.assertEqual(result["freshness"], "FRESH")

    def test_stale_is_labelled_but_offline_is_rejected(self):
        stale_now = self.now + timedelta(minutes=15)
        self.assertEqual(project_status(self.raw, stale_now)["freshness"], "STALE")
        with self.assertRaises(StatusUnavailable):
            project_status(self.raw, self.now + timedelta(minutes=21))

    def test_rejects_wrong_mode_baseline_and_duplicate_strategy(self):
        wrong_mode = dict(self.raw, mode="LIVE")
        with self.assertRaises(StatusUnavailable):
            project_status(wrong_mode, self.now)
        wrong_baseline = {**self.raw, "experiment": {**self.raw["experiment"], "baseline_id": "old"}}
        with self.assertRaises(StatusUnavailable):
            project_status(wrong_baseline, self.now)
        duplicate = {**self.raw, "accounts": self.raw["accounts"][:-1] + [self.raw["accounts"][0]]}
        with self.assertRaises(StatusUnavailable):
            project_status(duplicate, self.now)


if __name__ == "__main__":
    unittest.main()
