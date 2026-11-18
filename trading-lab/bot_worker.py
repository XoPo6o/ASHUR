import json
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone, date
from pathlib import Path

import ccxt
import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ashur_paper.db"
START_BALANCE = 10_000.0
RISK_PER_TRADE = 0.005
DAILY_LOSS_LIMIT = 0.02
MAX_POSITIONS = 2
FEE_RATE = 0.001
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME = "1h"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize(candles):
    frame = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame.dropna().sort_values("timestamp").reset_index(drop=True)


def fetch_binance(symbol, timeframe, limit):
    query = urllib.parse.urlencode({"symbol": symbol.replace("/", ""), "interval": timeframe, "limit": limit})
    url = "https://data-api.binance.vision/api/v3/klines?" + query
    request = urllib.request.Request(url, headers={"User-Agent": "ASHUR-Paper-Trading/0.2"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Binance returned no candles")
    return normalize([[r[0], r[1], r[2], r[3], r[4], r[5]] for r in payload])


def fetch_market(symbol, timeframe, limit=500):
    errors = []
    try:
        exchange = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "spot"}})
        rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if rows:
            return normalize(rows), "Bybit"
        errors.append("Bybit returned no candles")
    except Exception as exc:
        errors.append(f"Bybit: {type(exc).__name__}: {exc}")
    try:
        return fetch_binance(symbol, timeframe, limit), "Binance Public Data"
    except Exception as exc:
        errors.append(f"Binance: {type(exc).__name__}: {exc}")
    try:
        exchange = ccxt.kraken({"enableRateLimit": True})
        rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=min(limit, 720))
        if rows:
            return normalize(rows), "Kraken"
        errors.append("Kraken returned no candles")
    except Exception as exc:
        errors.append(f"Kraken: {type(exc).__name__}: {exc}")
    raise RuntimeError("All market-data sources failed: " + " | ".join(errors))


def with_indicators(frame):
    x = frame.copy()
    x["ema50"] = x["close"].ewm(span=50, adjust=False).mean()
    x["ema200"] = x["close"].ewm(span=200, adjust=False).mean()
    x["donchian_high"] = x["high"].rolling(20).max().shift(1)
    x["donchian_low"] = x["low"].rolling(10).min().shift(1)
    x["signal"] = "HOLD"
    x.loc[(x["close"] > x["donchian_high"]) & (x["ema50"] > x["ema200"]), "signal"] = "BUY"
    x.loc[x["close"] < x["donchian_low"], "signal"] = "SELL"
    return x


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS account (
        id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL, created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, side TEXT NOT NULL,
        qty REAL NOT NULL, price REAL NOT NULL, fee REAL NOT NULL, pnl REAL NOT NULL DEFAULT 0,
        opened_at TEXT NOT NULL, closed_at TEXT, status TEXT NOT NULL)""")
    conn.execute("INSERT OR IGNORE INTO account(id,cash,created_at) VALUES(1,?,?)",
                 (START_BALANCE, utc_now()))
    conn.execute("CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("""CREATE TABLE IF NOT EXISTS bot_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
        symbol TEXT NOT NULL, event TEXT NOT NULL, details TEXT NOT NULL)""")
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(trades)")}
    if "stop_price" not in columns:
        conn.execute("ALTER TABLE trades ADD COLUMN stop_price REAL")
    if "take_profit" not in columns:
        conn.execute("ALTER TABLE trades ADD COLUMN take_profit REAL")
    conn.commit()
    return conn


def cash_balance(conn):
    return float(conn.execute("SELECT cash FROM account WHERE id=1").fetchone()["cash"])


def positions(conn, symbol=None):
    if symbol:
        rows = conn.execute("SELECT * FROM trades WHERE status='OPEN' AND symbol=? ORDER BY id", (symbol,))
    else:
        rows = conn.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY id")
    return [dict(r) for r in rows.fetchall()]


def log_event(conn, symbol, event, details):
    conn.execute("INSERT INTO bot_events(created_at,symbol,event,details) VALUES(?,?,?,?)",
                 (utc_now(), symbol, event, details))


def realized_today(conn):
    today = date.today().isoformat()
    row = conn.execute("SELECT COALESCE(SUM(pnl),0) AS pnl FROM trades "
                       "WHERE status='CLOSED' AND substr(closed_at,1,10)=?", (today,)).fetchone()
    return float(row["pnl"])


def open_position(conn, symbol, price):
    active = positions(conn)
    if len(active) >= MAX_POSITIONS:
        return False, "Maximum open positions reached"
    if any(p["symbol"] == symbol for p in active):
        return False, "Position for this pair already exists"
    if realized_today(conn) <= -START_BALANCE * DAILY_LOSS_LIMIT:
        return False, "Daily loss limit reached"
    risk_budget = cash_balance(conn) * RISK_PER_TRADE
    notional = min(risk_budget / 0.02, cash_balance(conn) / (1 + FEE_RATE))
    qty = notional / price
    fee = notional * FEE_RATE
    if qty <= 0 or notional + fee > cash_balance(conn):
        return False, "Insufficient paper cash"
    conn.execute("UPDATE account SET cash=cash-? WHERE id=1", (notional + fee,))
    cur = conn.execute("""INSERT INTO trades(symbol,side,qty,price,fee,pnl,opened_at,status,stop_price,take_profit)
                          VALUES(?,?,?,?,?,0,?,'OPEN',?,?)""",
                       (symbol, "BUY", qty, price, fee, utc_now(), price * 0.98, price * 1.04))
    log_event(conn, symbol, "AUTO BUY",
              f"qty={qty:.8f}; entry={price:.4f}; SL={price*0.98:.4f}; TP={price*1.04:.4f}")
    return True, f"opened trade #{cur.lastrowid} at {price:.4f}"


def close_position(conn, p, price, reason):
    proceeds = p["qty"] * price
    exit_fee = proceeds * FEE_RATE
    entry_cost = p["qty"] * p["price"] + p["fee"]
    pnl = proceeds - exit_fee - entry_cost
    conn.execute("UPDATE account SET cash=cash+? WHERE id=1", (proceeds - exit_fee,))
    conn.execute("UPDATE trades SET status='CLOSED',closed_at=?,pnl=? WHERE id=?",
                 (utc_now(), pnl, p["id"]))
    log_event(conn, p["symbol"], "AUTO CLOSE", f"{reason}; price={price:.4f}; net_pnl={pnl:.4f}")


def run_cycle(conn):
    changed = False
    for symbol in SYMBOLS:
        try:
            raw, source = fetch_market(symbol, TIMEFRAME)
            data = with_indicators(raw)
            if len(data) < 205:
                print(f"{symbol}: waiting for 205 candles")
                continue
            signal_row = data.iloc[-2]  # only use the last fully closed hourly candle
            signal = str(signal_row["signal"])
            candle_id = signal_row["timestamp"].isoformat()
            current = data.iloc[-1]
            price = float(current["close"])
            low, high = float(current["low"]), float(current["high"])

            active = positions(conn, symbol)
            for p in active:
                stop = p.get("stop_price")
                target = p.get("take_profit")
                reason = exit_price = None
                if stop is not None and low <= float(stop):
                    reason, exit_price = "STOP LOSS", float(stop)
                elif target is not None and high >= float(target):
                    reason, exit_price = "TAKE PROFIT", float(target)
                elif signal == "SELL":
                    reason, exit_price = "STRATEGY EXIT", price
                if reason:
                    close_position(conn, p, exit_price, reason)
                    print(f"{symbol}: closed by {reason}")
                    changed = True

            key = f"last:{symbol}|{TIMEFRAME}"
            last = conn.execute("SELECT value FROM bot_state WHERE key=?", (key,)).fetchone()
            if last and last["value"] == candle_id:
                print(f"{symbol}: {signal} already evaluated for the latest closed 1h candle; waiting for the next hourly close")
                continue

            trend = "UP" if float(signal_row["ema50"]) > float(signal_row["ema200"]) else "DOWN"
            breakout_level = float(signal_row["donchian_high"])
            candle_close = float(signal_row["close"])
            print(
                f"{symbol}: signal={signal}; candle_close={candle_close:.4f}; "
                f"20-candle_breakout_level={breakout_level:.4f}; EMA50/EMA200_trend={trend}; "
                f"market_source={source}"
            )

            if signal == "BUY" and not positions(conn, symbol):
                ok, message = open_position(conn, symbol, price)
                if ok:
                    print(f"{symbol}: {message}")
                    changed = True
                else:
                    log_event(conn, symbol, "SKIP", message)
                    print(f"{symbol}: skipped: {message}")
                    changed = True
            elif signal == "BUY":
                print(f"{symbol}: BUY signal ignored — an open position already exists")
            else:
                print(f"{symbol}: no entry — strategy signal is {signal}, not BUY")

            conn.execute("INSERT OR REPLACE INTO bot_state(key,value) VALUES(?,?)", (key, candle_id))
            changed = True
        except Exception as exc:
            print(f"{symbol}: ERROR {type(exc).__name__}: {exc}")
            # Avoid filling the ledger with the same transient error every five minutes.
            key = f"error:{symbol}"
            previous = conn.execute("SELECT value FROM bot_state WHERE key=?", (key,)).fetchone()
            message = f"{type(exc).__name__}: {exc}"
            if not previous or previous["value"] != message:
                log_event(conn, symbol, "ERROR", message)
                conn.execute("INSERT OR REPLACE INTO bot_state(key,value) VALUES(?,?)", (key, message))
                changed = True

    if changed:
        conn.commit()
    else:
        conn.rollback()
    print(f"Cash: {cash_balance(conn):.2f} USDT | Open positions: {len(positions(conn))}")


if __name__ == "__main__":
    connection = connect_db()
    try:
        run_cycle(connection)
    finally:
        connection.close()
