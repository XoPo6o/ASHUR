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
            finally:
                worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
