#!/usr/bin/env python3
"""Build a strict summary from Freqtrade's archived backtest JSON files."""
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent / "user_data" / "backtest_results"
rows = []
errors = []

for archive in sorted(root.glob("*.zip")):
    try:
        with zipfile.ZipFile(archive) as bundle:
            candidates = [
                name for name in bundle.namelist()
                if name.endswith(".json") and not name.endswith("_config.json")
            ]
            if len(candidates) != 1:
                raise ValueError(f"expected one result JSON, found {len(candidates)}")
            payload = json.loads(bundle.read(candidates[0]))
        strategies = payload.get("strategy")
        if not isinstance(strategies, dict) or not strategies:
            raise ValueError("missing strategy result object")
        for name, stats in strategies.items():
            if not isinstance(stats, dict):
                raise ValueError(f"invalid stats for {name}")
            rows.append({
                "archive": archive.name,
                "strategy": name,
                "timeframe": stats.get("timeframe"),
                "pair": (stats.get("pairlist") or [None])[0],
                "period_start": stats.get("backtest_start"),
                "period_end": stats.get("backtest_end"),
                "days": stats.get("backtest_days"),
                "trades": stats.get("total_trades"),
                "wins": stats.get("wins"),
                "losses": stats.get("losses"),
                "winrate_pct": round((stats.get("winrate") or 0) * 100, 4),
                "net_profit_pct": round((stats.get("profit_total") or 0) * 100, 4),
                "net_profit_abs": stats.get("profit_total_abs"),
                "profit_factor": stats.get("profit_factor"),
                "expectancy": stats.get("expectancy"),
                "max_drawdown_pct": round((stats.get("max_drawdown_account") or 0) * 100, 4),
                "market_change_pct": round((stats.get("market_change") or 0) * 100, 4),
                "starting_balance": stats.get("starting_balance"),
                "final_balance": stats.get("final_balance"),
            })
    except Exception as exc:
        errors.append({"archive": archive.name, "error": str(exc)})

expected = 12
report = {
    "expected_runs": expected,
    "parsed_runs": len(rows),
    "errors": errors,
    "runs": rows,
    "status": "ok" if len(rows) == expected and not errors else "incomplete",
}
print(json.dumps(report, indent=2, sort_keys=True))
if report["status"] != "ok":
    raise SystemExit(f"Expected {expected} valid backtests, parsed {len(rows)}; errors={len(errors)}")
