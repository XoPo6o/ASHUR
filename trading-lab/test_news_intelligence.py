""""Offline tests for free-source ASHUR News Intelligence."""
import importlib.util
import sqlite3
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
import unittest
from email.utils import format_datetime
from pathlib import Path

MODULE = Path(__file__).with_name("news_intelligence.py")
spec = importlib.util.spec_from_file_location("news_intelligence", MODULE)
news = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news)

class TestNewsIntelligence(unittest.TestCase):
    def test_fetch_feed_retries_429_and_honors_retry_after(self):
        url = "https://news.google.com/rss/search?q=Bitcoin"
        rate_limited = HTTPError(url, 429, "Too Many Requests",
                                 {"Retry-After": "2"}, BytesIO(b""))
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit):
                return b"<rss><channel /></rss>"

        with patch.object(news.urllib.request, "urlopen",
                          side_effect=[rate_limited, Response()]) as opener:
            with patch.object(news.time, "sleep") as sleeper:
                self.assertEqual(news.fetch_feed(url), [])
        self.assertEqual(opener.call_count, 2)
        sleeper.assert_called_once_with(2.0)

    def test_fetch_feed_does_not_retry_when_retry_after_exceeds_safe_wait(self):
        url = "https://news.google.com/rss/search?q=Bitcoin"
        rate_limited = HTTPError(url, 429, "Too Many Requests",
                                 {"Retry-After": "60"}, BytesIO(b""))
        with patch.object(news.urllib.request, "urlopen",
                          side_effect=rate_limited) as opener:
            with patch.object(news.time, "sleep") as sleeper:
                with self.assertRaises(HTTPError):
                    news.fetch_feed(url)
        opener.assert_called_once()
        sleeper.assert_not_called()

    def test_google_news_source_is_free_rss_without_api_key(self):
        url = news.google_news_url("Bitcoin")
        self.assertTrue(url.startswith("https://news.google.com/rss/search?"))
        self.assertNotIn("api_key", url.lower())

    def test_classifies_severe_security_events_as_high_risk(self):
        result = news.classify_title("Major exploit reported at exchange; withdrawals suspended")
        self.assertEqual(result["sentiment"], "bearish")
        self.assertTrue(result["high_risk"])

    def test_substring_inside_hackathon_does_not_trigger_security_veto(self):
        result = news.classify_title("Crypto hackathon announces a new developer event")
        self.assertFalse(result["high_risk"])
        self.assertEqual(result["sentiment"], "neutral")

    def test_neutral_title_does_not_trigger_risk_veto(self):
        result = news.classify_title("Bitcoin market update: prices remain stable")
        self.assertFalse(result["high_risk"])
        self.assertEqual(result["sentiment"], "neutral")

    def test_deduplicates_same_url_and_stores_per_symbol(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        item = {"title": "Exchange exploit: withdrawals suspended", "url": "https://example.test/story",
                "published_at": format_datetime(news.utc_now()), "source": "Test"}
        self.assertEqual(news.save_items(conn, "BTC/USDT", [item]), 1)
        self.assertEqual(news.save_items(conn, "BTC/USDT", [item]), 0)
        veto = news.high_risk_news(conn, "BTC/USDT")
        self.assertIsNotNone(veto)
        self.assertTrue(veto["id"])
        self.assertIsNone(news.high_risk_news(conn, "ETH/USDT"))
        conn.close()

    def test_old_headline_does_not_veto_a_new_entry(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        old = news.utc_now() - news.timedelta(hours=12)
        item = {"title": "Exchange exploit: withdrawals suspended", "url": "https://example.test/old",
                "published_at": format_datetime(old), "source": "Test"}
        news.save_items(conn, "BTC/USDT", [item])
        self.assertIsNone(news.high_risk_news(conn, "BTC/USDT", hours=6))
        conn.close()

    def test_collector_persists_run_metrics_and_feed_errors(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        calls = {"count": 0}
        def fake_fetch(url):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("temporary feed outage")
            return [{"title": "Bitcoin market update", "url": "https://example.test/metric",
                     "published_at": format_datetime(news.utc_now()), "source": "Test"}]
        result = news.collect(conn, fetcher=fake_fetch)
        stats = news.collection_stats(conn, 24)
        self.assertEqual(stats["collector_runs"], 1)
        self.assertEqual(stats["fetched"], result["fetched"])
        self.assertEqual(stats["inserted"], result["inserted"])
        self.assertEqual(stats["feed_errors"], 1)
        self.assertIn("BTC/USDT", result["by_symbol"])
        conn.close()

    def test_veto_outcomes_capture_1h_4h_and_24h_counterfactual_returns(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        headline = {"id": "news-1", "title": "Exchange exploit", "source": "Test"}
        self.assertTrue(news.record_veto(conn, "strategy-a", "BTC/USDT", headline, 100.0))
        self.assertFalse(news.record_veto(conn, "strategy-a", "BTC/USDT", headline, 100.0))
        vetoed_at = news.datetime.fromisoformat(conn.execute(
            "SELECT vetoed_at FROM news_veto_outcomes"
        ).fetchone()[0])
        self.assertEqual(news.update_veto_outcomes(
            conn, "BTC/USDT", 98.0, vetoed_at + news.timedelta(hours=1)), 1)
        self.assertEqual(news.update_veto_outcomes(
            conn, "BTC/USDT", 102.0, vetoed_at + news.timedelta(hours=4)), 1)
        self.assertEqual(news.update_veto_outcomes(
            conn, "BTC/USDT", 95.0, vetoed_at + news.timedelta(hours=24)), 1)
        stats = news.veto_outcome_stats(conn)
        self.assertEqual(stats["tracked_vetoes"], 1)
        self.assertEqual(stats["measured_1h"], 1)
        self.assertEqual(stats["measured_4h"], 1)
        self.assertEqual(stats["measured_24h"], 1)
        self.assertEqual(stats["avoided_loss_1h"], 1)
        self.assertEqual(stats["missed_gain_4h"], 1)
        conn.close()

    def test_late_observation_is_not_mislabeled_as_1h_return(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        headline = {"id": "news-late", "title": "Exchange exploit", "source": "Test"}
        news.record_veto(conn, "strategy-a", "BTC/USDT", headline, 100.0)
        vetoed_at = news.datetime.fromisoformat(conn.execute(
            "SELECT vetoed_at FROM news_veto_outcomes"
        ).fetchone()[0])
        self.assertEqual(news.update_veto_outcomes(
            conn, "BTC/USDT", 97.0, vetoed_at + news.timedelta(hours=2)), 0)
        self.assertEqual(news.update_veto_outcomes(
            conn, "BTC/USDT", 96.0, vetoed_at + news.timedelta(hours=4)), 1)
        stats = news.veto_outcome_stats(conn)
        self.assertEqual(stats["measured_1h"], 0)
        self.assertEqual(stats["measured_4h"], 1)
        conn.close()

    def test_future_dated_headline_does_not_veto(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        future = news.utc_now() + news.timedelta(hours=2)
        item = {"title": "Exchange exploit: withdrawals suspended", "url": "https://example.test/future",
                "published_at": format_datetime(future), "source": "Test"}
        news.save_items(conn, "BTC/USDT", [item])
        self.assertIsNone(news.high_risk_news(conn, "BTC/USDT", hours=6))
        conn.close()

    def test_collector_respects_minimum_interval(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        now = news.utc_now()
        conn.execute("""INSERT INTO news_collection_runs
            (started_at,finished_at,source_count,fetched_count,inserted_count,error_count,errors_json)
            VALUES(?,?,?,?,?,?,?)""",
            (now.isoformat(), now.isoformat(), 1, 10, 5, 0, "[]"))
        conn.commit()
        def should_not_fetch(url):
            raise AssertionError("RSS fetch must be skipped inside the minimum interval")
        result = news.collect_if_due(conn, fetcher=should_not_fetch,
                                     min_interval_seconds=900, at=now + news.timedelta(minutes=5))
        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "minimum_interval")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM news_collection_runs").fetchone()[0], 1)
        conn.close()

    def test_collector_continues_when_one_feed_fails(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        calls = {"count": 0}
        def fake_fetch(url):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("temporary feed outage")
            return [{"title": "Bitcoin partnership announced", "url": "https://example.test/ok",
                     "published_at": "", "source": "Test"}]
        result = news.collect(conn, fetcher=fake_fetch)
        self.assertEqual(len(result["errors"]), 1)
        self.assertGreaterEqual(result["fetched"], 1)
        conn.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
