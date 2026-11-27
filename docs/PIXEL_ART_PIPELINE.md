# ASHUR — Babylon Inventory Pixel-Art Production Pipeline

Status: **PRIMARY ART PRODUCTION PLAN**
Selected editor: **Pixelorama** (free, open-source MIT license).

## Non-negotiable production rule
All final pixel-art assets for Babylon Inventory must be authored as pixel art in Pixelorama. Do not draw final artwork with SVG paths, CSS shapes, gradients, filters, or programmatic pixel painting. HTML/CSS may assemble the interface and display exported assets, but must not substitute for the artwork.

## Why Pixelorama
- Free and open-source under MIT; use the free desktop build from the official project.
- Dedicated pixel-art workflow: pixel-perfect drawing tools, palettes, indexed color, layers, tilesets/tilemaps, animation and sprite-sheet export.
- Active project with a substantial community; GitHub repository has over 11k stars, and Steam user reviews are very positive (Steam build is not the free download route).
- The native project source must be preserved alongside exported PNG assets.

## Production pipeline

### 1. Art direction and reference breakdown
- Use Babylon Inventory as the approved visual target.
- Record composition, silhouettes, depth planes, lighting direction, material language, ornament density and pixel scale before drawing.
- Build a fresh palette for the art direction; do not automatically reuse the previous navy/burgundy/gold/cyan palette.
- Keep the five established references available for comparison, but Babylon Inventory remains the active target.

### 2. Pixelorama project setup
- Create a native .pxo project.
- Establish a master palette and indexed-color workflow where practical.
- Set consistent canvas and sprite dimensions; initial working targets: scene 320x180, strategy icons 32x32 or 48x48, reusable tiles 16x16 or 32x32. These are starting constraints and may be adjusted to the composition.
- Organize layers by depth, architecture, lighting, props, characters, foreground and effects.

### 3. Draw the actual assets in Pixelorama
- Background: complete Babylon night-market scene with clear foreground, middle ground and distant skyline.
- Landmark architecture: ziggurat, temple, hanging gardens and city structures.
- Signature subject: a readable, detailed Lamassu sprite with deliberate silhouette and shading clusters.
- Interface art: ornamental frame corners, stone/metal trims, separators and decorative tiles.
- Strategy set: six distinct icons with readable silhouettes at native size.
- No generic placeholder rectangles presented as finished art.

### 4. Pixel-art quality control
- Inspect at native 1x, then integer scales 2x and 4x using nearest-neighbor.
- Check silhouette readability, cluster discipline, consistent pixel scale, palette count, contrast, lighting, edge quality and absence of accidental single-pixel noise.
- Check assets on desktop and mobile backgrounds.
- Compare the result against the approved reference; never claim a similarity percentage without an actual side-by-side visual review.

### 5. Export and integration
- Preserve .pxo source files.
- Export transparent PNG sprites, backgrounds, tilesets and sprite sheets.
- Keep asset names and dimensions documented.
- Integrate exported art into the website. HTML/CSS is for layout, responsive behavior, data, charts and controls only.

### 6. Review gates
- Gate A: approve the palette and art-direction sheet.
- Gate B: approve one finished scene and one representative icon.
- Gate C: approve the complete asset pack.
- Gate D: only then replace artwork in the main Wall.
- Keep the trading worker, strategy logic, data, history and paper/shadow runtime untouched during art production.

## First production milestone
Create a complete Babylon night-scene study in Pixelorama, with a strong ziggurat silhouette and a separately readable Lamassu. Then create one strategy icon at native resolution. Deliver the .pxo source and exported PNGs for review before expanding the asset pack.

## Current known limitation
The existing pixel-lab/ assets are only a technical raster test, not approved final art. They must not be treated as the quality baseline. The main Wall remains unchanged until the review gates are passed.
