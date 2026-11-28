# ASHUR Pixel Foundry

A deterministic, spec-driven pixel-art raster toolkit. The AI describes the art direction and scene; the renderer draws actual pixels on a logical low-resolution canvas. The same scene specification can be versioned, rendered again, inspected, and exported for websites or games.

## Current MVP (0.1)

- Logical-resolution raster canvas; integer nearest-neighbour scaling only.
- Palette validation and exact-palette quantization.
- Layered JSON scene specification.
- Pixel primitives: rectangles, ellipses, lines, polygons, single pixels, bitmap text, hard palette ramps, silhouette outlines and controlled dithering.
- Seeded procedural materials: brick walls, stone floors, clustered foliage, stepped ziggurats, columns and stone archways.
- Sprite atlas packing with JSON frame metadata and animation-strip export.
- QA report: dimensions, palette drift, connected-component/cluster sizes, isolated pixels, silhouette boundary complexity and luminance separation.
- CLI for rendering and inspecting PNG assets.

## Quick start

Python 3.10+; install Pillow:

```bash
python -m pip install Pillow
python -m pixel_foundry.cli render pixel_foundry/examples/babylon_art_bible.json --output out/babylon.png --scale 3
python -m pixel_foundry.cli inspect out/babylon.png
```

## Scene format

A renderer scene has `canvas`, `palette`, and ordered `layers`. An **art bible** additionally declares `style`, `pixel_scale`, `perspective`, `lighting` and a focal point. The CLI validates an art bible and converts it to a renderer scene automatically. Layers are composited back-to-front. Coordinates and shapes are defined at native logical resolution; scale is applied only at export using nearest-neighbour.

```json
{
  "canvas": {"width": 160, "height": 90},
  "background": "deep_night",
  "palette": {"colors": {"deep_night":"#10152B","stone":"#B88B62","gold":"#E8B65A"}},
  "layers": [
    {"name":"distant skyline","ops":[{"type":"rect","x":0,"y":60,"w":160,"h":30,"color":"deep_night"}]},
    {"name":"landmark","ops":[{"type":"polygon","points":[[40,70],[80,25],[120,70]],"color":"stone"}]}
  ]
}
```

## AI Art Director contract\n\nThe model authors an art bible as structured JSON; `pixel_foundry.art_director` validates it and converts it to a deterministic scene spec. This keeps creative intent explicit and lets the raster renderer remain reproducible. Example: `examples/babylon_art_bible.json`. The current module validates structured decisions; it does not itself host or call a language model.\n\n## Art direction standard

The complete production standard is [`PIXEL_ART_FIELD_MANUAL.md`](PIXEL_ART_FIELD_MANUAL.md). It defines planning, pixel craft, materials, lighting, perspective, character construction, generator contracts, visual QA, the three-reviewer gate and the implementation roadmap. Treat it as the source of truth; the short rules below are only a summary.

## Design rules

- Silhouette and composition before surface detail.
- A small, intentional palette with hue/value ramps.
- One logical pixel scale per asset family.
- Clusters follow form and material; avoid accidental isolated pixels.
- Backgrounds carry less contrast and saturation than focal subjects.
- Dithering is a material/value tool, not decorative noise.
- Nearest-neighbour integer scaling; no blur, resampling gradients or vector lookalikes.
- QA warnings are prompts for review, not automatic aesthetic judgments.

## Roadmap

1. **Core renderer** — implemented in MVP.
2. **Palette and cluster tools** — ramps, ramps-aware shading, outline and cluster diagnostics.
3. **Scene grammar** — reusable architecture, terrain, vegetation, props and material generators.
4. **Sprite studio** — expand the current atlas/strip helpers into pivots, animation timelines, tags and per-frame events.
5. **UI kit mode** — nine-slice frames, panels, icon families, typography and responsive layout export.
6. **AI art director** — natural-language brief to editable scene spec, with constrained revisions.
7. **Browser preview and GitHub publishing** — reviewable previews without modifying the production Wall.
8. **Automated visual regression** — native-size and 2x/4x review snapshots.

This is an intentionally honest MVP, not yet a general-purpose AI art studio. Each roadmap stage must be tested with real assets before being called complete.
