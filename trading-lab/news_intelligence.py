#!/usr/bin/env python3
"""Free-source ASHUR news collector. Metadata only; no paid APIs or trading actions."""
import hashlib
from email.utils import parsedate_to_datetime
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("ASHUR_DATA_DIR", str(Path.home() / ".local/share/ashur"))).expanduser()
DB = DATA_DIR / "ashur_shadow.db"
USER_AGENT = "ASHUR-News-Intelligence/0.1 (paper research)"
SYMBOL_QUERIES = {
    "BTC/USDT": '"Bitcoin" OR BTC crypto',
    "ETH/USDT": '"Ethereum" OR ETH crypto',
    "BNB/USDT": '"BNB" OR Binance Coin crypto',
    "SOL/USDT": '"Solana" OR SOL crypto',
}
NEGATIVE_TERMS = {
    "hack": 0.9, "hacked": 0.9, "exploit": 0.9, "breach": 0.9,
    "bankruptcy": 1.0, "insolvency": 1.0, "fraud": 0.9,
    "delist": 0.85, "delisting": 0.85, "trading halt": 0.85,
    "lawsuit": 0.65, "sued": 0.7, "investigation": 0.6,
    "outage": 0.55, "withdrawals suspended": 0.95,
}
POSITIVE_TERMS = {"approval": 0.5, "approved": 0.5, "launch": 0.25, "partnership": 0.25}

def utc_now():
    return datetime.now(timezone.utc)

def google_news_url(query):
    params = urllib.parse.urlencode({"q": query + " when:24h", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    return "https://news.google.com/rss/search?" + params

def fetch_feed(url, timeout=12):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(2_000_000)
    root = ET.fromstring(payload)
    items = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        published = (node.findtext("pubDate") or "").strip()
        source_node = node.find("source")
        source = (source_node.text or "").strip() if source_node is not None else "Google News RSS"
        if title and link:
            items.append({"title": title, "url": link, "published_at": published, "source": source})
    return items

def classify_title(title):
    text = re.sub(r"\s+", " ", title.lower())
    negative = max((score for term, score in NEGATIVE_TERMS.items() if term in text), default=0.0)
    positive = max((score for term, score in POSITIVE_TERMS.items() if term in text), default=0.0)
    # Conservative v0: only severe negative event terms may veto a new paper entry.
    return {"sentiment": "bearish" if negative > positive else ("bullish" if positive > negative else "neutral"),
            "score": round(positive - negative, 3), "risk": round(negative, 3),
            "high_risk": negative >= 0.85}

def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS news_items(
        id TEXT PRIMARY KEY, symbol TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
        source TEXT NOT NULL, published_at TEXT, fetched_at TEXT NOT NULL,
        sentiment TEXT NOT NULL, sentiment_score REAL NOT NULL, risk_score REAL NOT NULL,
        high_risk INTEGER NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_news_symbol_fetched ON news_items(symbol, fetched_at)")
    conn.commit()

def save_items(conn, symbol, items):
    inserted = 0
    for item in items:
        key = hashlib.sha256((symbol + "|" + (item["url"] or item["title"])).encode("utf-8")).hexdigest()
        classification = classify_title(item["title"])
        cursor = conn.execute("""INSERT OR IGNORE INTO news_items
            (id,symbol,title,url,source,published_at,fetched_at,sentiment,sentiment_score,risk_score,high_risk)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (key, symbol, item["title"], item["url"], item["source"], item["published_at"],
             utc_now().isoformat(), classification["sentiment"], classification["score"],
             classification["risk"], int(classification["high_risk"])))
        inserted += cursor.rowcount
    conn.commit()
    return inserted

def collect(conn, fetcher=fetch_feed):
    summary = {"enabled": True, "sources": ["Google News RSS"], "fetched": 0, "inserted": 0, "errors": []}
    for symbol, query in SYMBOL_QUERIES.items():
        try:
            items = fetcher(google_news_url(query))
            summary["fetched"] += len(items)
            summary["inserted"] += save_items(conn, symbol, items)
        except Exception as exc:
            summary["errors"].append(f"{symbol}: {type(exc).__name__}: {exc}")
    return summary

def high_risk_news(conn, symbol, hours=6):
    cutoff = utc_now() - timedelta(hours=hours)
    rows = conn.execute("""SELECT title, source, published_at, fetched_at, risk_score
        FROM news_items WHERE symbol=? AND high_risk=1
        ORDER BY fetched_at DESC LIMIT 100""", (symbol,)).fetchall()
    for row in rows:
        try:
            published = parsedate_to_datetime(row[2])
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published.astimezone(timezone.utc) < cutoff:
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        return {"title": row[0], "source": row[1], "published_at": row[2],
                "fetched_at": row[3], "risk_score": float(row[4])}
    return None

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=20)
    init_db(conn)
    result = collect(conn)
    print("ASHUR_NEWS_SUMMARY " + json.dumps(result, ensure_ascii=False), flush=True)
    conn.close()

if __name__ == "__main__":
    main()
