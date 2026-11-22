""""Offline tests for free-source ASHUR News Intelligence."""
import importlib.util
import sqlite3
import unittest
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

    def test_neutral_title_does_not_trigger_risk_veto(self):
        result = news.classify_title("Bitcoin market update: prices remain stable")
        self.assertFalse(result["high_risk"])
        self.assertEqual(result["sentiment"], "neutral")

    def test_deduplicates_same_url_and_stores_per_symbol(self):
        conn = sqlite3.connect(":memory:")
        news.init_db(conn)
        item = {"title": "Exchange exploit: withdrawals suspended", "url": "https://example.test/story",
                "published_at": "", "source": "Test"}
        self.assertEqual(news.save_items(conn, "BTC/USDT", [item]), 1)
        self.assertEqual(news.save_items(conn, "BTC/USDT", [item]), 0)
        self.assertIsNotNone(news.high_risk_news(conn, "BTC/USDT"))
        self.assertIsNone(news.high_risk_news(conn, "ETH/USDT"))
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
