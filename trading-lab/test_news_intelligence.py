""""Offline tests for free-source ASHUR News Intelligence."""
import importlib.util
import sqlite3
import unittest
from email.utils import format_datetime
from pathlib import Path

MODULE = Path(__file__).with_name("news_intelligence.py")
spec = importlib.util.spec_from_file_location("news_intelligence", MODULE)
news = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news)

class TestNewsIntelligence(unittest.TestCase):
    def test_google_news_source_is_free_rss_without_api_key(self):
        url = news.google_news_url("Bitcoin")
        self.assertTrue(url.startswith("https://news.google.com/rss/search?"))
        self.assertNotIn("api_key", url.lower())

    def test_classifies_severe_security_events_as_high_risk(self):
        result = news.classify_title("Major exploit reported at exchange; withdrawals suspended")
        self.assertEqual(result["sentiment"], "bearish")
        self.assertTrue(result["high_risk"])

    def test_substring_inside_hackathon_does_not_trigger_security_veto(self):
        result = news.classify_title("Crypto hackathon announces new developer partnership")
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
        self.assertIsNotNone(news.high_risk_news(conn, "BTC/USDT"))
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

    def test_future_dated_headline_does_not_veto(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        future = news.utc_now() + news.timedelta(hours=2)
        item = {"title": "Exchange exploit: withdrawals suspended", "url": "https://example.test/future",
                "published_at": format_datetime(future), "source": "Test"}
        news.save_items(conn, "BTC/USDT", [item])
        self.assertIsNone(news.high_risk_news(conn, "BTC/USDT", hours=6))
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
