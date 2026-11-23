import json
import math
import os
import shutil
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

import pandas as pd
import news_intelligence as news

ROOT = Path(__file__).resolve().parent
# Keep mutable paper state outside the Git checkout. The default is persistent
# across code syncs/redeploys on a normal Enzonic server filesystem.
DATA_DIR = Path(
    os.environ.get("ASHUR_DATA_DIR", str(Path.home() / ".local" / "share" / "ashur"))
).expanduser()
DB = DATA_DIR / "ashur_shadow.db"
STATUS_FILE = DATA_DIR / "ashur_shadow_status.json"


def prepare_data_dir():
    """Create persistent storage and migrate the legacy in-repository state once."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    legacy_db = ROOT / "ashur_shadow.db"
    legacy_status = ROOT / "ashur_shadow_status.json"

    if not DB.exists() and legacy_db.exists():
        # SQLite's backup API also includes committed WAL content safely.
        with sqlite3.connect(str(legacy_db), timeout=30) as source:
            with sqlite3.connect(str(DB), timeout=30) as target:
                source.backup(target)
        print(f"STATE_MIGRATED source={legacy_db} destination={DB}", flush=True)

    if not STATUS_FILE.exists() and legacy_status.exists():
        shutil.copy2(legacy_status, STATUS_FILE)
        print(
            f"STATUS_MIGRATED source={legacy_status} destination={STATUS_FILE}",
            flush=True,
        )

    print(f"STATE_STORAGE_READY path={DATA_DIR} db_exists={DB.exists()}", flush=True)
START_CASH = 1000.0
RISK = 0.005
DAILY_STOP = 0.02
FEE = 0.001
SLIPPAGE = 0.0005
MAX_NOTIONAL = 0.95

# Six isolated paper accounts. The final strategies are exploratory and require forward validation.
# Public market-data polling is read-only; this worker never sends exchange orders.
STRATEGIES = [
    {"id": "BNB_4H_KELTNER_ADX", "symbol": "BNB/USDT", "interval": "240",
     "label": "Keltner breakout + ADX", "grade": "RESEARCH_PASS"},
    {"id": "BNB_4H_ADX_TREND", "symbol": "BNB/USDT", "interval": "240",
     "label": "ADX trend filter", "grade": "RESEARCH_PASS"},
    {"id": "BNB_1H_DONCHIAN_ADX25", "symbol": "BNB/USDT", "interval": "60",
     "label": "Donchian ensemble + ADX25", "grade": "RESEARCH_PASS"},
    {"id": "BNB_15M_EMA_TREND", "symbol": "BNB/USDT", "interval": "15",
     "label": "EMA20/50 trend continuation", "grade": "PAPER_VALIDATION"},
    {"id": "SOL_4H_DONCHIAN_VOL", "symbol": "SOL/USDT", "interval": "240",
     "label": "Donchian volatility regime", "grade": "EXPERIMENTAL_LOW_SAMPLE"},
    {"id": "BNB_1D_DONCHIAN55", "symbol": "BNB/USDT", "interval": "D",
     "label": "Donchian55 trend", "grade": "EXPERIMENTAL_LOW_SAMPLE"},
]

def now():
    return datetime.now(timezone.utc).isoformat()

def api_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ASHUR-Live-Shadow/1.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))

def candle_is_fresh(last_candle_open_ms, interval, now_ms=None):
    """A closed candle must not be more than two full intervals behind now."""
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    interval_ms = {"15": 900000, "60": 3600000, "240": 14400000, "D": 86400000}[interval]
    candle_close_ms = int(last_candle_open_ms) + interval_ms
    age_ms = now_ms - candle_close_ms
    return 0 <= age_ms <= 2 * interval_ms


def validate_ohlcv_frame(frame, interval):
    """Fail closed on malformed OHLCV before indicators or paper decisions use it."""
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing or frame.empty:
        raise ValueError("OHLCV frame missing columns or empty: " + ",".join(missing))

    interval_ms = {"15": 900000, "60": 3600000, "240": 14400000, "D": 86400000}[interval]
    timestamps = frame["timestamp"].to_numpy(dtype="int64")
    if len(set(timestamps.tolist())) != len(timestamps):
        raise ValueError("OHLCV contains duplicate candle timestamps")
    if len(timestamps) > 1 and (timestamps[1:] <= timestamps[:-1]).any():
        raise ValueError("OHLCV candle timestamps are not strictly increasing")
    if (timestamps % interval_ms != 0).any():
        raise ValueError("OHLCV candle timestamp is not aligned to timeframe")

    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    if not math.isfinite(values).all():
        raise ValueError("OHLCV contains non-finite values")
    open_, high, low, close, volume = values.T
    if (values[:, :4] <= 0).any():
        raise ValueError("OHLCV contains non-positive prices")
    if (volume < 0).any():
        raise ValueError("OHLCV contains negative volume")
    if (high < low).any() or (high < open_).any() or (high < close).any():
        raise ValueError("OHLCV high is below candle range")
    if (low > open_).any() or (low > close).any():
        raise ValueError("OHLCV low is above candle range")
    return frame


def target_exit_reference_price(price, target):
    """Cap favorable target fills at the target level to avoid optimistic gap fills."""
    return min(float(price), float(target))


def validate_ticker_price(price):
    price = float(price)
    if not math.isfinite(price) or price <= 0:
        raise ValueError("Ticker price must be finite and positive")
    return price


def fetch_bybit_klines(symbol, interval, limit=350):
    market_symbol = symbol.replace("/", "")
    ms = {"15": 900000, "60": 3600000, "240": 14400000, "D": 86400000}[interval]
    cutoff = int(datetime.now(timezone.utc).timestamp() * 1000)
    errors = []
    try:
        query = urllib.parse.urlencode({"category": "spot", "symbol": market_symbol,
                                        "interval": interval, "limit": limit})
        payload = api_json("https://api.bybit.com/v5/market/kline?" + query)
        if payload.get("retCode") != 0:
            raise RuntimeError("Bybit kline: " + str(payload.get("retMsg")))
        rows = payload["result"]["list"]
        frame = pd.DataFrame([[int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                                float(r[4]), float(r[5])] for r in rows],
                             columns=["timestamp", "open", "high", "low", "close", "volume"])
        frame = frame.sort_values("timestamp").reset_index(drop=True)
        frame = frame[frame.timestamp + ms <= cutoff].reset_index(drop=True)
        frame = validate_ohlcv_frame(frame, interval)
        if len(frame) >= 220:
            if not candle_is_fresh(frame.iloc[-1].timestamp, interval, cutoff):
                raise RuntimeError("Bybit latest closed candle is stale")
            return frame
        errors.append("Bybit returned too few closed candles")
    except Exception as exc:
        errors.append("Bybit: " + str(exc))
    # Binance public market-data mirror is the automatic fallback for runner regions
    # where Bybit's public REST endpoint is blocked.
    try:
        binance_interval = {"15": "15m", "60": "1h", "240": "4h", "D": "1d"}[interval]
        query = urllib.parse.urlencode({"symbol": market_symbol, "interval": binance_interval,
                                        "limit": limit})
        rows = api_json("https://data-api.binance.vision/api/v3/klines?" + query)
        frame = pd.DataFrame([[int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                                float(r[4]), float(r[5])] for r in rows],
                             columns=["timestamp", "open", "high", "low", "close", "volume"])
        frame = frame.sort_values("timestamp").reset_index(drop=True)
        frame = frame[frame.timestamp + ms <= cutoff].reset_index(drop=True)
        frame = validate_ohlcv_frame(frame, interval)
        if len(frame) >= 220:
            if not candle_is_fresh(frame.iloc[-1].timestamp, interval, cutoff):
                raise RuntimeError("Binance latest closed candle is stale")
            return frame
        errors.append("Binance returned too few closed candles")
    except Exception as exc:
        errors.append("Binance: " + str(exc))
    raise RuntimeError("No usable candle source: " + " | ".join(errors))

def validate_binance_ticker(payload, now_ms=None):
    """Require a recent Binance last-trade timestamp, not merely a fast HTTP response."""
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    close_ms = int(payload.get("closeTime", 0))
    age_ms = now_ms - close_ms
    if close_ms <= 0 or age_ms < 0 or age_ms > 30000:
        raise ValueError("Binance ticker last trade is stale")
    return validate_ticker_price(payload["lastPrice"])


def fetch_ticker(symbol):
    market_symbol = symbol.replace("/", "")
    errors = []
    try:
        query = urllib.parse.urlencode({"category": "spot", "symbol": market_symbol})
        request_started = time.monotonic()
        payload = api_json("https://api.bybit.com/v5/market/tickers?" + query)
        request_elapsed = time.monotonic() - request_started
        if payload.get("retCode") == 0 and payload.get("result", {}).get("list"):
            server_time_ms = int(payload.get("time", 0))
            now_ms = int(time.time() * 1000)
            if request_elapsed > 10 or not server_time_ms or abs(now_ms - server_time_ms) > 30000:
                raise RuntimeError("Bybit ticker response is stale")
            return validate_ticker_price(payload["result"]["list"][0]["lastPrice"])
        errors.append("Bybit ticker unavailable")
    except Exception as exc:
        errors.append("Bybit: " + str(exc))
    try:
        query = urllib.parse.urlencode({"symbol": market_symbol})
        request_started = time.monotonic()
        payload = api_json("https://data-api.binance.vision/api/v3/ticker/24hr?" + query)
        if time.monotonic() - request_started > 10:
            raise RuntimeError("Binance ticker response took too long")
        return validate_binance_ticker(payload)
    except Exception as exc:
        errors.append("Binance: " + str(exc))
    raise RuntimeError("No usable ticker source: " + " | ".join(errors))

def indicators(frame):
    x = frame.copy()
    for n in (20, 50, 100, 200):
        x["ema" + str(n)] = x.close.ewm(span=n, adjust=False).mean()
    prev = x.close.shift(1)
    tr = pd.concat([(x.high-x.low), (x.high-prev).abs(), (x.low-prev).abs()], axis=1).max(axis=1)
    x["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    up, down = x.high.diff(), -x.low.diff()
    plus = up.where((up > down) & (up > 0), 0.0)
    minus = down.where((down > up) & (down > 0), 0.0)
    atr = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    pdi = 100 * plus.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr
    mdi = 100 * minus.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr
    dx = 100 * (pdi-mdi).abs() / (pdi+mdi).replace(0, float("nan"))
    x["adx"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    for n in (20, 55, 100):
        x["dh" + str(n)] = x.high.rolling(n).max().shift(1)
    x["dl10"] = x.low.rolling(10).min().shift(1)
    x["dl20"] = x.low.rolling(20).min().shift(1)
    x["atr_pct"] = x.atr / x.close
    x["atr_p80"] = x.atr_pct.rolling(100, min_periods=50).quantile(0.80)
    x["keltner_upper"] = x.ema20 + 2 * x.atr
    return x

def signals(row, strategy_id):
    close = float(row.close)
    if strategy_id == "BNB_4H_KELTNER_ADX":
        entry = close > row.keltner_upper and row.ema50 > row.ema200 and row.adx > 15
        exit_ = close < row.ema20 or row.ema50 < row.ema200
    elif strategy_id == "BNB_4H_ADX_TREND":
        entry = row.ema50 > row.ema200 and row.adx > 20 and close > row.ema50
        exit_ = row.ema50 < row.ema200 or close < row.ema50
    elif strategy_id == "BNB_1H_DONCHIAN_ADX25":
        votes = sum([close > row.dh20, close > row.dh55, close > row.dh100])
        entry = votes >= 2 and close > row.ema200 and row.adx > 25
        exit_ = close < row.dl20 or close < row.ema100
    elif strategy_id == "SOL_4H_DONCHIAN_VOL":
        entry = close > row.dh55 and close > row.ema200 and row.atr_pct < row.atr_p80
        exit_ = close < row.dl20 or close < row.ema100
    elif strategy_id == "BNB_15M_EMA_TREND":
        entry = close > row.ema20 and row.ema20 > row.ema50 and row.adx > 12
        exit_ = close < row.ema50 or row.ema20 < row.ema50
    else:  # BNB_1D_DONCHIAN55
        entry = close > row.dh55 and close > row.ema200
        exit_ = close < row.dl10
    return bool(entry), bool(exit_)

def init_db(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS shadow_accounts(
      strategy_id TEXT PRIMARY KEY, label TEXT NOT NULL, symbol TEXT NOT NULL,
      interval TEXT NOT NULL, grade TEXT NOT NULL, cash REAL NOT NULL,
      starting_cash REAL NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS shadow_positions(
      strategy_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, qty REAL NOT NULL,
      entry REAL NOT NULL, entry_fee REAL NOT NULL, stop REAL NOT NULL,
      target REAL NOT NULL, opened_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS shadow_trades(
      id INTEGER PRIMARY KEY AUTOINCREMENT, strategy_id TEXT NOT NULL,
      symbol TEXT NOT NULL, entry REAL NOT NULL, exit REAL NOT NULL,
      qty REAL NOT NULL, fees REAL NOT NULL, pnl REAL NOT NULL,
      reason TEXT NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS shadow_state(
      strategy_id TEXT PRIMARY KEY, last_candle TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS shadow_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
      strategy_id TEXT NOT NULL, event TEXT NOT NULL, details TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS shadow_marks(
      strategy_id TEXT PRIMARY KEY, price REAL NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS shadow_trade_guard(
      strategy_id TEXT PRIMARY KEY, last_closed_candle TEXT NOT NULL);
    """)
    for s in STRATEGIES:
        conn.execute("""INSERT OR IGNORE INTO shadow_accounts
          (strategy_id,label,symbol,interval,grade,cash,starting_cash,created_at)
          VALUES(?,?,?,?,?,?,?,?)""",
          (s["id"],s["label"],s["symbol"],s["interval"],s["grade"],START_CASH,START_CASH,now()))
    conn.commit()

def event(conn, sid, kind, details):
    conn.execute("INSERT INTO shadow_events(created_at,strategy_id,event,details) VALUES(?,?,?,?)",
                 (now(), sid, kind, details))

def close_position(conn, s, price, reason, candle_id):
    p = conn.execute("SELECT * FROM shadow_positions WHERE strategy_id=?", (s["id"],)).fetchone()
    if not p:
        return
    fill = price * (1 - SLIPPAGE)
    proceeds = p["qty"] * fill
    exit_fee = proceeds * FEE
    pnl = proceeds - exit_fee - (p["qty"] * p["entry"] + p["entry_fee"])
    conn.execute("UPDATE shadow_accounts SET cash=cash+? WHERE strategy_id=?",
                 (proceeds-exit_fee, s["id"]))
    conn.execute("""INSERT INTO shadow_trades
      (strategy_id,symbol,entry,exit,qty,fees,pnl,reason,opened_at,closed_at)
      VALUES(?,?,?,?,?,?,?,?,?,?)""",
      (s["id"],s["symbol"],p["entry"],fill,p["qty"],p["entry_fee"]+exit_fee,
       pnl,reason,p["opened_at"],now()))
    conn.execute("DELETE FROM shadow_positions WHERE strategy_id=?", (s["id"],))
    conn.execute("""INSERT INTO shadow_trade_guard(strategy_id,last_closed_candle)
      VALUES(?,?) ON CONFLICT(strategy_id) DO UPDATE SET last_closed_candle=excluded.last_closed_candle""",
      (s["id"], candle_id))
    event(conn,s["id"],"CLOSE",f"{reason}; fill={fill:.6f}; net_pnl={pnl:.4f}")

def stop_exit_reason(price, stop):
    """Distinguish a stop fill from a gap-through-stop recovery fill."""
    return "GAP_STOP" if float(price) < float(stop) else "STOP"


def calculate_position_size(cash, price, atr):
    """Size a long paper position so stop loss includes both-side fees and slippage."""
    cash, price, atr = float(cash), float(price), float(atr)
    if cash <= 0 or price <= 0 or atr <= 0:
        return 0.0
    entry_fill = price * (1 + SLIPPAGE)
    stop_distance = 3 * atr
    if stop_distance >= entry_fill:
        return 0.0
    stop_price = entry_fill - stop_distance
    exit_fill = stop_price * (1 - SLIPPAGE)
    # Per-unit loss includes entry fee and net proceeds after the exit fee.
    risk_per_unit = entry_fill * (1 + FEE) - exit_fill * (1 - FEE)
    if risk_per_unit <= 0:
        return 0.0
    risk_budget = cash * RISK
    risk_limited_qty = risk_budget / risk_per_unit
    notional_cap = cash * MAX_NOTIONAL / (1 + FEE)
    cash_limited_qty = notional_cap / entry_fill
    return max(0.0, min(risk_limited_qty, cash_limited_qty))


def position_net_pnl_at_price(position, price):
    """Estimate liquidation PnL after exit slippage and fee, including entry fee."""
    exit_fill = float(price) * (1 - SLIPPAGE)
    net_exit = float(position["qty"]) * exit_fill * (1 - FEE)
    entry_cost = float(position["qty"]) * float(position["entry"]) + float(position["entry_fee"])
    return net_exit - entry_cost


def daily_loss_limit_hit(conn, strategy_id, position, price, today=None):
    today = today or datetime.now(timezone.utc).date().isoformat()
    realized = conn.execute(
        """SELECT COALESCE(SUM(pnl),0) AS p FROM shadow_trades
           WHERE strategy_id=? AND substr(closed_at,1,10)=?""",
        (strategy_id, today),
    ).fetchone()["p"]
    return float(realized) + position_net_pnl_at_price(position, price) <= -START_CASH * DAILY_STOP


def open_position(conn, s, price, atr):
    account = conn.execute("SELECT * FROM shadow_accounts WHERE strategy_id=?", (s["id"],)).fetchone()
    today = datetime.now(timezone.utc).date().isoformat()
    day_pnl = conn.execute("""SELECT COALESCE(SUM(pnl),0) AS p FROM shadow_trades
      WHERE strategy_id=? AND substr(closed_at,1,10)=?""",(s["id"],today)).fetchone()["p"]
    if day_pnl <= -START_CASH * DAILY_STOP:
        event(conn,s["id"],"SKIP","Daily paper loss limit reached")
        return
    fill = price * (1 + SLIPPAGE)
    stop_distance = 3 * atr
    qty = calculate_position_size(account["cash"], price, atr)
    notional = qty * fill
    fee = notional * FEE
    if qty <= 0 or notional + fee > account["cash"]:
        return
    stop, target = fill-stop_distance, fill+4*stop_distance
    conn.execute("UPDATE shadow_accounts SET cash=cash-? WHERE strategy_id=?",
                 (notional+fee,s["id"]))
    conn.execute("""INSERT OR REPLACE INTO shadow_positions
      (strategy_id,symbol,qty,entry,entry_fee,stop,target,opened_at)
      VALUES(?,?,?,?,?,?,?,?)""",
      (s["id"],s["symbol"],qty,fill,fee,stop,target,now()))
    event(conn,s["id"],"OPEN",f"paper BUY; qty={qty:.8f}; entry={fill:.6f}; SL={stop:.6f}; TP={target:.6f}")

def export_status(conn, worker_errors=0, successful_strategies=None):
    # Keep status export safe for legacy/test databases created before News Intelligence.
    news.init_db(conn)
    accounts = conn.execute("SELECT * FROM shadow_accounts ORDER BY strategy_id").fetchall()
    successful_strategies = len(STRATEGIES) - int(worker_errors) if successful_strategies is None else int(successful_strategies)
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    news_vetoes_24h = conn.execute(
        "SELECT COUNT(*) FROM news_veto_outcomes WHERE vetoed_at>=?",
        (cutoff_24h,),
    ).fetchone()[0]
    output = {"updated_at": now(), "mode": "PAPER_ONLY",
              "market_data": "Public spot market data; Bybit primary, Binance fallback",
              "worker_health": {"strategy_count": len(STRATEGIES),
                                "successful_strategies": successful_strategies,
                                "error_count": int(worker_errors),
                                "all_strategies_ok": int(worker_errors) == 0 and successful_strategies == len(STRATEGIES)},
              "news_intelligence": {**news.collection_stats(conn, 24),
                                    "news_vetoes_24h": int(news_vetoes_24h),
                                    "veto_outcomes": news.veto_outcome_stats(conn)},
              "accounts": []}
    for a in accounts:
        pos = conn.execute("SELECT * FROM shadow_positions WHERE strategy_id=?", (a["strategy_id"],)).fetchone()
        mark = conn.execute("SELECT price,updated_at FROM shadow_marks WHERE strategy_id=?", (a["strategy_id"],)).fetchone()
        trades = conn.execute("SELECT pnl,fees,reason,opened_at,closed_at FROM shadow_trades WHERE strategy_id=? ORDER BY id", (a["strategy_id"],)).fetchall()
        realized = sum(float(t["pnl"]) for t in trades)
        wins = sum(float(t["pnl"]) > 0 for t in trades)
        gross_profit = sum(float(t["pnl"]) for t in trades if float(t["pnl"]) > 0)
        gross_loss = abs(sum(float(t["pnl"]) for t in trades if float(t["pnl"]) < 0))
        price = float(mark["price"]) if mark else None
        unrealized = 0.0
        position = None
        liquidation_value = 0.0
        if pos:
            mark_price = price if price is not None else float(pos["entry"])
            # Mark open positions at estimated net liquidation value, not gross market value.
            liquidation_value = (
                float(pos["qty"]) * mark_price * (1 - SLIPPAGE) * (1 - FEE)
            )
            entry_cost = float(pos["qty"]) * float(pos["entry"]) + float(pos["entry_fee"])
            unrealized = liquidation_value - entry_cost
            position = {"symbol":pos["symbol"],"qty":float(pos["qty"]),"entry":float(pos["entry"]),
                        "mark":mark_price,"stop":float(pos["stop"]),"target":float(pos["target"]),
                        "unrealized_pnl":round(unrealized,4),"opened_at":pos["opened_at"]}
        cash = float(a["cash"])
        equity = cash + liquidation_value
        output["accounts"].append({
            "strategy_id":a["strategy_id"],"label":a["label"],"symbol":a["symbol"],
            "timeframe":{"15":"15m","60":"1h","240":"4h","D":"1d"}.get(a["interval"],a["interval"]),
            "grade":a["grade"],"starting_cash":float(a["starting_cash"]),"cash":round(cash,4),
            "equity":round(equity,4),"net_pnl":round(equity-float(a["starting_cash"]),4),
            "realized_pnl":round(realized,4),"unrealized_pnl":round(unrealized,4),
            "return_pct":round((equity/float(a["starting_cash"])-1)*100,4),
            "trades":len(trades),"wins":wins,"win_rate_pct":round(wins/len(trades)*100,2) if trades else 0,
            "profit_factor":round(gross_profit/gross_loss,3) if gross_loss else (None if not gross_profit else "inf"),
            "fees":round(sum(float(t["fees"]) for t in trades),4),"last_price":price,
            "last_price_at":mark["updated_at"] if mark else None,"position":position
        })
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")

def run():
    prepare_data_dir()
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    news.init_db(conn)
    cache = {}
    strategy_errors = 0
    successful_strategies = 0
    for s in STRATEGIES:
        try:
            key = (s["symbol"],s["interval"])
            if key not in cache:
                cache[key] = (indicators(fetch_bybit_klines(*key)), fetch_ticker(s["symbol"]))
            data, price = cache[key]
            news.update_veto_outcomes(conn, s["symbol"], price)
            row = data.iloc[-1]  # latest fully closed candle; indicators never use a forming candle
            candle_id = str(int(row.timestamp))
            # Strategy decisions must use the fully closed candle, matching the historical
            # backtest. The live ticker is reserved for execution, stops/targets, and equity marks.
            # Re-checking the same closed-candle signal each cycle allows execution after candle
            # close without letting a still-forming candle rewrite the strategy rules.
            entry_signal, exit_signal = signals(row, s["id"])
            news_veto = None
            conn.execute("INSERT OR REPLACE INTO shadow_marks VALUES(?,?,?)",(s["id"],price,now()))
            pos = conn.execute("SELECT * FROM shadow_positions WHERE strategy_id=?",(s["id"],)).fetchone()
            closed_this_cycle = False
            if pos:
                if price <= pos["stop"]:
                    close_position(conn,s,price,stop_exit_reason(price, pos["stop"]),candle_id)
                    closed_this_cycle = True
                elif price >= pos["target"]:
                    target_reference = target_exit_reference_price(price, pos["target"])
                    close_position(conn,s,target_reference,"TARGET",candle_id)
                    closed_this_cycle = True
                elif daily_loss_limit_hit(conn, s["id"], pos, price):
                    close_position(conn,s,price,"DAILY_STOP",candle_id)
                    closed_this_cycle = True
                elif exit_signal:
                    close_position(conn,s,price,"SIGNAL",candle_id)
                    closed_this_cycle = True
            guard = conn.execute("SELECT last_closed_candle FROM shadow_trade_guard WHERE strategy_id=?",(s["id"],)).fetchone()
            cooldown_active = bool(guard and guard["last_closed_candle"] == candle_id)
            pos = conn.execute("SELECT * FROM shadow_positions WHERE strategy_id=?",(s["id"],)).fetchone()
            if not pos and entry_signal and not closed_this_cycle and not cooldown_active:
                news_veto = news.high_risk_news(conn, s["symbol"])
                if news_veto:
                    news.record_veto(conn, s["id"], s["symbol"], news_veto, price)
                    entry_signal = False
                    event(conn, s["id"], "NEWS_VETO",
                          f"new entry blocked by high-risk headline: {news_veto['title'][:240]}")
                if entry_signal:
                    open_position(conn,s,price,float(row.atr))
                    pos = conn.execute("SELECT * FROM shadow_positions WHERE strategy_id=?",(s["id"],)).fetchone()
            previous = conn.execute("SELECT last_candle FROM shadow_state WHERE strategy_id=?",(s["id"],)).fetchone()
            if not previous or previous["last_candle"] != candle_id:
                conn.execute("INSERT OR REPLACE INTO shadow_state VALUES(?,?)",(s["id"],candle_id))
                event(conn,s["id"],"CHECK",f"candle={candle_id}; candle_close={float(row.close):.6f}; live={price:.6f}; entry={entry_signal}; exit={exit_signal}; cooldown={cooldown_active}")
            conn.commit()
            successful_strategies += 1
            print(f'{s["id"]}: OK price={price:.6f} entry={entry_signal} exit={exit_signal} news_veto={bool(news_veto)} cooldown={cooldown_active} position={bool(pos)}')
        except Exception as exc:
            strategy_errors += 1
            conn.rollback()
            event(conn,s["id"],"ERROR",f"{type(exc).__name__}: {exc}")
            conn.commit()
            print(f'{s["id"]}: ERROR {type(exc).__name__}: {exc}')
    export_status(conn, worker_errors=strategy_errors, successful_strategies=successful_strategies)
    conn.close()
    print(f"WORKER_SUMMARY strategies={len(STRATEGIES)} errors={strategy_errors}", flush=True)
    if strategy_errors:
        raise SystemExit(1)

if __name__ == "__main__":
    run()
