# ASHUR Trading Lab — MVP 0.1

A paper-trading laboratory for Bybit Spot public market data. This is a separate app inside the ASHUR repository; the existing presentation website remains untouched.

## Safety by design
- No API keys are requested or supported.
- No private exchange endpoints and no real order execution.
- BTC/USDT and ETH/USDT only.
- 4h default timeframe.
- Virtual starting balance: 10,000 USDT.
- Risk sizing capped at 0.5% per trade, 2% daily realized loss limit, maximum 2 open positions.
- No leverage, martingale, or averaging down.

## Run locally
Python 3.11+ recommended.

```bash
cd trading-lab
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

The app fetches public OHLCV candles from Bybit through CCXT. Paper trades are stored in `ashur_paper.db` beside the app.

## Deploy
Create a Streamlit Community Cloud app using this repository, branch `mvp-paper-trading`, and main file path `trading-lab/app.py`. Requirements path: `trading-lab/requirements.txt`.

## Current MVP scope
- Public spot candles and EMA/Donchian indicators.
- Market chart and basic signal display.
- Simulated paper buy/close actions.
- SQLite cash, positions, and closed-trade ledger.
- Basic risk gates and audit table.

Backtesting, automated strategy execution, portfolio equity history, and independent SHAMASH rule engine are planned next. This MVP is a software prototype, not a profitable or validated trading strategy.
