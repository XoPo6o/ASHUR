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
PAPER_BASELINE_ID = "ashur-paper-30d-2026-11-25-v2"
RISK = 0.005
DAILY_STOP = 0.02
FEE = 0.001
SLIPPAGE = 0.0005
MAX_NOTIONAL = 0.95

# Six isolated paper accounts. The final strategies are exploratory and require forward validation.
# Public market-data polling is read-only; this worker never sends exchange orders.
STRATEGIES = [
    {"id": "BNB_4H_KELTNER_ADX", "symbol": "BNB/USDT", "interval": "240",
     "label": "Keltner breakout + ADX", "grade": "PROMISING_LOW_SAMPLE"},
    {"id": "BNB_4H_ADX_TREND", "symbol": "BNB/USDT", "interval": "240",
     "label": "ADX trend filter", "grade": "PROMISING_LOW_SAMPLE"},
    {"id": "BNB_1H_DONCHIAN_ADX25", "symbol": "BNB/USDT", "interval": "60",
     "label": "Donchian ensemble + ADX25", "grade": "NO_EDGE_IN_HELD_OUT_TEST"},
    {"id": "BNB_15M_EMA_TREND", "symbol": "BNB/USDT", "interval": "15",
     "label": "EMA20/50 trend continuation", "grade": "REJECTED_HISTORICAL_SCREEN"},
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
    interval_ms = {"1": 60000, "15": 900000, "60": 3600000, "240": 14400000, "D": 86400000}[interval]
    candle_close_ms = int(last_candle_open_ms) + interval_ms
    age_ms = now_ms - candle_close_ms
    return 0 <= age_ms <= 2 * interval_ms


def validate_ohlcv_continuity(frame, interval):
    """Reject missing candles in continuous crypto spot OHLCV history."""
    if frame.empty or len(frame) < 2:
        return frame
    interval_ms = {"1": 60000, "15": 900000, "60": 3600000, "240": 14400000, "D": 86400000}[interval]
    timestamps = frame["timestamp"].astype("int64").to_numpy()
    gaps = timestamps[1:] - timestamps[:-1]
    if (gaps != interval_ms).any():
        index = int(next(i for i, gap in enumerate(gaps, start=1) if gap != interval_ms))
        raise ValueError(
            f"OHLCV missing or irregular candle interval: expected={interval_ms}ms "
            f"between rows {index-1} and {index}, got={int(gaps[index-1])}ms"
        )
    return frame


def validate_ohlcv_frame(frame, interval):
    """Fail closed on malformed OHLCV before indicators or paper decisions use it."""
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing or frame.empty:
        raise ValueError("OHLCV frame missing columns or empty: " + ",".join(missing))

    interval_ms = {"1": 60000, "15": 900000, "60": 3600000, "240": 14400000, "D": 86400000}[interval]
    timestamps = frame["timestamp"].to_numpy(dtype="int64")
    if len(set(timestamps.tolist())) != len(timestamps):
        raise ValueError("OHLCV contains duplicate candle timestamps")
    if len(timestamps) > 1 and (timestamps[1:] <= timestamps[:-1]).any():
        raise ValueError("OHLCV candle timestamps are not strictly increasing")
    if (timestamps % interval_ms != 0).any():
        raise ValueError("OHLCV candle timestamp is not aligned to timeframe")

    values = frame[["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
    if not all(math.isfinite(float(value)) for value in values.ravel()):
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
        frame = validate_ohlcv_continuity(validate_ohlcv_frame(frame, interval), interval)
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
        frame = validate_ohlcv_continuity(validate_ohlcv_frame(frame, interval), interval)
        if len(frame) >= 220:
            if not candle_is_fresh(frame.iloc[-1].timestamp, interval, cutoff):
                raise RuntimeError("Binance latest closed candle is stale")
            return frame
        errors.append("Binance returned too few closed candles")
    except Exception as exc:
        errors.append("Binance: " + str(exc))
    raise RuntimeError("No usable candle source: " + " | ".join(errors))

def validate_execution_klines(frame, since_ms, cutoff_ms):
    """Require a continuous sequence starting at the exact next expected minute."""
    if frame.empty:
        if int(since_ms) + 60000 <= int(cutoff_ms):
            raise RuntimeError("1m execution data missing: expected at least one closed minute")
        return frame
    frame = validate_ohlcv_frame(frame, "1")
    timestamps = frame["timestamp"].astype("int64").to_numpy()
    if int(timestamps[0]) != int(since_ms):
        raise RuntimeError(
            f"1m execution data gap before first candle: expected={since_ms}, got={int(timestamps[0])}"
        )
    if len(timestamps) > 1 and (timestamps[1:] - timestamps[:-1] != 60000).any():
        raise RuntimeError("1m execution candles contain a missing-minute gap")
    if not candle_is_fresh(timestamps[-1], "1", cutoff_ms):
        raise RuntimeError("1m execution candles are stale")
    return frame


MAX_INTRABAR_RECOVERY_MINUTES = 7 * 24 * 60
MAX_INTRABAR_HEALTH_AGE_SECONDS = 240
EXECUTION_KLINE_PAGE_SIZE = 1000


def _execution_frame(rows, columns):
    return pd.DataFrame(
        [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])]
         for r in rows], columns=columns
    )


def _fetch_execution_pages(symbol, since_ms, cutoff_ms, source):
    """Page through the complete closed-minute window; never silently truncate at 1000 bars."""
    market_symbol = symbol.replace("/", "")
    columns = ["timestamp", "open", "high", "low", "close", "volume"]
    cursor = int(since_ms)
    frames = []
    expected_last = ((int(cutoff_ms) - 60000) // 60000) * 60000
    if cursor > expected_last:
        return pd.DataFrame(columns=columns)

    page_count = 0
    while cursor <= expected_last:
        page_count += 1
        if page_count > (MAX_INTRABAR_RECOVERY_MINUTES // EXECUTION_KLINE_PAGE_SIZE) + 2:
            raise RuntimeError("1m recovery exceeded pagination safety limit")
        page_end = min(int(cutoff_ms), cursor + (EXECUTION_KLINE_PAGE_SIZE - 1) * 60000)
        if source == "bybit":
            query = urllib.parse.urlencode({
                "category": "spot", "symbol": market_symbol, "interval": "1",
                "start": cursor, "end": page_end, "limit": EXECUTION_KLINE_PAGE_SIZE,
            })
            payload = api_json("https://api.bybit.com/v5/market/kline?" + query)
            if payload.get("retCode") != 0:
                raise RuntimeError("Bybit execution klines: " + str(payload.get("retMsg")))
            rows = payload["result"]["list"]
        else:
            query = urllib.parse.urlencode({
                "symbol": market_symbol, "interval": "1m",
                "startTime": cursor, "endTime": page_end,
                "limit": EXECUTION_KLINE_PAGE_SIZE,
            })
            rows = api_json("https://data-api.binance.vision/api/v3/klines?" + query)

        frame = _execution_frame(rows, columns)
        if frame.empty:
            break
        frame = frame.sort_values("timestamp").reset_index(drop=True)
        frame = frame[(frame.timestamp >= cursor) & (frame.timestamp + 60000 <= int(cutoff_ms))].reset_index(drop=True)
        if frame.empty:
            break
        frames.append(frame)
        next_cursor = int(frame.iloc[-1].timestamp) + 60000
        if next_cursor <= cursor:
            raise RuntimeError("1m recovery pagination did not advance")
        cursor = next_cursor

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    combined = combined.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return validate_execution_klines(combined, since_ms, cutoff_ms)


def fetch_execution_klines(symbol, since_ms):
    """Fetch every closed 1m candle since the cursor, with pagination and strict continuity."""
    cutoff = int(time.time() * 1000)
    since_ms = int(since_ms)
    missing_minutes = max(0, ((cutoff - 60000) // 60000 - since_ms) // 60000 + 1)
    if missing_minutes > MAX_INTRABAR_RECOVERY_MINUTES:
        raise RuntimeError(
            f"1m protection gap too large to reconstruct: {missing_minutes} minutes "
            f"(limit {MAX_INTRABAR_RECOVERY_MINUTES})"
        )
    errors = []
    for source in ("bybit", "binance"):
        try:
            return _fetch_execution_pages(symbol, since_ms, cutoff, source)
        except Exception as exc:
            errors.append(f"{source}: {type(exc).__name__}: {exc}")
    raise RuntimeError("No complete 1m execution history: " + " | ".join(errors))


def intrabar_exit_signal(position, candles):
    """Return the earliest conservative stop/target touch from ordered 1m OHLC candles."""
    stop = float(position["stop"])
    target = float(position["target"])
    for candle in candles.itertuples(index=False):
        opened = float(candle.open)
        high = float(candle.high)
        low = float(candle.low)
        stop_hit = low <= stop
        target_hit = high >= target
        if stop_hit:
            # If both levels trade in one minute, assume the adverse stop happened first.
            reference = min(opened, stop) if opened <= stop else stop
            reason = "GAP_STOP" if opened < stop else "STOP"
            return reason, reference, int(candle.timestamp)
        if target_hit:
            # Do not grant a better-than-target fill on an opening gap.
            return "TARGET", target, int(candle.timestamp)
    return None


def minute_cursor_for_now(now_ms=None):
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    return (now_ms // 60000) * 60000


def recover_intrabar_cursor(last_checked_open_ms, now_ms=None, max_gap_minutes=900):
    """Preserve the original cursor; long gaps must be backfilled or fail-safe closed."""
    return int(last_checked_open_ms)


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
    CREATE TABLE IF NOT EXISTS shadow_intrabar_state(
      strategy_id TEXT PRIMARY KEY, last_checked_open_ms INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS shadow_intrabar_health(
      strategy_id TEXT PRIMARY KEY, last_success_at TEXT, last_error TEXT,
      last_error_at TEXT);
    CREATE TABLE IF NOT EXISTS ashur_meta(
      key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    for s in STRATEGIES:
        conn.execute("""INSERT OR IGNORE INTO shadow_accounts
          (strategy_id,label,symbol,interval,grade,cash,starting_cash,created_at)
          VALUES(?,?,?,?,?,?,?,?)""",
          (s["id"],s["label"],s["symbol"],s["interval"],s["grade"],START_CASH,START_CASH,now()))
        # Keep the persisted dashboard grade aligned with the current research review.
        conn.execute("UPDATE shadow_accounts SET grade=? WHERE strategy_id=?",
                     (s["grade"], s["id"]))
    conn.commit()

def reset_paper_baseline_once(conn):
    """Archive all pre-experiment Paper state, then atomically create a clean baseline."""
    conn.execute("""CREATE TABLE IF NOT EXISTS ashur_meta(
        key TEXT PRIMARY KEY, value TEXT NOT NULL
    )""")
    existing = conn.execute("SELECT value FROM ashur_meta WHERE key='paper_baseline_id'").fetchone()
    if existing and existing["value"] == PAPER_BASELINE_ID:
        return False
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    archive_db = DATA_DIR / ("ashur_shadow.pre_" + PAPER_BASELINE_ID + ".sqlite3")
    archive_status = DATA_DIR / ("ashur_shadow_status.pre_" + PAPER_BASELINE_ID + ".json")
    if not archive_db.exists() and DB.exists():
        with sqlite3.connect(str(DB), timeout=30) as source:
            with sqlite3.connect(str(archive_db), timeout=30) as target:
                source.backup(target)
    if STATUS_FILE.exists() and not archive_status.exists():
        shutil.copy2(STATUS_FILE, archive_status)
    baseline_at = now()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for table in ("shadow_positions", "shadow_trades", "shadow_state", "shadow_events",
                      "shadow_marks", "shadow_trade_guard", "shadow_intrabar_state",
                      "shadow_intrabar_health"):
            conn.execute("DELETE FROM " + table)
        for strategy in STRATEGIES:
            conn.execute("UPDATE shadow_accounts SET cash=?, starting_cash=?, grade=?, created_at=? WHERE strategy_id=?",
                         (START_CASH, START_CASH, strategy["grade"], baseline_at, strategy["id"]))
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('shadow_trades','shadow_events')")
        conn.execute("INSERT OR REPLACE INTO ashur_meta(key,value) VALUES('paper_baseline_id',?)",
                     (PAPER_BASELINE_ID,))
        conn.execute("INSERT OR REPLACE INTO ashur_meta(key,value) VALUES('paper_baseline_at',?)",
                     (baseline_at,))
        event(conn, "SYSTEM", "PAPER_BASELINE_RESET",
              "baseline_id=" + PAPER_BASELINE_ID + "; starting_cash=" + format(START_CASH, ".2f") +
              " per strategy; archived_db=" + archive_db.name)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    print("PAPER_BASELINE_RESET_OK id=" + PAPER_BASELINE_ID + " at=" + baseline_at +
          " accounts=" + str(len(STRATEGIES)) + " cash_each=" + format(START_CASH, ".2f") +
          " archive=" + archive_db.name, flush=True)
    return True

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
    conn.execute("DELETE FROM shadow_intrabar_state WHERE strategy_id=?", (s["id"],))
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
    # Persist the last fully closed minute. The current minute may still be forming
    # and must be fetched after it closes, otherwise the first post-entry slice is skipped.
    cursor_ms = minute_cursor_for_now() - 60000
    conn.execute(
        """INSERT OR REPLACE INTO shadow_intrabar_state(strategy_id,last_checked_open_ms)
           VALUES(?,?)""",
        (s["id"], cursor_ms),
    )
    conn.execute(
        """INSERT INTO shadow_intrabar_health(strategy_id,last_success_at,last_error,last_error_at)
           VALUES(?,?,NULL,NULL) ON CONFLICT(strategy_id) DO UPDATE SET
           last_success_at=excluded.last_success_at,last_error=NULL,last_error_at=NULL""",
        (s["id"], now()),
    )
    event(conn,s["id"],"OPEN",f"paper BUY; qty={qty:.8f}; entry={fill:.6f}; SL={stop:.6f}; TP={target:.6f}")

def probe_intrabar_recovery(conn, strategy):
    """Require a fresh closed-minute data probe before any new paper entry."""
    health = conn.execute(
        "SELECT last_success_at,last_error FROM shadow_intrabar_health WHERE strategy_id=?",
        (strategy["id"],),
    ).fetchone()
    had_error = bool(health and health["last_error"])
    had_success = bool(health and health["last_success_at"])
    if had_success and not had_error:
        try:
            success_at = datetime.fromisoformat(str(health["last_success_at"]).replace("Z", "+00:00"))
            health_age = (datetime.now(timezone.utc) - success_at).total_seconds()
        except (TypeError, ValueError):
            health_age = float("inf")
        if 0 <= health_age <= MAX_INTRABAR_HEALTH_AGE_SECONDS:
            return True

    since_ms = minute_cursor_for_now() - 60000
    try:
        candles = fetch_execution_klines(strategy["symbol"], since_ms)
        if candles.empty:
            raise RuntimeError("No closed 1m candle available for protection validation")
        conn.execute(
            """INSERT INTO shadow_intrabar_health(strategy_id,last_success_at,last_error,last_error_at)
               VALUES(?,?,NULL,NULL) ON CONFLICT(strategy_id) DO UPDATE SET
               last_success_at=excluded.last_success_at,last_error=NULL,last_error_at=NULL""",
            (strategy["id"], now()),
        )
        event_name = "PROTECTION_RECOVERED" if had_error else ("PROTECTION_INITIALIZED" if not had_success else "PROTECTION_REFRESHED")
        event(conn, strategy["id"], event_name,
              f"validated_closed_minutes={len(candles)}; entry_allowed_this_cycle={not had_error}")
        return not had_error
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"[:500]
        conn.execute(
            """INSERT INTO shadow_intrabar_health(strategy_id,last_success_at,last_error,last_error_at)
               VALUES(?,NULL,?,?) ON CONFLICT(strategy_id) DO UPDATE SET
               last_error=excluded.last_error,last_error_at=excluded.last_error_at""",
            (strategy["id"], error_text, now()),
        )
        event(conn, strategy["id"], "PROTECTION_RECOVERY_BLOCKED", error_text)
    return False


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
    intrabar_warnings_24h = conn.execute(
        """SELECT COUNT(*) FROM shadow_events
           WHERE event='INTRABAR_DATA_WARNING' AND created_at>=?""",
        (cutoff_24h,),
    ).fetchone()[0]
    baseline_id = conn.execute("SELECT value FROM ashur_meta WHERE key='paper_baseline_id'").fetchone()
    baseline_at = conn.execute("SELECT value FROM ashur_meta WHERE key='paper_baseline_at'").fetchone()
    output = {"updated_at": now(), "mode": "PAPER_ONLY",
              "experiment": {
                  "baseline_id": baseline_id["value"] if baseline_id else None,
                  "baseline_at": baseline_at["value"] if baseline_at else None,
                  "starting_equity_per_strategy": START_CASH,
                  "strategy_count": len(STRATEGIES),
              },
              "market_data": "Public spot market data; Bybit primary, Binance fallback",
              "worker_health": {"strategy_count": len(STRATEGIES),
                                "successful_strategies": successful_strategies,
                                "error_count": int(worker_errors),
                                "intrabar_data_warnings_24h": int(intrabar_warnings_24h),
                                "all_strategies_ok": int(worker_errors) == 0 and successful_strategies == len(STRATEGIES),
                                "protection_degraded_positions": 0,
                                "protection_degraded_strategies": 0,
                                "all_protections_ok": True},
              "news_intelligence": {**news.collection_stats(conn, 24),
                                    "news_vetoes_24h": int(news_vetoes_24h),
                                    "veto_outcomes": news.veto_outcome_stats(conn)},
              "accounts": []}
    for a in accounts:
        pos = conn.execute("SELECT * FROM shadow_positions WHERE strategy_id=?", (a["strategy_id"],)).fetchone()
        mark = conn.execute("SELECT price,updated_at FROM shadow_marks WHERE strategy_id=?", (a["strategy_id"],)).fetchone()
        trades = conn.execute("SELECT pnl,fees,reason,opened_at,closed_at FROM shadow_trades WHERE strategy_id=? ORDER BY id", (a["strategy_id"],)).fetchall()
        realized = sum(float(t["pnl"]) for t in trades)
        recent_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        recent_trades = conn.execute(
            """SELECT id,entry,exit,qty,fees,pnl,reason,opened_at,closed_at
               FROM shadow_trades WHERE strategy_id=? AND closed_at>=?
               ORDER BY id DESC LIMIT 100""",
            (a["strategy_id"], recent_cutoff),
        ).fetchall()
        wins = sum(float(t["pnl"]) > 0 for t in trades)
        gross_profit = sum(float(t["pnl"]) for t in trades if float(t["pnl"]) > 0)
        gross_loss = abs(sum(float(t["pnl"]) for t in trades if float(t["pnl"]) < 0))
        price = float(mark["price"]) if mark else None
        unrealized = 0.0
        position = None
        liquidation_value = 0.0
        protection = conn.execute(
            "SELECT last_success_at,last_error,last_error_at FROM shadow_intrabar_health WHERE strategy_id=?",
            (a["strategy_id"],),
        ).fetchone()
        protection_status = "DEGRADED" if protection and protection["last_error"] else "NOT_REQUIRED"
        if pos:
            protection_status = "UNKNOWN"
            if protection and protection["last_success_at"] and not protection["last_error"]:
                protection_status = "OK"
            if protection_status != "OK":
                output["worker_health"]["protection_degraded_positions"] += 1
                output["worker_health"]["all_protections_ok"] = False
            mark_price = price if price is not None else float(pos["entry"])
            # Mark open positions at estimated net liquidation value, not gross market value.
            liquidation_value = (
                float(pos["qty"]) * mark_price * (1 - SLIPPAGE) * (1 - FEE)
            )
            entry_cost = float(pos["qty"]) * float(pos["entry"]) + float(pos["entry_fee"])
            unrealized = liquidation_value - entry_cost
            position = {"symbol":pos["symbol"],"qty":float(pos["qty"]),"entry":float(pos["entry"]),
                        "mark":mark_price,"stop":float(pos["stop"]),"target":float(pos["target"]),
                        "unrealized_pnl":round(unrealized,4),"opened_at":pos["opened_at"],
                        "protection_status":protection_status,
                        "last_intrabar_success_at":protection["last_success_at"] if protection else None,
                        "last_intrabar_error":protection["last_error"] if protection else None}
        if protection and protection["last_error"]:
            output["worker_health"]["protection_degraded_strategies"] += 1
            output["worker_health"]["all_protections_ok"] = False
        cash = float(a["cash"])
        equity = cash + liquidation_value
        output["accounts"].append({
            "strategy_id":a["strategy_id"],"label":a["label"],"symbol":a["symbol"],
            "timeframe":{"15":"15m","60":"1h","240":"4h","D":"1d"}.get(a["interval"],a["interval"]),
            "grade":a["grade"],"protection_status":protection_status,
            "starting_cash":float(a["starting_cash"]),"cash":round(cash,4),
            "equity":round(equity,4),"net_pnl":round(equity-float(a["starting_cash"]),4),
            "realized_pnl":round(realized,4),"unrealized_pnl":round(unrealized,4),
            "return_pct":round((equity/float(a["starting_cash"])-1)*100,4),
            "trades":len(trades),"wins":wins,"win_rate_pct":round(wins/len(trades)*100,2) if trades else 0,
            "profit_factor":round(gross_profit/gross_loss,3) if gross_loss else (None if not gross_profit else "inf"),
            "fees":round(sum(float(t["fees"]) for t in trades),4),
            "recent_trades_30d":[
                {"id":int(t["id"]),"entry":float(t["entry"]),"exit":float(t["exit"]),
                 "qty":float(t["qty"]),"fees":round(float(t["fees"]),6),
                 "net_pnl":round(float(t["pnl"]),6),"reason":t["reason"],
                 "opened_at":t["opened_at"],"closed_at":t["closed_at"]}
                for t in recent_trades
            ],
            "last_price":price,"last_price_at":mark["updated_at"] if mark else None,
            "position":position
        })
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")

def run():
    prepare_data_dir()
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    if os.environ.get("ASHUR_RESET_PAPER_BASELINE_ID") == PAPER_BASELINE_ID:
        reset_paper_baseline_once(conn)
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
                # Always honor a currently breached stop/target even if the 1m feed is unavailable.
                if price <= pos["stop"]:
                    close_position(conn, s, price, stop_exit_reason(price, pos["stop"]), candle_id)
                    closed_this_cycle = True
                elif price >= pos["target"]:
                    target_reference = target_exit_reference_price(price, pos["target"])
                    close_position(conn, s, target_reference, "TARGET", candle_id)
                    closed_this_cycle = True
                else:
                    cursor = conn.execute(
                        "SELECT last_checked_open_ms FROM shadow_intrabar_state WHERE strategy_id=?",
                        (s["id"],),
                    ).fetchone()
                    protection_ok = True
                    if cursor is None:
                        protection_ok = False
                        error_text = "Existing open position has no persisted 1m protection cursor"
                    else:
                        previous_cursor = int(cursor["last_checked_open_ms"])
                        recovered_cursor = recover_intrabar_cursor(previous_cursor)
                        since_ms = recovered_cursor + 60000
                        try:
                            execution_candles = fetch_execution_klines(s["symbol"], since_ms)
                        except Exception as exc:
                            protection_ok = False
                            error_text = f"{type(exc).__name__}: {exc}"[:500]
                            execution_candles = None

                    if not protection_ok:
                        # Paper fail-safe: flatten at the current validated ticker when the
                        # stop history cannot be reconstructed. This is a simulation safeguard,
                        # not an exchange-side stop or a claim about historical execution.
                        event(conn, s["id"], "INTRABAR_DATA_WARNING", error_text)
                        event(conn, s["id"], "PROTECTION_GAP_FAILSAFE",
                              f"paper position closed at live mark={price:.6f}; new entries blocked this cycle")
                        conn.execute(
                            """INSERT INTO shadow_intrabar_health(strategy_id,last_error,last_error_at)
                               VALUES(?,?,?) ON CONFLICT(strategy_id) DO UPDATE SET
                               last_error=excluded.last_error,last_error_at=excluded.last_error_at""",
                            (s["id"], error_text, now()),
                        )
                        close_position(conn, s, price, "PROTECTION_GAP_FAILSAFE", candle_id)
                        closed_this_cycle = True
                    else:
                        conn.execute(
                            """INSERT INTO shadow_intrabar_health(strategy_id,last_success_at,last_error,last_error_at)
                               VALUES(?,?,NULL,NULL) ON CONFLICT(strategy_id) DO UPDATE SET
                               last_success_at=excluded.last_success_at,last_error=NULL,last_error_at=NULL""",
                            (s["id"], now()),
                        )
                        intrabar_exit = intrabar_exit_signal(pos, execution_candles)
                        if not execution_candles.empty:
                            last_checked = int(execution_candles.iloc[-1].timestamp)
                            conn.execute(
                                "UPDATE shadow_intrabar_state SET last_checked_open_ms=? WHERE strategy_id=?",
                                (last_checked, s["id"]),
                            )
                        if intrabar_exit:
                            reason, reference_price, exit_candle_ms = intrabar_exit
                            close_position(conn, s, reference_price, reason, candle_id)
                            event(conn, s["id"], "INTRABAR_EXIT",
                                  f"{reason}; reference={reference_price:.6f}; candle={exit_candle_ms}")
                            closed_this_cycle = True
                if not closed_this_cycle:
                    if daily_loss_limit_hit(conn, s["id"], pos, price):
                        close_position(conn, s, price, "DAILY_STOP", candle_id)
                        closed_this_cycle = True
                    elif exit_signal:
                        close_position(conn, s, price, "SIGNAL", candle_id)
                        closed_this_cycle = True
            guard = conn.execute("SELECT last_closed_candle FROM shadow_trade_guard WHERE strategy_id=?",(s["id"],)).fetchone()
            cooldown_active = bool(guard and guard["last_closed_candle"] == candle_id)
            pos = conn.execute("SELECT * FROM shadow_positions WHERE strategy_id=?",(s["id"],)).fetchone()
            entry_protection_ok = probe_intrabar_recovery(conn, s) if not pos else True
            if not pos and entry_signal and not closed_this_cycle and not cooldown_active and entry_protection_ok:
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
