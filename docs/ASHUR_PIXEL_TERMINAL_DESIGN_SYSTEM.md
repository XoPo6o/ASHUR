# ASHUR Pixel Trading Terminal — design system v0.1

## Art direction
A deliberate blend of:
- **Pixelhood**: pixel-world atmosphere, stylized Assyrian/Nineveh environment, small pixel-art guardian/lamassu motifs and environmental storytelling.
- **Retro Pixel UI**: hard pixel borders, inset frames, rectangular controls, compact labels, status chips and clear pressed/active states.
- **ASHUR identity**: Assyrian reliefs, lamassu, cuneiform and palace geometry, translated into a restrained 8-bit visual language.

The result is a professional analytics terminal inside a retro game world. Data must remain more legible than decoration.

## Color tokens
| Token | Hex | Use |
|---|---|---|
| Night / background | `#0B141D` | Main canvas |
| Deep night | `#101E2A` | Secondary surfaces |
| Basalt panel | `#142633` | Main cards |
| Raised panel | `#1B3340` | Secondary cards and controls |
| Stone line | `#365564` | Borders and dividers |
| Assyrian gold | `#E4B86A` | Primary figures and highlights |
| Turquoise | `#65D8D0` | Charts and active UI |
| Emerald | `#65D69A` | Positive P&L and healthy state |
| Coral | `#ED7774` | Negative P&L and errors |
| Ivory | `#E9E5D6` | Primary text |
| Sand-grey | `#9AB0B6` | Secondary text |

Color is semantic, not decorative: green only means positive/healthy, coral only means negative/error, turquoise marks data series/active state, gold marks key totals and the ASHUR identity.

## Typography
- Press Start 2P: short labels, section identifiers and selected micro-headings only. Never use it for paragraphs or dense numeric data.
- IBM Plex Mono: balances, percentages, timestamps, chart axes, IDs and tabular figures.
- Inter: explanatory text, captions and longer descriptions.
- Use tabular numerals for all monetary values and percentages.

## Pixel construction
- Use a consistent 4px base spacing grid.
- Default panel border: 2px; nested/inset line: 1px.
- Use square corners; avoid soft rounded SaaS-card styling.
- Use hard offset shadows (3–4px) to create tactile game UI depth.
- Pixel artwork must use crisp edges and nearest-neighbour scaling; no blur or anti-aliased resizing.
- For scalable ornamental frames, use SVG or 9-slice assets rather than stretching pixel-art corners.

## Component language
- Metric panel: micro-label, large tabular value, unit/context line.
- Chart panel: title, status/time-range chip, chart area, legend and exact value tooltip.
- Strategy tile: strategy ID, market/timeframe, health state, equity, P&L and open-position indicator.
- Status chip: explicit semantic label; never color alone.
- Empty state: explain what data is missing and when the chart becomes meaningful.
- Navigation: short pixel labels, high-contrast active state, keyboard/touch accessible targets.

## Layout and responsive behavior
- Desktop: 12-column visual grid; four primary metric cards; large equity chart plus daily snapshot; six strategy tiles in two rows.
- Tablet: two metric columns; two strategy columns; charts stack where necessary.
- Mobile: single-column panels, horizontally scrollable top navigation, compact chart legend, touch targets at least 44px high.
- Keep numeric values and chart axes readable; do not shrink the pixel font to fit.

## Motion
- Restrained state feedback only: subtle pixel blink for status change, short panel press offset, no perpetual particle effects.
- Respect reduced-motion preferences.
- No animation may obscure a changing financial value or system warning.

## First prototype
`wall-preview.html` is the first visual composition. It uses the verified 30-day baseline (6 x 1,000 USDT), a single baseline marker, and explicit empty states. It is not connected to live data and must not be treated as a production dashboard.
