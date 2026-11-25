#!/usr/bin/env python3
"""Historical screening of the six exact ASHUR live-shadow strategy rules.

This is research only. It never imports the live worker's database or sends orders.
"""
import argparse
import csv
import importlib.util
import json
import math
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

LOOKBACK_DAYS = 1095
INITIAL_EQUITY = 1000.0
RISK_PER_TRADE = 0.005
DAILY_STOP_FRACTION = 0.02
MAX_NOTIONAL_FRACTION = 0.95
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005
ATR_STOP_MULTIPLE = 3.0
REWARD_RISK = 4.0
TRAIN_FRACTION = 0.60
VALIDATION_FRACTION = 0.20

DATASETS = [
    ("BNB/USDT", "15m", 900_000, ["BNB_15M_EMA_TREND"]),
    ("BNB/USDT", "1h", 3_600_000, ["BNB_1H_DONCHIAN_ADX25"]),
    ("BNB/USDT", "4h", 14_400_000, ["BNB_4H_KELTNER_ADX", "BNB_4H_ADX_TREND"]),
    ("BNB/USDT", "1d", 86_400_000, ["BNB_1D_DONCHIAN55"]),
    ("SOL/USDT", "4h", 14_400_000, ["SOL_4H_DONCHIAN_VOL"]),
]

STRATEGY_COLUMNS = {
    "BNB_15M_EMA_TREND": ("ema15_entry", "ema15_exit"),
    "BNB_1H_DONCHIAN_ADX25": ("don_adx25_entry", "don_adx_exit"),
    "BNB_4H_KELTNER_ADX": ("keltner_adx_entry", "keltner_adx_exit"),
    "BNB_4H_ADX_TREND": ("adx_trend_entry", "adx_trend_exit"),
    "BNB_1D_DONCHIAN55": ("don55_entry", "don55_exit"),
    "SOL_4H_DONCHIAN_VOL": ("don_vol_entry", "don_vol_exit"),
}


def load_research_engine(live_code_dir):
    module_path = Path(live_code_dir) / "strategy_lab_v3.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"Expected research engine not found: {module_path}")
    spec = importlib.util.spec_from_file_location("ashur_strategy_lab_v3", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.LOOKBACK_DAYS = LOOKBACK_DAYS
    return module


def add_live_signals(frame):
    x = frame.copy()
    x["ema15_entry"] = (x.close > x.ema20) & (x.ema20 > x.ema50) & (x.adx > 12)
    x["ema15_exit"] = (x.close < x.ema50) | (x.ema20 < x.ema50)

    don_votes = (
        (x.close > x.donchian20).astype(int)
        + (x.close > x.donchian55).astype(int)
        + (x.close > x.donchian100).astype(int)
    )
    x["don_adx25_entry"] = (don_votes >= 2) & (x.close > x.ema200) & (x.adx > 25)
    x["don_adx_exit"] = (x.close < x.donchian20low) | (x.close < x.ema100)

    x["keltner_adx_entry"] = (
        (x.close > x.keltner_upper) & (x.ema50 > x.ema200) & (x.adx > 15)
    )
    x["keltner_adx_exit"] = (x.close < x.ema20) | (x.ema50 < x.ema200)

    x["adx_trend_entry"] = (
        (x.ema50 > x.ema200) & (x.adx > 20) & (x.close > x.ema50)
    )
    x["adx_trend_exit"] = (x.ema50 < x.ema200) | (x.close < x.ema50)

    x["don55_entry"] = (x.close > x.donchian55) & (x.close > x.ema200)
    x["don55_exit"] = x.close < x.donchian10low

    x["don_vol_entry"] = (
        (x.close > x.donchian55) & (x.close > x.ema200) & (x.atr_pct < x.atr_pct_p80)
    )
    x["don_vol_exit"] = (x.close < x.donchian20low) | (x.close < x.ema100)
    return x


def simulate_live_rules(frame, strategy_id, start, end, annual_bars):
    """Causal bar backtest with live risk sizing, costs, 3 ATR stop and 4R target."""
    entry_col, exit_col = STRATEGY_COLUMNS[strategy_id]
    cash = INITIAL_EQUITY
    position = None
    trades = []
    equity_curve = []
    daily_realized = 0.0
    active_day = None
    daily_blocked = False
    start = max(205, int(start))

    def close_position(raw_price, reason, bar_day, bars_held):
        nonlocal cash, position, daily_realized, daily_blocked
        exit_fill = float(raw_price) * (1 - SLIPPAGE_RATE)
        proceeds = position["qty"] * exit_fill
        exit_fee = proceeds * FEE_RATE
        pnl = proceeds - exit_fee - position["entry_cost"]
        cash += proceeds - exit_fee
        daily_realized += pnl
        trades.append({
            "pnl": pnl,
            "fees": position["entry_fee"] + exit_fee,
            "bars": bars_held,
            "reason": reason,
        })
        position = None
        if daily_realized <= -INITIAL_EQUITY * DAILY_STOP_FRACTION:
            daily_blocked = True

    for i in range(start, end):
        previous = frame.iloc[i - 1]
        bar = frame.iloc[i]
        bar_day = bar.timestamp.date()
        if active_day != bar_day:
            active_day = bar_day
            daily_realized = 0.0
            daily_blocked = False
        exited = False

        if position is not None:
            reason = None
            raw_exit = None
            if float(bar.open) <= position["stop"]:
                reason, raw_exit = "STOP_GAP", float(bar.open)
            elif float(bar.open) >= position["target"]:
                reason, raw_exit = "TARGET_GAP", float(bar.open)
            elif float(bar.low) <= position["stop"]:
                reason, raw_exit = "STOP", position["stop"]
            elif float(bar.high) >= position["target"]:
                reason, raw_exit = "TARGET", position["target"]
            elif bool(previous[exit_col]):
                reason, raw_exit = "SIGNAL", float(bar.open)

            if reason:
                close_position(raw_exit, reason, bar_day, i - position["entry_index"] + 1)
                exited = True
            else:
                mark_net = (
                    position["qty"] * float(bar.close)
                    * (1 - SLIPPAGE_RATE) * (1 - FEE_RATE)
                    - position["entry_cost"]
                )
                if daily_realized + mark_net <= -INITIAL_EQUITY * DAILY_STOP_FRACTION:
                    close_position(float(bar.close), "DAILY_STOP", bar_day,
                                   i - position["entry_index"] + 1)
                    exited = True

        if position is None and not exited and not daily_blocked and bool(previous[entry_col]):
            atr = float(previous.atr) if pd.notna(previous.atr) else float("nan")
            raw_entry = float(bar.open)
            entry = raw_entry * (1 + SLIPPAGE_RATE)
            stop_distance = ATR_STOP_MULTIPLE * atr
            if math.isfinite(stop_distance) and 0 < stop_distance < entry:
                stop = entry - stop_distance
                target = entry + REWARD_RISK * stop_distance
                risk_budget = cash * RISK_PER_TRADE
                exit_at_stop = stop * (1 - SLIPPAGE_RATE)
                risk_per_unit = entry * (1 + FEE_RATE) - exit_at_stop * (1 - FEE_RATE)
                risk_qty = risk_budget / risk_per_unit if risk_per_unit > 0 else 0.0
                notional_cap = cash * MAX_NOTIONAL_FRACTION / (1 + FEE_RATE)
                qty = min(risk_qty, notional_cap / entry) if entry > 0 else 0.0
                notional = qty * entry
                entry_fee = notional * FEE_RATE
                entry_cost = notional + entry_fee
                if qty > 0 and entry_cost <= cash:
                    cash -= entry_cost
                    position = {
                        "qty": qty, "entry": entry, "entry_fee": entry_fee,
                        "entry_cost": entry_cost, "entry_index": i,
                        "stop": stop, "target": target,
                    }
                    # Conservative same-bar barrier handling: assume stop before target.
                    if float(bar.low) <= stop:
                        close_position(min(float(bar.open), stop), "ENTRY_BAR_STOP", bar_day, 1)
                        exited = True
                    elif float(bar.high) >= target:
                        close_position(target, "ENTRY_BAR_TARGET", bar_day, 1)
                        exited = True

        equity = cash
        if position is not None:
            equity += (
                position["qty"] * float(bar.close)
                * (1 - SLIPPAGE_RATE) * (1 - FEE_RATE)
            )
        equity_curve.append(equity)

    if position is not None:
        close_position(float(frame.iloc[end - 1].close), "PERIOD_END",
                       frame.iloc[end - 1].timestamp.date(),
                       end - position["entry_index"])

    values = [INITIAL_EQUITY] + equity_curve + [cash]
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak * 100)

    pnls = [t["pnl"] for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]
    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    returns = pd.Series(values).pct_change().dropna()
    sharpe = (
        float(returns.mean() / returns.std() * math.sqrt(annual_bars))
        if len(returns) > 2 and returns.std() > 0 else 0.0
    )
    years = max(
        (frame.iloc[end - 1].timestamp - frame.iloc[start].timestamp).total_seconds()
        / 31_557_600,
        1 / 365,
    )
    return {
        "trades": len(trades),
        "wins": len(winners),
        "win_rate_pct": round(100 * len(winners) / len(trades), 2) if trades else 0.0,
        "net_pnl_usdt": round(cash - INITIAL_EQUITY, 2),
        "return_pct": round((cash / INITIAL_EQUITY - 1) * 100, 3),
        "cagr_pct": round(((cash / INITIAL_EQUITY) ** (1 / years) - 1) * 100, 2) if cash > 0 else -100.0,
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else ("inf" if gross_profit else 0.0),
        "max_drawdown_pct": round(max_drawdown, 2),
        "sharpe_approx": round(sharpe, 3),
        "fees_usdt": round(sum(t["fees"] for t in trades), 2),
        "expectancy_usdt": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        "avg_bars_held": round(sum(t["bars"] for t in trades) / len(trades), 2) if trades else 0.0,
        "ending_equity_usdt": round(cash, 2),
        "exit_reasons": {
            reason: sum(1 for t in trades if t["reason"] == reason)
            for reason in sorted({t["reason"] for t in trades})
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-code-dir", required=True)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    lab = load_research_engine(args.live_code_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    print(
        f"ASHUR live strategy screening | {LOOKBACK_DAYS} days | chronological "
        f"{TRAIN_FRACTION:.0%}/{VALIDATION_FRACTION:.0%}/{1-TRAIN_FRACTION-VALIDATION_FRACTION:.0%} | "
        f"risk {RISK_PER_TRADE:.2%} | stop {ATR_STOP_MULTIPLE} ATR | target {REWARD_RISK}R | "
        f"fee {FEE_RATE:.2%}/side | slippage {SLIPPAGE_RATE:.2%}/side",
        flush=True,
    )

    for symbol, timeframe, interval_ms, strategy_ids in DATASETS:
        print(f"FETCH {symbol} {timeframe}", flush=True)
        raw = lab.fetch_history(symbol, timeframe, interval_ms)
        timestamps = raw.timestamp.astype("int64").to_numpy()
        if len(timestamps) > 1 and (timestamps[1:] - timestamps[:-1] != interval_ms).any():
            raise RuntimeError(f"Non-contiguous history: {symbol} {timeframe}")
        frame = add_live_signals(lab.indicators(raw))
        n = len(frame)
        train_end = int(n * TRAIN_FRACTION)
        validation_end = int(n * (TRAIN_FRACTION + VALIDATION_FRACTION))
        annual_bars = {
            "15m": 96 * 365, "1h": 24 * 365, "4h": 6 * 365, "1d": 365,
        }[timeframe]

        for strategy_id in strategy_ids:
            metrics = {}
            for label, start, end in [
                ("train", 205, train_end),
                ("validation", train_end, validation_end),
                ("test", validation_end, n),
            ]:
                metrics[label] = simulate_live_rules(frame, strategy_id, start, end, annual_bars)
            row = {
                "strategy_id": strategy_id, "symbol": symbol, "timeframe": timeframe,
                "candles": n, "period_start_utc": frame.iloc[0].timestamp.isoformat(),
                "period_end_utc": frame.iloc[-1].timestamp.isoformat(), **metrics,
            }
            results.append(row)
            print(json.dumps({
                "strategy_id": strategy_id, "symbol": symbol, "timeframe": timeframe,
                "train_return_pct": metrics["train"]["return_pct"],
                "validation_return_pct": metrics["validation"]["return_pct"],
                "test_return_pct": metrics["test"]["return_pct"],
                "test_trades": metrics["test"]["trades"],
                "test_pf": metrics["test"]["profit_factor"],
                "test_mdd_pct": metrics["test"]["max_drawdown_pct"],
            }), flush=True)

    def candidate(row):
        validation, test = row["validation"], row["test"]
        return (
            validation["trades"] >= 8 and test["trades"] >= 8
            and isinstance(validation["profit_factor"], (int, float))
            and isinstance(test["profit_factor"], (int, float))
            and validation["profit_factor"] > 1 and test["profit_factor"] > 1
            and validation["return_pct"] > 0 and test["return_pct"] > 0
            and test["max_drawdown_pct"] <= 20
        )

    payload = {
        "config": {
            "lookback_days": LOOKBACK_DAYS,
            "split": {"train": TRAIN_FRACTION, "validation": VALIDATION_FRACTION,
                      "test": 1 - TRAIN_FRACTION - VALIDATION_FRACTION},
            "initial_equity_per_strategy_usdt": INITIAL_EQUITY,
            "risk_per_trade": RISK_PER_TRADE,
            "daily_loss_limit": DAILY_STOP_FRACTION,
            "max_notional_fraction": MAX_NOTIONAL_FRACTION,
            "atr_stop_multiple": ATR_STOP_MULTIPLE,
            "reward_risk": REWARD_RISK,
            "fee_each_side": FEE_RATE,
            "slippage_each_side": SLIPPAGE_RATE,
            "execution": "closed-candle signal, next-bar open entry, gap-aware stop/target, conservative stop-first same-bar handling",
            "daily_stop": "approximated at timeframe bar close; live bot polls ticker more frequently",
            "excluded": ["historical news veto", "1m intrabar replay for every historical timeframe candle"],
            "warning": "Historical screening only. Held-out test is not future validation and does not prove profitability.",
        },
        "results": results,
        "shortlist": [r["strategy_id"] for r in results if candidate(r)],
    }
    json_path = output_dir / "ashur_live_strategy_research.json"
    csv_path = output_dir / "ashur_live_strategy_research.csv"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    fields = [
        "strategy_id", "symbol", "timeframe", "candles",
        "train_return_pct", "train_trades", "train_pf",
        "validation_return_pct", "validation_trades", "validation_pf",
        "test_return_pct", "test_trades", "test_win_rate_pct", "test_pf",
        "test_max_drawdown_pct", "test_sharpe_approx", "test_fees_usdt",
        "test_expectancy_usdt", "test_ending_equity_usdt",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in results:
            writer.writerow({
                "strategy_id": row["strategy_id"], "symbol": row["symbol"],
                "timeframe": row["timeframe"], "candles": row["candles"],
                "train_return_pct": row["train"]["return_pct"],
                "train_trades": row["train"]["trades"],
                "train_pf": row["train"]["profit_factor"],
                "validation_return_pct": row["validation"]["return_pct"],
                "validation_trades": row["validation"]["trades"],
                "validation_pf": row["validation"]["profit_factor"],
                "test_return_pct": row["test"]["return_pct"],
                "test_trades": row["test"]["trades"],
                "test_win_rate_pct": row["test"]["win_rate_pct"],
                "test_pf": row["test"]["profit_factor"],
                "test_max_drawdown_pct": row["test"]["max_drawdown_pct"],
                "test_sharpe_approx": row["test"]["sharpe_approx"],
                "test_fees_usdt": row["test"]["fees_usdt"],
                "test_expectancy_usdt": row["test"]["expectancy_usdt"],
                "test_ending_equity_usdt": row["test"]["ending_equity_usdt"],
            })
    print("SHORTLIST=" + json.dumps(payload["shortlist"]), flush=True)
    print(f"Saved {json_path} and {csv_path}", flush=True)


if __name__ == "__main__":
    main()
