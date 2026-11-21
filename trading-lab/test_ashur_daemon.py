"""Offline regression tests for ASHUR daemon and persistent paper state."""
import importlib.util
import sqlite3
import unittest
from unittest.mock import patch
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


daemon = load_module("ashur_daemon_under_test", MODULE_DIR / "ashur_daemon.py")
worker = load_module("live_shadow_worker_under_test", MODULE_DIR / "live_shadow_worker.py")


class TestAshurRuntime(unittest.TestCase):
    def test_daemon_has_no_git_ledger_publisher(self):
        self.assertFalse(hasattr(daemon, "publish_ledger"))
        self.assertEqual(daemon.WORKER.name, "live_shadow_worker.py")

    def test_legacy_sqlite_and_status_migrate_to_persistent_storage_once(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            repo_dir = tmp_path / "repo"
            state_dir = tmp_path / "persistent-state"
            repo_dir.mkdir()

            legacy_db = repo_dir / "ashur_shadow.db"
            with sqlite3.connect(legacy_db) as conn:
                conn.execute("CREATE TABLE migration_probe (value TEXT)")
                conn.execute("INSERT INTO migration_probe VALUES ('preserve-me')")

            legacy_status = repo_dir / "ashur_shadow_status.json"
            legacy_status.write_text('{"mode":"PAPER_ONLY"}', encoding="utf-8")

            original = (worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE)
            try:
                worker.ROOT = repo_dir
                worker.DATA_DIR = state_dir
                worker.DB = state_dir / "ashur_shadow.db"
                worker.STATUS_FILE = state_dir / "ashur_shadow_status.json"

                worker.prepare_data_dir()

                with sqlite3.connect(worker.DB) as conn:
                    value = conn.execute("SELECT value FROM migration_probe").fetchone()[0]
                self.assertEqual(value, "preserve-me")
                self.assertEqual(
                    worker.STATUS_FILE.read_text(encoding="utf-8"),
                    '{"mode":"PAPER_ONLY"}',
                )

                # A later code sync must never overwrite already-migrated live state.
                with sqlite3.connect(legacy_db) as conn:
                    conn.execute("UPDATE migration_probe SET value='stale-repo-copy'")
                legacy_status.write_text('{"mode":"STALE"}', encoding="utf-8")

                worker.prepare_data_dir()
                with sqlite3.connect(worker.DB) as conn:
                    value = conn.execute("SELECT value FROM migration_probe").fetchone()[0]
                self.assertEqual(value, "preserve-me")
                self.assertEqual(
                    worker.STATUS_FILE.read_text(encoding="utf-8"),
                    '{"mode":"PAPER_ONLY"}',
                )
            finally:
                worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE = original


    def test_gap_through_stop_is_classified_separately(self):
        self.assertEqual(worker.stop_exit_reason(100.0, 100.0), "STOP")
        self.assertEqual(worker.stop_exit_reason(99.99, 100.0), "GAP_STOP")
        self.assertEqual(worker.stop_exit_reason(100.01, 100.0), "STOP")

    def test_recovery_gap_stop_closes_at_live_price_and_blocks_same_cycle_reentry(self):
        import tempfile
        import pandas as pd

        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            original = (worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE, worker.STRATEGIES)
            strategy = {
                "id": "BNB_15M_EMA_TREND", "symbol": "BNB/USDT", "interval": "15",
                "label": "recovery test", "grade": "PAPER_VALIDATION",
            }
            try:
                worker.ROOT = tmp_path
                worker.DATA_DIR = tmp_path / "state"
                worker.DB = worker.DATA_DIR / "ashur_shadow.db"
                worker.STATUS_FILE = worker.DATA_DIR / "ashur_shadow_status.json"
                worker.STRATEGIES = [strategy]

                worker.prepare_data_dir()
                conn = sqlite3.connect(worker.DB)
                conn.row_factory = sqlite3.Row
                worker.init_db(conn)
                conn.execute(
                    "UPDATE shadow_accounts SET cash=? WHERE strategy_id=?",
                    (899.9, strategy["id"]),
                )
                conn.execute(
                    """INSERT INTO shadow_positions
                       (strategy_id,symbol,qty,entry,entry_fee,stop,target,opened_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (strategy["id"], strategy["symbol"], 1.0, 100.0, 0.1,
                     95.0, 120.0, "2026-11-20T10:00:00+00:00"),
                )
                conn.commit()
                conn.close()

                closed_candle = pd.DataFrame([{
                    "timestamp": 2_000_000_000_000,
                    "close": 100.0,
                    "atr": 1.0,
                }])
                with patch.object(worker, "fetch_bybit_klines", return_value=object()), \
                     patch.object(worker, "indicators", return_value=closed_candle), \
                     patch.object(worker, "fetch_ticker", return_value=90.0), \
                     patch.object(worker, "signals", return_value=(True, False)), \
                     patch.object(worker, "open_position", wraps=worker.open_position) as reopen:
                    worker.run()
                    reopen.assert_not_called()

                conn = sqlite3.connect(worker.DB)
                conn.row_factory = sqlite3.Row
                trade = conn.execute(
                    "SELECT * FROM shadow_trades WHERE strategy_id=?",
                    (strategy["id"],),
                ).fetchone()
                position = conn.execute(
                    "SELECT * FROM shadow_positions WHERE strategy_id=?",
                    (strategy["id"],),
                ).fetchone()
                guard = conn.execute(
                    "SELECT last_closed_candle FROM shadow_trade_guard WHERE strategy_id=?",
                    (strategy["id"],),
                ).fetchone()
                conn.close()

                expected_fill = 90.0 * (1 - worker.SLIPPAGE)
                expected_pnl = expected_fill * (1 - worker.FEE) - (100.0 + 0.1)
                self.assertIsNotNone(trade)
                self.assertEqual(trade["reason"], "GAP_STOP")
                self.assertAlmostEqual(trade["exit"], expected_fill, places=8)
                self.assertAlmostEqual(trade["pnl"], expected_pnl, places=8)
                self.assertIsNone(position)
                self.assertEqual(guard["last_closed_candle"], "2000000000000")
            finally:
                worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE, worker.STRATEGIES = original


    def test_position_size_respects_risk_after_fees_and_slippage(self):
        cash, price, atr = 1000.0, 500.0, 2.0
        qty = worker.calculate_position_size(cash, price, atr)
        entry = price * (1 + worker.SLIPPAGE)
        stop = entry - 3 * atr
        exit_fill = stop * (1 - worker.SLIPPAGE)
        modeled_loss = qty * (entry * (1 + worker.FEE) - exit_fill * (1 - worker.FEE))
        self.assertGreater(qty, 0)
        self.assertLessEqual(modeled_loss, cash * worker.RISK + 1e-9)
        self.assertLessEqual(qty * entry * (1 + worker.FEE), cash * worker.MAX_NOTIONAL + 1e-9)

    def test_position_size_rejects_invalid_market_inputs(self):
        self.assertEqual(worker.calculate_position_size(1000, 0, 2), 0)
        self.assertEqual(worker.calculate_position_size(1000, 500, 0), 0)
        self.assertEqual(worker.calculate_position_size(1000, 500, 200), 0)

    def test_closed_candle_freshness_guard(self):
        now_ms = 2_000_000_000_000
        interval_ms = 900_000
        fresh_open = now_ms - interval_ms - 60_000
        stale_open = now_ms - (4 * interval_ms)
        self.assertTrue(worker.candle_is_fresh(fresh_open, "15", now_ms))
        self.assertFalse(worker.candle_is_fresh(stale_open, "15", now_ms))
        self.assertFalse(worker.candle_is_fresh(now_ms, "15", now_ms))

    def test_ticker_price_must_be_finite_and_positive(self):
        self.assertEqual(worker.validate_ticker_price("123.45"), 123.45)
        for invalid in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                worker.validate_ticker_price(invalid)

    def test_binance_ticker_requires_recent_last_trade_timestamp(self):
        now_ms = 2_000_000_000_000
        fresh = {"closeTime": now_ms - 1000, "lastPrice": "123.45"}
        stale = {"closeTime": now_ms - 31000, "lastPrice": "123.45"}
        self.assertEqual(worker.validate_binance_ticker(fresh, now_ms), 123.45)
        with self.assertRaises(ValueError):
            worker.validate_binance_ticker(stale, now_ms)
        with self.assertRaises(ValueError):
            worker.validate_binance_ticker({"closeTime": 0, "lastPrice": "123.45"}, now_ms)

    def test_daily_loss_limit_includes_open_position_loss(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "risk.sqlite"
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            worker.init_db(conn)
            position = {"qty": 1.0, "entry": 100.0, "entry_fee": 0.1}
            self.assertFalse(worker.daily_loss_limit_hit(
                conn, "BNB_15M_EMA_TREND", position, 99.9, today="2099-01-01"
            ))
            self.assertTrue(worker.daily_loss_limit_hit(
                conn, "BNB_15M_EMA_TREND", position, 70.0, today="2099-01-01"
            ))
            conn.close()

    def test_status_reports_partial_worker_failures(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            original = (worker.DATA_DIR, worker.STATUS_FILE)
            try:
                worker.DATA_DIR = Path(temporary)
                worker.STATUS_FILE = Path(temporary) / "status.json"
                conn = sqlite3.connect(":memory:")
                conn.row_factory = sqlite3.Row
                worker.init_db(conn)
                worker.export_status(conn, worker_errors=2, successful_strategies=4)
                import json
                status = json.loads(worker.STATUS_FILE.read_text(encoding="utf-8"))
                self.assertEqual(status["worker_health"]["error_count"], 2)
                self.assertEqual(status["worker_health"]["successful_strategies"], 4)
                self.assertFalse(status["worker_health"]["all_strategies_ok"])
                conn.close()
            finally:
                worker.DATA_DIR, worker.STATUS_FILE = original

    def test_worker_returns_failure_when_market_data_fails(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            original = (worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE)
            try:
                worker.ROOT = tmp_path
                worker.DATA_DIR = tmp_path / "state"
                worker.DB = worker.DATA_DIR / "ashur_shadow.db"
                worker.STATUS_FILE = worker.DATA_DIR / "ashur_shadow_status.json"

                def unavailable(*args, **kwargs):
                    raise RuntimeError("simulated market-data outage")

                with patch.object(worker, "fetch_bybit_klines", side_effect=unavailable):
                    with self.assertRaises(SystemExit) as result:
                        worker.run()

                self.assertEqual(result.exception.code, 1)
                self.assertTrue(worker.STATUS_FILE.exists())
                status = worker.STATUS_FILE.read_text(encoding="utf-8")
                self.assertIn('"mode": "PAPER_ONLY"', status)
                self.assertIn('"error_count": 6', status)
                self.assertIn('"all_strategies_ok": false', status)
            finally:
                worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
