#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parent / "user_data" / "backtest_results"
rows = []
for path in sorted(root.glob("*.json")):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    strategies = payload.get("strategy", {})
    if not isinstance(strategies, dict):
        continue
    for name, stats in strategies.items():
        if isinstance(stats, dict):
            rows.append({
                "file": path.name, "strategy": name,
                "total_trades": stats.get("total_trades"),
                "profit_total_abs": stats.get("profit_total_abs"),
                "profit_total_pct": stats.get("profit_total_pct"),
                "wins": stats.get("wins"), "losses": stats.get("losses"),
                "winrate": stats.get("winrate"),
                "profit_factor": stats.get("profit_factor"),
                "expectancy": stats.get("expectancy"),
                "max_drawdown_account": stats.get("max_drawdown_account"),
                "max_drawdown": stats.get("max_drawdown"),
                "backtest_start": stats.get("backtest_start"),
                "backtest_end": stats.get("backtest_end"),
            })
print(json.dumps(rows, indent=2, default=str) if rows else
      "No parseable strategy summaries found; inspect raw JSON artifacts.")
