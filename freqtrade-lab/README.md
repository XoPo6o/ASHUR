# ASHUR × Freqtrade evaluation lab

Isolated evaluation branch: it does not change the production ASHUR daemon, root requirements, startup command, runtime database or current Silly Development deployment.

## Strategy ports

Six Strategy v3 ports of ASHUR's current PAPER_ONLY baseline:
- BNB 15m EMA20/EMA50 + ADX12
- BNB 1h Donchian 20/55/100 voting + EMA200 + ADX25
- BNB 4h EMA50/EMA200 + ADX20
- BNB 4h Keltner breakout + EMA50/EMA200 + ADX15
- SOL 4h Donchian55 + EMA200 + ATR percentile filter
- BNB 1d Donchian55 + EMA200

Donchian channels use prior candles only (shift(1)). The framework risk sizing targets 0.5% equity against a 15% hard stop plus 0.15% per-side estimated costs. The custom stop may tighten to 3 ATR; target is 4R. Cooldown, StoplossGuard and MaxDrawdown protections are enabled for evaluation.

## Test protocol

The workflow pins the official Freqtrade Docker image to 2026.10 and uses Bybit public Spot OHLCV. No API keys are used. It validates configs/strategies, downloads history, runs chronological in-sample and out-of-sample backtests, includes a 0.15% per-side cost assumption, uses lower-timeframe detail candles, runs lookahead checks and uploads raw JSON plus a summary artifact.

Do not tune against the out-of-sample period. A strategy is not a winner based on one attractive backtest. Require enough trades, positive OOS expectancy after costs, acceptable drawdown, robustness across periods and forward dry-run evidence.

## Important Bybit limitation

Freqtrade supports Bybit Spot, but its current exchange notes say stoploss-on-exchange is not available for Bybit Spot. The stop is therefore managed by the bot process; if the host goes offline, the exchange does not retain that stop. This is a blocker for unattended real-money Spot trading until exchange-side protection is separately designed and tested.

## Why this branch is not deployed into the existing ASHUR process

Silly Development installs the linked directory's root requirements, applies sillydev.conf and restarts the server's single startup process. ASHUR currently owns that process. Adding Freqtrade dependencies or changing startup in-place could interrupt or break ASHUR. This branch is intentionally isolated. GitHub Actions performs the benchmark; a separate Silly Development server/container is required for a persistent Freqtrade dry-run service. This branch does not create or buy another server.

## Local Docker

```bash
docker pull freqtradeorg/freqtrade:2026.10
docker run --rm freqtradeorg/freqtrade:2026.10 --version
```

Official docs: https://www.freqtrade.io/en/stable/
