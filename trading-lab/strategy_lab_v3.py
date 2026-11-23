import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from execution_model import (
    DEFAULT_BASE_SLIPPAGE_BPS,
    DEFAULT_MAX_IMPACT_BPS,
    DEFAULT_SPREAD_BPS,
    DEFAULT_VOLATILITY_IMPACT,
    fill_price,
)

ROOT = Path(__file__).resolve().parent
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
TIMEFRAMES = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
LOOKBACK_DAYS = 1095
INITIAL_EQUITY = 10_000.0
RISK_PER_TRADE = 0.005
MAX_NOTIONAL_FRACTION = 0.95
FEE_RATE = 0.001
SPREAD_BPS = DEFAULT_SPREAD_BPS
BASE_SLIPPAGE_BPS = DEFAULT_BASE_SLIPPAGE_BPS
VOLATILITY_IMPACT = DEFAULT_VOLATILITY_IMPACT
MAX_IMPACT_BPS = DEFAULT_MAX_IMPACT_BPS
MAX_PARTICIPATION = 0.02
ATR_STOP_MULTIPLE = 3.0
REWARD_RISK = 4.0
TRAIN_FRACTION = 0.60
VALIDATION_FRACTION = 0.20

def execution_fill(price, side, reference_bar, order_notional):
    """Use only the last completed candle to estimate spread and market impact."""
    atr_pct = float(reference_bar.atr_pct) if pd.notna(reference_bar.atr_pct) else 0.0
    dollar_volume = float(reference_bar.close) * float(reference_bar.volume)
    return fill_price(
        price, side, atr_pct, dollar_volume, order_notional,
        spread_bps=SPREAD_BPS,
        base_slippage_bps=BASE_SLIPPAGE_BPS,
        volatility_impact=VOLATILITY_IMPACT,
        max_impact_bps=MAX_IMPACT_BPS,
    )


def fetch_history(symbol, timeframe, interval_ms):
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int((datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000)
    cursor, rows = start_ms, []
    while cursor < end_ms:
        query = urllib.parse.urlencode({"symbol": symbol.replace("/", ""), "interval": timeframe,
                                        "startTime": cursor, "endTime": end_ms, "limit": 1000})
        url = "https://data-api.binance.vision/api/v3/klines?" + query
        req = urllib.request.Request(url, headers={"User-Agent": "ASHUR-Research/2.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            batch = json.loads(response.read().decode("utf-8"))
        if not isinstance(batch, list) or not batch:
            break
        rows.extend([[r[0], r[1], r[2], r[3], r[4], r[5]] for r in batch])
        nxt = int(batch[-1][0]) + interval_ms
        if nxt <= cursor:
            raise RuntimeError(f"Pagination stalled: {symbol} {timeframe}")
        cursor = nxt
        time.sleep(0.06)
    x = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    for c in ["open", "high", "low", "close", "volume"]:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    x["timestamp"] = pd.to_datetime(x["timestamp"], unit="ms", utc=True)
    x = x.dropna().drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    now = pd.Timestamp.now(tz="UTC")
    x = x[x["timestamp"] + pd.Timedelta(milliseconds=interval_ms) <= now].reset_index(drop=True)
    if len(x) < 250:
        raise RuntimeError(f"Insufficient closed candles for {symbol} {timeframe}: {len(x)}")
    return x


def indicators(frame):
    x = frame.copy()
    for n in [20, 50, 100, 200]:
        x[f"ema{n}"] = x.close.ewm(span=n, adjust=False).mean()
    delta = x.close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    x["rsi"] = 100 - 100 / (1 + rs)
    prev_close = x.close.shift(1)
    tr = pd.concat([(x.high-x.low), (x.high-prev_close).abs(), (x.low-prev_close).abs()], axis=1).max(axis=1)
    x["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    x["atr_pct"] = x.atr / x.close
    x["donchian20"] = x.high.rolling(20).max().shift(1)
    x["donchian100"] = x.high.rolling(100).max().shift(1)
    x["donchian20low"] = x.low.rolling(20).min().shift(1)
    x["atr_pct_p80"] = x.atr_pct.rolling(100, min_periods=50).quantile(0.80)
    x["donchian55"] = x.high.rolling(55).max().shift(1)
    x["donchian10low"] = x.low.rolling(10).min().shift(1)
    x["ret20"] = x.close.pct_change(20)
    x["ret60"] = x.close.pct_change(60)
    x["ret120"] = x.close.pct_change(120)
    # Wilder ADX
    up = x.high.diff()
    down = -x.low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr_w = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr_w
    minus_di = 100 * minus_dm.ewm(alpha=1/14, adjust=False, min_periods=14).mean() / atr_w
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, float("nan"))
    x["adx"] = dx.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    # Supertrend, causal iterative bands
    mid = (x.high + x.low) / 2
    upper = mid + 3.0 * x.atr
    lower = mid - 3.0 * x.atr
    st = [float("nan")] * len(x)
    direction = [0] * len(x)
    final_upper, final_lower = float("nan"), float("nan")
    for i in range(len(x)):
        if pd.isna(x.atr.iloc[i]):
            continue
        if i == 0 or pd.isna(final_upper):
            final_upper, final_lower = float(upper.iloc[i]), float(lower.iloc[i])
            direction[i] = 1 if x.close.iloc[i] >= mid.iloc[i] else -1
        else:
            final_upper = min(float(upper.iloc[i]), final_upper) if x.close.iloc[i-1] <= final_upper else float(upper.iloc[i])
            final_lower = max(float(lower.iloc[i]), final_lower) if x.close.iloc[i-1] >= final_lower else float(lower.iloc[i])
            prior = direction[i-1]
            if prior <= 0 and x.close.iloc[i] > final_upper:
                direction[i] = 1
            elif prior >= 0 and x.close.iloc[i] < final_lower:
                direction[i] = -1
            else:
                direction[i] = prior
        st[i] = final_lower if direction[i] > 0 else final_upper
    x["supertrend_dir"] = direction
    x["supertrend"] = st
    # Keltner upper channel
    x["keltner_upper"] = x.ema20 + 2.0 * x.atr
    # annualization factors for volatility targeting
    return x


# Each signal is computed at candle close; orders execute no earlier than next candle open.
def signal_columns(x):
    p = x.shift(1)
    x["mom_entry"] = (x.ret60 > 0) & (x.close > x.ema200)
    x["mom_exit"] = (x.ret20 < 0) | (x.close < x.ema100)
    x["don_entry"] = (x.close > x.donchian55) & (x.close > x.ema200)
    x["don_exit"] = x.close < x.donchian10low
    x["adx_entry"] = (x.ema50 > x.ema200) & (x.adx > 20) & (x.close > x.ema50)
    x["adx_exit"] = (x.ema50 < x.ema200) | (x.close < x.ema50)
    x["st_entry"] = (x.supertrend_dir > 0) & (p.supertrend_dir <= 0)
    x["st_exit"] = x.supertrend_dir < 0
    x["kel_entry"] = (x.close > x.keltner_upper) & (x.ema50 > x.ema200) & (x.adx > 15)
    x["kel_exit"] = (x.close < x.ema20) | (x.ema50 < x.ema200)
    x["mr_entry"] = (x.close > x.ema200) & (p.rsi < 30) & (x.rsi >= 30)
    x["mr_exit"] = (x.rsi > 60) | (x.close < x.ema50)
    x["fastmom_entry"] = (x.ret20 > 0) & (x.ret60 > 0) & (x.close > x.ema200)
    x["fastmom_exit"] = (x.ret20 < 0) | (x.close < x.ema100)
    x["don_ensemble_entry"] = (((x.close > x.donchian20).astype(int) + (x.close > x.donchian55).astype(int) + (x.close > x.donchian100).astype(int)) >= 2) & (x.close > x.ema200)
    x["don_ensemble_exit"] = (x.close < x.donchian20low) | (x.close < x.ema100)
    x["don_cost_entry"] = x["don_ensemble_entry"] & ((x.close / x.donchian20 - 1) > 0.0025)
    x["don_adx_entry"] = x["don_ensemble_entry"] & (x.adx > 25)
    x["don_vol_entry"] = (x.close > x.donchian55) & (x.close > x.ema200) & (x.atr_pct < x.atr_pct_p80)
    x["trend_pullback_entry"] = (x.ema50 > x.ema200) & (p.rsi < 40) & (x.rsi >= 40) & (x.close > x.ema50)
    x["trend_pullback_exit"] = (x.rsi < 45) | (x.close < x.ema100)
    x["triple_momentum_entry"] = (((x.ret20 > 0).astype(int) + (x.ret60 > 0).astype(int) + (x.ret120 > 0).astype(int)) >= 2) & (x.close > x.ema200)
    x["triple_momentum_exit"] = (x.ret20 < 0) | (x.close < x.ema100)
    return x


STRATEGIES = {
    "time_series_momentum_60": ("mom_entry", "mom_exit"),
    "donchian_55_trend": ("don_entry", "don_exit"),
    "adx_trend_filter": ("adx_entry", "adx_exit"),
    "supertrend_10_3": ("st_entry", "st_exit"),
    "keltner_breakout_adx": ("kel_entry", "kel_exit"),
    "bull_regime_mean_reversion": ("mr_entry", "mr_exit"),
    "multi_horizon_momentum": ("fastmom_entry", "fastmom_exit"),
    "donchian_ensemble_20_55_100": ("don_ensemble_entry", "don_ensemble_exit"),
    "donchian_cost_aware_025pct": ("don_cost_entry", "don_ensemble_exit"),
    "donchian_ensemble_adx25": ("don_adx_entry", "don_ensemble_exit"),
    "donchian_volatility_regime": ("don_vol_entry", "don_ensemble_exit"),
    "trend_pullback_rsi40": ("trend_pullback_entry", "trend_pullback_exit"),
    "triple_horizon_momentum": ("triple_momentum_entry", "triple_momentum_exit"),
}


def simulate(x, strategy, start, end, annual_bars):
    entry_col, exit_col = STRATEGIES[strategy]
    cash, pos, trades, curve = INITIAL_EQUITY, None, [], []
    start = max(205, start)
    for i in range(start, end):
        prev, bar = x.iloc[i-1], x.iloc[i]
        exited = False
        if pos:
            # Gap-aware stop/target fills: if open gaps through a barrier, fill at open, otherwise barrier.
            reason, raw_exit = None, None
            if float(bar.open) <= pos["stop"]:
                reason, raw_exit = "STOP_GAP", float(bar.open)
            elif float(bar.open) >= pos["target"]:
                reason, raw_exit = "TARGET_GAP", float(bar.open)
            elif float(bar.low) <= pos["stop"]:
                reason, raw_exit = "STOP", pos["stop"]
            elif float(bar.high) >= pos["target"]:
                reason, raw_exit = "TARGET", pos["target"]
            elif bool(prev[exit_col]):
                reason, raw_exit = "SIGNAL", float(bar.open)
            if reason:
                px = execution_fill(raw_exit, "sell", prev, pos["qty"] * raw_exit)
                proceeds = pos["qty"] * px
                fee = proceeds * FEE_RATE
                cash += proceeds-fee
                trades.append({"pnl": proceeds-fee-pos["entry_cost"], "fees":pos["entry_fee"]+fee,
                               "bars":i-pos["entry_i"]+1, "reason":reason})
                pos, exited = None, True
        if pos is None and not exited and bool(prev[entry_col]):
            atr = float(prev.atr) if pd.notna(prev.atr) else float("nan")
            raw = float(bar.open)
            stop_dist = ATR_STOP_MULTIPLE*atr
            if pd.notna(stop_dist) and stop_dist > 0 and stop_dist < raw:
                risk_cash = cash*RISK_PER_TRADE
                reference_dollar_volume = float(prev.close) * float(prev.volume)
                liquidity_cap = reference_dollar_volume * MAX_PARTICIPATION
                notional = min(
                    risk_cash/(stop_dist/raw),
                    cash*MAX_NOTIONAL_FRACTION/(1+FEE_RATE),
                    liquidity_cap,
                )
                if notional > 0:
                    entry = execution_fill(raw, "buy", prev, notional)
                    notional = min(
                        risk_cash/(stop_dist/entry),
                        cash*MAX_NOTIONAL_FRACTION/(1+FEE_RATE),
                        liquidity_cap,
                    )
                    entry = execution_fill(raw, "buy", prev, notional)
                    qty = notional/entry
                    fee = notional*FEE_RATE
                    cost = notional+fee
                    if cost <= cash and qty > 0:
                        cash -= cost
                        pos = {"qty":qty,"entry":entry,"entry_fee":fee,"entry_cost":cost,"entry_i":i,
                               "stop":entry-stop_dist,"target":entry+REWARD_RISK*stop_dist}
                        # Entry-bar barrier check: stop first if OHLC cannot reveal order.
                        if float(bar.low) <= pos["stop"] or float(bar.high) >= pos["target"]:
                            if float(bar.low) <= pos["stop"]:
                                raw_exit, reason = pos["stop"], "ENTRY_BAR_STOP"
                            else:
                                raw_exit, reason = pos["target"], "ENTRY_BAR_TARGET"
                            px = execution_fill(raw_exit, "sell", prev, qty * raw_exit)
                            proceeds=qty*px
                            exit_fee=proceeds*FEE_RATE
                            cash += proceeds-exit_fee
                            trades.append({"pnl":proceeds-exit_fee-cost,"fees":fee+exit_fee,"bars":1,"reason":reason})
                            pos, exited = None, True

        equity = cash
        if pos:
            mark_raw = float(bar.close)
            mark_price = execution_fill(mark_raw, "sell", prev, pos["qty"] * mark_raw)
            equity += pos["qty"] * mark_price * (1-FEE_RATE)
        curve.append(equity)
    if pos:
        last_bar = x.iloc[end-1]
        reference_bar = x.iloc[end-2] if end - 2 >= 0 else last_bar
        raw_exit = float(last_bar.close)
        px = execution_fill(raw_exit, "sell", reference_bar, pos["qty"] * raw_exit)
        proceeds=pos["qty"]*px
        fee=proceeds*FEE_RATE
        cash += proceeds-fee
        trades.append({"pnl":proceeds-fee-pos["entry_cost"],"fees":pos["entry_fee"]+fee,
                       "bars":end-pos["entry_i"],"reason":"TEST_END"})
    # Include cash/equity correctly; drawdown includes initial equity and final liquidation.
    values=[INITIAL_EQUITY]+curve+[cash]
    peak, mdd=values[0], 0.0
    for v in values:
        peak=max(peak,v)
        if peak>0: mdd=max(mdd,(peak-v)/peak*100)
    pnl=[t["pnl"] for t in trades]
    gp=sum(v for v in pnl if v>0)
    gl=abs(sum(v for v in pnl if v<0))
    total=cash-INITIAL_EQUITY
    rets=pd.Series(values).pct_change().dropna()
    sharpe=float(rets.mean()/rets.std()*((annual_bars)**0.5)) if len(rets)>2 and rets.std()>0 else 0.0
    years=max((x.iloc[end-1].timestamp-x.iloc[start].timestamp).total_seconds()/31557600, 1/365)
    return {"trades":len(trades),"wins":sum(v>0 for v in pnl),
            "win_rate_pct":round(100*sum(v>0 for v in pnl)/len(trades),2) if trades else 0,
            "net_pnl_usdt":round(total,2),"return_pct":round(total/INITIAL_EQUITY*100,3),
            "cagr_pct":round(((cash/INITIAL_EQUITY)**(1/years)-1)*100,2) if cash>0 else -100,
            "profit_factor":round(gp/gl,3) if gl else ("inf" if gp else 0),
            "max_drawdown_pct":round(mdd,2),"sharpe_approx":round(sharpe,3),
            "fees_usdt":round(sum(t["fees"] for t in trades),2),
            "expectancy_usdt":round(sum(pnl)/len(pnl),2) if pnl else 0,
            "avg_bars_held":round(sum(t["bars"] for t in trades)/len(trades),2) if trades else 0,
            "ending_equity_usdt":round(cash,2),
            "exits":{k:sum(t["reason"]==k for t in trades) for k in sorted({t["reason"] for t in trades})}}


def buy_hold(x, start, end):
    entry_bar = x.iloc[start]
    entry_reference = x.iloc[start-1] if start > 0 else entry_bar
    raw_entry = float(entry_bar.open)
    a = execution_fill(raw_entry, "buy", entry_reference, INITIAL_EQUITY)
    qty=INITIAL_EQUITY/(a*(1+FEE_RATE))
    last_bar = x.iloc[end-1]
    exit_reference = x.iloc[end-2] if end-2 >= 0 else last_bar
    raw_exit = float(last_bar.close)
    b = execution_fill(raw_exit, "sell", exit_reference, qty * raw_exit)
    ending=qty*b*(1-FEE_RATE)
    return {"trades":1,"wins":int(ending>INITIAL_EQUITY),"win_rate_pct":100 if ending>INITIAL_EQUITY else 0,
            "net_pnl_usdt":round(ending-INITIAL_EQUITY,2),"return_pct":round((ending/INITIAL_EQUITY-1)*100,3),
            "cagr_pct":None,"profit_factor":None,"max_drawdown_pct":None,"sharpe_approx":None,
            "fees_usdt":round(INITIAL_EQUITY*FEE_RATE+qty*b*FEE_RATE,2),
            "expectancy_usdt":round(ending-INITIAL_EQUITY,2),"avg_bars_held":end-start,
            "ending_equity_usdt":round(ending,2)}


def main():
    rows=[]
    print(f"ASHUR research v3 | {LOOKBACK_DAYS}d | 4 assets | 1h/4h/1d | fee {FEE_RATE:.2%}/side | dynamic spread/impact model | risk {RISK_PER_TRADE:.2%}")
    for symbol in SYMBOLS:
        for tf, interval in TIMEFRAMES.items():
            raw=fetch_history(symbol,tf,interval)
            x=signal_columns(indicators(raw))
            n=len(x); train_end=int(n*TRAIN_FRACTION); val_end=int(n*(TRAIN_FRACTION+VALIDATION_FRACTION))
            annual_bars={"1h":24*365,"4h":6*365,"1d":365}[tf]
            for strategy in STRATEGIES:
                metrics={}
                for label,a,b in [("train",205,train_end),("validation",train_end,val_end),("test",val_end,n)]:
                    metrics[label]=simulate(x,strategy,a,b,annual_bars)
                row={"symbol":symbol,"timeframe":tf,"strategy":strategy,"candles":n,
                     "start":x.iloc[0].timestamp.isoformat(),"end":x.iloc[-1].timestamp.isoformat(),**metrics}
                rows.append(row)
                print(json.dumps({"symbol":symbol,"tf":tf,"strategy":strategy,
                    "train":metrics["train"]["return_pct"],"validation":metrics["validation"]["return_pct"],
                    "test":metrics["test"]["return_pct"],"test_trades":metrics["test"]["trades"],
                    "test_pf":metrics["test"]["profit_factor"],"test_dd":metrics["test"]["max_drawdown_pct"],
                    "test_fees":metrics["test"]["fees_usdt"]}))
            bh=buy_hold(x,val_end,n)
            rows.append({"symbol":symbol,"timeframe":tf,"strategy":"buy_and_hold_benchmark","candles":n,
                         "start":x.iloc[0].timestamp.isoformat(),"end":x.iloc[-1].timestamp.isoformat(),
                         "train":{},"validation":{},"test":bh})
    rows.sort(key=lambda r:(r["test"].get("return_pct",-999),r["test"].get("profit_factor") if isinstance(r["test"].get("profit_factor"),(int,float)) else -1),reverse=True)
    payload={"config":{"lookback_days":LOOKBACK_DAYS,"train_fraction":TRAIN_FRACTION,
        "validation_fraction":VALIDATION_FRACTION,"test_fraction":1-TRAIN_FRACTION-VALIDATION_FRACTION,
        "fee_each_side":FEE_RATE,
        "execution_cost_model":{
            "spread_bps_full":SPREAD_BPS,
            "base_slippage_bps_each_side":BASE_SLIPPAGE_BPS,
            "volatility_impact_coefficient":VOLATILITY_IMPACT,
            "max_impact_bps_each_side":MAX_IMPACT_BPS,
            "max_order_participation_of_previous_candle_dollar_volume":MAX_PARTICIPATION,
            "liquidity_reference":"previous completed candle only",
            "limitation":"OHLCV proxy, not historical bid/ask quotes or order-book replay"
        },
        "risk_per_trade":RISK_PER_TRADE,
        "max_notional_fraction":MAX_NOTIONAL_FRACTION,"stop_atr_multiple":ATR_STOP_MULTIPLE,
        "target_r":REWARD_RISK,"symbols":SYMBOLS,"timeframes":list(TIMEFRAMES),
        "execution":"signal on closed candle, entry next open, gap-aware stop/target, fees and slippage both sides",
        "warning":"Long-only spot historical simulation. No guarantee of future profitability. Fixed rules, chronological train/validation/test; test is held out, not future paper validation."},
        "results":rows}
    (ROOT/"strategy_research_v3.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    fields=["symbol","timeframe","strategy","train_return_pct","validation_return_pct","test_return_pct","test_trades","test_pf","test_mdd_pct","test_sharpe_approx","test_fees_usdt","test_ending_equity"]
    with (ROOT/"strategy_research_v3.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:
            t=r["test"];w.writerow({"symbol":r["symbol"],"timeframe":r["timeframe"],"strategy":r["strategy"],
                "train_return_pct":r.get("train",{}).get("return_pct"),
                "validation_return_pct":r.get("validation",{}).get("return_pct"),
                "test_return_pct":t.get("return_pct"),"test_trades":t.get("trades"),
                "test_pf":t.get("profit_factor"),"test_mdd_pct":t.get("max_drawdown_pct"),
                "test_sharpe_approx":t.get("sharpe_approx"),"test_fees_usdt":t.get("fees_usdt"),
                "test_ending_equity":t.get("ending_equity_usdt")})
    candidates=[r for r in rows if r["strategy"]!="buy_and_hold_benchmark" and r["test"].get("trades",0)>=8
        and isinstance(r["test"].get("profit_factor"),(int,float)) and r["test"]["profit_factor"]>1
        and r["test"].get("return_pct",0)>0 and r["validation"].get("return_pct",0)>0]
    print("=== CANDIDATES: positive validation AND test, PF>1, >=8 test trades ===")
    print(json.dumps([{"symbol":r["symbol"],"timeframe":r["timeframe"],"strategy":r["strategy"],
        "validation":r["validation"]["return_pct"],"test":r["test"]["return_pct"],
        "trades":r["test"]["trades"],"pf":r["test"]["profit_factor"],"mdd":r["test"]["max_drawdown_pct"]} for r in candidates],ensure_ascii=False))
    print(f"Saved strategy_research_v3.json and strategy_research_v3.csv; rows={len(rows)}")


if __name__=="__main__":
    main()
