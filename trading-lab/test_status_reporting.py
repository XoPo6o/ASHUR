"""Regression tests for accurate Paper status reporting."""
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import live_shadow_worker as worker
import news_intelligence as news


def test_empty_strategy_win_rate_is_null_and_news_outcomes_are_baseline_scoped():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    worker.init_db(conn)
    news.init_db(conn)

    baseline_at = "2026-11-25T10:51:24.754378+00:00"
    conn.execute("INSERT INTO ashur_meta(key,value) VALUES(?,?)",
                 ("paper_baseline_id", "ashur-paper-30d-2026-11-25-v2"))
    conn.execute("INSERT INTO ashur_meta(key,value) VALUES(?,?)",
                 ("paper_baseline_at", baseline_at))
    conn.execute(
        """INSERT INTO news_veto_outcomes
           (strategy_id,symbol,news_id,headline,source,vetoed_at,entry_reference)
           VALUES(?,?,?,?,?,?,?)""",
        ("old-strategy", "BNB/USDT", "old-news", "Old headline", "Test",
         "2026-11-24T10:00:00+00:00", 600.0),
    )
    conn.execute(
        """INSERT INTO news_veto_outcomes
           (strategy_id,symbol,news_id,headline,source,vetoed_at,entry_reference)
           VALUES(?,?,?,?,?,?,?)""",
        ("new-strategy", "BNB/USDT", "new-news", "New headline", "Test",
         "2026-11-25T18:16:45+00:00", 600.0),
    )
    conn.commit()

    with tempfile.TemporaryDirectory() as tmp:
        old_data_dir, old_status_file = worker.DATA_DIR, worker.STATUS_FILE
        worker.DATA_DIR = Path(tmp)
        worker.STATUS_FILE = Path(tmp) / "status.json"
        try:
            worker.export_status(conn)
            status = json.loads(worker.STATUS_FILE.read_text(encoding="utf-8"))
        finally:
            worker.DATA_DIR, worker.STATUS_FILE = old_data_dir, old_status_file

    assert status["mode"] == "PAPER_ONLY"
    assert status["experiment"]["baseline_id"] == "ashur-paper-30d-2026-11-25-v2"
    assert status["worker_health"]["all_strategies_ok"] is True
    assert status["worker_health"]["all_protections_ok"] is True
    assert len(status["accounts"]) == 6
    assert all(a["trades"] == 0 and a["win_rate_pct"] is None for a in status["accounts"])
    intelligence = status["news_intelligence"]
    assert intelligence["veto_outcomes"]["tracked_vetoes"] == 2
    assert intelligence["baseline_veto_outcomes"]["tracked_vetoes"] == 1
    assert intelligence["baseline_veto_outcomes"]["avg_net_return_24h_pct"] is None
    assert intelligence["news_veto_attempts_24h"] == 0
    for account in status["accounts"]:
        assert len(account["equity_curve_24h"]) == 1
        assert len(account["equity_curve_30d_hourly"]) == 1
        assert account["pnl_24h"] is None
        assert account["cycle_gap_max_seconds_24h"] is None
        assert account["fees_total"] == 0
        assert account["fees_24h"] == 0
        assert account["fee_assumption_pct_each_side"] == 0.1
        assert account["slippage_assumption_pct_each_side"] == 0.05
        assert len(account["realized_equity_curve_since_baseline"]) == 1
    assert conn.execute("SELECT COUNT(*) FROM shadow_equity_snapshots").fetchone()[0] == 6
    conn.close()


def test_equity_history_metrics_calculates_24h_pnl_drawdown_and_cycle_gaps():
    rows = [
        {"snapshot_at": "2026-11-25T11:55:00+00:00", "equity": 990.0},
        {"snapshot_at": "2026-11-25T12:05:00+00:00", "equity": 1000.0},
        {"snapshot_at": "2026-11-26T11:55:00+00:00", "equity": 1010.0},
        {"snapshot_at": "2026-11-26T12:00:00+00:00", "equity": 1005.0},
    ]
    now_dt = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    metrics = worker.equity_history_metrics(rows, 1000.0, now_dt)

    assert metrics["pnl_24h"] == 15.0
    assert metrics["max_drawdown_pct_30d"] == 1.0
    assert metrics["current_drawdown_pct_30d"] == 0.495
    assert metrics["cycle_gap_max_seconds_24h"] == 85800.0
    assert metrics["latest_snapshot_age_seconds"] == 0.0
    assert metrics["snapshot_count_24h"] == 3
    assert metrics["snapshot_count_30d"] == 4
    assert len(metrics["equity_curve_24h"]) == 3
    assert len(metrics["equity_curve_30d_hourly"]) == 4


def test_realized_equity_curve_reconstructs_baseline_and_trade_closes():
    trades = [
        {"closed_at": "2026-11-25T12:00:00+00:00", "pnl": -5.0},
        {"closed_at": "2026-11-25T13:00:00+00:00", "pnl": 10.0},
    ]
    curve, max_drawdown = worker.realized_equity_history(
        trades, 1000.0, "2026-11-25T10:00:00+00:00"
    )
    assert [point["equity"] for point in curve] == [1000.0, 995.0, 1005.0]
    assert max_drawdown == 0.5



def test_baseline_reset_clears_persisted_equity_snapshots():
    with tempfile.TemporaryDirectory() as tmp:
        old_data_dir, old_db, old_status = worker.DATA_DIR, worker.DB, worker.STATUS_FILE
        worker.DATA_DIR = Path(tmp)
        worker.DB = Path(tmp) / "ashur_shadow.db"
        worker.STATUS_FILE = Path(tmp) / "ashur_shadow_status.json"
        try:
            conn = sqlite3.connect(worker.DB)
            conn.row_factory = sqlite3.Row
            worker.init_db(conn)
            conn.execute(
                "INSERT INTO ashur_meta(key,value) VALUES('paper_baseline_id','old-baseline')"
            )
            conn.execute(
                "INSERT INTO ashur_meta(key,value) VALUES('paper_baseline_at','2026-11-20T00:00:00+00:00')"
            )
            conn.execute(
                """INSERT INTO shadow_equity_snapshots
                   (snapshot_at,strategy_id,cash,equity,realized_pnl,unrealized_pnl,fees_total)
                   VALUES(?,?,?,?,?,?,?)""",
                ("2026-11-20T01:00:00+00:00", "BNB_15M_EMA_TREND", 995, 995, -5, 0, 1),
            )
            conn.commit()

            assert worker.reset_paper_baseline_once(conn) is True
            assert conn.execute(
                "SELECT COUNT(*) FROM shadow_equity_snapshots"
            ).fetchone()[0] == 0
            assert conn.execute(
                "SELECT value FROM ashur_meta WHERE key='paper_baseline_id'"
            ).fetchone()[0] == worker.PAPER_BASELINE_ID
            assert (Path(tmp) / f"ashur_shadow.pre_{worker.PAPER_BASELINE_ID}.sqlite3").exists()
            conn.close()
        finally:
            worker.DATA_DIR, worker.DB, worker.STATUS_FILE = old_data_dir, old_db, old_status
