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

def _contains_term(text, term):
    # Match complete words/phrases only: "hackathon" must not trigger "hack".
    pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None

def classify_title(title):
    text = re.sub(r"\s+", " ", title.lower())
    negative = max((score for term, score in NEGATIVE_TERMS.items() if _contains_term(text, term)), default=0.0)
    positive = max((score for term, score in POSITIVE_TERMS.items() if _contains_term(text, term)), default=0.0)
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
    conn.execute("""CREATE TABLE IF NOT EXISTS news_veto_outcomes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, strategy_id TEXT NOT NULL, symbol TEXT NOT NULL,
        news_id TEXT NOT NULL, headline TEXT NOT NULL, source TEXT NOT NULL,
        vetoed_at TEXT NOT NULL, entry_reference REAL NOT NULL,
        price_1h REAL, return_1h REAL, price_4h REAL, return_4h REAL,
        price_24h REAL, return_24h REAL,
        UNIQUE(strategy_id, news_id, vetoed_at))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_news_veto_pending ON news_veto_outcomes(symbol, vetoed_at)")
    conn.execute("""CREATE TABLE IF NOT EXISTS news_collection_runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
        source_count INTEGER NOT NULL, fetched_count INTEGER NOT NULL, inserted_count INTEGER NOT NULL,
        error_count INTEGER NOT NULL, errors_json TEXT NOT NULL)""")
    conn.commit()

def collection_stats(conn, hours=24):
    cutoff = (utc_now() - timedelta(hours=hours)).isoformat()
    news_row = conn.execute("""SELECT COUNT(*), COUNT(DISTINCT url), SUM(high_risk)
        FROM news_items WHERE fetched_at >= ?""", (cutoff,)).fetchone()
    run_row = conn.execute("""SELECT COUNT(*), COALESCE(SUM(fetched_count),0),
        COALESCE(SUM(inserted_count),0), COALESCE(SUM(error_count),0)
        FROM news_collection_runs WHERE started_at >= ?""", (cutoff,)).fetchone()
    return {"window_hours": hours, "stored_items": int(news_row[0] or 0),
            "unique_urls": int(news_row[1] or 0), "high_risk_items": int(news_row[2] or 0),
            "collector_runs": int(run_row[0] or 0), "fetched": int(run_row[1] or 0),
            "inserted": int(run_row[2] or 0), "feed_errors": int(run_row[3] or 0)}

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
    started_at = utc_now().isoformat()
    summary = {"enabled": True, "sources": ["Google News RSS"], "fetched": 0,
               "inserted": 0, "errors": [], "by_symbol": {}}
    for symbol, query in SYMBOL_QUERIES.items():
        try:
            items = fetcher(google_news_url(query))
            inserted = save_items(conn, symbol, items)
            summary["fetched"] += len(items)
            summary["inserted"] += inserted
            summary["by_symbol"][symbol] = {"fetched": len(items), "inserted": inserted}
        except Exception as exc:
            message = f"{symbol}: {type(exc).__name__}: {exc}"
            summary["errors"].append(message)
            summary["by_symbol"][symbol] = {"fetched": 0, "inserted": 0, "error": message}
    conn.execute("""INSERT INTO news_collection_runs
        (started_at,finished_at,source_count,fetched_count,inserted_count,error_count,errors_json)
        VALUES(?,?,?,?,?,?,?)""",
        (started_at, utc_now().isoformat(), len(summary["sources"]), summary["fetched"],
         summary["inserted"], len(summary["errors"]), json.dumps(summary["errors"], ensure_ascii=False)))
    conn.commit()
    summary["stats_24h"] = collection_stats(conn, 24)
    return summary

def record_veto(conn, strategy_id, symbol, headline, price):
    if not headline or not headline.get("id") or float(price) <= 0:
        return False
    cursor = conn.execute("""INSERT OR IGNORE INTO news_veto_outcomes
        (strategy_id,symbol,news_id,headline,source,vetoed_at,entry_reference)
        VALUES(?,?,?,?,?,?,?)""",
        (strategy_id, symbol, headline["id"], headline["title"], headline["source"],
         utc_now().isoformat(), float(price)))
    conn.commit()
    return cursor.rowcount == 1

def update_veto_outcomes(conn, symbol, price, at=None):
    price = float(price)
    if price <= 0:
        return 0
    at = at or utc_now()
    if isinstance(at, str):
        at = datetime.fromisoformat(at)
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    updated = 0
    rows = conn.execute("""SELECT id,vetoed_at,entry_reference,price_1h,price_4h,price_24h
        FROM news_veto_outcomes WHERE symbol=? AND price_24h IS NULL""", (symbol,)).fetchall()
    for row in rows:
        try:
            vetoed_at = datetime.fromisoformat(row[1])
            if vetoed_at.tzinfo is None:
                vetoed_at = vetoed_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        elapsed = (at - vetoed_at).total_seconds()
        entry = float(row[2])
        if elapsed >= 3600 and row[3] is None:
            ret = (price * (1 - 0.0005) * (1 - 0.001)) / (entry * (1 + 0.0005) * (1 + 0.001)) - 1
            conn.execute("UPDATE news_veto_outcomes SET price_1h=?,return_1h=? WHERE id=?",
                         (price, ret, row[0]))
            updated += 1
        if elapsed >= 14400 and row[4] is None:
            ret = (price * (1 - 0.0005) * (1 - 0.001)) / (entry * (1 + 0.0005) * (1 + 0.001)) - 1
            conn.execute("UPDATE news_veto_outcomes SET price_4h=?,return_4h=? WHERE id=?",
                         (price, ret, row[0]))
            updated += 1
        if elapsed >= 86400 and row[5] is None:
            ret = (price * (1 - 0.0005) * (1 - 0.001)) / (entry * (1 + 0.0005) * (1 + 0.001)) - 1
            conn.execute("UPDATE news_veto_outcomes SET price_24h=?,return_24h=? WHERE id=?",
                         (price, ret, row[0]))
            updated += 1
    conn.commit()
    return updated

def veto_outcome_stats(conn):
    rows = conn.execute("""SELECT COUNT(*), SUM(return_1h IS NOT NULL), SUM(return_4h IS NOT NULL),
        SUM(return_24h IS NOT NULL), AVG(return_1h), AVG(return_4h), AVG(return_24h),
        SUM(return_1h < 0), SUM(return_1h > 0), SUM(return_4h < 0), SUM(return_4h > 0),
        SUM(return_24h < 0), SUM(return_24h > 0) FROM news_veto_outcomes""").fetchone()
    return {"tracked_vetoes": int(rows[0] or 0), "measured_1h": int(rows[1] or 0),
            "measured_4h": int(rows[2] or 0), "measured_24h": int(rows[3] or 0),
            "avg_net_return_1h_pct": round(float(rows[4] or 0) * 100, 4),
            "avg_net_return_4h_pct": round(float(rows[5] or 0) * 100, 4),
            "avg_net_return_24h_pct": round(float(rows[6] or 0) * 100, 4),
            "avoided_loss_1h": int(rows[7] or 0), "missed_gain_1h": int(rows[8] or 0),
            "avoided_loss_4h": int(rows[9] or 0), "missed_gain_4h": int(rows[10] or 0),
            "avoided_loss_24h": int(rows[11] or 0), "missed_gain_24h": int(rows[12] or 0)}

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
            published = published.astimezone(timezone.utc)
            # Reject stale and future-dated headlines; neither is safe for a live veto.
            if published < cutoff or published > utc_now() + timedelta(minutes=5):
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
