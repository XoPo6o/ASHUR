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

Donchian channels use prior candles only (shift(1)). Risk sizing targets 0.5% equity against a conservative 15% hard stop plus 0.15% per-side estimated costs. A 3-ATR custom stop may tighten the hard stop; target is 4R. Cooldown, StoplossGuard and MaxDrawdown protections are configured.

## Test protocol and data access

The workflow pins the official Freqtrade Docker image to 2026.10. GitHub-hosted runners are in a restricted region: Bybit returns CloudFront 403 and Binance's standard API returns HTTP 451. For research-only historical candles, the Binance configs route CCXT's public endpoints to Binance's official market-data-only mirror, data-api.binance.vision. That mirror provides public exchangeInfo and kline endpoints without credentials. No private endpoints, keys or order APIs are used.

This is a strategy-engine/backtest test on Binance spot market history, not a test of Bybit connectivity or Bybit fills. A separate config-bybit-dryrun.json is included for a future dry-run on a host that can reach Bybit.

The benchmark validates config and strategy discovery, downloads historical OHLCV, runs chronological in-sample (2024-11-21 to 2025-11-21) and out-of-sample (2025-11-21 to 2026-11-21) backtests, charges 0.15% per side, uses lower-timeframe detail candles, enables protections, runs lookahead and recursive checks, and uploads raw JSON plus a machine-readable summary.

Do not tune against the out-of-sample period. A strategy is not a winner based on one attractive backtest. Require enough trades, positive OOS expectancy after costs, acceptable drawdown, robustness across periods and forward dry-run evidence.

## Important Bybit limitation

Freqtrade supports Bybit Spot, but current exchange notes say stoploss-on-exchange is not available for Bybit Spot. The stop is managed by the bot process; if the host goes offline, the exchange does not retain that stop. This is a blocker for unattended real-money Spot trading until exchange-side protection is separately designed and tested.

## Hosting isolation

Silly Development installs the linked directory's root requirements, applies sillydev.conf and restarts the server's single startup process. ASHUR currently owns that process. Adding Freqtrade dependencies or changing startup in-place could interrupt or break ASHUR. This branch intentionally does not do that. The benchmark runs in GitHub Actions. A persistent Freqtrade dry-run needs a separate server/container with enough resources; no additional paid server is created by this branch.

A read-only query of our actual ASHUR server returned:
- 256 MiB RAM limit
- 512 MiB disk limit
- 25% of one CPU core
- current use at probe time: 13.73 MiB RAM and 160.39 MiB disk

Freqtrade recommends at least 2 GB RAM and 2 vCPU for a Linux cloud instance. Our current host is far below that; even Silly Development's documented Plus allocation of 1.25 GB / 125% CPU remains below the recommendation. Deploying Freqtrade beside ASHUR on this host is not safe.

## Local Docker

```bash
docker pull freqtradeorg/freqtrade:2026.10
docker run --rm freqtradeorg/freqtrade:2026.10 --version
```

Official docs: https://www.freqtrade.io/en/stable/
