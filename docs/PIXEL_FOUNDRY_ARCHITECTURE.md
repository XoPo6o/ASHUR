# ASHUR Pixel Foundry — architecture and art standard

Status: active development, MVP stage. This document supersedes the Pixelorama-only production constraint for this branch. Pixelorama may remain an optional external inspection/editor, but is not required for generation.

## Product goal

A reusable AI-assisted pixel-art production system for:
- game environments, characters, props, tilesets and animation;
- pixel-art website interfaces, dashboards, icons, panels and typography;
- repeatable art packs with source specifications, raster exports and metadata.

The system must produce actual low-resolution raster artwork. It must not disguise SVG/CSS geometry, blurred images or generic AI illustrations as authored pixel art.

## Core architecture

1. **AI Art Director** — converts a natural-language brief into a structured art bible and scene specification: target platform, canvas, camera, perspective, silhouette hierarchy, depth planes, lighting, material language, palette and focal points.
2. **Style & Palette Engine** — creates constrained palettes and color ramps; assigns ramps to materials and lighting roles; checks contrast and palette budgets.
3. **Raster Core** — draws on a logical low-resolution pixel grid. Export scaling is integer-only nearest-neighbour. Geometry, alpha masks, indexed-color export and deterministic seeds are explicit.
4. **Shape & Material Generators** — reusable grammar for architecture, terrain, brickwork, stone, foliage, clouds, metal, cloth, water, ornament and UI frames. Generators emit ordinary raster primitives so their output remains editable and testable.
5. **Scene Composer** — orders layers, controls depth, parallax, foreground/midground/background, lighting overlays and composition.
6. **Sprite & UI Studios** — atlas packing, pivots, animation strips, nine-slice UI panels, icon families, reusable tiles and responsive layout metadata.
7. **Pixel QA Inspector** — reports palette drift, isolated pixels, cluster issues, contour breaks, scale inconsistencies, contrast and silhouette readability. Automated metrics flag risks; human/art-director review decides aesthetics.
8. **Export & Integration** — PNG/RGBA/indexed assets, sprite atlases, animation metadata, tileset JSON and web/game-ready bundles. Publishing is isolated from the production site until approval.

## Non-negotiable pixel-art rules

### Composition and readability
- Design the silhouette first; details must support the read, not compete with it.
- Establish a clear focal hierarchy and strong value grouping before ornament.
- Separate foreground, middle ground and background with value, saturation, overlap and detail density.
- Keep background contrast and saturation lower than the focal subject unless the brief deliberately reverses the hierarchy.
- Test at native resolution before viewing enlarged.

### Pixel clusters and contours
- Pixels form intentional clusters that describe volume, material, light or texture.
- Avoid accidental single-pixel noise. Isolated pixels are allowed only when they have a clear role (stars, sparks, glints, tiny highlights).
- Contours must be deliberate; avoid inconsistent stair-step rhythm and accidental tangencies.
- Use consistent cluster scale within an asset family. Do not mix tiny dithering with chunky geometry without a deliberate style reason.

### Palette, light and materials
- Use a limited, purposeful palette with ramps that move in value and, where useful, hue.
- Assign colors semantic roles: deepest shadow, ambient shadow, local base, light, highlight and emissive accent.
- Lighting direction must remain consistent across a scene and its assets.
- Materials need distinct cluster grammar: stone is not metal; foliage is not smoke; cloth is not brick.
- Dithering is a controlled value/material transition, not a universal texture overlay.
- Avoid excessive pure black, pure white and unrelated accent colors.

### Pixel scale and export
- Work at the intended logical resolution. Do not draw large and pixelate down as a substitute for authored clusters.
- Enlarge only with nearest-neighbour at integer scales (2x, 3x, 4x).
- No blur, bilinear/bicubic interpolation or antialiased vector edges in final pixel assets.
- Preserve transparency, logical dimensions, pivots, animation timing and metadata.
- Review at 1x, 2x, 4x and on the actual target surface (mobile, desktop, game viewport).

## Content modes

- **Scene mode:** layered backgrounds, architecture, landscapes, interiors and lighting.
- **Sprite mode:** characters, creatures, objects, weapons, props and effects.
- **Tileset mode:** seamless tiles, autotile rules, terrain transitions and map previews.
- **Animation mode:** frame strips, timing, loop flags, pivots and frame metadata.
- **UI mode:** pixel typography, panels, buttons, frames, separators, icons, nine-slice assets and responsive web composition.
- **Asset-pack mode:** consistent families of sprites and UI components governed by one art bible.

## Quality gates

- **A — Art bible:** approve canvas, palette, perspective, light direction, pixel scale and silhouette language.
- **B — Proof asset:** approve one complete scene study and one representative sprite/icon at native size.
- **C — System consistency:** verify multiple assets, states and sizes follow the same visual grammar.
- **D — Technical QA:** run tests, inspect alpha, palette, dimensions, sprite metadata and nearest-neighbour scaling.
- **E — Integration approval:** only then publish to the target site/game. For ASHUR, the production Wall and trading worker remain untouched until explicit approval.

No similarity percentage may be claimed without a real side-by-side visual review against the selected reference.

## Reference implementations and what to learn

- [vollmerm/tileset_gen](https://github.com/vollmerm/tileset_gen): declarative specs, seeded generators, tilesets, metadata and previews.
- [Pixelorama](https://github.com/Orama-Interactive/Pixelorama): mature pixel-art editing concepts, layers, animation and tiles.
- [pyxelate](https://github.com/sedthh/pyxelate): palette/contour/dithering ideas for reference-image analysis, not a replacement for authored art.
- [Visecity/pixel-art-generator](https://github.com/Visecity/pixel-art-generator): inspect its Python/Pillow DSL and layered sprite concepts; audit before adopting code.
- [Lospec tutorials](https://lospec.com/pixel-art-tutorials): practical lessons on palettes, clusters, dithering, backgrounds and perspective.

The Foundry borrows architectural ideas, not unreviewed code. Any copied implementation must be license-audited and attributed.

## Current implementation status

Implemented in the current branch:
- logical raster canvas and primitive renderer;
- JSON scenes and named palettes;
- seeded brick, stone-floor and foliage generators;
- nearest-neighbour integer export;
- palette/isolated-pixel QA report;
- sprite atlas packing and animation-strip metadata;
- GitHub Actions tests and sample render.

Not yet implemented:
- natural-language AI planner that writes and revises scene specs;
- advanced cluster/contour/silhouette/contrast diagnostics;
- perspective-aware architecture and organic shape grammar;
- true indexed PNG with robust transparency policy across target engines;
- autotile rules, nine-slice UI assets and font atlas tooling;
- browser preview/editor and one-click approved publishing.

The MVP must not be described as a finished general-purpose AI pixel-art studio until those capabilities are implemented and tested.
