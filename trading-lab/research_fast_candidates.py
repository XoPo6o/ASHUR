"""Research-only 15m/1h candidate screen for BNB/USDT.

Candidates are not wired into the live worker. Signals are evaluated on closed candles,
entries execute on the next candle open, and the simulation reuses ASHUR's live risk,
stop, target, fee, and slippage assumptions.
"""
import csv
import json
from pathlib import Path

import pandas as pd

import strategy_lab_v3 as lab
import research_live_six as common


LOOKBACK_DAYS = 1095
OUTPUT_DIR = Path(__file__).resolve().parent / "research-output"
TIMEFRAMES = {"15m": 900_000, "1h": 3_600_000}
CANDIDATES = {
    "EMA20_RECLAIM_TREND": "ema20_reclaim_trend",
    "EMA_PULLBACK_RSI40": "ema_pullback_rsi40",
    "TRIPLE_HORIZON_MOMENTUM": "triple_momentum_all",
    "DONCHIAN20_ADX_VOLUME": "donchian20_adx_volume",
    "KELTNER_BREAKOUT_ADX": "keltner_breakout_adx",
    "SUPERTREND_10_3": "supertrend_10_3",
}


def prepare_timeframe(timeframe, interval_ms):
    lab.LOOKBACK_DAYS = LOOKBACK_DAYS
    raw = lab.fetch_history("BNB/USDT", timeframe, interval_ms)
    gaps = raw["timestamp"].diff().dropna()
    expected = pd.Timedelta(milliseconds=interval_ms)
    if not gaps.eq(expected).all():
        raise RuntimeError(
            f"OHLCV continuity failure for BNB/USDT {timeframe}: "
            f"{int((gaps != expected).sum())} irregular gaps"
        )
    x = lab.signal_columns(lab.indicators(raw))
    previous = x.shift(1)
    x["volume_sma20"] = x.volume.rolling(20).mean()

    x["ema20_reclaim_trend_entry"] = (
        (x.ema50 > x.ema200) & (x.ema20 > x.ema50) &
        (previous.close <= previous.ema20) & (x.close > x.ema20) & (x.adx > 15)
    )
    x["ema20_reclaim_trend_exit"] = (x.close < x.ema50) | (x.ema20 < x.ema50)

    x["ema_pullback_rsi40_entry"] = (
        (x.ema50 > x.ema200) & (previous.rsi < 40) &
        (x.rsi >= 40) & (x.close > x.ema50)
    )
    x["ema_pullback_rsi40_exit"] = (x.rsi < 40) | (x.close < x.ema100)

    x["triple_momentum_all_entry"] = (
        (x.ret20 > 0) & (x.ret60 > 0) & (x.ret120 > 0) &
        (x.close > x.ema200) & (x.adx > 15)
    )
    x["triple_momentum_all_exit"] = (x.ret20 < 0) | (x.close < x.ema100)

    x["donchian20_adx_volume_entry"] = (
        (x.close > x.donchian20) & (x.close > x.ema200) &
        (x.adx > 20) & (x.volume > 1.2 * x.volume_sma20)
    )
    x["donchian20_adx_volume_exit"] = (
        (x.close < x.donchian10low) | (x.close < x.ema100)
    )

    lab.STRATEGIES["ema_pullback_rsi40"] = (
        "ema_pullback_rsi40_entry", "ema_pullback_rsi40_exit"
    )
    lab.STRATEGIES["triple_momentum_all"] = (
        "triple_momentum_all_entry", "triple_momentum_all_exit"
    )
    lab.STRATEGIES["ema20_reclaim_trend"] = (
        "ema20_reclaim_trend_entry", "ema20_reclaim_trend_exit"
    )
    lab.STRATEGIES["donchian20_adx_volume"] = (
        "donchian20_adx_volume_entry", "donchian20_adx_volume_exit"
    )
    x["market_regime"] = x.apply(common.market_regime, axis=1)
    x.attrs["timeframe"] = timeframe
    return x


def research_candidate(x, timeframe, candidate_name, signal_name):
    entry_col, _ = lab.STRATEGIES[signal_name]
    n = len(x)
    train_end = int(n * 0.60)
    validation_end = int(n * 0.80)

    splits = {
        "train": common.simulate_detailed(x, signal_name, 205, train_end),
        "validation": common.simulate_detailed(x, signal_name, train_end, validation_end),
        "test": common.simulate_detailed(x, signal_name, validation_end, n),
    }
    stress = {}
    for multiplier in (1, 2, 3):
        m = common.simulate_detailed(
            x, signal_name, validation_end, n,
            fee_rate=lab.FEE_RATE * multiplier,
            slippage_rate=lab.SLIPPAGE_RATE * multiplier,
        )
        stress[f"{multiplier}x"] = {
            "trades": m["trades"], "return_pct": m["return_pct"],
            "profit_factor": m["profit_factor"],
            "max_drawdown_pct": m["max_drawdown_pct"], "fees_usdt": m["fees_usdt"],
        }

    test = splits["test"]
    return {
        "candidate": candidate_name,
        "symbol": "BNB/USDT",
        "timeframe": timeframe,
        "candles": n,
        "period_start": x.timestamp.iloc[0].isoformat(),
        "period_end": x.timestamp.iloc[-1].isoformat(),
        "signal_frequency": {
            f"last_{days}d": common.signal_frequency(x, entry_col, days)
            for days in (30, 90, 180)
        },
        "splits": {
            name: {k: v for k, v in metrics.items() if k != "trades_detail"}
            for name, metrics in splits.items()
        },
        "test_trade_regimes": common.summarize_trade_regimes(test["trades_detail"]),
        "cost_stress_test": stress,
        "rolling_60d_oos": common.rolling_60d_tests(x, signal_name, timeframe),
        "test_trades_detail": test["trades_detail"],
        "research_limits": [
            "Historical candles use Binance public data mirror.",
            "Signals use closed candles; entries execute at the next candle open.",
            "Fees and slippage are included; 2x and 3x cost stress tests are reported.",
            "Stop/target replay uses timeframe OHLC and assumes stop first if both barriers are touched.",
            "News veto and live intrabar protection gates are not modeled.",
            "Rolling 60-day windows are independent flat-start tests, not a compounded portfolio.",
            "These candidates are research-only and are not enabled in the live worker.",
        ],
    }


def main():
    results = []
    print("ASHUR 15m/1h candidate screen | 1095d | chronological 60/20/20")
    for timeframe, interval_ms in TIMEFRAMES.items():
        x = prepare_timeframe(timeframe, interval_ms)
        for candidate_name, signal_name in CANDIDATES.items():
            result = research_candidate(x, timeframe, candidate_name, signal_name)
            results.append(result)
            test = result["splits"]["test"]
            print(json.dumps({
                "candidate": candidate_name,
                "timeframe": timeframe,
                "trades": test["trades"],
                "return_pct": test["return_pct"],
                "profit_factor": test["profit_factor"],
                "max_drawdown_pct": test["max_drawdown_pct"],
                "signals_30d": result["signal_frequency"]["last_30d"]["signals"],
                "signals_90d": result["signal_frequency"]["last_90d"]["signals"],
                "signals_180d": result["signal_frequency"]["last_180d"]["signals"],
                "positive_60d_windows": result["rolling_60d_oos"]["positive_windows"],
            }, ensure_ascii=False))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "config": {
            "lookback_days": LOOKBACK_DAYS,
            "train_validation_test": [0.60, 0.20, 0.20],
            "starting_equity_per_candidate_usdt": lab.INITIAL_EQUITY,
            "risk_per_trade": lab.RISK_PER_TRADE,
            "stop_atr_multiple": lab.ATR_STOP_MULTIPLE,
            "target_r_multiple": lab.REWARD_RISK,
            "max_notional_fraction": lab.MAX_NOTIONAL_FRACTION,
            "fee_each_side": lab.FEE_RATE,
            "slippage_each_side": lab.SLIPPAGE_RATE,
            "timeframes": list(TIMEFRAMES),
            "candidates": list(CANDIDATES),
            "enabled_in_live_worker": False,
        },
        "results": results,
    }
    json_path = OUTPUT_DIR / "fast_candidate_research.json"
    csv_path = OUTPUT_DIR / "fast_candidate_research.csv"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    fields = [
        "candidate", "timeframe", "candles",
        "train_return_pct", "validation_return_pct", "test_return_pct",
        "test_trades", "test_win_rate_pct", "test_profit_factor",
        "test_max_drawdown_pct", "test_fees_usdt",
        "signals_30d", "signals_90d", "signals_180d",
        "stress_2x_return_pct", "stress_3x_return_pct",
        "positive_60d_windows", "rolling_window_count",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            test = result["splits"]["test"]
            writer.writerow({
                "candidate": result["candidate"], "timeframe": result["timeframe"],
                "candles": result["candles"],
                "train_return_pct": result["splits"]["train"]["return_pct"],
                "validation_return_pct": result["splits"]["validation"]["return_pct"],
                "test_return_pct": test["return_pct"], "test_trades": test["trades"],
                "test_win_rate_pct": test["win_rate_pct"],
                "test_profit_factor": test["profit_factor"],
                "test_max_drawdown_pct": test["max_drawdown_pct"],
                "test_fees_usdt": test["fees_usdt"],
                "signals_30d": result["signal_frequency"]["last_30d"]["signals"],
                "signals_90d": result["signal_frequency"]["last_90d"]["signals"],
                "signals_180d": result["signal_frequency"]["last_180d"]["signals"],
                "stress_2x_return_pct": result["cost_stress_test"]["2x"]["return_pct"],
                "stress_3x_return_pct": result["cost_stress_test"]["3x"]["return_pct"],
                "positive_60d_windows": result["rolling_60d_oos"]["positive_windows"],
                "rolling_window_count": result["rolling_60d_oos"]["window_count"],
            })
    print(f"FAST_CANDIDATE_RESEARCH_COMPLETE candidates={len(results)} json={json_path} csv={csv_path}")


if __name__ == "__main__":
    main()
