"""Regression tests for deduplicated high-risk news veto events."""
import sqlite3

import live_shadow_worker as worker


def test_news_veto_event_is_deduplicated_per_strategy_candle_and_headline():
    conn = sqlite3.connect(":memory:")
    worker.init_db(conn)
    headline = {"id": "headline-1", "title": "Exchange exploit reported"}

    assert worker.log_news_veto_once(conn, "BNB_15M_EMA_TREND", "candle-100", headline) is True
    conn.commit()
    assert worker.log_news_veto_once(conn, "BNB_15M_EMA_TREND", "candle-100", headline) is False
    assert worker.log_news_veto_once(conn, "BNB_15M_EMA_TREND", "candle-115", headline) is True
    assert worker.log_news_veto_once(
        conn, "BNB_15M_EMA_TREND", "candle-115",
        {"id": "headline-2", "title": "Second exchange exploit"}
    ) is True

    rows = conn.execute(
        "SELECT strategy_id,event,details FROM shadow_events WHERE event='NEWS_VETO' ORDER BY id"
    ).fetchall()
    assert len(rows) == 3
    assert "candle=candle-100; news_id=headline-1" in rows[0][2]
    assert "candle=candle-115; news_id=headline-1" in rows[1][2]
    assert "candle=candle-115; news_id=headline-2" in rows[2][2]
    conn.close()
