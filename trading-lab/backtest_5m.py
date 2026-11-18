import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME = "5m"
INTERVAL_MS = 5 * 60 * 1000
LOOKBACK_DAYS = 30
START_BALANCE = 10_000.0
RISK_PER_TRADE = 0.005
STOP_PCT = 0.02
TARGET_PCT = 0.04
FEE_RATE = 0.001


def fetch_history(symbol):
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int((datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000)
    cursor = start_ms
    candles = []

    while cursor < end_ms:
        query = urllib.parse.urlencode({
            "symbol": symbol.replace("/", ""),
            "interval": TIMEFRAME,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": 1000,
        })
        url = "https://data-api.binance.vision/api/v3/klines?" + query
        request = urllib.request.Request(url, headers={"User-Agent": "ASHUR-5m-Backtest/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            batch = json.loads(response.read().decode("utf-8"))
        if not isinstance(batch, list) or not batch:
            break
        candles.extend([[r[0], r[1], r[2], r[3], r[4], r[5]] for r in batch])
        next_cursor = int(batch[-1][0]) + INTERVAL_MS
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(0.12)

    frame = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame = frame.dropna().drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    now = pd.Timestamp.now(tz="UTC")
    frame = frame[frame["timestamp"] + pd.Timedelta(milliseconds=INTERVAL_MS) <= now].reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"No closed 5m candles returned for {symbol}")

    frame["ema50"] = frame["close"].ewm(span=50, adjust=False).mean()
    frame["ema200"] = frame["close"].ewm(span=200, adjust=False).mean()
    frame["donchian_high"] = frame["high"].rolling(20).max().shift(1)
    for window in [10, 20, 40]:
        frame[f"donchian_low_{window}"] = frame["low"].rolling(window).min().shift(1)
    frame["signal"] = "HOLD"
    frame.loc[(frame["close"] > frame["donchian_high"]) & (frame["ema50"] > frame["ema200"]), "signal"] = "BUY"
    return frame


def backtest(symbol, frame, exit_mode):
    cash = START_BALANCE
    position = None
    trades = []
    equity_curve = []

    for i in range(201, len(frame)):
        previous = frame.iloc[i - 1]
        bar = frame.iloc[i]
        exited_this_bar = False

        if position is not None:
            reason = None
            exit_price = None
            if float(bar["low"]) <= position["stop"]:
                reason, exit_price = "STOP LOSS", position["stop"]
            elif float(bar["high"]) >= position["target"]:
                reason, exit_price = "TAKE PROFIT", position["target"]
            elif (
                (exit_mode.startswith("donchian") and float(previous["close"]) < float(previous[f"donchian_low_{exit_mode.split('_')[1]}"]))
                or (exit_mode == "ema_cross" and float(previous["ema50"]) < float(previous["ema200"]))
            ):
                reason, exit_price = "STRATEGY EXIT", float(bar["open"])

            if reason:
                exit_fee = position["qty"] * exit_price * FEE_RATE
                proceeds = position["qty"] * exit_price - exit_fee
                cash += proceeds
                pnl = proceeds - position["entry_cost"]
                trades.append({
                    "pnl": pnl,
                    "fees": position["entry_fee"] + exit_fee,
                    "reason": reason,
                    "entry": position["entry"],
                    "exit": exit_price,
                })
                position = None
                exited_this_bar = True

        if position is None and not exited_this_bar and str(previous["signal"]) == "BUY":
            entry = float(bar["open"])
            notional = min(cash * RISK_PER_TRADE / STOP_PCT, cash / (1 + FEE_RATE))
            if notional > 0:
                qty = notional / entry
                entry_fee = notional * FEE_RATE
                cash -= notional + entry_fee
                position = {
                    "entry": entry,
                    "qty": qty,
                    "entry_fee": entry_fee,
                    "entry_cost": notional + entry_fee,
                    "stop": entry * (1 - STOP_PCT),
                    "target": entry * (1 + TARGET_PCT),
                }

                # Conservative intrabar handling: if both barriers are hit, stop wins.
                if float(bar["low"]) <= position["stop"]:
                    exit_price, reason = position["stop"], "STOP LOSS"
                elif float(bar["high"]) >= position["target"]:
                    exit_price, reason = position["target"], "TAKE PROFIT"
                else:
                    exit_price = reason = None
                if reason:
                    exit_fee = qty * exit_price * FEE_RATE
                    proceeds = qty * exit_price - exit_fee
                    cash += proceeds
                    pnl = proceeds - position["entry_cost"]
                    trades.append({
                        "pnl": pnl,
                        "fees": entry_fee + exit_fee,
                        "reason": reason,
                        "entry": entry,
                        "exit": exit_price,
                    })
                    position = None
                    exited_this_bar = True

        mark = cash + (position["qty"] * float(bar["close"]) if position else 0.0)
        equity_curve.append(mark)

    last_close = float(frame.iloc[-1]["close"])
    unrealized = 0.0
    ending_equity = cash
    if position:
        exit_fee_estimate = position["qty"] * last_close * FEE_RATE
        unrealized = position["qty"] * last_close - exit_fee_estimate - position["entry_cost"]
        ending_equity = cash + position["qty"] * last_close

    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    peak = START_BALANCE
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            max_drawdown = max(max_drawdown, (peak - value) / peak * 100)

    total_fees = sum(t["fees"] for t in trades)
    return {
        "symbol": symbol,
        "exit_mode": exit_mode,
        "candles": len(frame),
        "period_start_utc": frame.iloc[0]["timestamp"].isoformat(),
        "period_end_utc": frame.iloc[-1]["timestamp"].isoformat(),
        "closed_trades": len(trades),
        "wins": len(wins),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "net_realized_pnl_usdt": round(sum(t["pnl"] for t in trades), 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else ("infinite" if gross_profit else 0.0),
        "total_fees_usdt": round(total_fees, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "open_position": bool(position),
        "open_position_unrealized_pnl_usdt": round(unrealized, 2),
        "ending_equity_including_open_position_usdt": round(ending_equity, 2),
        "exit_reasons": {
            reason: sum(1 for t in trades if t["reason"] == reason)
            for reason in ["STOP LOSS", "TAKE PROFIT", "STRATEGY EXIT"]
        },
    }


def main():
    print(f"ASHUR 5m historical paper backtest | last {LOOKBACK_DAYS} days | fee {FEE_RATE * 100:.2f}% per side")
    results = []
    exit_modes = ["donchian_10", "donchian_20", "donchian_40", "ema_cross", "no_signal_exit"]
    for symbol in SYMBOLS:
        frame = fetch_history(symbol)
        for exit_mode in exit_modes:
            result = backtest(symbol, frame, exit_mode)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False))
    for exit_mode in exit_modes:
        group = [r for r in results if r["exit_mode"] == exit_mode]
        combined_pnl = sum(r["net_realized_pnl_usdt"] for r in group)
        combined_fees = sum(r["total_fees_usdt"] for r in group)
        combined_trades = sum(r["closed_trades"] for r in group)
        print(json.dumps({
            "exit_mode": exit_mode,
            "combined_independent_10k_accounts": True,
            "starting_capital_usdt": START_BALANCE * len(group),
            "closed_trades": combined_trades,
            "net_realized_pnl_usdt": round(combined_pnl, 2),
            "total_fees_usdt": round(combined_fees, 2),
            "ending_equity_usdt_excluding_open_positions": round(START_BALANCE * len(group) + combined_pnl, 2),
            "note": "Each symbol is simulated with its own 10,000 USDT account; this is a strategy diagnostic, not a guarantee of future returns."
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
