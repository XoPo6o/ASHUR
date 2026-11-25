# ASHUR Pixel Trading Terminal — roadmap

Status: approved direction; implementation branch: `ashur-pixel-terminal-ui`.
Base: `ashur-live-shadow` commit `2a8048b8814589a3be082a858e8924e6399ec012`.
Scope: read-only Paper/Shadow analytics UI. No order execution, no strategy changes, no mutation of the trading database.

## Approved visual direction
- Pixelhood: pixel-art world building, atmosphere, decorative world elements and character-like visual motifs.
- Retro Pixel UI: pixel borders, panels, buttons, status lamps, meters and interaction states.
- ASHUR house style: Assyrian/Nineveh architecture, lamassu, cuneiform and palace motifs; midnight basalt palette, turquoise data visualization, gold accents, green positive values and coral negative values.
- Professional analytics remain legible: chart scales, exact numeric values, tooltips, accessible contrast and responsive layouts.

## Audit findings
- Root `index.html` is the existing Assyrian presentation website. It is not a trading dashboard.
- `trading-lab/app.py` is an older Streamlit MVP. It reads `ashur_paper.db`, has a 10,000 USDT single-account assumption and a separate BTC/ETH paper-trading flow. It is not the active six-strategy Paper/Shadow experiment and must not be repurposed as the data source.
- Active experiment implementation is `trading-lab/live_shadow_worker.py`; its read model is exported to `ashur_shadow_status.json` from the worker's persistent data directory. The checked-in status JSON is stale and must not be used as live data.
- The current export includes baseline metadata, worker health, six accounts, cash/equity/P&L, trade counts, win rate, profit factor, fees, recent trades, market marks and open-position details.
- The worker's SQLite schema includes `shadow_accounts`, `shadow_positions`, `shadow_trades`, `shadow_events`, `shadow_marks`, `shadow_intrabar_health` and `ashur_meta`.
- The UI must consume a safe read-only projection of the live worker status. Do not expose the SQLite file or worker's private data directory to the browser.

## Ten-stage delivery plan
1. Audit current site, runtime, status export, deployment and existing UI. DONE (initial repository audit; see audit findings below).
2. Define information architecture and data contract for Command Center, Daily Report, Strategy Room, Equity & Performance, Trade History, System Status and Archive. DONE (initial IA and read-only data contract documented).
3. Build the design system: pixel grid, palette, type scale, 9-slice panel borders, buttons, indicators, icons, decorative Assyrian assets and responsive rules. IN PROGRESS (design tokens and first visual components documented; more components remain).
4. Build Command Center: portfolio equity, P&L, trades, drawdown, equity curve, daily P&L, six strategy states and system health.
5. Build analytics charts: equity curve, daily P&L, drawdown, strategy comparison, trade distribution and calendar heatmap.
6. Build Daily Report and dated report archive with 24-hour and baseline-relative comparisons.
7. Integrate the real Paper/Shadow status through a read-only endpoint or safely published status projection; never read the stale repository JSON as live data.
8. Implement mobile layouts and touch-friendly navigation.
9. Test calculations against SQLite/exported status, empty states, timezone boundaries, stale data, all six strategies, accessibility and responsive layouts.
10. Deploy only after review, keeping the existing landing page and trading runtime stable; verify production and record the release commit.

## Non-negotiable safety rules
- Paper Only. No exchange order endpoints.
- Freeze strategy rules and parameters throughout the 30-day experiment.
- UI is read-only and must not write to trading tables.
- The active baseline ID is `ashur-paper-30d-2026-11-25-v2`; starting equity is 1,000 USDT per strategy, six strategies, 6,000 USDT total.
- No fabricated performance series. With no observations, show a baseline marker and an explicit empty state.
- Do not use legacy `ashur_paper.db` or the checked-in stale `ashur_shadow_status.json` as current experiment data.
- Do not merge into the live branch or deploy until the preview and data contract are reviewed.

## Progress on 2026-11-25
- Stage 1 audit completed.
- Stage 2 initial information architecture and read-only data contract completed; see `docs/ASHUR_PIXEL_TERMINAL_DATA_CONTRACT.md`.
- Stage 3 in progress: design tokens and visual rules documented in `docs/ASHUR_PIXEL_TERMINAL_DESIGN_SYSTEM.md`; standalone `wall-preview.html` contains the first Pixelhood/Retro Pixel UI composition. It is a static design prototype and is not connected to production data.
- Work is isolated on `ashur-pixel-terminal-ui`; no merge or deployment has occurred.

## First implementation deliverables
- `wall-preview.html`: standalone visual prototype using only verified baseline facts and explicit empty states.
- This roadmap document: project scope, audit findings, safety constraints and stage tracking.
