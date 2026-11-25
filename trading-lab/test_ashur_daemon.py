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


    def test_signals_use_closed_candle_not_intrabar_ticker(self):
        import tempfile
        import pandas as pd

        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            original = (worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE, worker.STRATEGIES)
            strategy = {
                "id": "BNB_15M_EMA_TREND", "symbol": "BNB/USDT", "interval": "15",
                "label": "closed candle test", "grade": "PAPER_VALIDATION",
            }
            observed_closes = []
            try:
                worker.ROOT = tmp_path
                worker.DATA_DIR = tmp_path / "state"
                worker.DB = worker.DATA_DIR / "ashur_shadow.db"
                worker.STATUS_FILE = worker.DATA_DIR / "ashur_shadow_status.json"
                worker.STRATEGIES = [strategy]
                worker.prepare_data_dir()

                closed_candle = pd.DataFrame([{
                    "timestamp": 2_000_000_000_000,
                    "close": 100.0,
                    "atr": 1.0,
                }])

                def capture_signal_input(row, strategy_id):
                    observed_closes.append(float(row.close))
                    return False, False

                with patch.object(worker, "fetch_bybit_klines", return_value=object()), \
                     patch.object(worker, "indicators", return_value=closed_candle), \
                     patch.object(worker, "fetch_ticker", return_value=90.0), \
                     patch.object(worker, "signals", side_effect=capture_signal_input):
                    worker.run()

                self.assertEqual(observed_closes, [100.0])
                self.assertNotEqual(observed_closes[0], 90.0)
            finally:
                worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE, worker.STRATEGIES = original


    def test_ohlcv_continuity_rejects_missing_strategy_candles(self):
        import pandas as pd

        start = 1_999_999_800_000
        complete = pd.DataFrame([
            {"timestamp": start, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1.0},
            {"timestamp": start + 900_000, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 1.0},
            {"timestamp": start + 1_800_000, "open": 101.0, "high": 103.0, "low": 100.5, "close": 102.0, "volume": 1.0},
        ])
        self.assertEqual(len(worker.validate_ohlcv_continuity(complete, "15")), 3)
        missing = complete.drop(index=1).reset_index(drop=True)
        with self.assertRaisesRegex(ValueError, "missing or irregular"):
            worker.validate_ohlcv_continuity(missing, "15")


    def test_ohlcv_validation_rejects_malformed_market_data(self):
        import pandas as pd

        valid = pd.DataFrame([
            {"timestamp": 1_800_000_000_000, "open": 100.0, "high": 105.0,
             "low": 99.0, "close": 103.0, "volume": 10.0},
            {"timestamp": 1_800_000_900_000, "open": 103.0, "high": 106.0,
             "low": 101.0, "close": 104.0, "volume": 12.0},
        ])
        self.assertEqual(len(worker.validate_ohlcv_frame(valid, "15")), 2)

        invalid_cases = []
        duplicate = valid.copy()
        duplicate.loc[1, "timestamp"] = duplicate.loc[0, "timestamp"]
        invalid_cases.append(duplicate)

        bad_range = valid.copy()
        bad_range.loc[1, "high"] = 102.0
        invalid_cases.append(bad_range)

        negative_volume = valid.copy()
        negative_volume.loc[1, "volume"] = -1.0
        invalid_cases.append(negative_volume)

        non_finite = valid.copy()
        non_finite.loc[1, "close"] = float("nan")
        invalid_cases.append(non_finite)

        misaligned = valid.copy()
        misaligned.loc[1, "timestamp"] += 1
        invalid_cases.append(misaligned)

        for frame in invalid_cases:
            with self.subTest(frame=frame.to_dict()):
                with self.assertRaises(ValueError):
                    worker.validate_ohlcv_frame(frame, "15")

    def test_open_position_equity_includes_exit_fee_and_slippage(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            original = (worker.DATA_DIR, worker.STATUS_FILE)
            try:
                worker.DATA_DIR = Path(temporary)
                worker.STATUS_FILE = Path(temporary) / "status.json"
                conn = sqlite3.connect(":memory:")
                conn.row_factory = sqlite3.Row
                worker.init_db(conn)
                strategy_id = "BNB_15M_EMA_TREND"
                conn.execute(
                    "UPDATE shadow_accounts SET cash=? WHERE strategy_id=?",
                    (899.9, strategy_id),
                )
                conn.execute(
                    """INSERT INTO shadow_positions
                       (strategy_id,symbol,qty,entry,entry_fee,stop,target,opened_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (strategy_id, "BNB/USDT", 1.0, 100.0, 0.1, 97.0, 112.0,
                     "2026-11-23T10:00:00+00:00"),
                )
                conn.execute(
                    "INSERT INTO shadow_marks VALUES(?,?,?)",
                    (strategy_id, 110.0, "2026-11-23T10:05:00+00:00"),
                )
                worker.export_status(conn)
                status = json.loads(worker.STATUS_FILE.read_text(encoding="utf-8"))
                account = next(x for x in status["accounts"] if x["strategy_id"] == strategy_id)
                net_liquidation = 110.0 * (1 - worker.SLIPPAGE) * (1 - worker.FEE)
                expected_equity = 899.9 + net_liquidation
                expected_unrealized = net_liquidation - (100.0 + 0.1)
                self.assertAlmostEqual(account["equity"], expected_equity, places=4)
                self.assertAlmostEqual(account["unrealized_pnl"], expected_unrealized, places=4)
                conn.close()
            finally:
                worker.DATA_DIR, worker.STATUS_FILE = original


    def test_minute_feed_outage_does_not_disable_signal_exit(self):
        import json
        import tempfile
        import pandas as pd

        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            original = (worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE, worker.STRATEGIES)
            strategy = {
                "id": "BNB_15M_EMA_TREND", "symbol": "BNB/USDT", "interval": "15",
                "label": "minute feed outage test", "grade": "PAPER_VALIDATION",
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
                    """INSERT INTO shadow_positions
                       (strategy_id,symbol,qty,entry,entry_fee,stop,target,opened_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (strategy["id"], strategy["symbol"], 1.0, 100.0, 0.1,
                     95.0, 120.0, "2026-11-23T10:00:00+00:00"),
                )
                conn.execute(
                    "INSERT INTO shadow_intrabar_state VALUES(?,?)",
                    (strategy["id"], worker.minute_cursor_for_now() - 60000),
                )
                conn.commit()
                conn.close()

                closed_candle = pd.DataFrame([{
                    "timestamp": 2_000_000_000_000, "close": 100.0, "atr": 1.0,
                }])
                with (
                    patch.object(worker, "fetch_bybit_klines", return_value=object()),
                    patch.object(worker, "indicators", return_value=closed_candle),
                    patch.object(worker, "fetch_ticker", return_value=100.0),
                    patch.object(worker, "signals", return_value=(False, True)),
                    patch.object(worker, "fetch_execution_klines", side_effect=RuntimeError("minute API unavailable")),
                ):
                    worker.run()

                conn = sqlite3.connect(worker.DB)
                trade = conn.execute(
                    "SELECT reason FROM shadow_trades WHERE strategy_id=?",
                    (strategy["id"],),
                ).fetchone()
                conn.close()
                self.assertEqual(trade[0], "PROTECTION_GAP_FAILSAFE")
                status = json.loads(worker.STATUS_FILE.read_text(encoding="utf-8"))
                self.assertEqual(status["worker_health"]["intrabar_data_warnings_24h"], 1)
                account = next(x for x in status["accounts"] if x["strategy_id"] == strategy["id"])
                self.assertIsNone(account["position"])
            finally:
                worker.ROOT, worker.DATA_DIR, worker.DB, worker.STATUS_FILE, worker.STRATEGIES = original


    def test_intrabar_exit_uses_earliest_minute_and_conservative_same_bar_order(self):
        import pandas as pd

        position = {"stop": 95.0, "target": 120.0}
        candles = pd.DataFrame([
            {"timestamp": 1_000, "open": 100.0, "high": 110.0, "low": 99.0, "close": 105.0, "volume": 1.0},
            {"timestamp": 61_000, "open": 105.0, "high": 121.0, "low": 103.0, "close": 119.0, "volume": 1.0},
            {"timestamp": 121_000, "open": 119.0, "high": 122.0, "low": 90.0, "close": 100.0, "volume": 1.0},
        ])
        self.assertEqual(worker.intrabar_exit_signal(position, candles), ("TARGET", 120.0, 61_000))
        target_gap = pd.DataFrame([
            {"timestamp": 301_000, "open": 125.0, "high": 128.0, "low": 121.0, "close": 126.0, "volume": 1.0},
        ])
        self.assertEqual(worker.intrabar_exit_signal(position, target_gap), ("TARGET", 120.0, 301_000))

        both_touched = pd.DataFrame([
            {"timestamp": 181_000, "open": 100.0, "high": 125.0, "low": 90.0, "close": 110.0, "volume": 1.0},
        ])
        self.assertEqual(worker.intrabar_exit_signal(position, both_touched), ("STOP", 95.0, 181_000))

    def test_execution_candles_reject_missing_first_minute_and_internal_gaps(self):
        import pandas as pd

        now_ms = (2_000_000_000_000 // 60000) * 60000 + 30_000
        since_ms = (now_ms // 60000) * 60000 - 180_000
        contiguous = pd.DataFrame([
            {"timestamp": since_ms, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1.0},
            {"timestamp": since_ms + 60_000, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 1.0},
        ])
        checked = worker.validate_execution_klines(contiguous, since_ms, now_ms)
        self.assertEqual(len(checked), 2)

        missing_first = contiguous.iloc[1:].reset_index(drop=True)
        with self.assertRaisesRegex(RuntimeError, "gap before first candle"):
            worker.validate_execution_klines(missing_first, since_ms, now_ms)

        internal_gap = pd.concat([
            contiguous.iloc[:1],
            contiguous.iloc[1:].assign(timestamp=since_ms + 120_000),
        ], ignore_index=True)
        with self.assertRaisesRegex(RuntimeError, "missing-minute gap"):
            worker.validate_execution_klines(internal_gap, since_ms, now_ms)

    def test_empty_execution_candles_are_allowed_when_no_minute_closed_yet(self):
        import pandas as pd

        empty = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        now_ms = (2_000_000_000_000 // 60000) * 60000 + 20_000
        checked = worker.validate_execution_klines(empty, (now_ms // 60000) * 60000, now_ms)
        self.assertTrue(checked.empty)
        with self.assertRaisesRegex(RuntimeError, "missing"):
            worker.validate_execution_klines(empty, (now_ms // 60000) * 60000 - 120_000, now_ms)


    def test_intrabar_gap_stop_uses_candle_open(self):
        import pandas as pd

        position = {"stop": 95.0, "target": 120.0}
        candles = pd.DataFrame([
            {"timestamp": 241_000, "open": 90.0, "high": 94.0, "low": 88.0, "close": 92.0, "volume": 1.0},
        ])
        self.assertEqual(worker.intrabar_exit_signal(position, candles), ("GAP_STOP", 90.0, 241_000))

    def test_minute_cursor_rounds_down_to_current_minute(self):
        self.assertEqual(worker.minute_cursor_for_now(125_999), 120_000)

    def test_intrabar_cursor_is_never_reset_after_long_worker_outage(self):
        now_ms = 2_000_000_000_000
        recent = now_ms - 10 * 60000
        stale = now_ms - 3087 * 60000
        self.assertEqual(worker.recover_intrabar_cursor(recent, now_ms), recent)
        self.assertEqual(worker.recover_intrabar_cursor(stale, now_ms), stale)

    def test_intrabar_history_paginates_full_51_hour_window(self):
        import pandas as pd
        now_ms = 2_000_000_000_000
        cutoff = now_ms
        last_open = ((cutoff - 60000) // 60000) * 60000
        since = last_open - 2001 * 60000
        original_time = worker.time.time
        original_api = worker.api_json
        requests = []

        def fake_api(url):
            from urllib.parse import urlparse, parse_qs
            params = parse_qs(urlparse(url).query)
            start = int(params.get("start", params.get("startTime"))[0])
            end = int(params.get("end", params.get("endTime"))[0])
            requests.append((start, end))
            stamps = list(range(start, end, 60000))[:worker.EXECUTION_KLINE_PAGE_SIZE]
            rows = [[stamp, "100", "101", "99", "100", "1"] for stamp in reversed(stamps)]
            return {"retCode": 0, "result": {"list": rows}}

        try:
            worker.time.time = lambda: cutoff / 1000
            worker.api_json = fake_api
            candles = worker._fetch_execution_pages("BNB/USDT", since, cutoff, "bybit")
            self.assertEqual(len(candles), 2002)
            self.assertEqual(int(candles.iloc[0].timestamp), since)
            self.assertEqual(int(candles.iloc[-1].timestamp), last_open)
            self.assertGreaterEqual(len(requests), 3)
            self.assertTrue((candles.timestamp.diff().dropna() == 60000).all())
        finally:
            worker.time.time = original_time
            worker.api_json = original_api


    def test_target_gap_fill_is_capped_at_target_reference(self):
        self.assertEqual(worker.target_exit_reference_price(125.0, 120.0), 120.0)
        self.assertEqual(worker.target_exit_reference_price(120.0, 120.0), 120.0)
        self.assertEqual(worker.target_exit_reference_price(118.0, 120.0), 118.0)


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
