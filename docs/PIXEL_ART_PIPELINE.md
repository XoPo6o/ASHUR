# ASHUR — Pixel-Art Production Pipeline

Status: **superseded by ASHUR Pixel Foundry**

The original document required all final art to be authored in Pixelorama and preserve native `.pxo` files. That workflow is no longer the required production path: the active goal is an AI-assisted raster toolchain that can be operated from the ChatGPT + GitHub workflow without a separate desktop editor.

The current architecture and quality rules are maintained here:

- [Pixel Foundry architecture](PIXEL_FOUNDRY_ARCHITECTURE.md)
- [Pixel Foundry implementation](../pixel_foundry/README.md)

## New production workflow

1. AI Art Director translates the brief into a style bible and editable JSON scene specification.
2. Palette and Style Engine constrains colors, ramps, lighting and material identity.
3. Raster Core draws actual pixels at logical resolution.
4. Shape and Material Generators build reusable architecture, terrain, props, foliage and UI components.
5. Scene Composer assembles depth layers and composition.
6. Sprite/UI tools export atlases, animation strips, frames and metadata.
7. Pixel QA checks technical and visual risks; artistic approval remains a separate gate.
8. Approved exports are integrated into the target website or game.

## ASHUR production safety

- The Babylon Inventory reference remains the selected art direction for the first showcase.
- The production Wall must not be replaced before explicit review approval.
- The trading worker, strategies, database, history and paper/shadow runtime must not be modified as part of Pixel Foundry work.
- No similarity score is claimed without a side-by-side visual review.
