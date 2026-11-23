"""Rolling walk-forward evaluation for ASHUR spot strategies."""
import csv
import json
from pathlib import Path

import pandas as pd
import strategy_lab_v3 as base

ROOT = Path(__file__).resolve().parent
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
TIMEFRAMES = {"1h": 3_600_000, "4h": 14_400_000}
TRAIN_DAYS, VALIDATION_DAYS, TEST_DAYS, STEP_DAYS = 180, 60, 60, 60
MIN_VALIDATION_TRADES = 5


def _index_at_or_after(frame, timestamp):
    return int(frame["timestamp"].searchsorted(pd.Timestamp(timestamp), side="left"))


def walk_forward_market(frame, symbol, timeframe):
    x = base.signal_columns(base.indicators(frame))
    annual_bars = {"1h": 24 * 365, "4h": 6 * 365}[timeframe]
    test_start_time = pd.Timestamp(x.iloc[205]["timestamp"]) + pd.Timedelta(
        days=TRAIN_DAYS + VALIDATION_DAYS
    )
    final_time = pd.Timestamp(x.iloc[-1]["timestamp"])
    folds = []
    while test_start_time + pd.Timedelta(days=TEST_DAYS) <= final_time:
        validation_end_time = test_start_time
        validation_start_time = validation_end_time - pd.Timedelta(days=VALIDATION_DAYS)
        train_start_time = validation_start_time - pd.Timedelta(days=TRAIN_DAYS)
        train_start = max(205, _index_at_or_after(x, train_start_time))
        validation_start = _index_at_or_after(x, validation_start_time)
        validation_end = _index_at_or_after(x, validation_end_time)
        test_start = validation_end
        test_end = _index_at_or_after(x, test_start_time + pd.Timedelta(days=TEST_DAYS))
        if test_end - test_start < 10 or validation_end - validation_start < 10:
            break

        validation_results = []
        for strategy in base.STRATEGIES:
            train_metrics = base.simulate(x, strategy, train_start, validation_start, annual_bars)
            validation_metrics = base.simulate(x, strategy, validation_start, validation_end, annual_bars)
            validation_results.append({
                "strategy": strategy,
                "train": train_metrics,
                "validation": validation_metrics,
            })
        eligible = [
            r for r in validation_results
            if r["train"]["trades"] >= MIN_VALIDATION_TRADES
            and r["train"]["return_pct"] > 0
            and isinstance(r["train"]["profit_factor"], (int, float))
            and r["train"]["profit_factor"] > 1.0
            and r["validation"]["trades"] >= MIN_VALIDATION_TRADES
            and r["validation"]["return_pct"] > 0
            and isinstance(r["validation"]["profit_factor"], (int, float))
            and r["validation"]["profit_factor"] > 1.0
        ]
        eligible.sort(
            key=lambda r: (r["validation"]["return_pct"], r["validation"]["profit_factor"]),
            reverse=True,
        )
        selected = eligible[0] if eligible else None
        test_metrics = (
            base.simulate(x, selected["strategy"], test_start, test_end, annual_bars)
            if selected else None
        )
        folds.append({
            "symbol": symbol, "timeframe": timeframe,
            "train_start": str(x.iloc[train_start]["timestamp"]),
            "validation_start": str(x.iloc[validation_start]["timestamp"]),
            "validation_end": str(x.iloc[validation_end - 1]["timestamp"]),
            "test_start": str(x.iloc[test_start]["timestamp"]),
            "test_end": str(x.iloc[test_end - 1]["timestamp"]),
            "selected_strategy": selected["strategy"] if selected else None,
            "train": selected["train"] if selected else None,
            "validation": selected["validation"] if selected else None,
            "validation_return_pct": selected["validation"]["return_pct"] if selected else None,
            "validation_trades": selected["validation"]["trades"] if selected else 0,
            "test": test_metrics,
            "eligible_validation_strategies": len(eligible),
            "selection_rule": "train and validation each require min trades, positive return and PF>1; rank by validation return",
        })
        test_start_time += pd.Timedelta(days=STEP_DAYS)
    return folds


def main():
    all_folds = []
    print("ASHUR walk-forward | rolling 180d train / 60d validation / 60d OOS test")
    for symbol in SYMBOLS:
        for timeframe, interval in TIMEFRAMES.items():
            raw = base.fetch_history(symbol, timeframe, interval)
            folds = walk_forward_market(raw, symbol, timeframe)
            all_folds.extend(folds)
            for fold in folds:
                test = fold["test"] or {}
                print(json.dumps({
                    "symbol": symbol, "timeframe": timeframe,
                    "test_start": fold["test_start"], "selected": fold["selected_strategy"],
                    "train_return_pct": (fold["train"] or {}).get("return_pct"),
                    "validation_return_pct": fold["validation_return_pct"],
                    "test_return_pct": test.get("return_pct"),
                    "test_trades": test.get("trades"), "test_pf": test.get("profit_factor"),
                }))
    tested = [f for f in all_folds if f["test"] is not None]
    returns = [f["test"]["return_pct"] for f in tested]
    summary = {
        "folds_total": len(all_folds),
        "folds_with_selected_strategy": len(tested),
        "profitable_oos_folds": sum(v > 0 for v in returns),
        "oos_fold_win_rate_pct": round(100 * sum(v > 0 for v in returns) / len(returns), 2) if returns else 0.0,
        "mean_oos_return_pct": round(sum(returns) / len(returns), 3) if returns else None,
        "median_oos_return_pct": round(float(pd.Series(returns).median()), 3) if returns else None,
        "warning": "Historical rolling OOS simulation, not forward paper trading or a return forecast.",
    }
    payload = {
        "config": {
            "symbols": SYMBOLS, "timeframes": list(TIMEFRAMES),
            "train_days": TRAIN_DAYS, "validation_days": VALIDATION_DAYS,
            "test_days": TEST_DAYS, "step_days": STEP_DAYS,
            "minimum_validation_trades": MIN_VALIDATION_TRADES,
            "selection_uses_test": False,
            "selection_gate": "train and validation must each have >=5 trades, positive net return and PF>1; rank by validation return",
            "execution_model": "OHLCV proxy with prior-candle liquidity/volatility inputs",
            "fee_each_side": base.FEE_RATE,
        },
        "summary": summary, "folds": all_folds,
    }
    (ROOT / "walk_forward_results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    fields = ["symbol", "timeframe", "test_start", "test_end", "selected_strategy",
              "train_return_pct", "validation_return_pct", "validation_trades", "test_return_pct",
              "test_trades", "test_profit_factor", "test_max_drawdown_pct", "test_fees_usdt",
              "test_spread_cost_usdt", "test_base_slippage_cost_usdt", "test_market_impact_cost_usdt"]
    with (ROOT / "walk_forward_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for fold in all_folds:
            test = fold["test"] or {}
            writer.writerow({
                "symbol": fold["symbol"], "timeframe": fold["timeframe"],
                "test_start": fold["test_start"], "test_end": fold["test_end"],
                "selected_strategy": fold["selected_strategy"],
                "train_return_pct": (fold["train"] or {}).get("return_pct"),
                "validation_return_pct": fold["validation_return_pct"],
                "validation_trades": fold["validation_trades"],
                "test_return_pct": test.get("return_pct"), "test_trades": test.get("trades"),
                "test_profit_factor": test.get("profit_factor"),
                "test_max_drawdown_pct": test.get("max_drawdown_pct"),
                "test_fees_usdt": test.get("fees_usdt"),
                "test_spread_cost_usdt": test.get("spread_cost_usdt"),
                "test_base_slippage_cost_usdt": test.get("base_slippage_cost_usdt"),
                "test_market_impact_cost_usdt": test.get("market_impact_cost_usdt"),
            })
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    print("Saved walk_forward_results.json and walk_forward_results.csv")


if __name__ == "__main__":
    main()
