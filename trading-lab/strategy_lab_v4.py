"""ASHUR strategy research v4: validation-led Keltner/ADX parameter robustness.
Uses v3 execution engine and data loader; long-only spot, no leverage, no live orders.
"""
import csv, json
from pathlib import Path
import strategy_lab_v3 as base

ROOT = Path(__file__).resolve().parent
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
TIMEFRAMES = {"1h": 3_600_000, "4h": 14_400_000}
ADX_LEVELS = [12, 15, 18, 21, 24, 27]
KELTNER_MULTIPLIERS = [1.5, 1.75, 2.0, 2.25, 2.5]
TREND_FILTERS = [(50, 200), (50, 100)]
MIN_VALIDATION_TRADES = 12
TOP_N_PER_MARKET = 5
base.STRATEGIES["keltner_v4"] = ("v4_entry", "v4_exit")

def metric_row(symbol, tf, params, train, validation, test=None):
    row = {"symbol": symbol, "timeframe": tf, **params,
           "train": train, "validation": validation}
    if test is not None:
        row["test"] = test
    return row



def cost_stress_metrics(x, strategy_name, start, end, annual_bars):
    """Re-test a fixed candidate under harsher execution assumptions; never re-rank on test."""
    names = ("SPREAD_BPS", "BASE_SLIPPAGE_BPS", "VOLATILITY_IMPACT", "MAX_IMPACT_BPS")
    original = {name: getattr(base, name) for name in names}
    results = {}
    try:
        for label, multiplier in (("stress_2x", 2.0), ("stress_3x", 3.0)):
            base.SPREAD_BPS = original["SPREAD_BPS"] * multiplier
            base.BASE_SLIPPAGE_BPS = original["BASE_SLIPPAGE_BPS"] * multiplier
            base.VOLATILITY_IMPACT = original["VOLATILITY_IMPACT"] * multiplier
            base.MAX_IMPACT_BPS = original["MAX_IMPACT_BPS"] * multiplier
            results[label] = base.simulate(x, strategy_name, start, end, annual_bars)
    finally:
        for name, value in original.items():
            setattr(base, name, value)
    return results


def main():
    all_rows = []
    selected_rows = []
    print("ASHUR research v4.1 | Keltner x ADX robustness | validation quality gate")
    for symbol in SYMBOLS:
        for tf, interval in TIMEFRAMES.items():
            raw = base.fetch_history(symbol, tf, interval)
            x = base.signal_columns(base.indicators(raw))
            n = len(x)
            train_end = int(n * base.TRAIN_FRACTION)
            val_end = int(n * (base.TRAIN_FRACTION + base.VALIDATION_FRACTION))
            annual_bars = {"1h": 24*365, "4h": 6*365}[tf]
            candidates = []
            for fast, slow in TREND_FILTERS:
                for adx_level in ADX_LEVELS:
                    for mult in KELTNER_MULTIPLIERS:
                        entry_col, exit_col = "v4_entry", "v4_exit"
                        x[entry_col] = ((x.close > x.ema20 + mult*x.atr) &
                                        (x[f"ema{fast}"] > x[f"ema{slow}"]) &
                                        (x.adx > adx_level))
                        x[exit_col] = ((x.close < x.ema20) |
                                       (x[f"ema{fast}"] < x[f"ema{slow}"]))
                        params = {"strategy": "keltner_adx_grid",
                                  "trend_fast": fast, "trend_slow": slow,
                                  "adx_min": adx_level, "atr_channel_mult": mult}
                        train = base.simulate(x, "keltner_v4", 205, train_end, annual_bars)
                        validation = base.simulate(x, "keltner_v4", train_end, val_end, annual_bars)
                        candidates.append(metric_row(symbol, tf, params, train, validation))
            # Select ONLY on validation. Test data is not used to rank or tune candidates.
            eligible = [
                r for r in candidates
                if r["validation"]["trades"] >= MIN_VALIDATION_TRADES
                and r["validation"]["return_pct"] > 0
                and isinstance(r["validation"]["profit_factor"], (int, float))
                and r["validation"]["profit_factor"] > 1.0
            ]
            eligible.sort(key=lambda r: (
                r["validation"]["return_pct"],
                r["validation"]["profit_factor"] if isinstance(r["validation"]["profit_factor"], (int,float)) else -1
            ), reverse=True)
            chosen = eligible[:TOP_N_PER_MARKET]
            for row in chosen:
                p = row
                fast, slow = p["trend_fast"], p["trend_slow"]
                x["v4_entry"] = ((x.close > x.ema20 + p["atr_channel_mult"]*x.atr) &
                                 (x[f"ema{fast}"] > x[f"ema{slow}"]) &
                                 (x.adx > p["adx_min"]))
                x["v4_exit"] = ((x.close < x.ema20) |
                                (x[f"ema{fast}"] < x[f"ema{slow}"]))
                row["test"] = base.simulate(x, "keltner_v4", val_end, n, annual_bars)
                row["cost_stress"] = cost_stress_metrics(x, "keltner_v4", val_end, n, annual_bars)
                row["selection"] = "top_validation_only"
                selected_rows.append(row)
            # Fixed baselines are controls, not tuned candidates.
            for name, (entry, exit_) in {
                "keltner_v3_baseline": ("kel_entry", "kel_exit"),
                "adx_trend_filter_baseline": ("adx_entry", "adx_exit")
            }.items():
                base.STRATEGIES["v4_control"] = (entry, exit_)
                tr = base.simulate(x, "v4_control", 205, train_end, annual_bars)
                va = base.simulate(x, "v4_control", train_end, val_end, annual_bars)
                te = base.simulate(x, "v4_control", val_end, n, annual_bars)
                stress = cost_stress_metrics(x, "v4_control", val_end, n, annual_bars)
                selected_rows.append({"symbol":symbol,"timeframe":tf,"strategy":name,
                                      "train":tr,"validation":va,"test":te,"cost_stress":stress,
                                      "selection":"fixed_baseline_control"})
            bh = base.buy_hold(x, val_end, n)
            selected_rows.append({"symbol":symbol,"timeframe":tf,
                                  "strategy":"buy_and_hold_benchmark",
                                  "train":{},"validation":{},"test":bh,
                                  "selection":"benchmark"})
            all_rows.extend(candidates)
            print(json.dumps({"market":symbol+" "+tf,
                              "grid_candidates":len(candidates),
                              "eligible_validation":len(eligible),
                              "selected_for_test":len(chosen),
                              "best_validation_return":eligible[0]["validation"]["return_pct"] if eligible else None}))
    selected_rows.sort(key=lambda r: (
        r.get("test",{}).get("return_pct",-999),
        r.get("test",{}).get("profit_factor") if isinstance(r.get("test",{}).get("profit_factor"),(int,float)) else -1
    ), reverse=True)
    payload = {
      "config": {
        "lookback_days":base.LOOKBACK_DAYS,
        "symbols":SYMBOLS,"timeframes":list(TIMEFRAMES),
        "adx_levels":ADX_LEVELS,"keltner_atr_multipliers":KELTNER_MULTIPLIERS,
        "trend_filter_pairs":TREND_FILTERS,
        "selection":"Top 5 among validation-qualified candidates only; test is evaluated only after selection.",
        "validation_quality_gate":{"minimum_trades":MIN_VALIDATION_TRADES,"net_return_pct_gt":0,"profit_factor_gt":1.0},
        "split":"Chronological 60% train / 20% validation / 20% held-out test",
        "fees_each_side":base.FEE_RATE,
        "execution_cost_model":{
          "spread_bps_full":base.SPREAD_BPS,
          "base_slippage_bps_each_side":base.BASE_SLIPPAGE_BPS,
          "volatility_impact_coefficient":base.VOLATILITY_IMPACT,
          "max_impact_bps_each_side":base.MAX_IMPACT_BPS,
          "max_order_participation_of_previous_candle_dollar_volume":base.MAX_PARTICIPATION,
          "liquidity_reference":"previous completed candle only",
          "limitation":"OHLCV proxy, not historical bid/ask quotes or order-book replay"
        },
        "risk_per_trade":base.RISK_PER_TRADE,"leverage":0,
        "execution":"closed-candle signal, next-open entry, gap-aware stops/targets; long-only spot",
        "cost_stress_scenarios":{
          "stress_2x":"2x spread, base slippage, volatility impact and impact cap",
          "stress_3x":"3x spread, base slippage, volatility impact and impact cap",
          "purpose":"Sensitivity analysis only; held-out test results are not used to re-rank candidates."
        },
        "warning":"Historical simulation, not forward paper results or a promise of future returns."
      },
      "validation_grid":all_rows,
      "selected_and_controls":selected_rows
    }
    (ROOT/"strategy_research_v4.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    fields=["symbol","timeframe","strategy","trend_fast","trend_slow","adx_min","atr_channel_mult",
            "selection","train_return_pct","validation_return_pct","test_return_pct",
            "test_trades","test_profit_factor","test_max_drawdown_pct","test_fees_usdt",
            "test_spread_cost_usdt","test_base_slippage_cost_usdt","test_market_impact_cost_usdt",
            "test_partial_fill_count","test_average_fill_ratio_pct","test_unfilled_notional_usdt",
            "stress_2x_return_pct","stress_2x_profit_factor",
            "stress_3x_return_pct","stress_3x_profit_factor"]
    with (ROOT/"strategy_research_v4.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in selected_rows:
            t=r.get("test",{}); v=r.get("validation",{}); tr=r.get("train",{})
            w.writerow({"symbol":r["symbol"],"timeframe":r["timeframe"],
                "strategy":r.get("strategy","keltner_adx_grid"),
                "trend_fast":r.get("trend_fast"),"trend_slow":r.get("trend_slow"),
                "adx_min":r.get("adx_min"),"atr_channel_mult":r.get("atr_channel_mult"),
                "selection":r.get("selection"),
                "train_return_pct":tr.get("return_pct"),
                "validation_return_pct":v.get("return_pct"),
                "test_return_pct":t.get("return_pct"),"test_trades":t.get("trades"),
                "test_profit_factor":t.get("profit_factor"),
                "test_max_drawdown_pct":t.get("max_drawdown_pct"),
                "test_fees_usdt":t.get("fees_usdt"),
                "test_spread_cost_usdt":t.get("spread_cost_usdt"),
                "test_base_slippage_cost_usdt":t.get("base_slippage_cost_usdt"),
                "test_market_impact_cost_usdt":t.get("market_impact_cost_usdt"),
                "test_partial_fill_count":t.get("partial_fill_count"),
                "test_average_fill_ratio_pct":t.get("average_fill_ratio_pct"),
                "test_unfilled_notional_usdt":t.get("unfilled_notional_usdt"),
                "stress_2x_return_pct":r.get("cost_stress",{}).get("stress_2x",{}).get("return_pct"),
                "stress_2x_profit_factor":r.get("cost_stress",{}).get("stress_2x",{}).get("profit_factor"),
                "stress_3x_return_pct":r.get("cost_stress",{}).get("stress_3x",{}).get("return_pct"),
                "stress_3x_profit_factor":r.get("cost_stress",{}).get("stress_3x",{}).get("profit_factor")})
    print("Saved strategy_research_v4.json and strategy_research_v4.csv")
    print("=== HELD-OUT TEST: validation-selected candidates + fixed controls ===")
    print(json.dumps([{"symbol":r["symbol"],"timeframe":r["timeframe"],
        "strategy":r.get("strategy","keltner_adx_grid"),
        "params":{k:r[k] for k in ("trend_fast","trend_slow","adx_min","atr_channel_mult") if k in r},
        "validation_return":r.get("validation",{}).get("return_pct"),
        "test_return":r.get("test",{}).get("return_pct"),
        "test_trades":r.get("test",{}).get("trades"),
        "test_pf":r.get("test",{}).get("profit_factor"),
        "stress_2x_return":r.get("cost_stress",{}).get("stress_2x",{}).get("return_pct"),
        "stress_3x_return":r.get("cost_stress",{}).get("stress_3x",{}).get("return_pct"),
        "test_dd":r.get("test",{}).get("max_drawdown_pct")}
        for r in selected_rows],ensure_ascii=False))

if __name__ == "__main__":
    main()
