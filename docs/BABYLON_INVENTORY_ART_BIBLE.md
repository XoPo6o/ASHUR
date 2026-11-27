# ASHUR — 01 Babylon Inventory Art Bible

Status: **controlled first pass**. This is the binding direction for the next Pixel Foundry UI pass; it is not a claim that the current artwork already matches the reference.

## Reference hierarchy

1. Primary: `wall-variants/01-babylon-inventory.html` — layout, proportions, hierarchy and surface treatment.
2. The approved Babylon Inventory reference image — visual target for the complete screen.
3. Existing Art Study 02 — experimental source material only. Its scene palette and object style are **not** the target.

## Visual identity

Babylon Inventory is a dark, restrained game dashboard. It is not a colorful fantasy landscape and not a neon arcade screen.

- Near-black midnight navy is the dominant field.
- Panels are blue/steel charcoal, with clear separation from the page background.
- Thin antique-gold strokes define important frames and selected information.
- Muted teal is a secondary signal color, used sparingly.
- Text is warm ivory; secondary labels are desaturated blue-gray.
- Pixel treatment belongs in borders, corners, separators, icons and data marks. It must not damage legibility.

## Palette contract

The canonical token file is `pixel_foundry/palettes/babylon_inventory.json`.

| Role | Token | Hex |
|---|---|---|
| Page background | void | `#0B1422` |
| Main panel | surface | `#142333` |
| Raised panel | surface_raised | `#1B2D3D` |
| Deep inset | surface_deep | `#101C2A` |
| Structural border | border | `#425568` |
| Gold border | border_gold | `#A98A5C` |
| Primary accent | gold | `#D6B574` |
| Highlight | gold_light | `#E9D6A7` |
| Main text | text | `#E6DDC8` |
| Muted text | muted | `#8F9DA5` |
| Secondary accent | teal | `#5D9692` |
| Deep teal | teal_deep | `#315F63` |

This is a controlled first-pass palette based on the visible reference, not a claim of exact source-pixel sampling. Once the original full-resolution reference asset is available in the repository, run a measured palette extraction and reconcile these tokens.

## Composition rules

- Preserve the reference's compact dashboard rhythm and strong horizontal alignment.
- Use consistent card padding, border thickness and corner treatment.
- Gold outlines are selective, not a universal thick frame around every object.
- Teal is for secondary state/series/indicators, never a competing dominant color.
- Charts use restrained thin strokes; no glow, gradients or decorative fills.
- Use negative space deliberately. Do not fill every empty area with scenery or icons.
- Mobile layouts must preserve hierarchy and readable labels rather than merely shrink a desktop page.

## Pixel-art rules

- Author at a logical pixel grid, then scale with nearest-neighbor.
- Hard edges only; no anti-aliasing or blur.
- Use deliberate clusters, not noisy single-pixel scatter.
- Use a consistent outline weight within each asset family.
- Every icon must remain recognizable at its intended on-screen size.
- Pixel texture is an accent. The information architecture remains the primary object.

## Explicit exclusions

Do not carry forward the Art Study 02 scene palette as the dashboard palette. In particular: no bright leaf greens, orange-heavy brick ramps, purple/magenta neon, rainbow accents, glossy 3D shading, generic fantasy UI, or thick decorative frames that overpower the data.

## Acceptance gates

1. Palette tokens match the canonical file; no unapproved colors.
2. Reference composition is recognizably preserved.
3. Card borders, spacing and information hierarchy are consistent.
4. Pixel edges remain crisp at 1x, 2x and 3x.
5. Key values and chart labels remain readable on mobile portrait and landscape.
6. The dashboard is visually reviewed against the reference before promotion.
7. Main trading worker, strategy logic, paper/shadow runtime and history data remain untouched.
