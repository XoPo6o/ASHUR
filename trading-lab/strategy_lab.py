import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAMES = {"5m": 5 * 60 * 1000, "15m": 15 * 60 * 1000, "1h": 60 * 60 * 1000}
LOOKBACK_DAYS = 180
INITIAL_EQUITY = 10_000.0
RISK_PER_TRADE = 0.005
MAX_NOTIONAL_FRACTION = 0.95
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005
ATR_STOP_MULTIPLE = 2.0
REWARD_RISK = 3.0
TRAIN_FRACTION = 0.70


def fetch_history(symbol, timeframe, interval_ms):
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int((datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000)
    cursor = start_ms
    rows = []
    while cursor < end_ms:
        query = urllib.parse.urlencode({
            "symbol": symbol.replace("/", ""),
            "interval": timeframe,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": 1000,
        })
        url = "https://data-api.binance.vision/api/v3/klines?" + query
        request = urllib.request.Request(url, headers={"User-Agent": "ASHUR-Strategy-Lab/1.0"})
        with urllib.request.urlopen(request, timeout=25) as response:
            batch = json.loads(response.read().decode("utf-8"))
        if not isinstance(batch, list) or not batch:
            break
        rows.extend([[r[0], r[1], r[2], r[3], r[4], r[5]] for r in batch])
        next_cursor = int(batch[-1][0]) + interval_ms
        if next_cursor <= cursor:
            raise RuntimeError(f"Pagination stalled for {symbol} {timeframe}")
        cursor = next_cursor
        time.sleep(0.08)

    frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame = frame.dropna().drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    now = pd.Timestamp.now(tz="UTC")
    frame = frame[frame["timestamp"] + pd.Timedelta(milliseconds=interval_ms) <= now].reset_index(drop=True)
    if len(frame) < 500:
        raise RuntimeError(f"Insufficient closed candles for {symbol} {timeframe}: {len(frame)}")
    return frame


def add_indicators(frame):
    x = frame.copy()
    x["ema20"] = x["close"].ewm(span=20, adjust=False).mean()
    x["ema50"] = x["close"].ewm(span=50, adjust=False).mean()
    x["ema200"] = x["close"].ewm(span=200, adjust=False).mean()

    delta = x["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    x["rsi"] = 100 - (100 / (1 + rs))
    x.loc[(loss == 0) & (gain > 0), "rsi"] = 100

    previous_close = x["close"].shift(1)
    true_range = pd.concat([
        x["high"] - x["low"],
        (x["high"] - previous_close).abs(),
        (x["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    x["atr"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

    x["bb_mid"] = x["close"].rolling(20).mean()
    bb_std = x["close"].rolling(20).std(ddof=0)
    x["bb_upper"] = x["bb_mid"] + 2 * bb_std
    x["bb_lower"] = x["bb_mid"] - 2 * bb_std

    fast = x["close"].ewm(span=12, adjust=False).mean()
    slow = x["close"].ewm(span=26, adjust=False).mean()
    x["macd"] = fast - slow
    x["macd_signal"] = x["macd"].ewm(span=9, adjust=False).mean()

    x["donchian_high_20"] = x["high"].rolling(20).max().shift(1)
    x["donchian_low_10"] = x["low"].rolling(10).min().shift(1)
    x["volume_sma20"] = x["volume"].rolling(20).mean()

    prev = x.shift(1)
    x["ema_cross_entry"] = (x["ema20"] > x["ema50"]) & (prev["ema20"] <= prev["ema50"]) & (x["close"] > x["ema200"])
    x["ema_cross_exit"] = (x["ema20"] < x["ema50"])

    x["macd_entry"] = (x["macd"] > x["macd_signal"]) & (prev["macd"] <= prev["macd_signal"]) & (x["close"] > x["ema200"])
    x["macd_exit"] = (x["macd"] < x["macd_signal"]) | (x["close"] < x["ema50"])

    x["rsi_pullback_entry"] = (x["ema50"] > x["ema200"]) & (x["rsi"] > 40) & (prev["rsi"] <= 40)
    x["rsi_pullback_exit"] = (x["rsi"] >= 70) | (x["close"] < x["ema50"])

    x["rsi_mean_entry"] = (x["rsi"] < 30) & (x["close"] < x["bb_lower"])
    x["rsi_mean_exit"] = (x["rsi"] >= 50) | (x["close"] >= x["bb_mid"])

    x["bb_breakout_entry"] = (x["close"] > x["bb_upper"]) & (prev["close"] <= prev["bb_upper"]) & (x["volume"] > 1.2 * x["volume_sma20"])
    x["bb_breakout_exit"] = x["close"] < x["bb_mid"]

    x["donchian_entry"] = (x["close"] > x["donchian_high_20"]) & (x["ema50"] > x["ema200"])
    x["donchian_exit"] = x["close"] < x["donchian_low_10"]
    return x


STRATEGIES = {
    "ema20_50_cross_trend": ("ema_cross_entry", "ema_cross_exit"),
    "macd_cross_ema200_filter": ("macd_entry", "macd_exit"),
    "rsi40_trend_pullback": ("rsi_pullback_entry", "rsi_pullback_exit"),
    "rsi_bollinger_mean_reversion": ("rsi_mean_entry", "rsi_mean_exit"),
    "bollinger_volume_breakout": ("bb_breakout_entry", "bb_breakout_exit"),
    "donchian20_ema_trend_breakout": ("donchian_entry", "donchian_exit"),
}


def simulate(frame, strategy_name, start_index, end_index):
    entry_column, exit_column = STRATEGIES[strategy_name]
    cash = INITIAL_EQUITY
    position = None
    trades = []
    equity_curve = []
    start_index = max(205, start_index)

    for i in range(start_index, end_index):
        previous = frame.iloc[i - 1]
        bar = frame.iloc[i]
        exited = False

        if position is not None:
            reason = None
            raw_exit = None
            if float(bar["low"]) <= position["stop"]:
                reason, raw_exit = "ATR_STOP", position["stop"]
            elif float(bar["high"]) >= position["target"]:
                reason, raw_exit = "ATR_TARGET", position["target"]
            elif bool(previous[exit_column]):
                reason, raw_exit = "SIGNAL_EXIT", float(bar["open"])

            if reason:
                exit_price = raw_exit * (1 - SLIPPAGE_RATE)
                proceeds = position["qty"] * exit_price
                exit_fee = proceeds * FEE_RATE
                cash += proceeds - exit_fee
                net_pnl = proceeds - exit_fee - position["entry_cost"]
                trades.append({
                    "net_pnl": net_pnl,
                    "fees": position["entry_fee"] + exit_fee,
                    "bars_held": i - position["entry_index"] + 1,
                    "reason": reason,
                })
                position = None
                exited = True

        if position is None and not exited and bool(previous[entry_column]):
            atr = float(previous["atr"])
            raw_entry = float(bar["open"])
            entry_price = raw_entry * (1 + SLIPPAGE_RATE)
            stop_distance = ATR_STOP_MULTIPLE * atr
            if pd.notna(atr) and atr > 0 and stop_distance < entry_price:
                stop_fraction = stop_distance / entry_price
                risk_budget = cash * RISK_PER_TRADE
                notional = min(risk_budget / stop_fraction, cash * MAX_NOTIONAL_FRACTION / (1 + FEE_RATE))
                qty = notional / entry_price
                entry_fee = notional * FEE_RATE
                entry_cost = notional + entry_fee
                if qty > 0 and entry_cost <= cash:
                    cash -= entry_cost
                    position = {
                        "qty": qty,
                        "entry_price": entry_price,
                        "entry_fee": entry_fee,
                        "entry_cost": entry_cost,
                        "entry_index": i,
                        "stop": entry_price - stop_distance,
                        "target": entry_price + REWARD_RISK * stop_distance,
                    }
                    # Conservative same-bar barrier handling: stop is assumed first.
                    reason = None
                    raw_exit = None
                    if float(bar["low"]) <= position["stop"]:
                        reason, raw_exit = "ATR_STOP", position["stop"]
                    elif float(bar["high"]) >= position["target"]:
                        reason, raw_exit = "ATR_TARGET", position["target"]
                    if reason:
                        exit_price = raw_exit * (1 - SLIPPAGE_RATE)
                        proceeds = qty * exit_price
                        exit_fee = proceeds * FEE_RATE
                        cash += proceeds - exit_fee
                        trades.append({
                            "net_pnl": proceeds - exit_fee - entry_cost,
                            "fees": entry_fee + exit_fee,
                            "bars_held": 1,
                            "reason": reason,
                        })
                        position = None
                        exited = True

        mark_equity = cash
        if position is not None:
            liquidation_value = position["qty"] * float(bar["close"]) * (1 - SLIPPAGE_RATE) * (1 - FEE_RATE)
            mark_equity += liquidation_value
        equity_curve.append(mark_equity)

    if position is not None:
        last_close = float(frame.iloc[end_index - 1]["close"])
        exit_price = last_close * (1 - SLIPPAGE_RATE)
        proceeds = position["qty"] * exit_price
        exit_fee = proceeds * FEE_RATE
        cash += proceeds - exit_fee
        trades.append({
            "net_pnl": proceeds - exit_fee - position["entry_cost"],
            "fees": position["entry_fee"] + exit_fee,
            "bars_held": end_index - position["entry_index"],
            "reason": "PERIOD_END",
        })
        position = None

    peak = INITIAL_EQUITY
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak * 100)

    pnls = [t["net_pnl"] for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]
    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    total_pnl = sum(pnls)
    return {
        "trades": len(trades),
        "wins": len(winners),
        "win_rate_pct": round(100 * len(winners) / len(trades), 2) if trades else 0.0,
        "net_pnl_usdt": round(total_pnl, 2),
        "return_pct": round(total_pnl / INITIAL_EQUITY * 100, 3),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else ("inf" if gross_profit else 0.0),
        "max_drawdown_pct": round(max_drawdown, 3),
        "fees_usdt": round(sum(t["fees"] for t in trades), 2),
        "expectancy_usdt": round(total_pnl / len(trades), 3) if trades else 0.0,
        "avg_bars_held": round(sum(t["bars_held"] for t in trades) / len(trades), 2) if trades else 0.0,
        "ending_equity_usdt": round(cash, 2),
        "exit_reasons": {
            reason: sum(1 for t in trades if t["reason"] == reason)
            for reason in ["ATR_STOP", "ATR_TARGET", "SIGNAL_EXIT", "PERIOD_END"]
        },
    }


def main():
    results = []
    print(
        f"ASHUR strategy lab | {LOOKBACK_DAYS} days | train {TRAIN_FRACTION:.0%} / OOS {1-TRAIN_FRACTION:.0%} | "
        f"fee {FEE_RATE:.2%} each side | slippage {SLIPPAGE_RATE:.2%} each side | "
        f"risk {RISK_PER_TRADE:.2%} | ATR stop {ATR_STOP_MULTIPLE}x | target {REWARD_RISK}R"
    )

    for symbol in SYMBOLS:
        for timeframe, interval_ms in TIMEFRAMES.items():
            raw = fetch_history(symbol, timeframe, interval_ms)
            frame = add_indicators(raw)
            split = int(len(frame) * TRAIN_FRACTION)
            for strategy_name in STRATEGIES:
                train = simulate(frame, strategy_name, 205, split)
                oos = simulate(frame, strategy_name, split, len(frame))
                row = {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "strategy": strategy_name,
                    "candles": len(frame),
                    "period_start_utc": frame.iloc[0]["timestamp"].isoformat(),
                    "period_end_utc": frame.iloc[-1]["timestamp"].isoformat(),
                    "train": train,
                    "out_of_sample": oos,
                }
                results.append(row)
                print(json.dumps({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "strategy": strategy_name,
                    "train_return_pct": train["return_pct"],
                    "train_pf": train["profit_factor"],
                    "oos_trades": oos["trades"],
                    "oos_return_pct": oos["return_pct"],
                    "oos_pf": oos["profit_factor"],
                    "oos_max_dd_pct": oos["max_drawdown_pct"],
                    "oos_fees_usdt": oos["fees_usdt"],
                }, ensure_ascii=False))

    results.sort(
        key=lambda r: (
            r["out_of_sample"]["return_pct"],
            r["out_of_sample"]["profit_factor"] if isinstance(r["out_of_sample"]["profit_factor"], (int, float)) else 999,
            -r["out_of_sample"]["max_drawdown_pct"],
        ),
        reverse=True,
    )
    json_path = ROOT / "strategy_research_results.json"
    csv_path = ROOT / "strategy_research_leaderboard.csv"
    json_path.write_text(json.dumps({
        "config": {
            "lookback_days": LOOKBACK_DAYS,
            "train_fraction": TRAIN_FRACTION,
            "fee_rate_each_side": FEE_RATE,
            "slippage_rate_each_side": SLIPPAGE_RATE,
            "risk_per_trade": RISK_PER_TRADE,
            "atr_stop_multiple": ATR_STOP_MULTIPLE,
            "reward_risk": REWARD_RISK,
            "long_only": True,
            "note": "Historical simulation, not a profit guarantee. OOS is chronological holdout, not independent future validation."
        },
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "symbol", "timeframe", "strategy", "train_return_pct", "train_trades", "train_pf",
            "oos_return_pct", "oos_trades", "oos_win_rate_pct", "oos_pf", "oos_max_drawdown_pct",
            "oos_fees_usdt", "oos_expectancy_usdt",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in results:
            writer.writerow({
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "strategy": row["strategy"],
                "train_return_pct": row["train"]["return_pct"],
                "train_trades": row["train"]["trades"],
                "train_pf": row["train"]["profit_factor"],
                "oos_return_pct": row["out_of_sample"]["return_pct"],
                "oos_trades": row["out_of_sample"]["trades"],
                "oos_win_rate_pct": row["out_of_sample"]["win_rate_pct"],
                "oos_pf": row["out_of_sample"]["profit_factor"],
                "oos_max_drawdown_pct": row["out_of_sample"]["max_drawdown_pct"],
                "oos_fees_usdt": row["out_of_sample"]["fees_usdt"],
                "oos_expectancy_usdt": row["out_of_sample"]["expectancy_usdt"],
            })

    eligible = [
        row for row in results
        if row["out_of_sample"]["trades"] >= 8
        and isinstance(row["out_of_sample"]["profit_factor"], (int, float))
        and row["out_of_sample"]["profit_factor"] > 1
        and row["out_of_sample"]["return_pct"] > 0
    ]
    print("=== OUT-OF-SAMPLE CANDIDATES: positive return, PF > 1, at least 8 trades ===")
    if not eligible:
        print("NONE. No tested configuration met all minimum OOS filters.")
    for row in eligible[:10]:
        print(json.dumps({
            "symbol": row["symbol"],
            "timeframe": row["timeframe"],
            "strategy": row["strategy"],
            "oos_return_pct": row["out_of_sample"]["return_pct"],
            "oos_trades": row["out_of_sample"]["trades"],
            "oos_pf": row["out_of_sample"]["profit_factor"],
            "oos_max_drawdown_pct": row["out_of_sample"]["max_drawdown_pct"],
            "oos_fees_usdt": row["out_of_sample"]["fees_usdt"],
        }, ensure_ascii=False))
    print(f"Saved {json_path.name} and {csv_path.name}")


if __name__ == "__main__":
    main()
