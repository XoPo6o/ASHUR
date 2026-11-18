import sqlite3
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone, date
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "ashur_paper.db"
START_BALANCE = 10_000.0
RISK_PER_TRADE = 0.005
DAILY_LOSS_LIMIT = 0.02
MAX_POSITIONS = 2
FEE_RATE = 0.001

st.set_page_config(page_title="ASHUR | Paper Trading", page_icon="𒀭", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700;800&display=swap');
:root { --gold:#c89b55; --bg:#08090b; --panel:#111317; --line:#292b30; }
.stApp { background: radial-gradient(ellipse at 50% -20%, #272016 0%, #08090b 48%); color:#e9e5dc; }
html, body, [class*="css"] { font-family:Inter,sans-serif; }
.block-container { padding-top:2rem; max-width:1500px; }
h1,h2,h3 { letter-spacing:-.035em; }
[data-testid="stMetric"] { background:linear-gradient(145deg,#17191d,#101114); border:1px solid #34302a; padding:17px 19px; border-radius:10px; }
[data-testid="stMetricLabel"] { color:#aaa49a; }
[data-testid="stMetricValue"] { color:#eee7dc; font-family:'IBM Plex Mono',monospace; }
div.stButton > button { background:#b88949; color:#090a0c; border:1px solid #d0a35f; font-weight:700; border-radius:7px; }
div.stButton > button:hover { background:#d0a35f; color:#090a0c; border-color:#e2bd80; }
div[data-testid="stForm"] { background:#111317; padding:18px; border:1px solid #34302a; border-radius:10px; }
hr { border-color:#292b30; }
.eyebrow { color:#c89b55; letter-spacing:.18em; font:600 11px 'IBM Plex Mono',monospace; }
.brand { font:700 38px 'IBM Plex Mono',monospace; letter-spacing:.13em; color:#e9e2d6; }
.subbrand { color:#aaa49a; font:11px 'IBM Plex Mono',monospace; letter-spacing:.16em; }
.panel { background:linear-gradient(145deg,#15171b,#0e1013); border:1px solid #34302a; border-radius:10px; padding:17px 20px; }
.good { color:#8dbb91; } .bad { color:#d88979; }
div[data-testid="stDataFrame"] { border:1px solid #292b30; border-radius:8px; }
</style>
""", unsafe_allow_html=True)

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS account (
        id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL, created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, side TEXT NOT NULL,
        qty REAL NOT NULL, price REAL NOT NULL, fee REAL NOT NULL, pnl REAL NOT NULL DEFAULT 0,
        opened_at TEXT NOT NULL, closed_at TEXT, status TEXT NOT NULL)""")
    conn.execute("INSERT OR IGNORE INTO account(id,cash,created_at) VALUES(1,?,?)",
                 (START_BALANCE, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    return conn

def get_account(conn):
    return conn.execute("SELECT cash FROM account WHERE id=1").fetchone()["cash"]

def get_positions(conn):
    rows = conn.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY id").fetchall()
    return [dict(r) for r in rows]

def get_closed(conn):
    rows = conn.execute("SELECT * FROM trades WHERE status='CLOSED' ORDER BY id DESC").fetchall()
    return pd.DataFrame([dict(r) for r in rows])

def _normalize_candles(candles):
    frame = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume"])
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame.dropna().sort_values("timestamp").reset_index(drop=True)


def _fetch_binance_public(symbol, timeframe, limit):
    # Binance public market-data mirror; no API key is required.
    market_symbol = symbol.replace("/", "")
    query = urllib.parse.urlencode({"symbol": market_symbol, "interval": timeframe, "limit": limit})
    url = "https://data-api.binance.vision/api/v3/klines?" + query
    request = urllib.request.Request(url, headers={"User-Agent": "ASHUR-Paper-Trading/0.1"})
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Binance returned no candles")
    candles = [[row[0], row[1], row[2], row[3], row[4], row[5]] for row in payload]
    return _normalize_candles(candles)


@st.cache_data(ttl=300, show_spinner=False)
def load_market(symbol, timeframe, limit):
    errors = []

    # Primary source.
    try:
        exchange = ccxt.bybit({"enableRateLimit": True, "options": {"defaultType": "spot"}})
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if candles:
            return _normalize_candles(candles), "Bybit"
        errors.append("Bybit: empty response")
    except Exception as exc:
        errors.append(f"Bybit: {type(exc).__name__}: {exc}")

    # Fallback 1: Binance public market-data mirror.
    try:
        frame = _fetch_binance_public(symbol, timeframe, limit)
        return frame, "Binance Public Data (fallback)"
    except Exception as exc:
        errors.append(f"Binance: {type(exc).__name__}: {exc}")

    # Fallback 2: Kraken public OHLC endpoint.
    try:
        exchange = ccxt.kraken({"enableRateLimit": True})
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=min(limit, 720))
        if candles:
            return _normalize_candles(candles), "Kraken (fallback)"
        errors.append("Kraken: empty response")
    except Exception as exc:
        errors.append(f"Kraken: {type(exc).__name__}: {exc}")

    raise RuntimeError("All market-data sources failed. " + " | ".join(errors))

def indicators(df):
    x = df.copy()
    x["ema50"] = x["close"].ewm(span=50, adjust=False).mean()
    x["ema200"] = x["close"].ewm(span=200, adjust=False).mean()
    x["donchian_high"] = x["high"].rolling(20).max().shift(1)
    x["donchian_low"] = x["low"].rolling(10).min().shift(1)
    x["volatility"] = x["close"].pct_change().rolling(20).std()
    x["signal"] = "HOLD"
    x.loc[(x["close"] > x["donchian_high"]) & (x["ema50"] > x["ema200"]), "signal"] = "BUY"
    x.loc[(x["close"] < x["donchian_low"]), "signal"] = "SELL"
    return x

def market_chart(df, symbol):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.timestamp, open=df.open, high=df.high, low=df.low, close=df.close, name=symbol))
    fig.add_trace(go.Scatter(x=df.timestamp, y=df.ema50, name="EMA 50", line=dict(color="#c89b55", width=1.4)))
    fig.add_trace(go.Scatter(x=df.timestamp, y=df.ema200, name="EMA 200", line=dict(color="#7894ad", width=1.4)))
    fig.update_layout(height=440, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=5,r=5,t=25,b=5), xaxis_rangeslider_visible=False, legend=dict(orientation="h",y=1.08))
    return fig

def daily_realized_loss(conn):
    today = date.today().isoformat()
    row = conn.execute("SELECT COALESCE(SUM(pnl),0) AS pnl FROM trades WHERE status='CLOSED' AND substr(closed_at,1,10)=?", (today,)).fetchone()
    return float(row["pnl"])

def open_paper_position(conn, symbol, price, risk_pct):
    cash = get_account(conn)
    positions = get_positions(conn)
    if len(positions) >= MAX_POSITIONS:
        return False, "ISHTAR: достигнут лимит двух открытых позиций."
    if any(p["symbol"] == symbol for p in positions):
        return False, "Для этой пары уже есть открытая позиция."
    realized = daily_realized_loss(conn)
    if realized <= -START_BALANCE * DAILY_LOSS_LIMIT:
        return False, "ISHTAR: дневной лимит убытка исчерпан."
    risk_budget = cash * min(risk_pct, RISK_PER_TRADE)
    stop_distance = 0.02
    notional = risk_budget / stop_distance
    notional = min(notional, cash / (1 + FEE_RATE))
    qty = notional / price
    fee = notional * FEE_RATE
    if qty <= 0 or notional + fee > cash:
        return False, "Недостаточно виртуального баланса."
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE account SET cash=cash-? WHERE id=1", (notional + fee,))
    conn.execute("""INSERT INTO trades(symbol,side,qty,price,fee,pnl,opened_at,status)
                    VALUES(?,?,?,?,?,0,?,'OPEN')""", (symbol,"BUY",qty,price,fee,now))
    conn.commit()
    return True, f"Виртуальная позиция открыта: {qty:.6f} {symbol.split('/')[0]}"

def close_paper_position(conn, position, price):
    now = datetime.now(timezone.utc).isoformat()
    proceeds = position["qty"] * price
    exit_fee = proceeds * FEE_RATE
    entry_cost = position["qty"] * position["price"] + position["fee"]
    pnl = proceeds - exit_fee - entry_cost
    conn.execute("UPDATE account SET cash=cash+? WHERE id=1", (proceeds-exit_fee,))
    conn.execute("UPDATE trades SET status='CLOSED',closed_at=?,pnl=? WHERE id=?",
                 (now,pnl,position["id"]))
    conn.commit()
    return pnl

def equity_snapshot(conn, prices):
    cash = get_account(conn)
    positions = get_positions(conn)
    market_value = sum(p["qty"] * prices.get(p["symbol"], p["price"]) for p in positions)
    return cash + market_value, positions, market_value

conn = db()
st.markdown('<div class="eyebrow">ALGORITHMIC TRADING LABORATORY · BUILD 0.1</div>', unsafe_allow_html=True)
st.markdown('<div class="brand">ASHUR</div><div class="subbrand">𒀭 PAPER TRADING SYSTEM / BYBIT SPOT</div>', unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.markdown("### CONTROL ROOM")
    symbol = st.selectbox("Trading pair", ["BTC/USDT","ETH/USDT"])
    timeframe = st.selectbox("Timeframe", ["4h","1h"], index=0)
    candle_limit = st.slider("Candles", 250, 1000, 500, 50)
    st.caption("Public market data only. No API keys.")
    st.markdown("---")
    st.markdown("**ISHTAR · Risk limits**")
    st.write("Risk / trade: **0.5% max**")
    st.write("Daily loss: **2% max**")
    st.write("Open positions: **2 max**")
    st.markdown("---")
    st.caption("Execution mode: PAPER ONLY")

try:
    with st.spinner("NABU is reading the market..."):
        raw, market_source = load_market(symbol, timeframe, candle_limit)
        data = indicators(raw)
    market_ok = True
    last_price = float(data.close.iloc[-1])
    signal = data.signal.iloc[-1]
except Exception as exc:
    market_ok = False
    market_source = None
    data = pd.DataFrame()
    last_price = None
    signal = "UNAVAILABLE"
    st.error(f"Market data unavailable: {exc}. Check connection and reload.")

prices = {symbol:last_price} if market_ok else {}
cash = get_account(conn)
equity, positions, market_value = equity_snapshot(conn, prices)
unrealized = sum(p["qty"] * (prices.get(p["symbol"],p["price"]) - p["price"]) - p["fee"] for p in positions)
closed = get_closed(conn)
realized_total = float(closed.pnl.sum()) if not closed.empty else 0.0

m1,m2,m3,m4 = st.columns(4)
m1.metric("PORTFOLIO EQUITY", f"$ {equity:,.2f}", f"{equity-START_BALANCE:+,.2f} USDT")
m2.metric("AVAILABLE CASH", f"$ {cash:,.2f}")
m3.metric("OPEN POSITIONS", f"{len(positions)} / {MAX_POSITIONS}")
m4.metric("REALIZED P&L", f"$ {realized_total:,.2f}")

st.markdown("### NABU · Market intelligence")
if market_ok:
    st.caption(f"Live market data source: {market_source} · refreshed every 5 minutes")
    a,b,c = st.columns(3)
    a.metric(f"{symbol} · LAST PRICE", f"$ {last_price:,.2f}")
    b.metric("TREND", "BULLISH" if data.ema50.iloc[-1] > data.ema200.iloc[-1] else "BEARISH")
    c.metric("STRATEGY SIGNAL", signal)
    st.plotly_chart(market_chart(data, symbol), use_container_width=True)
    with st.expander("Latest market data"):
        st.dataframe(data.tail(12).sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True)
else:
    st.info("Market chart will appear when public exchange data is available.")

st.markdown("---")
st.markdown("### MARDUK · Paper execution")
left,right = st.columns([1,1])
with left:
    st.markdown("**Open a virtual position**")
    st.caption("Position sizing is capped by ISHTAR. A 2% stop-distance assumption is used for sizing.")
    if market_ok:
        st.write(f"Current {symbol} price: **$ {last_price:,.2f}**")
        if st.button("＋  OPEN PAPER BUY", use_container_width=True, disabled=not market_ok):
            ok,msg = open_paper_position(conn, symbol, last_price, RISK_PER_TRADE)
            (st.success if ok else st.warning)(msg)
            st.rerun()
    else:
        st.button("＋  OPEN PAPER BUY", disabled=True, use_container_width=True)
with right:
    st.markdown("**Close a virtual position**")
    if positions:
        selected_id = st.selectbox("Select position", [p["id"] for p in positions],
                                   format_func=lambda pid: next(f"#{p['id']} · {p['symbol']} · {p['qty']:.6f}" for p in positions if p["id"]==pid))
        selected = next(p for p in positions if p["id"]==selected_id)
        exit_price = prices.get(selected["symbol"])
        if exit_price is not None and st.button("－  CLOSE PAPER POSITION", use_container_width=True):
            pnl = close_paper_position(conn, selected, exit_price)
            st.success(f"Position closed. Realized P&L: {pnl:+.2f} USDT")
            st.rerun()
    else:
        st.info("No open positions.")

st.markdown("---")
st.markdown("### Portfolio · Open positions")
if positions:
    rows=[]
    for p in positions:
        mark=prices.get(p["symbol"],p["price"])
        rows.append({"ID":p["id"],"Pair":p["symbol"],"Quantity":p["qty"],"Entry":p["price"],"Mark":mark,
                     "Unrealized P&L":p["qty"]*(mark-p["price"])-p["fee"],"Opened":p["opened_at"][:19]})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
else:
    st.caption("The portfolio is flat. No open virtual positions.")

st.markdown("### SHAMASH · Audit ledger")
if not closed.empty:
    st.dataframe(closed[["id","symbol","side","qty","price","fee","pnl","opened_at","closed_at"]].rename(
        columns={"id":"ID","symbol":"Pair","side":"Side","qty":"Qty","price":"Entry","fee":"Entry fee","pnl":"Net P&L","opened_at":"Opened","closed_at":"Closed"}),
        use_container_width=True,hide_index=True)
else:
    st.caption("No completed trades yet.")

st.markdown("---")
st.markdown('<div class="subbrand">ASHUR · RESEARCH FIRST. PAPER SECOND. REAL CAPITAL ONLY AFTER VALIDATION.</div>', unsafe_allow_html=True)
st.caption("Build 0.1 · Public Bybit market data · SQLite local ledger · All executions are simulated. No real orders can be sent.")
