"""Regression tests for accurate Paper status reporting."""
import json
import sqlite3
import tempfile
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

    assert len(status["accounts"]) == 6
    assert all(a["trades"] == 0 and a["win_rate_pct"] is None for a in status["accounts"])
    intelligence = status["news_intelligence"]
    assert intelligence["veto_outcomes"]["tracked_vetoes"] == 2
    assert intelligence["baseline_veto_outcomes"]["tracked_vetoes"] == 1
    assert intelligence["baseline_veto_outcomes"]["avg_net_return_24h_pct"] is None
    assert intelligence["news_veto_attempts_24h"] == 0
    conn.close()
