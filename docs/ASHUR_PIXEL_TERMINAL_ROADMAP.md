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
3. Build the design system: pixel grid, palette, type scale, 9-slice panel borders, buttons, indicators, icons, decorative Assyrian assets and responsive rules. BASELINE V0.1 DONE (tokens, typography, component rules and first responsive components documented; detailed component inventory continues during implementation).
4. Build Command Center: portfolio equity, P&L, trades, drawdown, equity curve, daily P&L, six strategy states and system health. IN PROGRESS (first screen composition and verified baseline allocation visualization implemented; runtime values and full chart series await data integration).
5. Build analytics charts: equity curve, daily P&L, drawdown, strategy comparison, trade distribution and calendar heatmap.
6. Build Daily Report and dated report archive with 24-hour and baseline-relative comparisons.
7. Integrate the real Paper/Shadow status through a read-only endpoint or safely published status projection; never read the stale repository JSON as live data. IN PROGRESS (runtime export audited; strict read model and standard-library HTTP endpoint implemented on the isolated branch; HTTPS access, live host verification and front-end wiring remain pending).
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
- Stage 3 baseline v0.1 completed: design tokens and visual rules documented in `docs/ASHUR_PIXEL_TERMINAL_DESIGN_SYSTEM.md`.
- Stage 4 in progress: `wall-preview.html` now includes the main dashboard composition, six unique strategy cards, verified 6 × 1,000 USDT capital-allocation visualization, responsive layout, and an equity-curve baseline marker that does not imply fabricated flat performance. It remains a static preview, not connected to production data.
- Work is isolated on `ashur-pixel-terminal-ui`; no merge or deployment has occurred.\n- Runtime adapter milestone: `dashboard/read_model.py` projects the worker's actual JSON export through a strict allowlist, validates the active baseline and six 1,000 USDT accounts, derives portfolio aggregates, and labels stale/offline data. `tests/test_dashboard_read_model.py` covers baseline, mode, duplicate-account, freshness and secret/path non-leakage guards. Tests have been authored but not executed in this environment; no endpoint or live connection is deployed.

## First implementation deliverables
- `wall-preview.html`: standalone visual prototype using only verified baseline facts and explicit empty states.
- This roadmap document: project scope, audit findings, safety constraints and stage tracking.


## Progress update — 2026-11-25 (visual refinement)
- Updated `wall-preview.html` to use the exact eight-point star SVG mark from the current `main/index.html` brand.
- Removed the full-page grid overlay and replaced it with a restrained layered midnight gradient with soft turquoise and warm-gold ambient light.
- Stage 4 remains IN PROGRESS. This is a design refinement only: the preview is still static, and live runtime integration, history collection, automated test execution, and review are not complete.


## Progress update — 2026-11-25 (read-only HTTP adapter)
- Added `dashboard/http_server.py`: same-origin dashboard page at `/`, `/healthz`, and `GET /api/dashboard/v1/status`; the API returns only the validated `project_status()` allowlist and never serves the raw worker JSON or SQLite database.
- Added bounded source-file handling, `no-store` response headers, exact CORS allowlisting, same-origin support for an HTTPS reverse proxy, and safe 503 behavior for missing/invalid/offline status.
- Updated `trading-lab/ashur_supervisor.py` to start the optional listener only when `SERVER_PORT` is supplied. The HTTP listener runs in a daemon thread; listener failure does not interrupt Paper/Shadow supervision.
- Added `tests/test_dashboard_http_server.py` and `.github/workflows/dashboard-checks.yml`. The workflow has been committed, but a successful CI run has not yet been confirmed.
- The endpoint remains isolated in `ashur-pixel-terminal-ui`; nothing has been merged or deployed. Silly Development's public app port is plain HTTP, so HTTPS tunnel/reverse-proxy setup must be resolved before connecting a production HTTPS website.

- Initial dashboard unit suite is green; broader calculation checks against live runtime exports, timezone boundaries, responsive browser rendering and production host verification remain for stage 9.


## Progress update — 2026-11-25 (browser data wiring)
- Connected the Command Center to the same-origin read-only status API. The page polls every 60 seconds with `cache: no-store` and updates portfolio equity, net P&L/return, closed trades, worker health, source freshness and six strategy balances/statuses.
- Failure state explicitly labels displayed values as baseline reference only; it does not present the last static baseline as current performance.
- Equity history, daily P&L history and drawdown remain empty until the separate append-only history collector exists; no synthetic chart series is drawn.
- Added preview integrity tests for the six strategy IDs, feed route, baseline-only failure behavior and the new official star/no-grid design. CI run #14 is in progress at this update; final result must be checked before calling this milestone green.
