"""Focused historical research for the six strategies currently running in ASHUR Paper/Shadow.

Uses the existing v3 causal indicators and execution assumptions, adds the live 15m EMA
strategy, verifies every historical signal against live_shadow_worker.signals(), and
records OOS, rolling-window, cost-stress, signal-frequency, and entry-regime metrics.
This is research only: it does not connect to private exchange APIs or change the live ledger.
"""
import csv
import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

import live_shadow_worker as worker
import strategy_lab_v3 as lab


LOOKBACK_DAYS = 1095
OUTPUT_DIR = Path(__file__).resolve().parent / "research-output"
CONFIGS = [
    {
        "id": "BNB_4H_KELTNER_ADX", "symbol": "BNB/USDT", "timeframe": "4h",
        "interval_ms": 14_400_000, "signal": "keltner_breakout_adx",
    },
    {
        "id": "BNB_4H_ADX_TREND", "symbol": "BNB/USDT", "timeframe": "4h",
        "interval_ms": 14_400_000, "signal": "adx_trend_filter",
    },
    {
        "id": "BNB_1H_DONCHIAN_ADX25", "symbol": "BNB/USDT", "timeframe": "1h",
        "interval_ms": 3_600_000, "signal": "donchian_ensemble_adx25",
    },
    {
        "id": "BNB_15M_EMA_TREND", "symbol": "BNB/USDT", "timeframe": "15m",
        "interval_ms": 900_000, "signal": "live_ema20_50_adx12",
    },
    {
        "id": "SOL_4H_DONCHIAN_VOL", "symbol": "SOL/USDT", "timeframe": "4h",
        "interval_ms": 14_400_000, "signal": "donchian_volatility_regime",
    },
    {
        "id": "BNB_1D_DONCHIAN55", "symbol": "BNB/USDT", "timeframe": "1d",
        "interval_ms": 86_400_000, "signal": "donchian_55_trend",
    },
]
ANNUAL_BARS = {"15m": 96 * 365, "1h": 24 * 365, "4h": 6 * 365, "1d": 365}


def market_regime(row):
    close, ema50, ema200 = float(row.close), float(row.ema50), float(row.ema200)
    if close > ema200 and ema50 > ema200:
        return "BULL"
    if close < ema200 and ema50 < ema200:
        return "BEAR"
    return "MIXED"


def prepare_frame(config):
    lab.LOOKBACK_DAYS = LOOKBACK_DAYS
    raw = lab.fetch_history(config["symbol"], config["timeframe"], config["interval_ms"])
    if len(raw) < 500:
        raise RuntimeError(f"Insufficient candles: {config['id']} has {len(raw)}")
    gaps = raw["timestamp"].diff().dropna()
    expected = pd.Timedelta(milliseconds=config["interval_ms"])
    if not gaps.eq(expected).all():
        bad = int((gaps != expected).sum())
        raise RuntimeError(f"OHLCV continuity failure for {config['id']}: {bad} irregular gaps")

    x = lab.signal_columns(lab.indicators(raw))
    if config["id"] == "BNB_15M_EMA_TREND":
        x["live_ema20_50_adx12_entry"] = (
            (x.close > x.ema20) & (x.ema20 > x.ema50) & (x.adx > 12)
        )
        x["live_ema20_50_adx12_exit"] = (
            (x.close < x.ema50) | (x.ema20 < x.ema50)
        )
        lab.STRATEGIES["live_ema20_50_adx12"] = (
            "live_ema20_50_adx12_entry", "live_ema20_50_adx12_exit"
        )
    x["market_regime"] = x.apply(market_regime, axis=1)
    return x


def verify_signal_parity(x, config):
    entry_col, exit_col = lab.STRATEGIES[config["signal"]]
    live_frame = x.rename(columns={
        "donchian20": "dh20",
        "donchian55": "dh55",
        "donchian100": "dh100",
        "donchian10low": "dl10",
        "donchian20low": "dl20",
        "atr_pct_p80": "atr_p80",
    })
    compared = 0
    for _, row in live_frame.iterrows():
        expected = worker.signals(row, config["id"])
        actual = (bool(row[entry_col]), bool(row[exit_col]))
        if actual != expected:
            raise AssertionError(
                f"Signal formula mismatch {config['id']} at {row.timestamp}: "
                f"research={actual}, live={expected}"
            )
        compared += 1
    return compared


def simulate_detailed(x, signal_name, start, end, fee_rate=None, slippage_rate=None):
    """Live-sized, next-open OHLC simulation with conservative stop-first intrabar handling."""
    fee_rate = lab.FEE_RATE if fee_rate is None else float(fee_rate)
    slippage_rate = lab.SLIPPAGE_RATE if slippage_rate is None else float(slippage_rate)
    entry_col, exit_col = lab.STRATEGIES[signal_name]
    cash = lab.INITIAL_EQUITY
    position = None
    trades = []
    equity_curve = []
    start = max(205, int(start))

    def record_trade(pos, i, exit_fill, exit_fee, reason, bars):
        pnl = pos["qty"] * exit_fill - exit_fee - pos["entry_cost"]
        trades.append({
            "entry_at": x.iloc[pos["entry_i"]].timestamp.isoformat(),
            "exit_at": x.iloc[i].timestamp.isoformat(),
            "entry_regime": pos["entry_regime"],
            "exit_regime": market_regime(x.iloc[i]),
            "net_pnl_usdt": round(pnl, 8),
            "fees_usdt": round(pos["entry_fee"] + exit_fee, 8),
            "bars_held": int(bars),
            "reason": reason,
        })

    for i in range(start, int(end)):
        previous, bar = x.iloc[i - 1], x.iloc[i]
        exited = False

        if position is not None:
            reason, raw_exit = None, None
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
                exit_fill = raw_exit * (1 - slippage_rate)
                proceeds = position["qty"] * exit_fill
                exit_fee = proceeds * fee_rate
                cash += proceeds - exit_fee
                record_trade(position, i, exit_fill, exit_fee, reason, i - position["entry_i"] + 1)
                position = None
                exited = True

        if position is None and not exited and bool(previous[entry_col]):
            atr = float(previous.atr) if pd.notna(previous.atr) else float("nan")
            raw_entry = float(bar.open)
            entry_fill = raw_entry * (1 + slippage_rate)
            stop_distance = lab.ATR_STOP_MULTIPLE * atr
            if pd.notna(stop_distance) and stop_distance > 0 and stop_distance < entry_fill:
                stop_price = entry_fill - stop_distance
                stop_exit_fill = stop_price * (1 - slippage_rate)
                risk_per_unit = (
                    entry_fill * (1 + fee_rate) - stop_exit_fill * (1 - fee_rate)
                )
                risk_budget = cash * lab.RISK_PER_TRADE
                risk_limited_qty = risk_budget / risk_per_unit if risk_per_unit > 0 else 0.0
                notional_cap = cash * lab.MAX_NOTIONAL_FRACTION / (1 + fee_rate)
                cash_limited_qty = notional_cap / entry_fill
                qty = max(0.0, min(risk_limited_qty, cash_limited_qty))
                notional = qty * entry_fill
                entry_fee = notional * fee_rate
                entry_cost = notional + entry_fee
                if qty > 0 and entry_cost <= cash:
                    cash -= entry_cost
                    position = {
                        "qty": qty, "entry": entry_fill, "entry_fee": entry_fee,
                        "entry_cost": entry_cost, "entry_i": i,
                        "stop": entry_fill - stop_distance,
                        "target": entry_fill + lab.REWARD_RISK * stop_distance,
                        "entry_regime": market_regime(previous),
                    }
                    # If both barriers are touched in one OHLC candle, assume stop first.
                    if float(bar.low) <= position["stop"] or float(bar.high) >= position["target"]:
                        if float(bar.low) <= position["stop"]:
                            raw_exit, reason = position["stop"], "ENTRY_BAR_STOP"
                        else:
                            raw_exit, reason = position["target"], "ENTRY_BAR_TARGET"
                        exit_fill = raw_exit * (1 - slippage_rate)
                        proceeds = qty * exit_fill
                        exit_fee = proceeds * fee_rate
                        cash += proceeds - exit_fee
                        record_trade(position, i, exit_fill, exit_fee, reason, 1)
                        position = None
                        exited = True

        equity = cash
        if position is not None:
            liquidation_value = (
                position["qty"] * float(bar.close) *
                (1 - slippage_rate) * (1 - fee_rate)
            )
            equity += liquidation_value
        equity_curve.append(equity)

    if position is not None:
        i = int(end) - 1
        raw_exit = float(x.iloc[i].close)
        exit_fill = raw_exit * (1 - slippage_rate)
        proceeds = position["qty"] * exit_fill
        exit_fee = proceeds * fee_rate
        cash += proceeds - exit_fee
        record_trade(position, i, exit_fill, exit_fee, "PERIOD_END", int(end) - position["entry_i"])
        position = None

    pnl_values = [t["net_pnl_usdt"] for t in trades]
    gross_profit = sum(v for v in pnl_values if v > 0)
    gross_loss = abs(sum(v for v in pnl_values if v < 0))
    values = [lab.INITIAL_EQUITY] + equity_curve + [cash]
    peak, max_drawdown = values[0], 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak * 100)
    returns = pd.Series(values).pct_change().dropna()
    sharpe = (
        float(returns.mean() / returns.std() * (ANNUAL_BARS[x.attrs.get("timeframe", "4h")] ** 0.5))
        if len(returns) > 2 and returns.std() > 0 else 0.0
    )
    years = max(
        (x.iloc[int(end) - 1].timestamp - x.iloc[start].timestamp).total_seconds() / 31557600,
        1 / 365,
    )
    ending = cash
    profit_factor = (
        round(gross_profit / gross_loss, 3) if gross_loss > 0
        else ("inf" if gross_profit > 0 else None)
    )
    return {
        "trades": len(trades),
        "wins": sum(v > 0 for v in pnl_values),
        "win_rate_pct": round(100 * sum(v > 0 for v in pnl_values) / len(trades), 2) if trades else None,
        "net_pnl_usdt": round(cash - lab.INITIAL_EQUITY, 2),
        "return_pct": round((cash / lab.INITIAL_EQUITY - 1) * 100, 3),
        "cagr_pct": round(((cash / lab.INITIAL_EQUITY) ** (1 / years) - 1) * 100, 2) if cash > 0 else -100,
        "profit_factor": profit_factor,
        "max_drawdown_pct": round(max_drawdown, 2),
        "sharpe_approx": round(sharpe, 3),
        "fees_usdt": round(sum(t["fees_usdt"] for t in trades), 2),
        "expectancy_usdt": round(sum(pnl_values) / len(trades), 2) if trades else None,
        "avg_bars_held": round(sum(t["bars_held"] for t in trades) / len(trades), 2) if trades else None,
        "ending_equity_usdt": round(ending, 2),
        "trades_detail": trades,
    }


def signal_frequency(x, entry_col, days):
    cutoff = x.timestamp.iloc[-1] - pd.Timedelta(days=days)
    window = x[x.timestamp >= cutoff]
    return {
        "days": days,
        "signals": int(window[entry_col].fillna(False).sum()),
        "by_regime": {
            regime: int(window.loc[window.market_regime == regime, entry_col].fillna(False).sum())
            for regime in ("BULL", "BEAR", "MIXED")
        },
    }


def summarize_trade_regimes(trades):
    result = {}
    for regime in ("BULL", "BEAR", "MIXED"):
        group = [t for t in trades if t["entry_regime"] == regime]
        wins = [t["net_pnl_usdt"] for t in group if t["net_pnl_usdt"] > 0]
        losses = [t["net_pnl_usdt"] for t in group if t["net_pnl_usdt"] < 0]
        gross_loss = abs(sum(losses))
        result[regime] = {
            "trades": len(group),
            "wins": len(wins),
            "win_rate_pct": round(len(wins) / len(group) * 100, 2) if group else None,
            "net_pnl_usdt": round(sum(t["net_pnl_usdt"] for t in group), 2),
            "profit_factor": round(sum(wins) / gross_loss, 3) if gross_loss else ("inf" if wins else None),
            "fees_usdt": round(sum(t["fees_usdt"] for t in group), 2),
        }
    return result


def rolling_60d_tests(x, signal_name, timeframe):
    end_time = x.timestamp.iloc[-1]
    windows = []
    for offset in range(5, -1, -1):
        window_end = end_time - pd.Timedelta(days=60 * offset)
        window_start = window_end - pd.Timedelta(days=60)
        start = int(x.timestamp.searchsorted(window_start, side="left"))
        end = int(x.timestamp.searchsorted(window_end, side="right"))
        if end - start < 205:
            continue
        metrics = simulate_detailed(x, signal_name, start, end)
        windows.append({
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "trades": metrics["trades"],
            "return_pct": metrics["return_pct"],
            "profit_factor": metrics["profit_factor"],
            "max_drawdown_pct": metrics["max_drawdown_pct"],
        })
    return {
        "windows": windows,
        "positive_windows": sum(w["return_pct"] > 0 for w in windows),
        "window_count": len(windows),
        "median_return_pct": round(float(pd.Series([w["return_pct"] for w in windows]).median()), 3) if windows else None,
    }


def research_one(config):
    x = prepare_frame(config)
    x.attrs["timeframe"] = config["timeframe"]
    compared = verify_signal_parity(x, config)
    entry_col, _ = lab.STRATEGIES[config["signal"]]
    n = len(x)
    train_end = int(n * 0.60)
    validation_end = int(n * 0.80)
    splits = {
        "train": simulate_detailed(x, config["signal"], 205, train_end),
        "validation": simulate_detailed(x, config["signal"], train_end, validation_end),
        "test": simulate_detailed(x, config["signal"], validation_end, n),
    }
    # Re-run the same held-out test at 2x and 3x execution costs.
    stress = {}
    for multiplier in (1, 2, 3):
        metrics = simulate_detailed(
            x, config["signal"], validation_end, n,
            fee_rate=lab.FEE_RATE * multiplier,
            slippage_rate=lab.SLIPPAGE_RATE * multiplier,
        )
        stress[f"{multiplier}x"] = {
            "trades": metrics["trades"], "net_pnl_usdt": metrics["net_pnl_usdt"],
            "return_pct": metrics["return_pct"], "profit_factor": metrics["profit_factor"],
            "max_drawdown_pct": metrics["max_drawdown_pct"], "fees_usdt": metrics["fees_usdt"],
        }
    test_trades = splits["test"]["trades_detail"]
    regimes = summarize_trade_regimes(test_trades)
    frequencies = {f"last_{d}d": signal_frequency(x, entry_col, d) for d in (30, 90, 180)}
    rolling = rolling_60d_tests(x, config["signal"], config["timeframe"])
    return {
        "strategy_id": config["id"],
        "symbol": config["symbol"],
        "timeframe": config["timeframe"],
        "candles": n,
        "period_start": x.timestamp.iloc[0].isoformat(),
        "period_end": x.timestamp.iloc[-1].isoformat(),
        "signal_parity_rows": compared,
        "signal_frequency": frequencies,
        "splits": {
            name: {k: v for k, v in metrics.items() if k != "trades_detail"}
            for name, metrics in splits.items()
        },
        "test_trade_regimes": regimes,
        "cost_stress_test": stress,
        "rolling_60d_oos": rolling,
        "test_trades_detail": test_trades,
        "research_limits": [
            "Historical candles use Binance public data mirror; live worker prefers Bybit and falls back to Binance.",
            "Signals use closed candles and execute at the next candle open with fees and slippage.",
            "Stop/target replay uses strategy-timeframe OHLC and assumes stop first when both barriers are touched.",
            "News veto, intrabar minute-feed outages, and live protection gates are not modeled in this historical simulation.",
            "Rolling 60-day windows are independent flat-start tests; they are not a continuously compounded portfolio.",
        ],
    }


def main():
    results = []
    print("ASHUR exact-live-six research | 1095d | chronological 60/20/20 | fee=0.10%/side | slippage=0.05%/side")
    for config in CONFIGS:
        result = research_one(config)
        results.append(result)
        test = result["splits"]["test"]
        print(json.dumps({
            "strategy_id": result["strategy_id"],
            "candles": result["candles"],
            "signal_parity_rows": result["signal_parity_rows"],
            "test_trades": test["trades"],
            "test_return_pct": test["return_pct"],
            "test_pf": test["profit_factor"],
            "test_mdd_pct": test["max_drawdown_pct"],
            "last_30d_signals": result["signal_frequency"]["last_30d"]["signals"],
            "last_90d_signals": result["signal_frequency"]["last_90d"]["signals"],
            "last_180d_signals": result["signal_frequency"]["last_180d"]["signals"],
            "positive_60d_windows": result["rolling_60d_oos"]["positive_windows"],
        }, ensure_ascii=False))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": {
            "lookback_days": LOOKBACK_DAYS,
            "train_validation_test": [0.60, 0.20, 0.20],
            "starting_equity_per_strategy_usdt": lab.INITIAL_EQUITY,
            "risk_per_trade": lab.RISK_PER_TRADE,
            "stop_atr_multiple": lab.ATR_STOP_MULTIPLE,
            "target_r_multiple": lab.REWARD_RISK,
            "max_notional_fraction": lab.MAX_NOTIONAL_FRACTION,
            "fee_each_side": lab.FEE_RATE,
            "slippage_each_side": lab.SLIPPAGE_RATE,
            "signal_execution": "closed candle signal; next candle open entry",
            "strategies": [c["id"] for c in CONFIGS],
        },
        "results": results,
    }
    json_path = OUTPUT_DIR / "live_six_research.json"
    csv_path = OUTPUT_DIR / "live_six_research.csv"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    fields = [
        "strategy_id", "symbol", "timeframe", "candles", "signal_parity_rows",
        "train_return_pct", "validation_return_pct", "test_return_pct",
        "test_trades", "test_win_rate_pct", "test_profit_factor", "test_max_drawdown_pct",
        "test_fees_usdt", "test_sharpe_approx", "signals_30d", "signals_90d", "signals_180d",
        "stress_2x_return_pct", "stress_3x_return_pct", "positive_60d_windows", "rolling_window_count",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            test = result["splits"]["test"]
            writer.writerow({
                "strategy_id": result["strategy_id"], "symbol": result["symbol"],
                "timeframe": result["timeframe"], "candles": result["candles"],
                "signal_parity_rows": result["signal_parity_rows"],
                "train_return_pct": result["splits"]["train"]["return_pct"],
                "validation_return_pct": result["splits"]["validation"]["return_pct"],
                "test_return_pct": test["return_pct"], "test_trades": test["trades"],
                "test_win_rate_pct": test["win_rate_pct"], "test_profit_factor": test["profit_factor"],
                "test_max_drawdown_pct": test["max_drawdown_pct"], "test_fees_usdt": test["fees_usdt"],
                "test_sharpe_approx": test["sharpe_approx"],
                "signals_30d": result["signal_frequency"]["last_30d"]["signals"],
                "signals_90d": result["signal_frequency"]["last_90d"]["signals"],
                "signals_180d": result["signal_frequency"]["last_180d"]["signals"],
                "stress_2x_return_pct": result["cost_stress_test"]["2x"]["return_pct"],
                "stress_3x_return_pct": result["cost_stress_test"]["3x"]["return_pct"],
                "positive_60d_windows": result["rolling_60d_oos"]["positive_windows"],
                "rolling_window_count": result["rolling_60d_oos"]["window_count"],
            })
    print(f"RESEARCH_COMPLETE strategies={len(results)} json={json_path} csv={csv_path}")


if __name__ == "__main__":
    main()
